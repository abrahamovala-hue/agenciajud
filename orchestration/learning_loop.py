"""
Learning loop — estrutura preparada, NAO automatizada.

Implementa o inicio do ciclo documentado em
docs/JUDITH-AI-TEAM-V2/models/LEARNING_EVALS_MODEL.md:

    interaction -> execution log -> outcome -> human feedback -> eval
    -> improvement proposal   [-> regression eval -> HUMAN APPROVAL -> version bump]

O que existe aqui:
- `attach_human_feedback()`: registra o feedback/correcao da Judith sobre uma
  execucao ja concluida.
- `collect_for_evaluation()`: junta os ExecutionLogs num formato que o
  AI Performance & Evals Agent consegue analisar.
- `ImprovementProposal`: o formato da PROPOSTA - sempre com
  `requires_human_approval=True` e `applied=False`, imutaveis por design.

O que NAO existe aqui, deliberadamente (regra dura,
`BUSINESS_RULES.md` regra 19 + item 12 da especificacao desta etapa):
- Nenhuma funcao que edite prompt, instructions, codigo, tools, guardrails
  ou knowledge de qualquer agente.
- Nenhuma funcao de "promover versao". Uma proposta so vira mudanca real
  quando um humano editar o arquivo do agente manualmente.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from orchestration.execution_log import ExecutionLog

ProposalKind = Literal["instructions", "gold_example", "routing_rule", "workflow_spec"]


class ImprovementProposal(BaseModel):
    """Proposta de melhoria gerada pelo AI Performance & Evals Agent.

    NUNCA e aplicada automaticamente. `applied` existe apenas para registro
    posterior, e so um humano deveria marca-lo - nao ha nenhum codigo neste
    repositorio que o faca.
    """

    target_agent_id: str
    kind: ProposalKind
    evidence: list[str] = Field(description="Casos concretos que motivaram a proposta (task_ids, padroes observados).")
    occurrences: int = Field(description="Quantas vezes o padrao foi observado. Minimo recomendado: 3.")
    current_behavior: str
    proposed_change: str
    expected_impact: str
    regression_risk: str

    requires_human_approval: Literal[True] = True
    """Sempre True. Nao ha caminho de auto-aprovacao - por design."""

    applied: Literal[False] = False
    """Sempre False quando a proposta e criada. Aplicar exige edicao manual
    do arquivo do agente por um humano."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def attach_human_feedback(log: ExecutionLog, feedback: str) -> ExecutionLog:
    """Registra o feedback/correcao da Judith sobre uma execucao concluida."""

    log.human_feedback = feedback
    return log


def collect_for_evaluation(logs: list[ExecutionLog]) -> dict:
    """Agrega ExecutionLogs num resumo que o AI Performance & Evals Agent
    consegue analisar (contagem por agente, escalacoes, feedback humano).

    Nao decide nada nem propoe nada - so organiza o material bruto.
    """

    per_agent: dict[str, dict] = {}
    for log in logs:
        for handoff in log.handoffs:
            entry = per_agent.setdefault(
                handoff.from_agent,
                {"calls": 0, "low_confidence": 0, "risks_raised": 0, "no_evidence": 0},
            )
            entry["calls"] += 1
            if handoff.confidence == "baixo":
                entry["low_confidence"] += 1
            if handoff.risks:
                entry["risks_raised"] += 1
            if not handoff.references:
                entry["no_evidence"] += 1

    return {
        "total_executions": len(logs),
        "per_agent": per_agent,
        "escalations": [
            {"task_id": log.task_id, "workflow": log.workflow, "raised_by": e.raised_by, "reason": e.reason}
            for log in logs
            for e in log.escalations
        ],
        "human_feedback": [
            {"task_id": log.task_id, "workflow": log.workflow, "feedback": log.human_feedback}
            for log in logs
            if log.human_feedback
        ],
        "outcomes": [{"task_id": log.task_id, "workflow": log.workflow, "status": log.status} for log in logs],
    }
