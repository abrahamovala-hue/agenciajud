"""
003 - camada L0 SYSTEM (F2.5).

DUAS COISAS, as duas aditivas:

1. Coluna `source_ref` em `judith_knowledge_documents`. Ate agora o caminho do
   arquivo so existia na FONTE (`docs/`), nao no documento - o que impedia
   auditar de qual arquivo cada linha veio.

2. Reclassificacao de 55 documentos de L2 para L0 (SYSTEM).

POR QUE A LISTA ESTA CHUMBADA AQUI
----------------------------------

Poderia derivar da taxonomia em tempo de execucao. Nao deriva de proposito:
uma migration precisa dizer o que ELA fez, no dia em que rodou. Se a taxonomia
mudar amanha, o registro do que aconteceu hoje continua correto.

O `down()` devolve as 55 para L2 - o estado exato da F2 - e remove a coluna.
Nenhum conteudo e tocado: `layer` e classificacao, nao dado de origem.

O QUE NAO VIROU L0
------------------

Preco, produto, politica e tecnica da Judith. `brand/`, `sources/` e
`BUSINESS_RULES` continuam L3; `knowledge/craft/` continua L2.
"""

from __future__ import annotations

from sqlalchemy import MetaData, inspect, text, update
from sqlalchemy.engine import Connection

from brain.schema import build_documents_table
from db.migrations.runner import Migration

#: As 55 chaves reclassificadas em 2026-08-27. Registro historico.
RECLASSIFIED_TO_L0: tuple[str, ...] = (
    "AGENT_ROSTER",
    "AUTONOMY_MODEL",
    "COLLABORATION_PROTOCOL_V1",
    "COLLABORATION_PROTOCOL_V2",
    "DECISION_CARD",
    "EVALS_README",
    "FICHA_01_CMO",
    "FICHA_02_BRAND_ARCHITECT",
    "FICHA_03_MARKETING_DIRECTOR",
    "FICHA_04_SOCIAL_MEDIA_MANAGER",
    "FICHA_05_MARKET_TREND_INTELLIGENCE",
    "FICHA_06_HOOK_FINDER",
    "FICHA_07_SCRIPT_WRITER",
    "FICHA_08_CAPTION_WRITER",
    "FICHA_09_VISUAL_CREATIVE",
    "FICHA_10_VIDEO_EDITOR",
    "FICHA_11_OFFER_FUNNEL_STRATEGIST",
    "FICHA_12_SALES_CONVERSION_AGENT",
    "FICHA_13_CRM_LIFECYCLE_AGENT",
    "FICHA_14_COMMUNITY_DM_AGENT",
    "FICHA_15_CUSTOMER_SUPPORT_AGENT",
    "FICHA_16_ANALYTICS_BI_AGENT",
    "FICHA_17_CUSTOMER_INSIGHTS_AGENT",
    "FICHA_18_KNOWLEDGE_MANAGER",
    "FICHA_19_AI_PERFORMANCE_EVALS_AGENT",
    "FICHA_20_BRAND_REVIEWER",
    "FICHA_21_QUALITY_CONTROL_AGENT",
    "HANDOFF_CONTRACT",
    "HANDOFF_EXAMPLES",
    "KNOWLEDGE_REFRESH_POLICY",
    "LEARNING_EVALS_MODEL",
    "MEMORY_MODEL",
    "ORCHESTRATION_V2",
    "PLAYBOOK_BRAND_REVIEW",
    "PLAYBOOK_CAPTION",
    "PLAYBOOK_HOOK",
    "PLAYBOOK_MARKETING_DIRECTOR",
    "PLAYBOOK_METRICS",
    "PLAYBOOK_PRODUCT_MARKETING",
    "PLAYBOOK_SCRIPT",
    "PLAYBOOK_SOCIAL",
    "PLAYBOOK_TREND",
    "PLAYBOOK_VIDEO",
    "PLAYBOOK_VIRAL",
    "PLAYBOOK_VISUAL",
    "PRD",
    "STATUS",
    "STATUS_V2",
    "VIDEO_EDIT_SPEC",
    "VIDEO_ENGINE_PLAN",
    "WORKFLOWS_V1",
    "WORKFLOWS_V2_INDEX",
    "WORKFLOW_CREATE_CAMPAIGN",
    "WORKFLOW_CREATE_REEL",
    "WORKFLOW_REPURPOSE",
)


def _tem_coluna(conexao: Connection, tabela: str, coluna: str, schema: str | None) -> bool:
    inspetor = inspect(conexao)
    return coluna in {c["name"] for c in inspetor.get_columns(tabela, schema=schema)}


def _qualificado(tabela: str, schema: str | None) -> str:
    return f'"{schema}"."{tabela}"' if schema else f'"{tabela}"'


def up(conexao: Connection, schema: str | None) -> None:
    metadata = MetaData(schema=schema)
    documentos = build_documents_table(metadata)

    # ADD COLUMN idempotente: em banco novo a coluna ja veio da 002, porque
    # `brain/schema.py` a declara. Em banco que rodou a 002 antes desta
    # mudanca, ela falta.
    if not _tem_coluna(conexao, documentos.name, "source_ref", schema):
        conexao.execute(text(f"ALTER TABLE {_qualificado(documentos.name, schema)} ADD COLUMN source_ref VARCHAR"))

    conexao.execute(update(documentos).where(documentos.c.external_key.in_(RECLASSIFIED_TO_L0)).values(layer="L0"))


def down(conexao: Connection, schema: str | None) -> None:
    metadata = MetaData(schema=schema)
    documentos = build_documents_table(metadata)

    # Volta ao estado da F2: as 55 eram L2.
    conexao.execute(update(documentos).where(documentos.c.external_key.in_(RECLASSIFIED_TO_L0)).values(layer="L2"))
    if _tem_coluna(conexao, documentos.name, "source_ref", schema):
        conexao.execute(text(f"ALTER TABLE {_qualificado(documentos.name, schema)} DROP COLUMN source_ref"))


MIGRATION = Migration(
    version=3,
    name="system_layer_l0",
    up=up,
    down=down,
    description="Adiciona source_ref e reclassifica 55 documentos de sistema de L2 para L0.",
)
