"""
002 — fundacao de Knowledge do Judith Brain (F2).

Cria as cinco tabelas de `brain/schema.py`. Puramente aditiva: nenhuma tabela
existente e tocada, nenhuma coluna alterada, nenhum dado migrado.

TEM `down`, e o `down` E seguro aqui — ao contrario da 001. A diferenca:
estas tabelas nascem vazias nesta migration e todo o conteudo delas e
DERIVADO de `docs/`, que continua sendo a fonte da verdade durante toda a F2.
Reverter reconstroi identico. No dia em que a Knowledge receber material que
so existe no banco (upload da Judith), este `down` precisa ser removido.

NAO cria tabela de embedding. Isso e F3.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.engine import Connection

from brain.schema import build_all
from db.migrations.runner import Migration


def up(conexao: Connection, schema: str | None) -> None:
    metadata = MetaData(schema=schema)
    tabelas = build_all(metadata)
    metadata.create_all(conexao, tables=tabelas, checkfirst=True)


def down(conexao: Connection, schema: str | None) -> None:
    metadata = MetaData(schema=schema)
    tabelas = build_all(metadata)
    # Ordem inversa: chunks antes de versions antes de documents.
    metadata.drop_all(conexao, tables=list(reversed(tabelas)), checkfirst=True)


MIGRATION = Migration(
    version=2,
    name="knowledge_foundation",
    up=up,
    down=down,
    description="Cria sources, documents, versions, chunks e conflicts do Judith Brain. Sem embeddings.",
)
