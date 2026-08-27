"""
ExecutionLog — rastro completo de uma execucao de Workflow.

Construido em memoria durante a execucao e PERSISTIDO ao final pela
`orchestration/execution_repository.py` (Judith Brain F1). O objeto continua
sendo a fonte da verdade em memoria; quem sabe SQL e so o repositorio.

Nem tudo que existe aqui vai para o banco. `inputs`, `outputs` e `result`
carregam texto de conversa da cliente e ficam so em memoria — ver a secao de
PII em `execution_repository.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestration.handoff import AgentHandoff

Status = Literal["running", "completed", "rejected", "pending_human_approval", "failed"]


class Escalation(BaseModel):
    raised_by: str
    reason: str
    at_step: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StepUsage(BaseModel):
    """Custo e latencia de UMA chamada de agente.

    Preenchido por `orchestration/step_helpers.py` a partir do `RunOutput` do
    Agno — runtime, nao texto do LLM. Todo campo numerico e opcional: modelo
    que nao devolve metrica nao pode derrubar a execucao.

    Existe para a comparacao de tiers que vem depois (hoje os 21 agentes
    rodam o mesmo modelo). Sem isto, so restaria o agregado DIARIO do
    `agno_metrics`, que nao responde "quanto custou ESTA execucao".
    """

    agent_id: str
    to_agent: str
    model_id: str | None = None
    model_provider: str | None = None
    reasoning_effort: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    total_tokens: int | None = None
    tool_calls: int = 0
    duration_ms: int | None = None
    error: str | None = None
    """Preenchido quando a chamada falhou. A execucao segue auditavel mesmo
    quando o agente estourou no meio."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionLog(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow: str
    channel: str = "internal"
    """Por onde a execucao entrou: "whatsapp" quando veio do canal real,
    "internal" para execucao local, eval ou teste. Explicito em vez de
    deduzido do prefixo do session_id — prefixo e convencao, nao contrato."""

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    session_id: str | None = None
    user_ref: str | None = None
    """Identificador ja anonimizado da pessoa (`wa_<hash>`), montado em
    app/whatsapp/channel.py. Telefone bruto nunca chega ate aqui."""

    agents_called: list[str] = Field(default_factory=list)
    handoffs: list[AgentHandoff] = Field(default_factory=list)
    inputs: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    escalations: list[Escalation] = Field(default_factory=list)
    model_usage: list[StepUsage] = Field(default_factory=list)
    human_feedback: str | None = None
    result: str | None = None
    error: str | None = None
    status: Status = "running"

    @property
    def duration_ms(self) -> int | None:
        """Duracao da execucao inteira. None enquanto nao terminou."""

        if self.finished_at is None:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)

    def token_totals(self) -> dict[str, int]:
        """Soma os tokens de todos os steps que reportaram metrica.

        Step sem metrica simplesmente nao entra na soma — a ausencia nao
        vira zero, porque zero e uma afirmacao e ausencia nao e.
        """

        campos = ("input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens", "total_tokens")
        totais: dict[str, int] = {}
        for step in self.model_usage:
            for campo in campos:
                valor = getattr(step, campo)
                if valor is not None:
                    totais[campo] = totais.get(campo, 0) + valor
        if self.model_usage:
            totais["steps"] = len(self.model_usage)
            totais["tool_calls"] = sum(step.tool_calls for step in self.model_usage)
        return totais

    def record_usage(self, usage: StepUsage) -> None:
        self.model_usage.append(usage)

    def record(self, handoff: AgentHandoff) -> None:
        """Registra um handoff e atualiza os campos derivados (agents_called, evidence)."""

        self.handoffs.append(handoff)
        if handoff.from_agent not in self.agents_called:
            self.agents_called.append(handoff.from_agent)
        for ref in handoff.references:
            if ref not in self.evidence:
                self.evidence.append(ref)

    def escalate(self, *, raised_by: str, reason: str, at_step: str) -> None:
        self.escalations.append(Escalation(raised_by=raised_by, reason=reason, at_step=at_step))

    def finish(self, *, status: Status, result: str | None = None, error: str | None = None) -> None:
        self.status = status
        self.result = result
        if error is not None:
            self.error = error
        self.finished_at = datetime.now(UTC)
