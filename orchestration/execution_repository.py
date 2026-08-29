"""
ExecutionRepository — o unico lugar do projeto que sabe SQL sobre execucao.

    ExecutionLog  ->  ExecutionRepository  ->  PostgreSQL

Workflows e Agents nao conhecem SQL. Eles chamam `persist_execution(log)` e
seguem a vida.


POR QUE UMA TABELA PROPRIA
--------------------------

O Agno ja persiste bastante, e nada disso e duplicado aqui:

- `ai.agno_sessions.runs` (JSONB) — o `RunOutput` inteiro de cada run, com
  mensagens, metrics e modelo. E a fonte para reconstruir uma conversa.
- `ai.agno_traces` / `ai.agno_spans` — timing e status por run/span
  (tracing=True no AgentOS, com o db do projeto).
- `ai.agno_metrics` — agregado DIARIO de tokens e modelos.
- `ai.agno_eval_runs` — resultados do framework de eval.

O que nao existe em lugar nenhum e a semantica de NEGOCIO da execucao: o
nosso `task_id`, o workflow como ANSWER_DM, o veredito do Evidence Gate, o
Quality Control, as escalacoes, os handoffs com confianca/riscos/fontes
realmente abertas, e o feedback da Judith. Sem isso nao da para perguntar
"quantas respostas sairam sem evidencia esta semana" — que e exatamente a
pergunta que o AI Performance & Evals Agent vai fazer.

O `agno_metrics` tambem nao responde "quanto custou ESTA execucao": ele
agrega por dia. Por isso `model_usage`/`token_usage` moram aqui, por step.


PII E SEGREDO — O QUE **NAO** E PERSISTIDO
------------------------------------------

Logging de execucao nao pode virar um vazamento novo. Duas travas:

1. Allowlist estrutural. So campos enumeraveis atravessam: agent_id, status,
   booleanos, chaves de documento, contagens, metricas. Texto livre de
   conversa fica de fora POR CONSTRUCAO — nao existe caminho no `_row()` que
   leve `log.inputs`, `log.outputs["final_response"]`, `log.result` ou o
   `context`/`objective`/`output`/`decision` dos handoffs ate o banco. O
   `context` do ANSWER_DM carrega a mensagem literal da cliente
   (`f"...: {message!r}"`), e por isso ele nunca entra.

2. Redacao defensiva (`_redact`). O pouco texto livre que sobra — `risks`
   escrito pelo LLM, `human_feedback` escrito pela Judith, `error` vindo de
   uma excecao — passa por um filtro que apaga chave de API, token da Meta,
   URL de banco com credencial, header Authorization e telefone em formato
   E.164. Cinto e suspensorio: a allowlist ja deveria bastar.

Telefone: o canal so entrega `user_ref` (`wa_<sha256[:12]>`) e `session_id`
(`wa:ANSWER_DM:<user_ref>`). O numero bruto nao chega nem ao ExecutionLog.

Texto de conversa para eval futuro: NAO entra na F1. Quando entrar, precisa
de decisao explicita sobre retencao e provavelmente de coluna separada com
politica propria — nao pendurado no meio de um JSONB operacional. Fica
registrado aqui como a fronteira que foi escolhida, nao como esquecimento.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from os import getenv
from typing import Any

from agno.utils.log import log_error, log_info
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    MetaData,
    String,
    Table,
    Text,
    cast,
    func,
    literal,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from orchestration.execution_log import ExecutionLog

TABLE_NAME = "judith_execution_logs"

# JSONB no Postgres (indexavel, com operador de containment) e JSON generico
# em qualquer outro dialeto — e assim que a suite roda sobre SQLite em memoria
# sem Postgres no CI, exercitando SQL de verdade em vez de um mock.
_JSON = JSONB().with_variant(JSON(), "sqlite")

REDACTED = "[REDACTED]"

# Padroes de segredo. Nao dependem do ambiente: valem tambem para um segredo
# que vaze de outra origem (mensagem de excecao de uma lib, por exemplo).
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),  # OpenAI
    re.compile(r"\bEAA[A-Za-z0-9]{20,}"),  # Meta / WhatsApp
    re.compile(r"\b(?:postgres|postgresql|mysql|mongodb)(?:\+\w+)?://[^\s:@/]+:[^\s@]+@\S+", re.IGNORECASE),
    re.compile(r"\b[Bb]earer\s+[A-Za-z0-9._\-]{12,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    # Telefone E.164. So aparece aqui se algo quebrou a regra de user_ref.
    re.compile(r"\+?\d{11,15}\b"),
)

# Segredos que este processo conhece. Redigidos pelo VALOR, nao pelo formato —
# pega tambem o que nao casa com nenhum padrao acima.
_SECRET_ENV_VARS = (
    "OPENAI_API_KEY",
    "OS_SECURITY_KEY",
    "DATABASE_URL",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_APP_SECRET",
    "WHATSAPP_VERIFY_TOKEN",
    "DB_PASS",
)

# Chaves de `log.outputs` que podem ser persistidas: todas enumeraveis ou
# booleanas. Adicionar chave aqui e uma decisao de privacidade — nao um
# detalhe. `final_response`, `outbound_message` e afins ficam de fora.
_OUTCOME_ALLOWLIST = (
    "route_to",
    "final_agent",
    "evidence_status",
    "evidence_reason",
    "outbound_allowed",
    "outbound_sanitized",
    "internal_terms_leaked",
    "factual_claims_detected",
    "evidence_required",
    "sources_opened",
    "references",
    # F2.7 — telemetria do Disclosure Gate. `disclosure_status` e uma decisao
    # (ALLOW/SAFE_REFORMULATION/BLOCK) e `disclosure_reason` carrega apenas
    # contagens ("5 medidas com gramagem"). Nenhum dos dois carrega o texto
    # inspecionado — e por isso que eles podem entrar aqui e `final_response`
    # nao pode.
    "disclosure_status",
    "disclosure_reason",
    "disclosure_blocked",
    # F2.8 round 2 — observabilidade do caminho do Brain. Nomes de tool e um
    # booleano; nenhum conteudo, nenhum prompt, nenhuma query.
    "brain_tools_called",
    "context_added",
)


def _redact(value: Any, *, _segredos: tuple[str, ...] | None = None) -> Any:
    """Apaga segredo e telefone de qualquer estrutura antes de ela virar linha."""

    segredos = _segredos if _segredos is not None else _env_secrets()

    if isinstance(value, str):
        limpo = value
        for segredo in segredos:
            limpo = limpo.replace(segredo, REDACTED)
        for padrao in _SECRET_PATTERNS:
            limpo = padrao.sub(REDACTED, limpo)
        return limpo
    if isinstance(value, dict):
        return {chave: _redact(item, _segredos=segredos) for chave, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item, _segredos=segredos) for item in value]
    return value


def _env_secrets() -> tuple[str, ...]:
    """Valores de segredo presentes no ambiente agora. Nunca sao guardados."""

    valores = []
    for nome in _SECRET_ENV_VARS:
        valor = (getenv(nome) or "").strip()
        # Valor curto demais viraria redacao indiscriminada de texto normal.
        if len(valor) >= 8:
            valores.append(valor)
    return tuple(valores)


def build_table(metadata: MetaData) -> Table:
    """Define `judith_execution_logs`.

    Colunas de topo = o que se filtra. JSONB = o que se inspeciona depois.
    Essa e a linha divisoria; nao ha JSONB aqui que precise virar filtro de
    listagem sem indice.
    """

    return Table(
        TABLE_NAME,
        metadata,
        # Chave natural. E o mesmo task_id que atravessa os handoffs, entao
        # regravar a mesma execucao (retry) atualiza a linha em vez de criar
        # uma segunda — ver `save()`.
        Column("task_id", String, primary_key=True, nullable=False),
        Column("workflow", String, nullable=False),
        Column("status", String, nullable=False),
        Column("channel", String, nullable=False),
        # Ponte para o que o Agno ja guarda: `ai.agno_sessions.session_id`.
        # Sem FK de proposito — a sessao pode ser podada sem levar junto o
        # rastro de execucao, que e o registro de auditoria.
        Column("session_id", String, nullable=True),
        Column("user_ref", String, nullable=True),
        Column("started_at", DateTime(timezone=True), nullable=False),
        Column("finished_at", DateTime(timezone=True), nullable=True),
        Column("duration_ms", BigInteger, nullable=True),
        # Veredito do Evidence Gate. Coluna propria, e nao dentro do JSONB,
        # porque "quantas respostas sairam sem evidencia" e pergunta de rotina.
        Column("evidence_status", String, nullable=True),
        Column("outbound_allowed", Boolean, nullable=True),
        Column("final_agent", String, nullable=True),
        Column("escalated", Boolean, nullable=False, default=False),
        Column("agents_called", _JSON, nullable=True),
        Column("handoffs", _JSON, nullable=True),
        Column("evidence", _JSON, nullable=True),
        Column("escalations", _JSON, nullable=True),
        Column("risks", _JSON, nullable=True),
        Column("outcome", _JSON, nullable=True),
        Column("model_usage", _JSON, nullable=True),
        Column("token_usage", _JSON, nullable=True),
        Column("human_feedback", Text, nullable=True),
        Column("error", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Index(f"ix_{TABLE_NAME}_workflow", "workflow"),
        Index(f"ix_{TABLE_NAME}_status", "status"),
        Index(f"ix_{TABLE_NAME}_channel", "channel"),
        Index(f"ix_{TABLE_NAME}_session_id", "session_id"),
        Index(f"ix_{TABLE_NAME}_user_ref", "user_ref"),
        Index(f"ix_{TABLE_NAME}_started_at", "started_at"),
        Index(f"ix_{TABLE_NAME}_evidence_status", "evidence_status"),
        Index(f"ix_{TABLE_NAME}_final_agent", "final_agent"),
        Index(f"ix_{TABLE_NAME}_escalated", "escalated"),
    )


def _handoff_row(handoff: Any) -> dict[str, Any]:
    """Handoff reduzido ao que e estrutural.

    Fica de fora, deliberadamente: `objective`, `context`, `decision` e
    `output`. No ANSWER_DM o `context` traz a mensagem literal da cliente, e
    `output` traz a resposta gerada. Nenhum dos dois e necessario para medir
    processo — que e o que a F1 mede.
    """

    return {
        "from_agent": handoff.from_agent,
        "to_agent": handoff.to_agent,
        "confidence": handoff.confidence,
        "risks": list(handoff.risks),
        "references": list(handoff.references),
        "sources_opened": list(handoff.sources_opened),
        "timestamp": handoff.timestamp.isoformat(),
    }


def _row(log: ExecutionLog) -> dict[str, Any]:
    """Converte um ExecutionLog na linha que vai para o banco.

    Esta funcao E a allowlist. Se um campo nao aparece aqui, ele nao e
    persistido — nao ha caminho alternativo.
    """

    agora = datetime.now(UTC)
    outcome = {chave: log.outputs.get(chave) for chave in _OUTCOME_ALLOWLIST if chave in log.outputs}
    riscos = [risco for handoff in log.handoffs for risco in handoff.risks]

    linha = {
        "task_id": log.task_id,
        "workflow": log.workflow,
        "status": log.status,
        "channel": log.channel,
        "session_id": log.session_id,
        "user_ref": log.user_ref,
        "started_at": log.started_at,
        "finished_at": log.finished_at,
        "duration_ms": log.duration_ms,
        "evidence_status": log.outputs.get("evidence_status"),
        "outbound_allowed": log.outputs.get("outbound_allowed"),
        "final_agent": log.outputs.get("final_agent"),
        "escalated": bool(log.escalations),
        "agents_called": list(log.agents_called),
        "handoffs": [_handoff_row(handoff) for handoff in log.handoffs],
        "evidence": list(log.evidence),
        "escalations": [
            {
                "raised_by": escalation.raised_by,
                "reason": escalation.reason,
                "at_step": escalation.at_step,
                "timestamp": escalation.timestamp.isoformat(),
            }
            for escalation in log.escalations
        ],
        "risks": riscos,
        "outcome": outcome,
        "model_usage": [
            {**step.model_dump(exclude={"timestamp"}), "timestamp": step.timestamp.isoformat()}
            for step in log.model_usage
        ],
        "token_usage": log.token_totals(),
        "human_feedback": log.human_feedback,
        "error": log.error,
        "created_at": agora,
        "updated_at": agora,
    }

    # Datas sao objetos datetime e nao devem virar string na redacao.
    datas = {chave: linha.pop(chave) for chave in ("started_at", "finished_at", "created_at", "updated_at")}
    limpa = _redact(linha)
    limpa.update(datas)
    return limpa


class ExecutionRepository:
    """Leitura e escrita de `judith_execution_logs`.

    Recebe um Engine em vez de construir um: assim o teste aponta para SQLite
    em memoria e producao aponta para o Postgres do AgentOS, sem ramo de
    codigo diferente entre os dois.
    """

    def __init__(self, engine: Engine, *, schema: str | None = None) -> None:
        self.engine = engine
        self.schema = schema
        self.metadata = MetaData(schema=schema)
        self.table = build_table(self.metadata)

    # --- migration ---------------------------------------------------------

    def ensure_table(self) -> None:
        """Migration aditiva e idempotente: CREATE TABLE/INDEX IF NOT EXISTS.

        Nao altera nem apaga nada que ja exista. Rollback e um
        `DROP TABLE ai.judith_execution_logs;` — nenhuma outra tabela depende
        desta, e nao ha foreign key apontando para ela.
        """

        self.metadata.create_all(self.engine, tables=[self.table], checkfirst=True)

    # --- escrita -----------------------------------------------------------

    def save(self, log: ExecutionLog) -> None:
        """Grava (ou regrava) a execucao. Idempotente por `task_id`.

        Retry do mesmo task_id atualiza a linha existente — nunca cria uma
        segunda. `created_at` do INSERT original e preservado.
        """

        linha = _row(log)
        with self.engine.begin() as conexao:
            if conexao.dialect.name == "postgresql":
                comando = pg_insert(self.table).values(**linha)
                atualizaveis = {
                    coluna: comando.excluded[coluna] for coluna in linha if coluna not in ("task_id", "created_at")
                }
                conexao.execute(comando.on_conflict_do_update(index_elements=["task_id"], set_=atualizaveis))
                return

            # SQLite (testes) tambem tem upsert, mas a construcao vem de outro
            # modulo do SQLAlchemy.
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            comando_sqlite = sqlite_insert(self.table).values(**linha)
            atualizaveis = {
                coluna: comando_sqlite.excluded[coluna] for coluna in linha if coluna not in ("task_id", "created_at")
            }
            conexao.execute(comando_sqlite.on_conflict_do_update(index_elements=["task_id"], set_=atualizaveis))

    # --- leitura -----------------------------------------------------------

    def count(self) -> int:
        """Quantas execucoes ja foram registradas."""

        with self.engine.begin() as conexao:
            return int(conexao.execute(select(func.count()).select_from(self.table)).scalar_one())

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conexao:
            linha = conexao.execute(select(self.table).where(self.table.c.task_id == task_id)).mappings().first()
        return dict(linha) if linha else None

    def list_executions(
        self,
        *,
        workflow: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        agent_id: str | None = None,
        model_id: str | None = None,
        evidence_status: str | None = None,
        user_ref: str | None = None,
        only_escalated: bool = False,
        only_with_human_feedback: bool = False,
        only_errors: bool = False,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Listagem filtrada, mais recente primeiro.

        Cobre as perguntas que o AI Performance & Evals Agent vai fazer sem
        que ele precise conhecer SQL nem o formato dos JSONB.
        """

        consulta = select(self.table)
        if workflow:
            consulta = consulta.where(self.table.c.workflow == workflow)
        if status:
            consulta = consulta.where(self.table.c.status == status)
        if channel:
            consulta = consulta.where(self.table.c.channel == channel)
        if evidence_status:
            consulta = consulta.where(self.table.c.evidence_status == evidence_status)
        if user_ref:
            consulta = consulta.where(self.table.c.user_ref == user_ref)
        if only_escalated:
            consulta = consulta.where(self.table.c.escalated.is_(True))
        if only_with_human_feedback:
            consulta = consulta.where(self.table.c.human_feedback.isnot(None))
        if only_errors:
            consulta = consulta.where(self.table.c.status == "failed")
        if since:
            consulta = consulta.where(self.table.c.started_at >= since)
        if agent_id:
            consulta = consulta.where(self._agent_participou(agent_id))
        if model_id:
            consulta = consulta.where(self._modelo_usado(model_id))

        consulta = consulta.order_by(self.table.c.started_at.desc()).limit(limit)
        with self.engine.begin() as conexao:
            return [dict(linha) for linha in conexao.execute(consulta).mappings()]

    # --- filtros sobre JSON ------------------------------------------------
    #
    # No Postgres usam o operador de containment do JSONB (`@>`), que e
    # indexavel por GIN quando o volume pedir. Em qualquer outro dialeto caem
    # para LIKE sobre o JSON serializado: bom o bastante para a suite, nunca
    # usado em producao.

    def _agent_participou(self, agent_id: str) -> Any:
        """`agents_called` e uma lista de strings: `@> '["community-dm-agent"]'`."""

        if self.engine.dialect.name == "postgresql":
            return self.table.c.agents_called.op("@>")(literal([agent_id], JSONB))
        return cast(self.table.c.agents_called, Text).like(f'%"{agent_id}"%')

    def _modelo_usado(self, model_id: str) -> Any:
        """`model_usage` e uma lista de objetos: `@> '[{"model_id": "..."}]'`.

        Containment de lista de strings nao serviria aqui — o valor procurado
        esta dentro de um objeto, nao e um elemento da lista.
        """

        if self.engine.dialect.name == "postgresql":
            return self.table.c.model_usage.op("@>")(literal([{"model_id": model_id}], JSONB))
        return cast(self.table.c.model_usage, Text).like(f'%"model_id": "{model_id}"%')


# ---------------------------------------------------------------------------
# Ponto de entrada usado pelos workflows
# ---------------------------------------------------------------------------

_repository: ExecutionRepository | None = None


def set_execution_repository(repository: ExecutionRepository | None) -> None:
    """Troca o repositorio ativo. Usado pelos testes; producao usa o default."""

    global _repository
    _repository = repository


def get_execution_repository() -> ExecutionRepository:
    """Repositorio apoiado no mesmo Postgres do AgentOS.

    Construido na primeira chamada, nao no import: importar este modulo nao
    pode abrir conexao — a suite roda sem Postgres.
    """

    global _repository
    if _repository is None:
        from db import get_postgres_db

        db = get_postgres_db()
        _repository = ExecutionRepository(db.db_engine, schema=db.db_schema)
    return _repository


def ensure_execution_log_table(db: Any) -> None:
    """Cria a tabela se faltar. Chamado no boot, junto dos outros reparos.

    Falha aqui nao derruba o processo: o AgentOS sobe e atende WhatsApp mesmo
    sem o rastro de execucao. O erro fica visivel no log — silencio seria pior
    que a ausencia da tabela.
    """

    try:
        # F2: quem cria o schema agora e o runner de migrations, para que toda
        # mudanca tenha versao e historico. A migration 001 faz exatamente o
        # mesmo create-if-not-exists que a F1 fazia — em producao ela e no-op,
        # porque a tabela ja existe com dado.
        from db.migrations import run_migrations

        run_migrations(db.db_engine, schema=db.db_schema)

        repositorio = ExecutionRepository(db.db_engine, schema=db.db_schema)
        set_execution_repository(repositorio)
        # Contagem no boot: uma consulta barata que torna a persistencia
        # verificavel so pelo log, sem abrir endpoint nem expor conteudo.
        log_info(
            f"judith_execution_logs pronto em {db.db_schema}.{TABLE_NAME} ({repositorio.count()} execucoes registradas)"
        )
    except SQLAlchemyError as exc:
        log_error(f"nao foi possivel preparar {TABLE_NAME}: {exc}")


def persist_execution(log: ExecutionLog) -> bool:
    """Persiste a execucao. NUNCA levanta.

    Contrato deliberado: a resposta para a cliente ja saiu (ou vai sair)
    quando isto roda. Falha de logging nao pode virar falha de atendimento.
    Mas tambem nao pode ser silenciosa — por isso `log_error` e o retorno
    booleano, que os testes usam para provar que a falha foi percebida.
    """

    try:
        get_execution_repository().save(log)
        # Metadado apenas — nunca a mensagem nem a resposta.
        log_info(f"execution log gravado: {log.task_id} {log.workflow} status={log.status} canal={log.channel}")
        return True
    except Exception as exc:  # noqa: BLE001
        log_error(f"falha ao persistir execution log {log.task_id} ({log.workflow}): {type(exc).__name__}: {exc}")
        return False
