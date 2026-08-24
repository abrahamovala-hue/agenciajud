"""Judith AI Business Team — V2 specialist agents.

Cada agente aqui corresponde a uma ficha em
`docs/JUDITH-AI-TEAM-V2/agents/`. Este pacote implementa 20 dos 21 papéis do
roster V2 como `Agent` do Agno — o único que ficou de fora é o Quality
Control Agent, classificado como lógica de checklist determinística, não um
Agent de LLM (ver a nota de implementação na própria ficha dele e
`docs/JUDITH-AI-TEAM-V2/STATUS_V2.md`).
"""

from agents.judith_team.ai_performance_evals_agent import ai_performance_evals_agent
from agents.judith_team.analytics_bi_agent import analytics_bi_agent
from agents.judith_team.brand_architect import brand_architect
from agents.judith_team.brand_reviewer import brand_reviewer
from agents.judith_team.caption_writer import caption_writer
from agents.judith_team.cmo import cmo
from agents.judith_team.community_dm_agent import community_dm_agent
from agents.judith_team.crm_lifecycle_agent import crm_lifecycle_agent
from agents.judith_team.customer_insights_agent import customer_insights_agent
from agents.judith_team.customer_support_agent import customer_support_agent
from agents.judith_team.hook_finder import hook_finder
from agents.judith_team.knowledge_manager import knowledge_manager
from agents.judith_team.market_trend_intelligence import market_trend_intelligence
from agents.judith_team.marketing_director import marketing_director
from agents.judith_team.offer_funnel_strategist import offer_funnel_strategist
from agents.judith_team.sales_conversion_agent import sales_conversion_agent
from agents.judith_team.script_writer import script_writer
from agents.judith_team.social_media_manager import social_media_manager
from agents.judith_team.video_editor import video_editor
from agents.judith_team.visual_creative import visual_creative

__all__ = [
    "ai_performance_evals_agent",
    "analytics_bi_agent",
    "brand_architect",
    "brand_reviewer",
    "caption_writer",
    "cmo",
    "community_dm_agent",
    "crm_lifecycle_agent",
    "customer_insights_agent",
    "customer_support_agent",
    "hook_finder",
    "knowledge_manager",
    "market_trend_intelligence",
    "marketing_director",
    "offer_funnel_strategist",
    "sales_conversion_agent",
    "script_writer",
    "social_media_manager",
    "video_editor",
    "visual_creative",
]
