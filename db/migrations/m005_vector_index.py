"""
005 - indice vetorial (F3 Hybrid RAG).

Puramente aditiva. Nenhum documento muda de status, nenhum chunk e reescrito,
nenhum conteudo e tocado. Cria uma tabela derivada e um indice sobre ela.

O QUE ENTRA
-----------

1. A extensao `vector` (pgvector), so no Postgres.
2. Tabela `judith_knowledge_embeddings`.
3. Indice HNSW com `vector_cosine_ops`, so no Postgres.

POR QUE FALHAR AQUI E SEGURO
----------------------------

`CREATE EXTENSION` exige que a extensao esteja disponivel no servidor. Se nao
estiver, esta migration levanta — e isso e o comportamento correto:

- quem chama e `ensure_execution_log_table`, que envolve `run_migrations` num
  `try/except SQLAlchemyError`. O erro vai para o log e o AgentOS sobe igual;
- a versao 005 NAO entra no historico, entao o proximo boot tenta de novo;
- `RAG_MODE` continua no default `current`, e o retrieval lexical de producao
  nao depende de nada disto.

Ou seja: sem pgvector, o sistema fica exatamente como estava antes da F3, com
uma linha de erro dizendo o porque. Nao ha estado intermediario.

POR QUE O INDICE VEM NA MIGRATION E NAO NO SCHEMA
-------------------------------------------------

`Index(..., postgresql_using="hnsw")` dentro de `build_embeddings_table` faria
`metadata.create_all` quebrar no SQLite dos testes, que nao conhece HNSW nem
indexa JSON assim. O tipo da coluna ja varia por dialeto; o indice varia
tambem, e o lugar de codigo que sabe disso e este.

O `down()` remove o indice e a tabela. NAO remove a extensao: outra coisa no
banco pode depender dela, e `DROP EXTENSION` seria destrutivo alem do escopo
desta migration. Perder a tabela nao perde conhecimento — todo o conteudo
continua em `versions` e `chunks`, e o pipeline reconstroi o indice.
"""

from __future__ import annotations

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Connection

from brain.schema import EMBEDDINGS_TABLE, build_embeddings_table
from db.migrations.runner import Migration

INDEX_NAME = f"ix_{EMBEDDINGS_TABLE}_hnsw_cosine"


def _e_postgres(conexao: Connection) -> bool:
    return conexao.dialect.name == "postgresql"


def _tem_tabela(conexao: Connection, tabela: str, schema: str | None) -> bool:
    return inspect(conexao).has_table(tabela, schema=schema)


def _qualificado(tabela: str, schema: str | None) -> str:
    return f'"{schema}"."{tabela}"' if schema else f'"{tabela}"'


def up(conexao: Connection, schema: str | None) -> None:
    if _e_postgres(conexao):
        # Sem IF NOT EXISTS a segunda execucao falharia; com ele, um banco que
        # ja tem pgvector (o `create_knowledge` do template usa PgVector) passa
        # direto. A extensao mora sempre em `public`, nunca no schema `ai`:
        # e assim que o resolvedor de tipos a encontra sem search_path custom.
        conexao.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    metadata = MetaData(schema=schema)
    embeddings = build_embeddings_table(metadata)
    if not _tem_tabela(conexao, embeddings.name, schema):
        embeddings.create(conexao)

    if _e_postgres(conexao):
        # HNSW e nao IVFFlat: IVFFlat precisa de dados representativos no
        # momento da criacao para calibrar as listas, e aqui a tabela nasce
        # vazia. HNSW e construido incrementalmente e nao tem esse requisito.
        #
        # `vector_cosine_ops` porque o pipeline grava vetores normalizados e o
        # retrieval compara por cosseno. Trocar a metrica do indice sem trocar
        # a do calculo daria um indice que ordena diferente da verdade.
        conexao.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS "{INDEX_NAME}" '
                f"ON {_qualificado(embeddings.name, schema)} "
                "USING hnsw (embedding vector_cosine_ops)"
            )
        )


def down(conexao: Connection, schema: str | None) -> None:
    metadata = MetaData(schema=schema)
    embeddings = build_embeddings_table(metadata)

    if _e_postgres(conexao):
        alvo = f'"{schema}"."{INDEX_NAME}"' if schema else f'"{INDEX_NAME}"'
        conexao.execute(text(f"DROP INDEX IF EXISTS {alvo}"))

    if _tem_tabela(conexao, embeddings.name, schema):
        embeddings.drop(conexao)


MIGRATION = Migration(
    version=5,
    name="vector_index",
    up=up,
    down=down,
    description=(
        "Cria a extensao pgvector, a tabela judith_knowledge_embeddings e o indice HNSW "
        "de cosseno. Aditiva e reversivel: o indice e derivado dos chunks."
    ),
)
