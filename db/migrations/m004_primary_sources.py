"""
004 - fontes primarias e conteudo pago (F2.7).

Puramente aditiva. Nenhuma linha existente e alterada, nenhum conteudo e
tocado, nenhum documento muda de status.

O QUE ENTRA
-----------

1. Tabela `judith_knowledge_artifacts`: o PDF original, byte a byte. Existe
   para que a fonte primaria seja auditavel SEM colocar propriedade
   intelectual paga no Git.

2. Em `judith_knowledge_documents`: `source_authority`, `provided_by`,
   `entitlement_scope`, `artifact_id`.

3. Em `judith_knowledge_chunks`: `content_kind`, `page`, `recipe_id`,
   `heading_path`, `entitlement_scope`.

POR QUE ADD COLUMN IDEMPOTENTE
------------------------------

Mesmo motivo da 003: em banco novo as colunas ja vem da criacao das tabelas,
porque `brain/schema.py` as declara. Em banco que rodou a 002 antes desta
mudanca, elas faltam. A migration precisa funcionar nos dois.

O `down()` remove as colunas e a tabela. E reversivel de verdade porque nada
aqui transforma dado existente — o unico risco de perder informacao e perder
os artifacts, e isso e exatamente o que reverter esta migration significa.
"""

from __future__ import annotations

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Connection

from brain.schema import build_artifacts_table, build_chunks_table, build_documents_table
from db.migrations.runner import Migration

#: coluna -> tipo SQL. Tipos escolhidos para funcionar em Postgres e SQLite.
_DOCUMENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_authority", "VARCHAR"),
    ("provided_by", "VARCHAR"),
    ("entitlement_scope", "VARCHAR"),
    ("artifact_id", "VARCHAR"),
)

_CHUNK_COLUMNS: tuple[tuple[str, str], ...] = (
    ("content_kind", "VARCHAR"),
    ("page", "INTEGER"),
    ("recipe_id", "VARCHAR"),
    ("heading_path", "VARCHAR"),
    ("entitlement_scope", "VARCHAR"),
)


def _tem_coluna(conexao: Connection, tabela: str, coluna: str, schema: str | None) -> bool:
    inspetor = inspect(conexao)
    return coluna in {c["name"] for c in inspetor.get_columns(tabela, schema=schema)}


def _tem_tabela(conexao: Connection, tabela: str, schema: str | None) -> bool:
    return inspect(conexao).has_table(tabela, schema=schema)


def _qualificado(tabela: str, schema: str | None) -> str:
    return f'"{schema}"."{tabela}"' if schema else f'"{tabela}"'


def up(conexao: Connection, schema: str | None) -> None:
    metadata = MetaData(schema=schema)
    documentos = build_documents_table(metadata)
    chunks = build_chunks_table(metadata)
    artifacts = build_artifacts_table(metadata)

    for tabela, colunas in ((documentos, _DOCUMENT_COLUMNS), (chunks, _CHUNK_COLUMNS)):
        for coluna, tipo in colunas:
            if not _tem_coluna(conexao, tabela.name, coluna, schema):
                conexao.execute(text(f"ALTER TABLE {_qualificado(tabela.name, schema)} ADD COLUMN {coluna} {tipo}"))

    if not _tem_tabela(conexao, artifacts.name, schema):
        artifacts.create(conexao)


def down(conexao: Connection, schema: str | None) -> None:
    metadata = MetaData(schema=schema)
    documentos = build_documents_table(metadata)
    chunks = build_chunks_table(metadata)
    artifacts = build_artifacts_table(metadata)

    if _tem_tabela(conexao, artifacts.name, schema):
        artifacts.drop(conexao)

    for tabela, colunas in ((documentos, _DOCUMENT_COLUMNS), (chunks, _CHUNK_COLUMNS)):
        for coluna, _ in colunas:
            if _tem_coluna(conexao, tabela.name, coluna, schema):
                conexao.execute(text(f"ALTER TABLE {_qualificado(tabela.name, schema)} DROP COLUMN {coluna}"))


MIGRATION = Migration(
    version=4,
    name="primary_sources_and_paid_content",
    up=up,
    down=down,
    description=(
        "Adiciona judith_knowledge_artifacts (PDF original imutavel) e as colunas de "
        "fonte primaria, entitlement e classificacao funcional de chunk."
    ),
)
