"""
AgentHandoff — contrato executavel de colaboracao entre agentes.

Implementa em codigo o que antes so existia como texto em
docs/JUDITH-AI-TEAM-V2/protocol/AGENT_HANDOFF_CONTRACT.md.

Dois modelos:

- AgentStepDecision: o subconjunto de campos que o PROPRIO AGENTE (LLM)
  preenche via `agent.run(message, output_schema=AgentStepDecision)`. Nao
  exige nenhuma mudanca na definicao dos 20 Agents ja implementados -
  `output_schema` e passado por chamada, nao na construcao do Agent (ver
  auditoria: `Agent.run()` aceita `output_schema` como parametro do run,
  confirmado no codigo-fonte instalado do Agno 2.6.4).

- AgentHandoff: o envelope completo. Os campos de "envelope"
  (from_agent/to_agent/workflow/task_id/timestamp/objective/context) sao
  preenchidos pelo orquestrador (codigo determinístico, nao pelo LLM) -
  ele sabe essa informacao porque e quem estrutura o Workflow. Os campos de
  "decisao" vem de um AgentStepDecision real, nunca de texto livre
  parseado por heuristica.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["alto", "medio", "baixo"]


class AgentStepDecision(BaseModel):
    """Subconjunto do AgentHandoff que o LLM preenche via output_schema."""

    decision: str = Field(description="A decisao/output principal desta etapa, resumido em 1-2 frases.")
    output: str = Field(description="O conteudo real produzido nesta etapa (o trabalho em si).")
    confidence: Confidence = Field(description="Confianca do agente na propria decisao.")
    risks: list[str] = Field(default_factory=list, description="Riscos ou duvidas identificados. Vazio se nenhum.")
    references: list[str] = Field(
        default_factory=list,
        description="Documentos/dados consultados para esta decisao. Vazio se nao consultou nenhum.",
    )
    recommended_next: str = Field(description="Para qual agente isso deveria ir a seguir, e por que.")


class RoutingDecision(AgentStepDecision):
    """AgentStepDecision + a quem rotear. Usado no classificador do ANSWER_DM."""

    route_to: Literal[
        "community-dm-agent",
        "customer-support-agent",
        "sales-conversion-agent",
        "crm-lifecycle-agent",
        "human-escalation",
    ]


class ReviewDecision(AgentStepDecision):
    """AgentStepDecision + veredito explicito (bool). Usado por qualquer
    etapa de gate/aprovacao (CMO aprovando objetivo, Brand Reviewer
    validando conteudo).

    O campo `approved` existe para o Quality Control determinístico poder
    checar aprovação sem depender de parsear texto livre (ex.: procurar a
    palavra "aprovado" dentro de `decision`) - Regra de Ouro do protocolo
    (`AGENT_COLLABORATION_PROTOCOL_V2.md`) fica verificável em código.
    """

    approved: bool
    needs_evidence: bool = Field(
        default=False,
        description=(
            "True quando o agente NAO consegue decidir por falta de evidencia documental. "
            "Nesse caso `approved` deve ser False e `risks` deve dizer que evidencia falta. "
            "Nao e rejeicao: e ausencia de base para decidir."
        ),
    )


class WeeklyReportDecision(AgentStepDecision):
    """AgentStepDecision + a estrutura do relatorio executivo semanal (CMO)."""

    kpis: list[str] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    recommended_plan: list[str] = Field(default_factory=list)


class AgentHandoff(BaseModel):
    """Envelope completo de uma entrega entre agentes (ou para o Quality Control/Judith)."""

    from_agent: str
    to_agent: str
    workflow: str
    task_id: str
    objective: str
    context: str
    evidence: list[str] = Field(default_factory=list)
    decision: str
    output: str
    confidence: Confidence
    risks: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    sources_opened: list[str] = Field(
        default_factory=list,
        description=(
            "Fontes que o agente REALMENTE abriu nesta execucao, extraidas das tool calls "
            "do runtime — nao do texto do LLM. `references` e o que o agente DIZ ter "
            "consultado; `sources_opened` e o que ele de fato consultou. Listar o catalogo "
            "(`listar_fontes_*`) nao entra aqui, de proposito: listar nao e consultar."
        ),
    )
    recommended_next: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_step_decision(
        cls,
        *,
        from_agent: str,
        to_agent: str,
        workflow: str,
        task_id: str,
        objective: str,
        context: str,
        step_decision: AgentStepDecision,
        sources_opened: list[str] | None = None,
    ) -> AgentHandoff:
        """Combina o envelope (conhecido pelo orquestrador) com a decisao real do agente."""

        return cls(
            sources_opened=sources_opened or [],
            from_agent=from_agent,
            to_agent=to_agent,
            workflow=workflow,
            task_id=task_id,
            objective=objective,
            context=context,
            evidence=step_decision.references,
            decision=step_decision.decision,
            output=step_decision.output,
            confidence=step_decision.confidence,
            risks=step_decision.risks,
            references=step_decision.references,
            recommended_next=step_decision.recommended_next,
        )
