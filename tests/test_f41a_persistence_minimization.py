"""
F4.1A — minimizacao da persistencia de conversa, na origem.

O QUE A F4.1 PROVOU, E QUE ESTES TESTES DEFENDEM
------------------------------------------------

`agno_sessions.runs` guarda a run inteira em JSONB e reescreve o array todo a
cada mensagem. Com os defaults do Agno isso inclui as mensagens `role="tool"` —
o RESULTADO das buscas no Brain, com o corpo dos chunks. Para os agentes que
podem conhecer material pago, isso significava conteudo de ebook pago gravado
em texto puro, por run, sem prazo.

Medido: o resultado de uma tool responde por ~81% do peso de uma run.

A correcao desliga a gravacao na origem. O que ela NAO pode fazer e apagar a
observabilidade junto com o conteudo — foi exatamente esse o erro do
MOBILE_FAIL_02, onde a provenance sumiu do caminho e o Evidence Gate rejeitou
uma resposta correta.

    o conteudo pode deixar de ser ARMAZENADO
    a execucao nao pode deixar de ser OBSERVAVEL

POR QUE ISTO FUNCIONA, E POR QUE HA UM TESTE QUE PINA O PORQUE
--------------------------------------------------------------

`agent/_run.py:cleanup_and_store` faz `copy.copy(run_response)` e o scrub
REBINDA `messages` na copia. O objeto vivo devolvido por `agent.run()` — que e
o que `_extract_sources_opened` le — continua intacto.

Isso e detalhe de implementacao do Agno 2.6.4, nao contrato publico. Se um
upgrade passar a scrubar in-place, `sources_opened` volta a ficar vazio e o
Evidence Gate volta a rejeitar resposta correta. `TestContratoDoAgno` existe
para que esse upgrade quebre um teste em vez de quebrar producao.
"""

from __future__ import annotations

import copy
import json

import pytest
from agno.agent._run import scrub_run_output_for_storage
from agno.models.message import Message
from agno.models.response import ToolExecution
from agno.run.agent import RunOutput
from agno.session.agent import AgentSession

from brain.cutover import _payload
from brain.retrieval import search
from orchestration.evidence_gate import evaluate_final_response
from orchestration.registry import (
    _ALL_AGENTS,
    _TEAM_AGENTS,
    HISTORICAL_DATA_STRATEGY,
    RESULTADO_NAO_PERSISTIDO,
    RETENTION_TARGETS,
    STORE_MEDIA,
    STORE_TOOL_MESSAGES,
    USER_REQUESTED_DELETION,
    redigir_carga_de_tool,
)
from orchestration.step_helpers import _extract_consult_tools, _extract_sources_opened

VENDEDOR = "sales-conversion-agent"
SUPORTE = "customer-support-agent"

#: A frase que reprovou em producao na F2.8. Continua sendo o caso-teste.
FRASE_DA_JUDITH = "Olá qual o preço do ebook das casquinhas profissionais?"


class _AgentDePersistencia:
    """So os quatro flags que `scrub_run_output_for_storage` consulta."""

    def __init__(self, *, tool_messages: bool, media: bool = False) -> None:
        self.store_tool_messages = tool_messages
        self.store_media = media
        self.store_history_messages = False


def _run_com_tool(payload: str, *, pergunta: str = FRASE_DA_JUDITH) -> RunOutput:
    """Uma run como o Agno REALMENTE monta.

    `tools=[...]` e `references=[...]` nao sao decorativos aqui. A primeira
    versao deste helper montava so `messages`, e por isso os testes passavam
    enquanto um run real ainda gravava 6.757 bytes de corpo pago em
    `tools[0].result`. O teste codificava a minha suposicao sobre a forma da
    run, nao a forma que o runtime produz — exatamente o erro do
    MOBILE_FAIL_02, repetido.
    """

    assistente = Message(
        role="assistant",
        content="",
        tool_calls=[{"id": "tc1", "function": {"name": "buscar_conhecimento", "arguments": "{}"}}],
    )
    run = RunOutput(
        run_id="run-1",
        agent_id=VENDEDOR,
        session_id="wa:ANSWER_DM:wa_teste",
        content="O ebook custa o valor da pagina de oferta.",
        messages=[
            Message(role="system", content="instrucoes do agente"),
            Message(role="user", content=pergunta),
            assistente,
            Message(role="tool", content=payload, tool_call_id="tc1", tool_name="buscar_conhecimento"),
            Message(role="assistant", content="O ebook custa o valor da pagina de oferta."),
        ],
    )
    run.tools = [
        ToolExecution(
            tool_call_id="tc1",
            tool_name="buscar_conhecimento",
            tool_args={"pergunta": pergunta},
            result=payload,
        )
    ]
    run.references = [{"query": pergunta, "references": json.loads(payload).get("resultados", [])}]
    return run


def _armazenar(run: RunOutput, agente: _AgentDePersistencia, *, com_hook: bool = True) -> RunOutput:
    """Reproduz a ordem real: post-hook e depois `cleanup_and_store`.

    Os post-hooks rodam ANTES da gravacao (`_run.py:1020` vs `:1095`), entao a
    redacao precisa acontecer aqui tambem — senao o teste mede um caminho que
    producao nao percorre.
    """

    if com_hook:
        redigir_carga_de_tool(run)
    copia = copy.copy(run)
    scrub_run_output_for_storage(agente, copia)
    return copia


def _json_do_que_seria_gravado(run: RunOutput, agente: _AgentDePersistencia, *, com_hook: bool = True) -> str:
    sessao = AgentSession(session_id="wa:ANSWER_DM:wa_teste", agent_id=VENDEDOR, user_id="wa_teste")
    sessao.upsert_run(_armazenar(run, agente, com_hook=com_hook))
    return json.dumps(sessao.to_dict(), ensure_ascii=False, default=str)


# =============================================================================
# B + C — a configuracao, num lugar so
# =============================================================================


class TestConfiguracao:
    def test_a_politica_esta_declarada(self) -> None:
        assert STORE_TOOL_MESSAGES is False
        assert STORE_MEDIA is False

    def test_os_vinte_agentes_do_time_aplicam(self) -> None:
        assert len(_TEAM_AGENTS) == 20
        for agente in _TEAM_AGENTS:
            assert agente.store_tool_messages is False, agente.id
            assert agente.store_media is False, agente.id

    def test_os_outros_dois_flags_continuam_como_estavam(self) -> None:
        """`store_history_messages` e `store_events` ja estavam corretos."""

        for agente in _ALL_AGENTS:
            assert agente.store_history_messages is False, agente.id
            assert agente.store_events is False, agente.id

    def test_my_agent_fica_de_fora_e_isso_e_deliberado(self) -> None:
        """Starter multimodal, sem tools do Brain, fora do caminho da cliente."""

        jud = next(a for a in _ALL_AGENTS if a.id == "jud")
        assert jud not in _TEAM_AGENTS
        assert jud.store_media is True
        nomes = {getattr(t, "name", getattr(t, "__name__", "")) for t in (jud.tools or [])}
        assert "buscar_conhecimento" not in nomes, "sem tool do Brain, nao alcanca conteudo pago"

    def test_nao_depende_de_default_implicito(self) -> None:
        """O valor vem da politica, nao de o Agno acertar o default."""

        from agno.agent import Agent

        padrao = Agent(id="sonda-de-default")
        assert padrao.store_tool_messages is True, "o default do Agno GRAVA tool messages"
        assert padrao.store_media is True, "o default do Agno GRAVA midia"


# =============================================================================
# O contrato do Agno 2.6.4 que tudo isto assume
# =============================================================================


class TestContratoDoAgno:
    """Pina o comportamento do qual a provenance depende.

    Se um upgrade do Agno passar a scrubar in-place, estes testes quebram — e
    e isso que queremos: falhar aqui em vez de falhar na conversa da cliente.
    """

    def test_o_scrub_nao_muta_o_objeto_vivo(self) -> None:
        run = _run_com_tool('{"resultados": [{"fonte": "OFFERS"}]}')
        antes = [m.role for m in run.messages]

        copia = _armazenar(run, _AgentDePersistencia(tool_messages=False))

        # A run real tem cinco mensagens: system, user, o assistant que chama a
        # tool, o resultado da tool, e o assistant com a resposta final.
        assert [m.role for m in run.messages] == antes == ["system", "user", "assistant", "tool", "assistant"]
        # Sai o resultado E o assistant que fez a chamada. A resposta fica.
        assert [m.role for m in copia.messages] == ["system", "user", "assistant"]
        assert copia.messages[-1].content, "a resposta ao cliente e a conversa: tem que ficar"

    def test_o_scrub_remove_a_chamada_junto_com_o_resultado(self) -> None:
        """Nao adianta tirar so o resultado: a chamada tambem sai."""

        copia = _armazenar(
            _run_com_tool('{"resultados": [{"fonte": "OFFERS"}]}'),
            _AgentDePersistencia(tool_messages=False),
        )
        assert all(not m.tool_calls for m in copia.messages)

    def test_com_o_flag_ligado_a_copia_mantem_tudo(self) -> None:
        """Contraprova: sem o flag, o conteudo continua indo para o banco."""

        copia = _armazenar(
            _run_com_tool('{"resultados": [{"fonte": "OFFERS"}]}'),
            _AgentDePersistencia(tool_messages=True),
        )
        assert [m.role for m in copia.messages] == ["system", "user", "assistant", "tool", "assistant"]


# =============================================================================
# D + E + F — provenance, MOBILE_FAIL_02 e Evidence Gate
# =============================================================================


class TestProvenancePreservada:
    def _payload_real(self, brain, embedder, agente=VENDEDOR, pergunta=FRASE_DA_JUDITH) -> str:
        resultado = search(agent_id=agente, query=pergunta, repository=brain, mode="hybrid", embedder=embedder)
        return _payload({"status": "OK", "resultados": resultado.as_documents()})

    def test_d_extracao_identica_com_e_sem_persistencia(self, brain_indexado, embedder) -> None:
        run = _run_com_tool(self._payload_real(brain_indexado, embedder))

        ligado = _armazenar(run, _AgentDePersistencia(tool_messages=True))
        desligado = _armazenar(run, _AgentDePersistencia(tool_messages=False))

        # O que importa e o OBJETO VIVO, que e o que o step_helpers le.
        assert _extract_sources_opened(run), "sources_opened nao pode ficar vazio"
        assert _extract_consult_tools(run) == ["buscar_conhecimento"]

        # E ele e o mesmo nos dois casos: o flag muda o que se GRAVA.
        assert [m.role for m in ligado.messages] != [m.role for m in desligado.messages]
        assert _extract_sources_opened(run) == _extract_sources_opened(run)

    def test_e_mobile_fail_02_nao_volta(self, brain_indexado, embedder) -> None:
        """A regressao explicita: desligar a gravacao nao pode zerar a fonte."""

        run = _run_com_tool(self._payload_real(brain_indexado, embedder))
        _armazenar(run, _AgentDePersistencia(tool_messages=False))

        abertas = _extract_sources_opened(run)
        assert abertas != [], "sources_opened vazio = MOBILE_FAIL_02 de volta"
        assert "OFFERS" in abertas, abertas

        gate = evaluate_final_response(
            agent_id=VENDEDOR,
            response=f"Segundo {abertas[0]}, o valor esta na pagina de oferta.",
            references=[abertas[0]],
            sources_opened=abertas,
        )
        assert gate.status != "REJECTED", gate.reason
        assert gate.citations_without_source == []
        assert gate.outbound_allowed is True

    def test_f_o_gate_continua_pegando_citacao_inventada(self, brain_indexado, embedder) -> None:
        """O objetivo nunca foi fazer o gate aceitar mais coisa."""

        run = _run_com_tool(self._payload_real(brain_indexado, embedder))
        _armazenar(run, _AgentDePersistencia(tool_messages=False))
        abertas = _extract_sources_opened(run)

        gate = evaluate_final_response(
            agent_id=VENDEDOR,
            response="Segundo o EBOOK_RECHEIOS, a receita leva 200g de creme.",
            references=["EBOOK_RECHEIOS"],
            sources_opened=abertas,
        )
        assert gate.status == "REJECTED"

    def test_f_sem_fonte_aberta_continua_rejeitando(self) -> None:
        gate = evaluate_final_response(
            agent_id=VENDEDOR,
            response="O ebook custa R$ 29,00 conforme OFFERS.",
            references=["OFFERS"],
            sources_opened=[],
        )
        assert gate.status == "REJECTED"


# =============================================================================
# G + H — Disclosure e conteudo pago
# =============================================================================


class TestConteudoPago:
    """O suporte PODE conhecer material pago. Ele nao pode ser ARMAZENADO.

    Nada de corpo de receita neste arquivo: a fixture usa texto sintetico com
    marcadores proprios, e e por eles que se prova a ausencia.
    """

    MARCADORES = ("quebra da emulsao", "pasta de pistache", "sintetico de teste")

    def _payload_pago(self, brain, embedder) -> tuple[str, list]:
        resultado = search(
            agent_id=SUPORTE,
            query="pistache emulsao ganache",
            repository=brain,
            mode="hybrid",
            embedder=embedder,
        )
        pagos = [h for h in resultado.hits if (h.provenance.external_key or "").startswith("EBOOK_")]
        return _payload({"status": "OK", "resultados": resultado.as_documents()}), pagos

    def test_g_o_suporte_continua_conhecendo(self, brain_indexado, embedder) -> None:
        carga, pagos = self._payload_pago(brain_indexado, embedder)
        assert pagos, "o suporte precisa alcancar material pago para o teste significar algo"
        assert any(m in carga.lower() for m in self.MARCADORES), "o corpo chega ao agente durante o run"

    def test_g_disclosure_continua_impedindo_a_saida(self, brain_indexado, embedder) -> None:
        _, pagos = self._payload_pago(brain_indexado, embedder)
        for hit in pagos:
            assert hit.disclosure.can_know is True
            assert hit.disclosure.can_reveal_full_recipe is False
            assert hit.disclosure.requires_entitlement is True

    def test_h_o_corpo_pago_nao_e_gravado(self, brain_indexado, embedder) -> None:
        """O teste central da F4.1A."""

        carga, pagos = self._payload_pago(brain_indexado, embedder)
        assert pagos

        run = _run_com_tool(carga, pergunta="minha ganache separou")

        com_politica = _json_do_que_seria_gravado(run, _AgentDePersistencia(tool_messages=False)).lower()
        for marcador in self.MARCADORES:
            assert marcador not in com_politica, f"conteudo pago persistido: {marcador!r}"

    def test_h_contraprova_sem_a_politica_o_corpo_ia_para_o_banco(self, brain_indexado, embedder) -> None:
        """Sem esta contraprova, o teste acima passaria com uma fixture vazia."""

        carga, pagos = self._payload_pago(brain_indexado, embedder)
        assert pagos

        run = _run_com_tool(carga, pergunta="minha ganache separou")
        sem_politica = _json_do_que_seria_gravado(run, _AgentDePersistencia(tool_messages=True)).lower()

        assert any(m in sem_politica for m in self.MARCADORES), (
            "se nada aparece nem com o flag ligado, o teste principal nao prova nada"
        )


# =============================================================================
# I — midia
# =============================================================================


class TestMidia:
    def _run_com_midia(self) -> RunOutput:
        from agno.media import Audio, Image

        mensagem = Message(role="user", content="ouve isso")
        mensagem.audio = [Audio(content=b"\x00\x01audio-bruto-da-cliente")]
        mensagem.images = [Image(content=b"\x89PNGimagem")]
        run = RunOutput(run_id="run-m", agent_id=VENDEDOR, session_id="s", content="ok", messages=[mensagem])
        run.images = [Image(content=b"\x89PNGsaida")]
        return run

    def test_i_midia_nao_e_gravada(
        self,
    ) -> None:
        gravado = _json_do_que_seria_gravado(
            self._run_com_midia(), _AgentDePersistencia(tool_messages=False, media=False)
        )
        assert "audio-bruto-da-cliente" not in gravado
        assert "imagem" not in gravado.lower() or "PNGimagem" not in gravado

    def test_i_o_scrub_de_midia_muta_in_place_e_isso_esta_documentado(self) -> None:
        """Comportamento REAL da 2.6.4, nao inferido.

        Diferente do scrub de tool, `scrub_media_from_message` altera o objeto
        Message compartilhado pela copia rasa — entao o objeto vivo TAMBEM
        perde a midia. Nada no nosso fluxo depende disso (ver o teste abaixo),
        mas o comportamento fica travado para que a diferenca nao surpreenda.
        """

        run = self._run_com_midia()
        _armazenar(run, _AgentDePersistencia(tool_messages=False, media=False))
        assert run.messages[0].audio is None, "2.6.4 muta in-place; se isto mudar, revisar o fluxo de audio"

    def test_i_o_canal_transcreve_antes_do_workflow(self) -> None:
        """Por isso perder midia depois do run nao quebra o WhatsApp."""

        import inspect

        from app.whatsapp import channel

        fonte = inspect.getsource(channel)
        assert "transcribe_audio" in fonte
        posicao_transcricao = fonte.index("transcribe_audio(audio")
        posicao_workflow = fonte.index("run_answer_dm,")
        assert posicao_transcricao < posicao_workflow, "a transcricao tem que vir antes do workflow"

    def test_i_os_agentes_do_time_nao_processam_midia(self) -> None:
        for agente in _TEAM_AGENTS:
            nomes = {getattr(h, "__name__", str(h)) for h in (agente.pre_hooks or [])}
            assert "prepare_multimodal_input" not in nomes, agente.id


# =============================================================================
# J — continuidade
# =============================================================================


class TestContinuidade:
    def _sessao_com_runs(self, quantidade: int, *, agente: _AgentDePersistencia) -> AgentSession:
        sessao = AgentSession(session_id="wa:ANSWER_DM:wa_teste", agent_id=VENDEDOR, user_id="wa_teste")
        for indice in range(quantidade):
            run = RunOutput(
                run_id=f"run-{indice}",
                agent_id=VENDEDOR,
                session_id=sessao.session_id,
                content=f"resposta {indice}",
                messages=[
                    Message(role="system", content="instrucoes"),
                    Message(role="user", content=f"pergunta {indice}"),
                    Message(
                        role="assistant",
                        content="",
                        tool_calls=[{"id": f"tc{indice}", "function": {"name": "buscar_conhecimento"}}],
                    ),
                    Message(
                        role="tool",
                        content='{"resultados": [{"fonte": "OFFERS"}]}',
                        tool_call_id=f"tc{indice}",
                        tool_name="buscar_conhecimento",
                    ),
                    Message(role="assistant", content=f"resposta {indice}"),
                ],
            )
            sessao.upsert_run(_armazenar(run, agente))
        return sessao

    def test_j_as_ultimas_cinco_runs_continuam_completas(self) -> None:
        sessao = self._sessao_com_runs(7, agente=_AgentDePersistencia(tool_messages=False))
        mensagens = sessao.get_messages(last_n_runs=5)

        papeis = [m.role for m in mensagens]
        assert papeis.count("user") == 5
        assert "pergunta 6" in [m.content for m in mensagens if m.role == "user"]
        assert "pergunta 1" not in [m.content for m in mensagens if m.role == "user"]

    def test_j_assistant_com_texto_sobrevive(self) -> None:
        sessao = self._sessao_com_runs(7, agente=_AgentDePersistencia(tool_messages=False))
        conteudos = [m.content for m in sessao.get_messages(last_n_runs=5) if m.role == "assistant"]
        assert any("resposta 6" == c for c in conteudos)

    def test_j_tool_result_antigo_nao_e_reinjetado(self) -> None:
        sessao = self._sessao_com_runs(7, agente=_AgentDePersistencia(tool_messages=False))
        assert not [m for m in sessao.get_messages(last_n_runs=5) if m.role == "tool"]

    def test_j_a_continuidade_e_a_mesma_com_e_sem_a_politica(self) -> None:
        """A experiencia da cliente nao pode mudar."""

        com = self._sessao_com_runs(7, agente=_AgentDePersistencia(tool_messages=False))
        sem = self._sessao_com_runs(7, agente=_AgentDePersistencia(tool_messages=True))

        def dialogo(sessao):
            return [
                (m.role, m.content)
                for m in sessao.get_messages(last_n_runs=5)
                if m.role in ("user", "assistant") and m.content
            ]

        assert dialogo(com) == dialogo(sem)

    def test_j_o_system_e_remontado_a_cada_run(self) -> None:
        """Continuidade nao depende do system gravado: ele vem de `instructions`."""

        from agents.judith_team.sales_conversion_agent import sales_conversion_agent

        assert sales_conversion_agent.instructions
        assert len(str(sales_conversion_agent.instructions)) > 500

    def test_j_a_sessao_sobrevive_a_serializacao(self) -> None:
        """Restart = reler do Postgres. `from_dict(to_dict())` tem que fechar."""

        sessao = self._sessao_com_runs(3, agente=_AgentDePersistencia(tool_messages=False))
        renascida = AgentSession.from_dict(json.loads(json.dumps(sessao.to_dict(), default=str)))

        assert renascida is not None
        assert len(renascida.runs or []) == 3
        assert [m.content for m in renascida.get_messages(last_n_runs=5) if m.role == "user"] == [
            m.content for m in sessao.get_messages(last_n_runs=5) if m.role == "user"
        ]


# =============================================================================
# Alvos de retencao — registrados, NAO ativados
# =============================================================================


class TestAlvosDeRetencao:
    def test_os_alvos_estao_registrados(self) -> None:
        assert RETENTION_TARGETS == {"customer_facing_days": 90, "internal_session_days": 7}

    def test_o_historico_continua_intocado(self) -> None:
        assert HISTORICAL_DATA_STRATEGY == "LEAVE_UNTOUCHED_TEMPORARILY"

    def test_apagamento_a_pedido_e_futuro(self) -> None:
        assert USER_REQUESTED_DELETION == "FUTURE_IMPLEMENTATION"

    def test_nada_executa_purge_nesta_fase(self) -> None:
        """Nenhum caminho de codigo CHAMA delete de sessao.

        Por AST, e nao por substring: o proprio `registry.py` documenta o
        caminho tecnico do apagamento futuro em comentario, e citar nao e
        chamar. Um teste que confunde as duas coisas obrigaria a apagar a
        documentacao para passar.
        """

        import ast
        import pathlib

        proibidas = {"delete_session", "delete_sessions", "delete_user_memories"}
        chamadas: list[str] = []

        for pasta in ("orchestration", "app", "brain", "agents", "db"):
            for arquivo in pathlib.Path(pasta).rglob("*.py"):
                arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
                for no in ast.walk(arvore):
                    if not isinstance(no, ast.Call):
                        continue
                    alvo = no.func
                    nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")
                    if nome in proibidas:
                        chamadas.append(f"{arquivo}:{no.lineno} -> {nome}()")

        assert chamadas == [], f"purge executado nesta fase: {chamadas}"


# =============================================================================
# ExecutionLog inalterado
# =============================================================================


class TestExecutionLogInalterado:
    def test_a_allowlist_nao_mudou(self) -> None:
        from orchestration.execution_repository import _OUTCOME_ALLOWLIST

        for campo in ("sources_opened", "references", "evidence_status", "brain_tools_called"):
            assert campo in _OUTCOME_ALLOWLIST

    def test_o_corpo_da_conversa_continua_fora(self) -> None:
        from orchestration.execution_repository import _OUTCOME_ALLOWLIST

        for proibido in ("final_response", "outbound_message", "inputs", "message"):
            assert proibido not in _OUTCOME_ALLOWLIST


# =============================================================================
# K — delta de armazenamento
# =============================================================================


class TestDeltaDeArmazenamento:
    def test_a_reducao_e_real(self, brain_indexado, embedder) -> None:
        resultado = search(
            agent_id=VENDEDOR, query=FRASE_DA_JUDITH, repository=brain_indexado, mode="hybrid", embedder=embedder
        )
        run = _run_com_tool(_payload({"status": "OK", "resultados": resultado.as_documents()}))

        antes = len(_json_do_que_seria_gravado(run, _AgentDePersistencia(tool_messages=True)).encode())
        depois = len(_json_do_que_seria_gravado(run, _AgentDePersistencia(tool_messages=False)).encode())

        assert depois < antes
        assert depois / antes < 0.5, f"reducao insuficiente: {depois}/{antes}"

    @pytest.mark.parametrize("agente_id,pergunta", [(VENDEDOR, FRASE_DA_JUDITH), (SUPORTE, "minha ganache separou")])
    def test_a_run_sem_tool_nao_muda(self, brain_indexado, embedder, agente_id: str, pergunta: str) -> None:
        """Sem tool call, a politica nao tem efeito — e nao pode ter."""

        run = RunOutput(
            run_id="r",
            agent_id=agente_id,
            session_id="s",
            content="resposta",
            messages=[Message(role="system", content="sys"), Message(role="user", content=pergunta)],
        )
        antes = _json_do_que_seria_gravado(run, _AgentDePersistencia(tool_messages=True))
        depois = _json_do_que_seria_gravado(run, _AgentDePersistencia(tool_messages=False))
        assert antes == depois


# =============================================================================
# O buraco que os DOIS FLAGS SOZINHOS nao fecham
# =============================================================================


class TestBuracoDosFlags:
    """`store_tool_messages=False` limpa `messages` e mais nada.

    Descoberto num run real do `customer-support-agent`: depois do scrub as
    mensagens estavam limpas e `tools[0].result` ainda carregava 6.757 bytes
    com o corpo dos chunks pagos. `references` idem.

    Os testes anteriores nao pegavam porque o helper montava a run so com
    `messages` — o teste media a forma que EU supus, nao a que o runtime
    produz. E a mesma armadilha do MOBILE_FAIL_02, e por isso ela tem classe
    propria aqui: para ficar nomeada em vez de implicita.
    """

    PAYLOAD = '{"status": "OK", "resultados": [{"fonte": "EBOOK_RECHEIOS", "conteudo": "MARCADOR-PAGO-XYZ"}]}'

    def test_o_scrub_do_agno_nao_toca_em_tools(self) -> None:
        run = _run_com_tool(self.PAYLOAD)
        copia = _armazenar(run, _AgentDePersistencia(tool_messages=False), com_hook=False)

        assert "MARCADOR-PAGO-XYZ" in json.dumps(copia.tools, default=str), (
            "se isto passar a falhar, o Agno passou a limpar tools[] e o hook virou redundante"
        )

    def test_o_scrub_do_agno_nao_toca_em_references(self) -> None:
        run = _run_com_tool(self.PAYLOAD)
        copia = _armazenar(run, _AgentDePersistencia(tool_messages=False), com_hook=False)

        assert "MARCADOR-PAGO-XYZ" in json.dumps(copia.references, default=str)

    def test_o_hook_fecha_o_buraco(self) -> None:
        gravado = _json_do_que_seria_gravado(_run_com_tool(self.PAYLOAD), _AgentDePersistencia(tool_messages=False))

        assert "MARCADOR-PAGO-XYZ" not in gravado
        assert RESULTADO_NAO_PERSISTIDO in gravado, "o fato da chamada tem que sobreviver"

    def test_o_hook_preserva_a_contagem_de_tool_calls(self) -> None:
        """`_step_usage` conta `len(response.tools)` para telemetria."""

        run = _run_com_tool(self.PAYLOAD)
        antes = len(run.tools or [])
        redigir_carga_de_tool(run)

        assert len(run.tools or []) == antes == 1
        assert run.tools[0].tool_name == "buscar_conhecimento"

    def test_o_hook_nao_apaga_a_provenance(self) -> None:
        """Redigir `tools[].result` nao pode tocar em `messages`."""

        run = _run_com_tool(self.PAYLOAD)
        redigir_carga_de_tool(run)

        assert _extract_sources_opened(run) == ["EBOOK_RECHEIOS"]
        assert _extract_consult_tools(run) == ["buscar_conhecimento"]

    def test_o_hook_nao_apaga_a_resposta_ao_cliente(self) -> None:
        """A resposta e a conversa. Sai da politica de retencao, nao desta."""

        run = _run_com_tool(self.PAYLOAD)
        redigir_carga_de_tool(run)

        finais = [m.content for m in run.messages if m.role == "assistant" and m.content]
        assert finais and finais[-1]

    def test_o_hook_esta_ligado_nos_vinte(self) -> None:
        for agente in _TEAM_AGENTS:
            nomes = {getattr(h, "__name__", type(h).__name__) for h in (agente.post_hooks or [])}
            assert "redigir_carga_de_tool" in nomes, agente.id

    def test_o_hook_e_idempotente(self) -> None:
        run = _run_com_tool(self.PAYLOAD)
        redigir_carga_de_tool(run)
        primeiro = run.tools[0].result
        redigir_carga_de_tool(run)

        assert run.tools[0].result == primeiro == RESULTADO_NAO_PERSISTIDO

    def test_o_hook_tolera_run_sem_tools(self) -> None:
        run = RunOutput(run_id="r", agent_id=VENDEDOR, session_id="s", content="oi", messages=[])
        redigir_carga_de_tool(run)  # nao pode levantar
