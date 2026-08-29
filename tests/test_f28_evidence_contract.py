"""
F2.8 round 2 — o contrato entre a tool do Brain e o Evidence Gate.

O QUE QUEBROU, E POR QUE NENHUM TESTE PEGOU
--------------------------------------------

O cutover renomeou a tool de consulta (`ler_documento` ->
`buscar_conhecimento`) e mudou o formato do retorno (as fontes passaram a
viver dentro de `resultados`). O extrator de `sources_opened` ficou para tras.

Resultado em producao: o agente consultou OFFERS, respondeu o preco certo, e o
Evidence Gate o acusou de citar fonte que nao abriu. `REJECTED`,
`outbound_allowed=False` — a Judith recebeu "vou confirmar" no lugar do preco.

Os 1000 testes passavam porque testavam retrieval de um lado e Evidence Gate
do outro. **Ninguem testava a costura.** E o que este arquivo faz.
"""

from __future__ import annotations

import pytest

from orchestration.evidence_gate import evaluate_final_response
from orchestration.step_helpers import _CONSULT_TOOLS, _extract_sources_opened, _sources_in_tool_result


class _Mensagem:
    """Mensagem de tool como o Agno REALMENTE a monta.

    A versao anterior fazia `json.dumps(content)` quando o content nao era
    string — e foi isso que escondeu o MOBILE_FAIL_02 por uma rodada inteira.
    O Agno nao serializa: `create_function_call_result` faz `content=output`.
    Uma tool que devolve dict chega ao historico como repr Python.

    Agora o default e `str(content)`, que e o que o runtime faz. Para testar o
    caminho JSON, passe a string ja serializada — como as tools corrigidas
    passaram a fazer.
    """

    def __init__(self, tool_name: str, content) -> None:
        self.role = "tool"
        self.tool_name = tool_name
        self.content = content if isinstance(content, str) else str(content)
        self.tool_calls = None


class _Resposta:
    def __init__(self, *mensagens) -> None:
        self.messages = list(mensagens)


# =============================================================================
# CONTRATO — o teste que impede a regressao acontecer de novo
# =============================================================================


class TestContratoDeTools:
    def test_toda_tool_de_consulta_do_brain_e_conhecida_pelo_evidence(self) -> None:
        """Se alguem renomear ou adicionar uma tool, este teste falha.

        Foi exatamente esta divergencia que bloqueou a resposta de preco em
        producao: a tool existia, consultava e devolvia — e o Evidence Gate
        nao sabia o nome dela.
        """

        from brain.cutover import CONSULTATION_TOOL_NAMES

        faltando = CONSULTATION_TOOL_NAMES - _CONSULT_TOOLS
        assert faltando == set(), (
            f"tool(s) de consulta do Brain invisiveis ao Evidence Gate: {sorted(faltando)}. "
            "Adicione em brain/cutover.py:CONSULTATION_TOOL_NAMES."
        )

    def test_as_tools_registradas_batem_com_o_contrato_declarado(self, monkeypatch) -> None:
        """O contrato precisa descrever o que `build_brain_tools_for` cria.

        Sem isto, declarar o contrato e depois esquecer de atualiza-lo daria
        um teste verde sobre uma mentira.
        """

        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "customer-support-agent")
        from brain.cutover import BRAIN_TOOL_NAMES, build_brain_tools_for

        registradas = {t.name for t in build_brain_tools_for("customer-support-agent")}
        assert registradas == BRAIN_TOOL_NAMES, (
            f"registradas={sorted(registradas)} contrato={sorted(BRAIN_TOOL_NAMES)}. "
            "Atualize brain/cutover.py se adicionou ou renomeou uma tool."
        )

    def test_listar_fontes_nao_conta_como_consulta(self) -> None:
        """Listar nunca foi consultar — a regra e anterior ao cutover."""

        from brain.cutover import CONSULTATION_TOOL_NAMES, LISTING_TOOL_NAMES

        assert not (LISTING_TOOL_NAMES & CONSULTATION_TOOL_NAMES)
        assert not (LISTING_TOOL_NAMES & _CONSULT_TOOLS)


# =============================================================================
# EXTRACAO DE FONTES — as duas formas de payload
# =============================================================================


class TestExtracaoDePayload:
    def test_payload_aninhado_de_buscar_conhecimento(self) -> None:
        """O formato que quebrou: `fonte` dentro de `resultados`."""

        payload = {
            "status": "OK",
            "contexto_adicionado": False,
            "resultados": [
                {"fonte": "OFFERS", "documento": "OFFERS", "camada": "L3"},
                {"fonte": "PRODUCTS", "documento": "PRODUCTS", "camada": "L3"},
            ],
        }
        assert _sources_in_tool_result(payload) == ["OFFERS", "PRODUCTS"]

    def test_payload_antigo_de_search_knowledge_base(self) -> None:
        """Lista crua no topo — nao pode regredir."""

        payload = [{"fonte": "OFFERS"}, {"fonte": "PRODUCTS"}]
        assert _sources_in_tool_result(payload) == ["OFFERS", "PRODUCTS"]

    def test_dict_com_fonte_no_topo_continua_valendo(self) -> None:
        assert _sources_in_tool_result({"fonte": "OFFERS"}) == ["OFFERS"]

    def test_fonte_nao_disponivel_nao_vira_fonte_legitima(self) -> None:
        """A busca devolveu a lacuna, nao o documento."""

        payload = {"resultados": [{"fonte": "INSTAGRAM_AUDIT", "status": "FONTE_NAO_DISPONIVEL"}]}
        assert _sources_in_tool_result(payload) == []

    def test_nenhum_resultado_nao_inventa_fonte(self) -> None:
        payload = {"status": "NENHUM_RESULTADO", "resultados": [], "contexto_adicionado": True}
        assert _sources_in_tool_result(payload) == []

    def test_brain_indisponivel_nao_vira_fonte(self) -> None:
        payload = {"status": "BRAIN_INDISPONIVEL", "detalhe": "OperationalError", "resultados": []}
        assert _sources_in_tool_result(payload) == []

    def test_nao_desce_ate_o_corpo_do_trecho(self) -> None:
        """Le procedencia, nunca conteudo — nem quando o corpo esta ali."""

        payload = {
            "resultados": [
                {"fonte": "EBOOK_RECHEIOS", "conteudo": "100 g de chocolate branco, 50 g de creme"}
            ]
        }
        assert _sources_in_tool_result(payload) == ["EBOOK_RECHEIOS"]


class TestExtracaoNoRuntime:
    def test_buscar_conhecimento_popula_sources_opened(self) -> None:
        """O bug em uma linha: isto devolvia [] e derrubava a resposta."""

        resposta = _Resposta(
            _Mensagem("buscar_conhecimento", {"status": "OK", "resultados": [{"fonte": "OFFERS"}]})
        )
        assert _extract_sources_opened(resposta) == ["OFFERS"]

    def test_search_knowledge_base_continua_funcionando(self) -> None:
        resposta = _Resposta(_Mensagem("search_knowledge_base", [{"fonte": "PRODUCTS"}]))
        assert _extract_sources_opened(resposta) == ["PRODUCTS"]

    def test_as_duas_tools_na_mesma_execucao(self) -> None:
        resposta = _Resposta(
            _Mensagem("search_knowledge_base", [{"fonte": "PRODUCTS"}]),
            _Mensagem("buscar_conhecimento", {"status": "OK", "resultados": [{"fonte": "OFFERS"}]}),
        )
        assert _extract_sources_opened(resposta) == ["PRODUCTS", "OFFERS"]

    def test_tool_desconhecida_nao_conta(self) -> None:
        """Uma tool que nao e de consulta nunca vira fonte aberta."""

        resposta = _Resposta(_Mensagem("listar_fontes_disponiveis", {"documentos_disponiveis": [{"fonte": "OFFERS"}]}))
        assert _extract_sources_opened(resposta) == []


# =============================================================================
# COSTURA — tool -> extracao -> Evidence Gate -> outbound
# =============================================================================


class TestCosturaCompleta:
    """O teste que teria pego o bug.

    Vai do retorno da tool ate o veredito do gate, no MESMO formato que o
    runtime produz.
    """

    def _gate(self, resposta_do_agente: str, tool_payload, *, tool: str, references: list[str]):
        runtime = _Resposta(_Mensagem(tool, tool_payload))
        opened = _extract_sources_opened(runtime)
        return opened, evaluate_final_response(
            agent_id="sales-conversion-agent",
            response=resposta_do_agente,
            references=references,
            sources_opened=opened,
        )

    def test_preco_via_buscar_conhecimento_passa(self) -> None:
        """O caso real da Judith, ponta a ponta."""

        opened, gate = self._gate(
            "Casquinhas Profissionais custa R$ 29,00 e Recheios Profissionais R$ 37,00.",
            {"status": "OK", "resultados": [{"fonte": "OFFERS"}, {"fonte": "PRODUCTS"}]},
            tool="buscar_conhecimento",
            references=["OFFERS", "PRODUCTS"],
        )

        assert opened == ["OFFERS", "PRODUCTS"]
        assert gate.status == "PASS", gate.reason
        assert gate.outbound_allowed is True

    def test_o_mesmo_caso_falhava_antes_do_contrato(self) -> None:
        """Prova do modo de falha: sem a tool no contrato, sources fica vazio.

        Simula o estado anterior removendo a tool do conjunto reconhecido.
        """

        import orchestration.step_helpers as helpers

        original = helpers._CONSULT_TOOLS
        helpers._CONSULT_TOOLS = original - {"buscar_conhecimento"}
        try:
            runtime = _Resposta(
                _Mensagem("buscar_conhecimento", {"status": "OK", "resultados": [{"fonte": "OFFERS"}]})
            )
            opened = helpers._extract_sources_opened(runtime)
            gate = evaluate_final_response(
                agent_id="sales-conversion-agent",
                response="Casquinhas custa R$ 29,00.",
                references=["OFFERS"],
                sources_opened=opened,
            )
            assert opened == []
            assert gate.status == "REJECTED"
        finally:
            helpers._CONSULT_TOOLS = original

    def test_citacao_realmente_fabricada_continua_rejeitada(self) -> None:
        """Corrigir observabilidade nao pode afrouxar o gate."""

        opened, gate = self._gate(
            "Segundo OFFERS, Casquinhas custa R$ 29,00.",
            {"status": "OK", "resultados": [{"fonte": "PRODUCTS"}]},
            tool="buscar_conhecimento",
            references=["OFFERS"],
        )

        assert opened == ["PRODUCTS"]
        assert gate.status == "REJECTED"
        assert "OFFERS" in gate.citations_without_source

    def test_claim_comercial_sem_consulta_continua_bloqueado(self) -> None:
        gate = evaluate_final_response(
            agent_id="sales-conversion-agent",
            response="Casquinhas custa R$ 29,00.",
            references=[],
            sources_opened=[],
        )
        assert gate.status == "NEEDS_EVIDENCE"
        assert gate.outbound_allowed is False

    def test_claim_comercial_apoiado_so_em_site_nao_basta(self) -> None:
        """Preco vem de OFFERS/PRODUCTS. BUSINESS_RULES 4."""

        _, gate = self._gate(
            "Casquinhas custa R$ 29,00.",
            {"status": "OK", "resultados": [{"fonte": "SITE_SNAPSHOT"}]},
            tool="buscar_conhecimento",
            references=["SITE_SNAPSHOT"],
        )
        assert gate.status != "PASS"


# =============================================================================
# OBSERVABILIDADE
# =============================================================================


class TestObservabilidade:
    def test_tools_usadas_sao_extraidas(self) -> None:
        from orchestration.step_helpers import _extract_consult_tools

        resposta = _Resposta(
            _Mensagem("buscar_conhecimento", {"resultados": []}),
            _Mensagem("search_knowledge_base", []),
        )
        assert _extract_consult_tools(resposta) == ["buscar_conhecimento", "search_knowledge_base"]

    def test_contador_de_contexto(self) -> None:
        from brain import query_context as qc

        qc.reset()
        qc.set_session("obs")
        assert qc.enrichment_count() == 0

        qc.remember("me passa a receita de pistache")
        qc.enrich("entao so os ingredientes")
        assert qc.enrichment_count() == 1
        qc.reset()

    def test_campos_de_observabilidade_sao_persistiveis(self) -> None:
        from orchestration.execution_repository import _OUTCOME_ALLOWLIST

        assert "brain_tools_called" in _OUTCOME_ALLOWLIST
        assert "context_added" in _OUTCOME_ALLOWLIST

    def test_log_do_whatsapp_carrega_o_caminho_do_brain(self) -> None:
        from dataclasses import asdict

        from app.whatsapp.channel import ChannelLog

        campos = asdict(ChannelLog())
        for campo in ("brain_tools_called", "sources_opened", "context_added", "disclosure_status"):
            assert campo in campos, campo

    def test_log_do_whatsapp_nao_carrega_conteudo(self) -> None:
        """Observabilidade nao pode virar vazamento."""

        from dataclasses import asdict

        from app.whatsapp.channel import ChannelLog

        campos = set(asdict(ChannelLog()))
        for proibido in ("message", "response", "outbound_message", "final_response", "phone", "prompt"):
            assert proibido not in campos, proibido


@pytest.mark.parametrize(
    ("payload", "esperado"),
    [
        ({"resultados": [{"fonte": "offers"}]}, ["OFFERS"]),
        ({"resultados": [{"fonte": " Products "}]}, ["PRODUCTS"]),
        ({"resultados": [{"fonte": "OFFERS"}, {"fonte": "OFFERS"}]}, ["OFFERS", "OFFERS"]),
    ],
)
def test_normalizacao_de_chave(payload, esperado) -> None:
    assert _sources_in_tool_result(payload) == esperado


# =============================================================================
# END-TO-END ate o OUTBOUND — o pedaco que faltava
# =============================================================================


class TestAteOOutbound:
    """Fecha a costura no ponto onde a mensagem realmente sai.

    `_finalize` e quem decide o que a cliente le. Testar so ate o gate
    deixaria de fora justamente o campo que o canal envia.
    """

    def _executar(self, resposta: str, fontes: list[str], references: list[str]):
        from orchestration.execution_log import ExecutionLog
        from orchestration.handoff import AgentHandoff, AgentStepDecision
        from orchestration.workflows.answer_dm import WORKFLOW_NAME, _finalize

        log = ExecutionLog(workflow=WORKFLOW_NAME)
        handoff = AgentHandoff(
            from_agent="sales-conversion-agent",
            to_agent="judith",
            workflow=WORKFLOW_NAME,
            task_id=log.task_id,
            objective="Responder intencao de compra",
            context="teste",
            decision="responder",
            output=resposta,
            confidence="alto",
            references=references,
            sources_opened=fontes,
            recommended_next="nenhum",
        )
        decisao = AgentStepDecision(
            output=resposta, decision="responder", confidence="alto",
            references=references, sources_opened=fontes,
            recommended_next="nenhum",
        )
        _finalize(log, agent_id="sales-conversion-agent", handoff=handoff, decision=decisao)
        return log.outputs

    def test_preco_com_fonte_aberta_sai_para_a_cliente(self) -> None:
        saida = self._executar(
            "Casquinhas Profissionais custa R$ 29,00 e Recheios Profissionais R$ 37,00.",
            fontes=["OFFERS", "PRODUCTS"],
            references=["OFFERS"],
        )

        assert saida["evidence_status"] == "PASS", saida["evidence_reason"]
        assert saida["outbound_allowed"] is True
        assert "R$ 29,00" in saida["outbound_message"]
        assert "R$ 37,00" in saida["outbound_message"]

    def test_a_cliente_nunca_ve_nome_de_documento_interno(self) -> None:
        saida = self._executar(
            "Segundo o documento OFFERS, Casquinhas custa R$ 29,00.",
            fontes=["OFFERS"],
            references=["OFFERS"],
        )

        assert saida["internal_terms_leaked"] is False
        assert "OFFERS" not in saida["outbound_message"]
        # A evidencia continua inteira no rastro — o corte e so na prosa.
        assert "OFFERS" in saida["sources_opened"]

    def test_sem_fonte_a_resposta_factual_nao_sai(self) -> None:
        saida = self._executar(
            "Casquinhas custa R$ 29,00.", fontes=[], references=[]
        )

        assert saida["outbound_allowed"] is False
        assert "R$ 29,00" not in saida["outbound_message"]

    def test_receita_completa_e_bloqueada_mesmo_com_fonte(self) -> None:
        """Evidence PASS nao autoriza entregar conteudo pago."""

        saida = self._executar(
            "A ganache leva 100 g de chocolate branco, 50 g de creme de leite, "
            "20 g de leite em po, 10 g de glucose e 10 g de manteiga.",
            fontes=["EBOOK_RECHEIOS", "PRODUCTS"],
            references=["EBOOK_RECHEIOS"],
        )

        assert saida.get("disclosure_status") == "BLOCK"
        assert "100 g" not in saida["outbound_message"]

    def test_observabilidade_chega_aos_outputs(self) -> None:
        saida = self._executar(
            "Casquinhas custa R$ 29,00.", fontes=["OFFERS"], references=["OFFERS"]
        )

        assert "context_added" in saida
        assert saida["sources_opened"] == ["OFFERS"]
