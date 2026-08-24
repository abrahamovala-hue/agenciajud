"""
Agent Registry — resolve agent_id -> Agent.

Deliberadamente simples: um dict. Nao e um service locator (sem DI, sem
factories, sem lazy loading magico) - so precisamos localizar os 20 Agents
ja instanciados por id, de um lugar central, em vez de cada Workflow
importar cada agente manualmente.
"""

from __future__ import annotations

from agno.agent import Agent

from agents.judith_team import (
    ai_performance_evals_agent,
    analytics_bi_agent,
    brand_architect,
    brand_reviewer,
    caption_writer,
    cmo,
    community_dm_agent,
    crm_lifecycle_agent,
    customer_insights_agent,
    customer_support_agent,
    hook_finder,
    knowledge_manager,
    market_trend_intelligence,
    marketing_director,
    offer_funnel_strategist,
    sales_conversion_agent,
    script_writer,
    social_media_manager,
    video_editor,
    visual_creative,
)
from agents.my_agent import my_agent

_ALL_AGENTS: list[Agent] = [
    my_agent,
    cmo,
    brand_architect,
    marketing_director,
    social_media_manager,
    market_trend_intelligence,
    hook_finder,
    script_writer,
    caption_writer,
    visual_creative,
    video_editor,
    offer_funnel_strategist,
    sales_conversion_agent,
    crm_lifecycle_agent,
    community_dm_agent,
    customer_support_agent,
    analytics_bi_agent,
    customer_insights_agent,
    knowledge_manager,
    ai_performance_evals_agent,
    brand_reviewer,
]

# Quality Control nao esta aqui de proposito: e validacao deterministica,
# nao um Agent do Agno (ver orchestration/quality_control.py e
# docs/JUDITH-AI-TEAM-V2/agents/21-quality-control-agent.md).

# `Agent.id` e Optional[str] na tipagem do Agno, mas todo agente deste
# projeto define um id explicitamente - o assert abaixo garante isso em
# tempo de import, em vez de falhar silenciosamente depois.
for _agent in _ALL_AGENTS:
    assert _agent.id, f"agente sem id definido: {_agent.name}"

AGENT_REGISTRY: dict[str, Agent] = {str(agent.id): agent for agent in _ALL_AGENTS}

assert len(AGENT_REGISTRY) == 21, f"esperava 21 ids unicos (jud + 20), achou {len(AGENT_REGISTRY)}"


class AgentNotFoundError(KeyError):
    """agent_id nao existe no registry."""


def get_agent(agent_id: str) -> Agent:
    """Resolve agent_id -> Agent. Lanca AgentNotFoundError com a lista de ids validos."""

    try:
        return AGENT_REGISTRY[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(AGENT_REGISTRY))
        raise AgentNotFoundError(f'agent_id "{agent_id}" nao existe no registry. IDs validos: {known}') from exc
