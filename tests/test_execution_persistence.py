"""
Judith Brain F1 — a fiacao: workflow -> repositorio -> banco.

`tests/test_execution_repository.py` cobre o repositorio isolado. Aqui o
teste sobe o ANSWER_DM inteiro (com os agentes dublados, sem LLM) e checa o
que ficou gravado — inclusive quando a execucao explode no meio.

Tambem guarda as invariantes que a F1 nao podia mexer: Evidence Gate,
Quality Control, Capability Policy e o canal WhatsApp.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from orchestration.handoff import AgentStepDecision, RoutingDecision


def _agente_dublado(decision: AgentStepDecision, *, opened: list[str] | None = None, metrics: Any = None):
    """Agent falso que devolve uma decisao estruturada e metricas do runtime."""

    message = MagicMock()
    message.role = "assistant"
    message.tool_calls = [
        {"function": {"name": "ler_documento", "arguments": json.dumps({"fonte": fonte})}} for fonte in (opened or [])
    ]

    resposta = MagicMock(
        content=decision,
        messages=[message],
        model="gpt-5-mini",
        model_provider="OpenAI",
        metrics=metrics,
        tools=[],
    )
    agente = MagicMock()
    agente.run.return_value = resposta
    agente.model = MagicMock(id="gpt-5-mini", provider="OpenAI", reasoning_effort="minimal")
    return agente


class _Metrics:
    input_tokens = 900
    output_tokens = 120
    reasoning_tokens = 32
    cache_read_tokens = 0
    total_tokens = 1020
    duration = 1.25


def _roda_answer_dm(monkeypatch, *, route_to: str = "customer-support-agent", metrics: Any = None, **kwargs):
    from orchestration.workflows import answer_dm as module

    classificacao = RoutingDecision(
        decision="classificado",
        output="resposta simulada",
        confidence="alto",
        references=[],
        recommended_next=route_to,
        route_to=route_to,
    )
    especialista = AgentStepDecision(
        decision="resolvido",
        output="resposta do especialista",
        confidence="alto",
        references=[],
        recommended_next="judith",
    )

    def fake_get_agent(agent_id: str):
        if agent_id == "community-dm-agent":
            return _agente_dublado(classificacao, metrics=metrics)
        return _agente_dublado(especialista, metrics=metrics)

    monkeypatch.setattr("orchestration.step_helpers.get_agent", fake_get_agent)
    return module.run_answer_dm("mensagem de teste", **kwargs)


# --- 1. O workflow grava ----------------------------------------------------


def test_answer_dm_persiste_a_execucao(monkeypatch, execution_repository_em_memoria) -> None:
    log, _qc = _roda_answer_dm(monkeypatch)

    linha = execution_repository_em_memoria.get(log.task_id)

    assert linha is not None, "ANSWER_DM terminou sem deixar rastro no banco"
    assert linha["workflow"] == "ANSWER_DM"
    assert linha["status"] == "completed"
    assert "community-dm-agent" in linha["agents_called"]


def test_answer_dm_grava_canal_sessao_e_user_ref(monkeypatch, execution_repository_em_memoria) -> None:
    log, _qc = _roda_answer_dm(
        monkeypatch,
        session_id="wa:ANSWER_DM:wa_abc123def456",
        user_id="wa_abc123def456",
        channel="whatsapp",
    )

    linha = execution_repository_em_memoria.get(log.task_id)

    assert linha["channel"] == "whatsapp"
    assert linha["session_id"] == "wa:ANSWER_DM:wa_abc123def456"
    assert linha["user_ref"] == "wa_abc123def456"


def test_execucao_local_fica_marcada_como_internal(monkeypatch, execution_repository_em_memoria) -> None:
    log, _qc = _roda_answer_dm(monkeypatch)

    assert execution_repository_em_memoria.get(log.task_id)["channel"] == "internal"


def test_answer_dm_grava_modelo_e_tokens(monkeypatch, execution_repository_em_memoria) -> None:
    """A baseline de modelo sai do runtime do Agno, nao do texto do LLM."""

    log, _qc = _roda_answer_dm(monkeypatch, metrics=_Metrics())

    linha = execution_repository_em_memoria.get(log.task_id)
    primeiro = linha["model_usage"][0]

    assert primeiro["agent_id"] == "community-dm-agent"
    assert primeiro["model_id"] == "gpt-5-mini"
    assert primeiro["reasoning_effort"] == "minimal"
    assert primeiro["input_tokens"] == 900
    assert primeiro["reasoning_tokens"] == 32
    assert primeiro["duration_ms"] == 1250
    assert linha["token_usage"]["total_tokens"] == 1020 * len(linha["model_usage"])


def test_sem_metricas_o_workflow_nao_quebra(monkeypatch, execution_repository_em_memoria) -> None:
    """Modelo que nao devolve metrica nao pode derrubar atendimento."""

    log, qc = _roda_answer_dm(monkeypatch, metrics=None)

    linha = execution_repository_em_memoria.get(log.task_id)

    assert log.status == "completed"
    assert qc.status == "PROCESSO_VALIDADO"
    assert linha["model_usage"][0]["input_tokens"] is None
    assert linha["model_usage"][0]["model_id"] == "gpt-5-mini"


# --- 2. Falha no meio continua auditavel ------------------------------------


def test_execucao_que_explode_no_meio_persiste_como_failed(monkeypatch, execution_repository_em_memoria) -> None:
    from orchestration.workflows import answer_dm as module

    def agente_que_explode(agent_id: str):
        raise RuntimeError("modelo fora do ar")

    monkeypatch.setattr("orchestration.step_helpers.get_agent", agente_que_explode)

    # O Agno converte a falha do step antes de ela chegar aqui, entao o tipo
    # exato varia. O que importa e que a excecao SOBE (o chamador fica sabendo)
    # e que a linha ficou gravada antes disso.
    with pytest.raises(Exception):  # noqa: B017
        module.run_answer_dm("mensagem de teste", task_id="task-explode")

    linha = execution_repository_em_memoria.get("task-explode")

    assert linha is not None, "execucao que falhou nao deixou rastro"
    assert linha["status"] == "failed"
    assert linha["error"]
    assert linha["finished_at"] is not None


def test_falha_de_persistencia_nao_impede_a_resposta(monkeypatch, execution_repository_em_memoria) -> None:
    """Banco fora do ar nao pode virar mensagem nao respondida."""

    def save_quebrado(_log):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(execution_repository_em_memoria, "save", save_quebrado)

    log, qc = _roda_answer_dm(monkeypatch)

    assert log.status == "completed"
    assert qc.status == "PROCESSO_VALIDADO"
    assert log.outputs["outbound_message"]


def test_mesma_execucao_regravada_nao_duplica(monkeypatch, execution_repository_em_memoria) -> None:
    _roda_answer_dm(monkeypatch, task_id="task-fixo")
    _roda_answer_dm(monkeypatch, task_id="task-fixo")

    linhas = execution_repository_em_memoria.list_executions(limit=100)

    assert [linha["task_id"] for linha in linhas].count("task-fixo") == 1


# --- 3. PII no caminho real -------------------------------------------------


def test_mensagem_da_cliente_nao_chega_ao_banco(monkeypatch, execution_repository_em_memoria) -> None:
    """O `context` do ANSWER_DM carrega a mensagem literal. Ela para antes do banco."""

    from orchestration.workflows import answer_dm as module

    classificacao = RoutingDecision(
        decision="classificado",
        output="ok",
        confidence="alto",
        references=[],
        recommended_next="customer-support-agent",
        route_to="customer-support-agent",
    )
    monkeypatch.setattr(
        "orchestration.step_helpers.get_agent",
        lambda agent_id: _agente_dublado(classificacao),
    )

    segredo_da_cliente = "meu CPF e 111.222.333-44 e moro na rua das Flores"
    log, _qc = module.run_answer_dm(segredo_da_cliente)

    gravado = str(execution_repository_em_memoria.get(log.task_id))

    assert "CPF" not in gravado
    assert "rua das Flores" not in gravado
    # ...mas o dado estrutural continua la.
    assert "community-dm-agent" in gravado


# --- 4. Invariantes que a F1 nao podia mexer --------------------------------


def test_evidence_gate_continua_bloqueando(monkeypatch, execution_repository_em_memoria) -> None:
    """Afirmacao comercial sem fonte aberta nao sai — e o bloqueio fica gravado."""

    from orchestration.workflows import answer_dm as module

    classificacao = RoutingDecision(
        decision="classificado",
        output="ok",
        confidence="alto",
        references=[],
        recommended_next="sales-conversion-agent",
        route_to="sales-conversion-agent",
    )
    vendedor = AgentStepDecision(
        decision="respondi o preco",
        output="O ebook custa R$ 97,00 e o desconto vai ate sexta.",
        confidence="alto",
        references=[],  # nada aberto: o gate tem que barrar
        recommended_next="judith",
    )

    def fake_get_agent(agent_id: str):
        if agent_id == "community-dm-agent":
            return _agente_dublado(classificacao)
        return _agente_dublado(vendedor)

    monkeypatch.setattr("orchestration.step_helpers.get_agent", fake_get_agent)
    log, _qc = module.run_answer_dm("quanto custa o ebook?")

    assert log.outputs["outbound_allowed"] is False
    assert log.outputs["evidence_status"] in {"NEEDS_EVIDENCE", "REJECTED"}
    assert "R$ 97,00" not in log.outputs["outbound_message"]

    linha = execution_repository_em_memoria.get(log.task_id)
    assert linha["evidence_status"] == log.outputs["evidence_status"]
    assert linha["outbound_allowed"] is False
    assert "R$ 97,00" not in str(linha), "resposta bloqueada vazou para o banco"


def test_quality_control_continua_deterministico(monkeypatch, execution_repository_em_memoria) -> None:
    _log, qc = _roda_answer_dm(monkeypatch)

    assert qc.status == "PROCESSO_VALIDADO"
    assert qc.missing_agents == []
    assert qc.citations_without_source == []


def test_capability_policy_intacta() -> None:
    """A F1 nao tocou em capabilities: a checagem continua sem LLM e sem banco."""

    from agents.capabilities import CAPABILITY_POLICY

    assert CAPABILITY_POLICY, "capability policy sumiu"


def test_escalacao_continua_sendo_registrada(monkeypatch, execution_repository_em_memoria) -> None:
    log, _qc = _roda_answer_dm(monkeypatch, route_to="human-escalation")

    linha = execution_repository_em_memoria.get(log.task_id)

    assert log.status == "pending_human_approval"
    assert linha["escalated"] is True
    assert linha["escalations"][0]["at_step"]


def test_canal_whatsapp_marca_a_execucao(monkeypatch) -> None:
    """O canal precisa dizer de onde veio — e entregar user_ref, nao telefone."""

    import asyncio

    from app.whatsapp import channel as ch
    from tests.test_whatsapp_channel import FakeConfig, _fake_answer_dm, _message, _no_media

    _no_media(monkeypatch)
    chamadas = _fake_answer_dm(
        monkeypatch,
        outputs={"outbound_message": "ok", "evidence_status": "CONFIRMED", "outbound_allowed": True},
    )
    asyncio.run(ch.handle_message(_message("text", "Oi!"), FakeConfig()))

    assert chamadas[0]["channel"] == "whatsapp"
    assert chamadas[0]["user_id"].startswith("wa_")
    assert "5511999999999" not in chamadas[0]["user_id"]


def test_resposta_com_formato_inesperado_nao_derruba_a_execucao(monkeypatch, execution_repository_em_memoria) -> None:
    """Regressao: a primeira versao da instrumentacao quebrou 7 testes.

    Ela fazia `len(response.tools)` e passava `response.model` direto para o
    Pydantic. Com um objeto que nao tem o formato esperado — dublê de teste,
    provider novo, resposta parcial — isso levantava no meio do workflow e
    matava a execucao. Metrica nunca pode derrubar atendimento.
    """

    from orchestration.step_helpers import _step_usage

    class RespostaEstranha:
        model = 12345  # nao e string
        tools = "isto nao e lista"
        metrics = object()  # sem nenhum dos campos esperados

    uso = _step_usage(
        agent=object(),
        agent_id="community-dm-agent",
        to_agent="judith",
        response=RespostaEstranha(),
        duration_ms=42,
    )

    assert uso.agent_id == "community-dm-agent"
    assert uso.model_id is None
    assert uso.tool_calls == 0
    assert uso.duration_ms == 42
