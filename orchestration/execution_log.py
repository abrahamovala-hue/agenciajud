"""
ExecutionLog — rastro completo de uma execucao de Workflow.

Ainda NAO persiste em banco (isso fica para quando o AI Performance & Evals
Agent precisar consumir isso de verdade - ver
docs/JUDITH-AI-TEAM-V2/models/LEARNING_EVALS_MODEL.md, passo 2). Por agora,
e um objeto em memoria construido durante a execucao e retornado/serializado
(`.model_dump()` / `.model_dump_json()`) ao final - dados suficientes para
mais tarde virar linha de tabela sem redesenhar o formato.
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


class ExecutionLog(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    agents_called: list[str] = Field(default_factory=list)
    handoffs: list[AgentHandoff] = Field(default_factory=list)
    inputs: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    escalations: list[Escalation] = Field(default_factory=list)
    human_feedback: str | None = None
    result: str | None = None
    status: Status = "running"

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

    def finish(self, *, status: Status, result: str | None = None) -> None:
        self.status = status
        self.result = result
        self.finished_at = datetime.now(UTC)
