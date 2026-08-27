"""
AgentOS
-------

Ponto de entrada do AgentOS.

Rodar local:
    python -m app.main
"""

from os import getenv
from pathlib import Path
from typing import Any

from agno.os import AgentOS
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.validate_envs import validate_envs

validate_envs()

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
from agents.my_agent import my_agent  # noqa: E402
from app.interfaces import build_interfaces  # noqa: E402
from app.security import build_api_settings, install_authenticated_metadata_routes
from db import get_postgres_db, repair_agentos_db_schema  # noqa: E402
from orchestration.execution_repository import ensure_execution_log_table


def _get_cors_allow_origins() -> list[str]:
    return [origin.strip().rstrip("/") for origin in getenv("CORS_ALLOW_ORIGINS", "").split(",") if origin.strip()]


api_settings = build_api_settings()

# `docs_enabled` do Agno so tem efeito quando o AgentOS cria o proprio FastAPI
# (agno/os/app.py:527). Como passamos um `base_app` pronto, quem decide sobre
# /docs, /redoc e /openapi.json e este construtor — nao o AgentOS.
base_app = FastAPI(
    title="AgentOS",
    docs_url="/docs" if api_settings.docs_enabled else None,
    redoc_url="/redoc" if api_settings.docs_enabled else None,
    openapi_url="/openapi.json" if api_settings.docs_enabled else None,
)

cors_allow_origins = _get_cors_allow_origins()
if cors_allow_origins:
    base_app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agentos_db = get_postgres_db()
repair_agentos_db_schema(agentos_db)
# Judith Brain F1: cria `judith_execution_logs` se faltar. Aditiva e
# idempotente, no mesmo ponto onde os outros reparos de schema ja rodam.
ensure_execution_log_table(agentos_db)

agent_os = AgentOS(
    name="AgentOS",
    tracing=True,
    scheduler=True,
    base_app=base_app,
    db=agentos_db,
    agents=[
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
    ],
    interfaces=build_interfaces(my_agent),
    config=str(Path(__file__).parent / "config.yaml"),
    # Autenticacao Bearer nativa do Agno nos routers administrativos. Ver
    # app/security.py para o recorte do que continua publico e por que.
    settings=api_settings,
    # F0.5: quando uma rota nossa colide com uma do AgentOS, a nossa vence
    # (agno/os/app.py:951). E assim que fechamos `/` e `/info`, que o Agno
    # publica sem autenticacao por construcao.
    on_route_conflict="preserve_base_app",
)

# F0.5: `/` e `/info` sairam da superficie anonima. Precisa ser antes do
# `get_app()`; ver a docstring da funcao para o porque.
install_authenticated_metadata_routes(base_app, agent_os, api_settings)

app = agent_os.get_app()


@base_app.get("/health", tags=["Ops"])
def healthcheck() -> dict[str, Any]:
    """Liveness endpoint para o healthcheck da Railway."""

    return {
        "status": "ok",
        "service": "agentos",
        "runtime_env": getenv("RUNTIME_ENV", "prd"),
    }


if __name__ == "__main__":
    agent_os.serve(
        app="main:app",
        reload=getenv("RUNTIME_ENV", "prd") == "dev",
    )
