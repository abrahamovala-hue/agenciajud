"""Runner das migrations. Ver `db/migrations/__init__.py` para o porque."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from agno.utils.log import log_error, log_info, log_warning
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, select
from sqlalchemy.engine import Connection, Engine

HISTORY_TABLE = "judith_schema_migrations"


@dataclass(frozen=True)
class Migration:
    """Uma mudanca de schema.

    `up` recebe (Connection, schema). A Connection ja esta em transacao — se
    levantar, nada e gravado e a versao nao entra no historico. O schema vem
    explicito porque em producao as tabelas vivem em `ai` e nos testes no
    default do SQLite; deduzir isso dentro de cada migration daria uma
    deducao diferente por migration.

    `down` e opcional. Migration puramente aditiva costuma ter um; migration
    que transforma dado normalmente nao tem, e e melhor declarar isso do que
    escrever um `down` que perde informacao em silencio.
    """

    version: int
    name: str
    up: Callable[[Connection, str | None], None]
    down: Callable[[Connection, str | None], None] | None = None
    description: str = ""

    @property
    def reversible(self) -> bool:
        return self.down is not None

    def checksum(self) -> str:
        """Hash do codigo-fonte do `up`.

        Serve para detectar que alguem editou uma migration ja aplicada — o
        banco entao nao corresponde mais ao que o codigo diz que ele e.
        """

        try:
            fonte = inspect.getsource(self.up)
        except (OSError, TypeError):
            fonte = self.name
        return hashlib.sha256(fonte.encode("utf-8")).hexdigest()[:16]


def _history_table(metadata: MetaData) -> Table:
    return Table(
        HISTORY_TABLE,
        metadata,
        Column("version", Integer, primary_key=True, nullable=False),
        Column("name", String, nullable=False),
        Column("checksum", String, nullable=False),
        Column("applied_at", DateTime(timezone=True), nullable=False),
    )


def _ensure_history(engine: Engine, schema: str | None) -> Table:
    metadata = MetaData(schema=schema)
    tabela = _history_table(metadata)
    metadata.create_all(engine, tables=[tabela], checkfirst=True)
    return tabela


def applied_versions(engine: Engine, schema: str | None = None) -> dict[int, str]:
    """Versao -> checksum do que ja foi aplicado."""

    tabela = _ensure_history(engine, schema)
    with engine.begin() as conexao:
        linhas = conexao.execute(select(tabela.c.version, tabela.c.checksum)).all()
    return {int(versao): str(checksum) for versao, checksum in linhas}


def pending_migrations(engine: Engine, schema: str | None = None) -> list[Migration]:
    aplicadas = applied_versions(engine, schema)
    return [m for m in MIGRATIONS if m.version not in aplicadas]


def run_migrations(engine: Engine, schema: str | None = None) -> list[int]:
    """Aplica o que falta, em ordem. Devolve as versoes aplicadas agora.

    Cada migration roda na propria transacao: uma falha nao deixa metade do
    schema aplicada nem grava a versao no historico.
    """

    tabela = _ensure_history(engine, schema)
    aplicadas = applied_versions(engine, schema)

    for migration in MIGRATIONS:
        anterior = aplicadas.get(migration.version)
        if anterior is not None and anterior != migration.checksum():
            # Nao da para "consertar" isto automaticamente: o banco pode ja
            # estar no formato novo ou no antigo. Denunciar alto e a unica
            # resposta honesta.
            log_error(
                f"migration {migration.version:03d} ({migration.name}) foi editada depois de aplicada "
                f"(checksum {anterior} -> {migration.checksum()}). O schema do banco pode nao corresponder ao codigo."
            )

    novas: list[int] = []
    for migration in MIGRATIONS:
        if migration.version in aplicadas:
            continue
        with engine.begin() as conexao:
            migration.up(conexao, schema)
            conexao.execute(
                tabela.insert().values(
                    version=migration.version,
                    name=migration.name,
                    checksum=migration.checksum(),
                    applied_at=datetime.now(UTC),
                )
            )
        novas.append(migration.version)
        log_info(f"migration {migration.version:03d} aplicada: {migration.name}")

    return novas


def rollback(engine: Engine, version: int, schema: str | None = None) -> None:
    """Desfaz UMA migration. Manual e deliberado — nunca chamado no boot.

    Migration sem `down` levanta em vez de fingir que reverteu.
    """

    migration = next((m for m in MIGRATIONS if m.version == version), None)
    if migration is None:
        raise ValueError(f"migration {version} nao existe")
    if migration.down is None:
        raise ValueError(
            f"migration {version:03d} ({migration.name}) nao e reversivel automaticamente. "
            "Reverter exige decisao manual sobre o dado."
        )

    tabela = _ensure_history(engine, schema)
    with engine.begin() as conexao:
        migration.down(conexao, schema)
        conexao.execute(tabela.delete().where(tabela.c.version == version))
    log_warning(f"migration {version:03d} revertida: {migration.name}")


# Registro. Importado no fim para evitar ciclo: os modulos de migration
# importam `Migration` daqui.
from db.migrations import (
    m001_execution_logs,
    m002_knowledge_foundation,
    m003_system_layer,
    m004_primary_sources,
    m005_vector_index,
)

MIGRATIONS: tuple[Migration, ...] = (
    m001_execution_logs.MIGRATION,
    m002_knowledge_foundation.MIGRATION,
    m003_system_layer.MIGRATION,
    m004_primary_sources.MIGRATION,
    m005_vector_index.MIGRATION,
)

_versoes = [m.version for m in MIGRATIONS]
assert _versoes == sorted(set(_versoes)), f"versoes de migration duplicadas ou fora de ordem: {_versoes}"
