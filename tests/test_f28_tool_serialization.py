"""
F2.8 — MOBILE_FAIL_02: o contrato de SERIALIZACAO da tool do Brain.

O QUE ACONTECEU
---------------

`buscar_conhecimento` devolvia `dict`. O Agno guarda o retorno de uma tool sem
converter (`create_function_call_result` faz `content=output`), entao o que
chegava ao historico era o repr Python:

    {'status': 'OK', 'resultados': [{'fonte': 'PRODUCTS', ...

`json.loads` falhava, `sources_opened` ficava vazio, o agente citava as fontes
que tinha lido, e o Evidence Gate concluia — corretamente, dado o que enxergava
— que a citacao era inventada. `REJECTED`, e a Judith recebeu o fallback.

POR QUE A RODADA ANTERIOR NAO PEGOU
-----------------------------------

O helper de teste fazia `json.dumps(content)` quando o content nao era string.
Ou seja: o teste alimentava JSON que o runtime nunca produzia. O teste
codificava a suposicao, nao o comportamento.

Este arquivo exercita a TOOL DE VERDADE — construida por
`build_brain_tools_for`, chamada como o Agno a chama — e so depois passa pelo
extrator e pelo gate.
"""

from __future__ import annotations

import ast
import json

import pytest
from sqlalchemy import create_engine

from brain.cutover import build_brain_tools_for
from orchestration.evidence_gate import evaluate_final_response
from orchestration.step_helpers import (
    _extract_consult_tools,
    _extract_sources_opened,
    _parse_tool_content,
    _sources_in_tool_result,
)

PERGUNTA = "Olá qual o preço do ebook das casquinhas profissionais?"


@pytest.fixture(scope="module")
def store():
    """Store com os documentos aprovados de `docs/` — sem depender dos PDFs."""

    from brain.approvals import apply_approvals
    from brain.backfill import run_backfill
    from brain.repository import KnowledgeRepository
    from db.migrations import run_migrations

    engine = create_engine("sqlite://")
    run_migrations(engine)
    repositorio = KnowledgeRepository(engine)
    run_backfill(repositorio)
    apply_approvals(repositorio)
    yield repositorio
    engine.dispose()


@pytest.fixture
def tools(store, monkeypatch):
    """As tools REAIS, com o repositorio plugado como no boot."""

    from brain import bootstrap

    monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "sales-conversion-agent")
    anterior = bootstrap._repository
    bootstrap.set_knowledge_repository(store)
    yield {t.name: t.entrypoint for t in build_brain_tools_for("sales-conversion-agent")}
    bootstrap.set_knowledge_repository(anterior)


class _MensagemDoAgno:
    """Mensagem de tool montada como o Agno monta.

    `content=output`, sem serializar. E o ponto exato onde o bug nascia.
    """

    def __init__(self, tool_name: str, output) -> None:
        self.role = "tool"
        self.tool_name = tool_name
        self.content = output if isinstance(output, str) else str(output)
        self.tool_calls = None


class _RespostaDoAgno:
    def __init__(self, *mensagens) -> None:
        self.messages = list(mensagens)


# =============================================================================
# A + B — a tool cumpre o contrato de serializacao
# =============================================================================


class TestContratoDeSerializacao:
    def test_buscar_conhecimento_devolve_str(self, tools) -> None:
        resultado = tools["buscar_conhecimento"](PERGUNTA)
        assert isinstance(resultado, str), f"devolveu {type(resultado).__name__}, nao str"

    def test_o_retorno_e_json_valido(self, tools) -> None:
        carga = json.loads(tools["buscar_conhecimento"](PERGUNTA))
        assert carga["status"] == "OK"
        assert isinstance(carga["resultados"], list)

    def test_listar_fontes_devolve_str_e_json(self, tools) -> None:
        carga = json.loads(tools["listar_fontes_disponiveis"]())
        assert isinstance(carga["documentos_disponiveis"], list)

    def test_json_preserva_acento(self, tools) -> None:
        """`ensure_ascii=False`: o modelo le "preço", nao "pre\\u00e7o"."""

        assert "\\u00e7" not in tools["buscar_conhecimento"]("preço")

    def test_nenhuma_tool_do_brain_devolve_estrutura_crua(self, tools) -> None:
        """Contrato: toda tool exposta ao Agno serializa ela mesma."""

        for nome, funcao in tools.items():
            saida = funcao(PERGUNTA) if nome == "buscar_conhecimento" else funcao()
            assert isinstance(saida, str), nome


# =============================================================================
# I + J — listar_fontes_disponiveis nao acessa campo inexistente
# =============================================================================


class TestListarFontes:
    def test_nao_crasha(self, tools) -> None:
        """Antes: AttributeError — `MissingSource` nao tem `.owner`."""

        saida = tools["listar_fontes_disponiveis"]()
        assert "has no attribute" not in saida
        assert "AttributeError" not in saida

    def test_usa_o_campo_real_do_modelo(self) -> None:
        import dataclasses

        from agents.knowledge_sources import MissingSource

        campos = {f.name for f in dataclasses.fields(MissingSource)}
        assert "ask_agent" in campos
        assert "owner" not in campos

    def test_lacunas_trazem_o_responsavel(self, tools) -> None:
        carga = json.loads(tools["listar_fontes_disponiveis"]())
        for lacuna in carga["fontes_ausentes"]:
            assert lacuna["fonte"]
            assert lacuna["responsavel"], "lacuna sem agente responsavel"


# =============================================================================
# C + D + E — costura ate o Evidence Gate, com a tool real
# =============================================================================


class TestCosturaComToolReal:
    def _executar(self, tools):
        """Tool real -> mensagem como o Agno monta -> extracao."""

        saida = tools["buscar_conhecimento"](PERGUNTA)
        resposta = _RespostaDoAgno(_MensagemDoAgno("buscar_conhecimento", saida))
        return saida, _extract_sources_opened(resposta), _extract_consult_tools(resposta)

    def test_sources_opened_nao_fica_vazio(self, tools) -> None:
        """O sintoma exato do MOBILE_FAIL_02."""

        _, abertas, chamadas = self._executar(tools)

        assert chamadas == ["buscar_conhecimento"]
        assert abertas, "sources_opened vazio — a provenance sumiu de novo"

    def test_traz_fonte_canonica_de_preco(self, tools) -> None:
        _, abertas, _ = self._executar(tools)
        assert "OFFERS" in abertas or "PRODUCTS" in abertas, abertas

    def test_referencias_legitimas_nao_sao_fabricadas(self, tools) -> None:
        from orchestration.evidence_gate import _fabricated_citations

        _, abertas, _ = self._executar(tools)
        referencias = [f"{abertas[0]} — consultado nesta execucao"]

        assert _fabricated_citations(referencias, abertas) == []

    def test_evidence_gate_nao_rejeita_por_falta_de_provenance(self, tools) -> None:
        """O teste de regressao do MOBILE_FAIL_02."""

        _, abertas, _ = self._executar(tools)
        gate = evaluate_final_response(
            agent_id="sales-conversion-agent",
            response="O ebook Casquinhas Profissionais custa R$ 29,00.",
            references=[abertas[0]],
            sources_opened=abertas,
        )

        assert gate.status != "REJECTED", gate.reason
        assert gate.citations_without_source == []


class TestReproducaoDoBugAntigo:
    def test_dict_cru_era_o_bug(self, tools) -> None:
        """Prova do modo de falha: `dict` -> repr -> json.loads falha.

        Sem o fallback do parser isto devolveria [] e o gate rejeitaria.
        """

        carga = json.loads(tools["buscar_conhecimento"](PERGUNTA))
        repr_python = str(carga)  # exatamente o que o Agno guardava

        with pytest.raises(json.JSONDecodeError):
            json.loads(repr_python)

        # O fallback salva o caso legado.
        assert _sources_in_tool_result(repr_python), "o fallback deixou de funcionar"


# =============================================================================
# F + G + H — o fallback de compatibilidade
# =============================================================================


class TestFallbackDeCompatibilidade:
    def test_repr_python_legado_e_aceito(self) -> None:
        legado = "{'status': 'OK', 'resultados': [{'fonte': 'OFFERS'}, {'fonte': 'PRODUCTS'}]}"
        assert _sources_in_tool_result(legado) == ["OFFERS", "PRODUCTS"]

    def test_json_continua_sendo_o_caminho_principal(self) -> None:
        assert _sources_in_tool_result('{"resultados": [{"fonte": "OFFERS"}]}') == ["OFFERS"]

    @pytest.mark.parametrize(
        "invalido",
        ["nao e nada disso", "", "   ", "{quebrado", "<html>erro</html>", "'MissingSource' object has no attribute"],
    )
    def test_conteudo_invalido_falha_fechado(self, invalido: str) -> None:
        """Melhor nenhuma fonte do que uma fonte que nao foi aberta."""

        assert _sources_in_tool_result(invalido) == []

    def test_literal_solto_nao_vira_estrutura(self) -> None:
        assert _parse_tool_content("'erro'") is None
        assert _parse_tool_content("42") is None
        assert _parse_tool_content("None") is None

    def test_nao_ha_superficie_de_execucao(self) -> None:
        """`ast.literal_eval` avalia literal; nao chama, nao importa, nao executa."""

        for hostil in (
            "__import__('os').system('echo x')",
            "open('/etc/passwd').read()",
            "[].__class__.__mro__",
            "exec('x=1')",
            "lambda: 1",
        ):
            assert _parse_tool_content(hostil) is None, hostil

    def test_o_codigo_nunca_usa_eval(self) -> None:
        import inspect

        from orchestration import step_helpers

        fonte = inspect.getsource(step_helpers)
        assert "ast.literal_eval" in fonte
        # `eval(` puro nao pode existir — so a forma segura.
        assert not any(
            linha.strip().startswith("eval(") or " eval(" in linha
            for linha in fonte.splitlines()
            if "literal_eval" not in linha
        )

    def test_literal_eval_nao_avalia_chamada(self) -> None:
        """Garantia da propria biblioteca, travada aqui."""

        with pytest.raises((ValueError, SyntaxError)):
            ast.literal_eval("__import__('os').getcwd()")
