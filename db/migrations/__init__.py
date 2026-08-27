"""
Migrations do Judith Brain — runner proprio, minusculo, versionado.

POR QUE NAO ALEMBIC
-------------------

Alembic e a resposta padrao, e foi descartada de proposito. Ela traz
`env.py`, `alembic.ini`, um diretorio `versions/` com revisao encadeada por
hash, e o `autogenerate` — que compara metadata contra o banco. Nada disso
encaixa aqui:

- O AgentOS cria as TABELAS DELE sozinho (`agno_sessions`, `agno_traces`,
  `agno_metrics`, ...), fora do nosso metadata. O `autogenerate` do Alembic
  veria tudo isso como "tabela desconhecida" e proporia DROP. Uma migration
  gerada sem revisao cuidadosa apagaria dado de producao.
- Precisamos rodar no boot do processo web (Railway nao tem passo de release
  separado hoje). Alembic e feito para rodar como comando, nao embutido.
- A suite roda sobre SQLite em memoria. Manter dois caminhos (SQL versionado
  para Postgres, `create_all` para teste) e exatamente a divergencia que
  deixou o buraco do /docs passar na F0.1.

Entao: migrations escritas em SQLAlchemy Core, que valem nos dois dialetos,
uma por modulo numerado neste pacote.

O QUE ESTE RUNNER GARANTE
-------------------------

- **Identificavel**: cada migration tem `version` (inteiro crescente) e
  `name`. A tabela `judith_schema_migrations` guarda o historico.
- **Idempotente**: migration ja aplicada nao roda de novo. Rodar o runner
  duas vezes seguidas nao muda nada.
- **Auditavel**: `applied_at` e `checksum` do codigo-fonte ficam gravados.
  Editar uma migration ja aplicada e detectado e denunciado no log.
- **Reversivel quando possivel**: `down()` e opcional e nunca roda sozinho.
  Migration sem `down()` declara isso explicitamente em vez de fingir.

O QUE ELE NAO FAZ, DE PROPOSITO
-------------------------------

Nao apaga tabela, nao apaga coluna, nao apaga dado. `rollback()` existe para
uso manual e deliberado, nunca no boot. `judith_execution_logs` ja tem dado
de producao: a migration 001 a ADOTA (create-if-not-exists), nao a recria.
"""

from __future__ import annotations

from db.migrations.runner import (
    MIGRATIONS,
    Migration,
    applied_versions,
    pending_migrations,
    rollback,
    run_migrations,
)

__all__ = [
    "MIGRATIONS",
    "Migration",
    "applied_versions",
    "pending_migrations",
    "rollback",
    "run_migrations",
]
