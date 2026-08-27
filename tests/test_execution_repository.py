"""
Judith Brain F1 — persistencia do ExecutionLog.

Roda sobre SQLite em memoria, nao sobre mock: o SQL exercitado aqui e o mesmo
que vai para o Postgres (a coluna JSONB tem variante JSON para sqlite, ver
`orchestration/execution_repository.py`). Mock provaria que o codigo chama o
que eu mandei chamar; isto prova que o banco aceita.

Contrato coberto:

1. Execucao bem sucedida e execucao com erro, ambas persistem.
2. Retry do mesmo task_id atualiza — nunca duplica.
3. Falha de persistencia nao quebra quem chamou, mas fica observavel.
4. agent_id, model_id, reasoning_effort e tokens sao gravados.
5. Ausencia de metrica nao quebra nada.
6. Segredo e telefone bruto nao chegam ao banco.
7. Texto de conversa nao chega ao banco.
8. Os filtros que o AI Performance & Evals Agent vai precisar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine

from orchestration.execution_log import Escalation, ExecutionLog, StepUsage
from orchestration.execution_repository import (
    REDACTED,
    ExecutionRepository,
    _redact,
    persist_execution,
    set_execution_repository,
)
from orchestration.handoff import AgentHandoff

TELEFONE_BRUTO = "5511987654321"
CHAVE_OPENAI = "sk-proj-" + "a" * 40
TOKEN_META = "EAA" + "b" * 40


@pytest.fixture
def repo():
    """Repositorio novo por teste, em memoria."""

    engine = create_engine("sqlite://")
    repositorio = ExecutionRepository(engine)
    repositorio.ensure_table()
    return repositorio


@pytest.fixture(autouse=True)
def _sem_repositorio_global():
    """Impede que um teste vaze repositorio para o proximo."""

    set_execution_repository(None)
    yield
    set_execution_repository(None)


def _handoff(
    *,
    from_agent: str = "community-dm-agent",
    to_agent: str = "customer-support-agent",
    references: list[str] | None = None,
    risks: list[str] | None = None,
) -> AgentHandoff:
    return AgentHandoff(
        from_agent=from_agent,
        to_agent=to_agent,
        workflow="ANSWER_DM",
        task_id="t-1",
        objective="Classificar mensagem recebida",
        # E aqui que a mensagem literal da cliente viaja no ANSWER_DM real.
        context=f"Mensagem recebida via Instagram: 'meu telefone e {TELEFONE_BRUTO}'",
        decision="Classifiquei como suporte",
        output="Oi Ana! Sobre o seu pedido, ja vou verificar.",
        confidence="alto",
        risks=risks or [],
        references=references or ["OFFERS"],
        sources_opened=["OFFERS"],
        recommended_next="customer-support-agent",
    )


def _log(
    *,
    task_id: str = "task-1",
    status: str = "completed",
    workflow: str = "ANSWER_DM",
    channel: str = "whatsapp",
    com_metricas: bool = True,
) -> ExecutionLog:
    log = ExecutionLog(task_id=task_id, workflow=workflow, channel=channel)
    log.session_id = "wa:ANSWER_DM:wa_8e8b60d7f9b1"
    log.user_ref = "wa_8e8b60d7f9b1"
    log.inputs["message"] = f"Oi, meu numero e {TELEFONE_BRUTO}"
    log.record(_handoff())
    log.outputs.update(
        {
            "route_to": "customer-support-agent",
            "final_agent": "customer-support-agent",
            "evidence_status": "CONFIRMED",
            "outbound_allowed": True,
            "final_response": "Oi Ana! Sobre o seu pedido, ja vou verificar.",
            "outbound_message": "Oi Ana! Sobre o seu pedido, ja vou verificar.",
        }
    )
    if com_metricas:
        log.record_usage(
            StepUsage(
                agent_id="community-dm-agent",
                to_agent="customer-support-agent",
                model_id="gpt-5-mini",
                model_provider="OpenAI",
                reasoning_effort="minimal",
                input_tokens=1200,
                output_tokens=80,
                reasoning_tokens=64,
                total_tokens=1344,
                tool_calls=2,
                duration_ms=1500,
            )
        )
    log.finish(status=status, result="Oi Ana! Sobre o seu pedido, ja vou verificar.")
    return log


# --- 1. Persistencia basica -------------------------------------------------


def test_execucao_bem_sucedida_persiste(repo) -> None:
    repo.save(_log())

    linha = repo.get("task-1")

    assert linha is not None
    assert linha["workflow"] == "ANSWER_DM"
    assert linha["status"] == "completed"
    assert linha["channel"] == "whatsapp"
    assert linha["evidence_status"] == "CONFIRMED"
    assert linha["final_agent"] == "customer-support-agent"
    assert linha["agents_called"] == ["community-dm-agent"]


def test_execucao_com_erro_persiste(repo) -> None:
    """O caso que mais interessa investigar nao pode ser o unico sem rastro."""

    log = _log(task_id="task-erro", status="failed")
    log.error = "RuntimeError: o modelo nao respondeu"
    repo.save(log)

    linha = repo.get("task-erro")

    assert linha["status"] == "failed"
    assert "RuntimeError" in linha["error"]


def test_execucao_inacabada_persiste_sem_finished_at(repo) -> None:
    log = ExecutionLog(task_id="task-viva", workflow="ANSWER_DM")
    repo.save(log)

    linha = repo.get("task-viva")

    assert linha["status"] == "running"
    assert linha["finished_at"] is None
    assert linha["duration_ms"] is None


def test_duracao_e_calculada(repo) -> None:
    log = _log(task_id="task-dur")

    repo.save(log)

    assert repo.get("task-dur")["duration_ms"] >= 0


# --- 2. Idempotencia --------------------------------------------------------


def test_retry_do_mesmo_task_id_nao_duplica(repo) -> None:
    repo.save(_log(task_id="task-retry", status="running"))
    repo.save(_log(task_id="task-retry", status="completed"))

    todas = repo.list_executions(limit=100)

    assert len([linha for linha in todas if linha["task_id"] == "task-retry"]) == 1
    assert repo.get("task-retry")["status"] == "completed"


def test_regravar_preserva_created_at(repo) -> None:
    """`created_at` marca quando a execucao entrou no banco, nao a ultima regravacao."""

    repo.save(_log(task_id="task-c"))
    criado = repo.get("task-c")["created_at"]

    repo.save(_log(task_id="task-c", status="failed"))

    assert repo.get("task-c")["created_at"] == criado
    assert repo.get("task-c")["updated_at"] is not None


# --- 3. Falha de logging nao derruba atendimento ----------------------------


class _RepositorioQuebrado:
    def save(self, log):
        raise RuntimeError("banco fora do ar")


def test_falha_de_persistencia_nao_levanta(monkeypatch) -> None:
    """A resposta para a cliente ja saiu. Logging nao pode virar falha de atendimento."""

    monkeypatch.setattr(
        "orchestration.execution_repository.get_execution_repository",
        lambda: _RepositorioQuebrado(),
    )

    assert persist_execution(_log()) is False


def test_falha_de_persistencia_e_observavel(monkeypatch, caplog) -> None:
    """Nao levantar nao pode virar silencio."""

    monkeypatch.setattr(
        "orchestration.execution_repository.get_execution_repository",
        lambda: _RepositorioQuebrado(),
    )

    with caplog.at_level("ERROR"):
        persist_execution(_log(task_id="task-observavel"))

    assert any("task-observavel" in registro.message for registro in caplog.records)


def test_persistencia_bem_sucedida_retorna_true(repo) -> None:
    set_execution_repository(repo)

    assert persist_execution(_log(task_id="task-ok")) is True
    assert repo.get("task-ok") is not None


# --- 4. Baseline de modelo --------------------------------------------------


def test_agent_id_e_model_id_sao_registrados(repo) -> None:
    repo.save(_log(task_id="task-modelo"))

    uso = repo.get("task-modelo")["model_usage"]

    assert uso[0]["agent_id"] == "community-dm-agent"
    assert uso[0]["model_id"] == "gpt-5-mini"
    assert uso[0]["model_provider"] == "OpenAI"
    assert uso[0]["reasoning_effort"] == "minimal"


def test_tokens_sao_registrados_quando_disponiveis(repo) -> None:
    repo.save(_log(task_id="task-tokens"))

    linha = repo.get("task-tokens")

    assert linha["model_usage"][0]["input_tokens"] == 1200
    assert linha["model_usage"][0]["reasoning_tokens"] == 64
    assert linha["token_usage"]["total_tokens"] == 1344
    assert linha["token_usage"]["tool_calls"] == 2
    assert linha["token_usage"]["steps"] == 1


def test_ausencia_de_tokens_nao_quebra(repo) -> None:
    """Modelo que nao devolve metrica nao pode derrubar a execucao."""

    log = _log(task_id="task-sem-metrica", com_metricas=False)
    log.record_usage(StepUsage(agent_id="cmo", to_agent="qc"))

    repo.save(log)
    linha = repo.get("task-sem-metrica")

    assert linha["model_usage"][0]["input_tokens"] is None
    # Ausencia nao vira zero: zero e uma afirmacao, ausencia nao e.
    assert "total_tokens" not in linha["token_usage"]
    assert linha["token_usage"]["steps"] == 1


def test_step_com_erro_e_registrado(repo) -> None:
    log = _log(task_id="task-step-erro", com_metricas=False)
    log.record_usage(StepUsage(agent_id="cmo", to_agent="qc", error="APIConnectionError: timeout"))

    repo.save(log)

    assert "APIConnectionError" in repo.get("task-step-erro")["model_usage"][0]["error"]


def test_totais_somam_varios_steps() -> None:
    log = ExecutionLog(workflow="ANSWER_DM")
    log.record_usage(StepUsage(agent_id="a", to_agent="b", input_tokens=10, total_tokens=15))
    log.record_usage(StepUsage(agent_id="b", to_agent="c", input_tokens=5, total_tokens=8))

    assert log.token_totals() == {"input_tokens": 15, "total_tokens": 23, "steps": 2, "tool_calls": 0}


# --- 5. PII e segredo -------------------------------------------------------


def test_segredos_nao_sao_persistidos(repo, monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "segredo-do-app-muito-longo")

    log = _log(task_id="task-segredo", com_metricas=False)
    log.error = (
        f"falhou com key={CHAVE_OPENAI} token={TOKEN_META} "
        "url=postgresql://user:senha123@host:5432/railway "
        "auth=Bearer abcdefghijklmnop segredo-do-app-muito-longo"
    )
    repo.save(log)

    gravado = repo.get("task-segredo")["error"]

    assert CHAVE_OPENAI not in gravado
    assert TOKEN_META not in gravado
    assert "senha123" not in gravado
    assert "abcdefghijklmnop" not in gravado
    assert "segredo-do-app-muito-longo" not in gravado
    assert REDACTED in gravado


def test_telefone_bruto_nao_e_persistido(repo) -> None:
    """Mesmo que algo quebre a regra do user_ref, o numero nao passa."""

    log = _log(task_id="task-fone", com_metricas=False)
    log.human_feedback = f"a cliente do numero {TELEFONE_BRUTO} reclamou"
    repo.save(log)

    linha = repo.get("task-fone")

    assert TELEFONE_BRUTO not in str(linha)
    assert REDACTED in linha["human_feedback"]


def test_user_ref_hasheado_pode_ser_persistido(repo) -> None:
    """O oposto do teste anterior: o identificador anonimo E o dado util."""

    repo.save(_log(task_id="task-ref"))

    assert repo.get("task-ref")["user_ref"] == "wa_8e8b60d7f9b1"


def test_texto_de_conversa_nao_e_persistido(repo) -> None:
    """A fronteira da F1: metadado e estrutura, nunca o conteudo da conversa."""

    repo.save(_log(task_id="task-texto"))
    linha = str(repo.get("task-texto"))

    assert "Oi Ana!" not in linha, "resposta gerada vazou para o banco"
    assert "Mensagem recebida via Instagram" not in linha, "context do handoff vazou"
    assert "Classifiquei como suporte" not in linha, "decision do handoff vazou"


def test_handoff_persiste_so_o_estrutural(repo) -> None:
    repo.save(_log(task_id="task-handoff"))

    handoff = repo.get("task-handoff")["handoffs"][0]

    assert set(handoff) == {
        "from_agent",
        "to_agent",
        "confidence",
        "risks",
        "references",
        "sources_opened",
        "timestamp",
    }
    assert handoff["sources_opened"] == ["OFFERS"]


def test_redact_preserva_texto_normal() -> None:
    """Redacao agressiva demais destruiria o dado que queremos analisar."""

    texto = "cliente perguntou sobre o preco do ebook; abri OFFERS e PRODUCTS.md"

    assert _redact(texto) == texto


def test_redact_atravessa_estruturas_aninhadas() -> None:
    limpo = _redact({"a": [{"b": f"key {CHAVE_OPENAI}"}]})

    assert CHAVE_OPENAI not in str(limpo)


# --- 6. Consultas para o AI Performance & Evals -----------------------------


@pytest.fixture
def repo_populado(repo):
    repo.save(_log(task_id="a1", workflow="ANSWER_DM", status="completed"))
    repo.save(_log(task_id="a2", workflow="ANSWER_DM", status="failed"))
    repo.save(_log(task_id="c1", workflow="CREATE_REEL", status="completed", channel="internal"))

    escalado = _log(task_id="e1", workflow="ANSWER_DM", status="pending_human_approval")
    escalado.escalations.append(Escalation(raised_by="evidence-gate", reason="sem fonte", at_step="final_response"))
    escalado.outputs["evidence_status"] = "NEEDS_EVIDENCE"
    repo.save(escalado)

    com_feedback = _log(task_id="f1", workflow="ANSWER_DM")
    com_feedback.human_feedback = "resposta ficou seca demais"
    repo.save(com_feedback)
    return repo


def test_ultimas_execucoes(repo_populado) -> None:
    assert len(repo_populado.list_executions(limit=3)) == 3


def test_filtro_por_workflow(repo_populado) -> None:
    resultado = repo_populado.list_executions(workflow="CREATE_REEL")

    assert [linha["task_id"] for linha in resultado] == ["c1"]


def test_filtro_por_status_e_erros(repo_populado) -> None:
    assert [linha["task_id"] for linha in repo_populado.list_executions(only_errors=True)] == ["a2"]
    assert [linha["task_id"] for linha in repo_populado.list_executions(status="failed")] == ["a2"]


def test_filtro_por_agent_id(repo_populado) -> None:
    todos = repo_populado.list_executions(agent_id="community-dm-agent", limit=100)
    nenhum = repo_populado.list_executions(agent_id="video-editor", limit=100)

    assert len(todos) == 5
    assert nenhum == []


def test_filtro_por_model_id(repo_populado) -> None:
    usados = repo_populado.list_executions(model_id="gpt-5-mini", limit=100)
    inexistente = repo_populado.list_executions(model_id="claude-opus-5", limit=100)

    assert len(usados) == 5
    assert inexistente == []


def test_filtro_por_escalacao(repo_populado) -> None:
    assert [linha["task_id"] for linha in repo_populado.list_executions(only_escalated=True)] == ["e1"]


def test_filtro_por_no_evidence(repo_populado) -> None:
    resultado = repo_populado.list_executions(evidence_status="NEEDS_EVIDENCE")

    assert [linha["task_id"] for linha in resultado] == ["e1"]


def test_filtro_por_human_feedback(repo_populado) -> None:
    resultado = repo_populado.list_executions(only_with_human_feedback=True)

    assert [linha["task_id"] for linha in resultado] == ["f1"]


def test_filtro_por_canal_e_user_ref(repo_populado) -> None:
    assert [linha["task_id"] for linha in repo_populado.list_executions(channel="internal")] == ["c1"]
    assert len(repo_populado.list_executions(user_ref="wa_8e8b60d7f9b1", limit=100)) == 5


def test_filtro_por_data(repo_populado) -> None:
    futuro = datetime.now(UTC) + timedelta(hours=1)
    passado = datetime.now(UTC) - timedelta(hours=1)

    assert repo_populado.list_executions(since=futuro) == []
    assert len(repo_populado.list_executions(since=passado, limit=100)) == 5


# --- 7. Migration -----------------------------------------------------------


def test_ensure_table_e_idempotente(repo) -> None:
    """Rodar a migration de novo (todo boot) nao pode falhar nem apagar dado."""

    repo.save(_log(task_id="task-migration"))
    repo.ensure_table()
    repo.ensure_table()

    assert repo.get("task-migration") is not None
