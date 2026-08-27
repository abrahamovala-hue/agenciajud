"""
001 — adota `judith_execution_logs` (F1).

Esta migration NAO cria nada novo em producao: a tabela ja existe la desde a
F1, criada por `metadata.create_all(checkfirst=True)` no boot, e ja tem dado
real. O que ela faz e trazer essa tabela para o historico de migrations, para
que a partir daqui toda mudanca de schema tenha registro explicito.

Por isso o `up` e create-if-not-exists sobre a MESMA definicao que a F1 usa —
importada, nao copiada: duas copias divergiriam na primeira coluna nova. Em
producao vira no-op e so grava a linha no historico; em banco novo (teste,
dev) cria a tabela.

Sem `down`: `judith_execution_logs` guarda registro de auditoria de producao.
Um `down` que desse DROP seria uma arma apontada justamente para o dado que a
F1 existe para preservar. Reverter isto exige decisao manual.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.engine import Connection

from db.migrations.runner import Migration


def up(conexao: Connection, schema: str | None) -> None:
    from orchestration.execution_repository import build_table

    metadata = MetaData(schema=schema)
    tabela = build_table(metadata)
    metadata.create_all(conexao, tables=[tabela], checkfirst=True)


MIGRATION = Migration(
    version=1,
    name="adopt_judith_execution_logs",
    up=up,
    down=None,
    description="Traz a tabela de execution log da F1 para o historico. Nunca recria nem apaga dado.",
)
