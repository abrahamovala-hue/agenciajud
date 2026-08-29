"""Fixtures compartilhadas da suite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from orchestration.execution_repository import ExecutionRepository, set_execution_repository


@pytest.fixture(autouse=True)
def execution_repository_em_memoria():
    """Aponta a persistencia de execucao para SQLite em memoria.

    Desde a F1 os workflows chamam `persist_execution()` no fim. Sem esta
    fixture, cada teste de workflow tentaria abrir conexao com o Postgres de
    producao — que nao existe no CI. O erro seria engolido por design
    (`persist_execution` nunca levanta), mas a suite pagaria o timeout de
    conexao a cada teste e nao provaria nada sobre a gravacao.

    Com um banco de verdade em memoria, o caminho de escrita e exercitado
    junto com o workflow, e cada teste comeca com a tabela vazia.
    """

    engine = create_engine("sqlite://")
    repositorio = ExecutionRepository(engine)
    repositorio.ensure_table()
    set_execution_repository(repositorio)
    yield repositorio
    set_execution_repository(None)
    engine.dispose()


# =============================================================================
# F3 — Hybrid RAG
# Fixtures da F3 — um Brain com material pago sintetico.
# 
# POR QUE O CONTEUDO PAGO AQUI E INVENTADO
# ----------------------------------------
# 
# Os tres ebooks da Judith vivem SO no Postgres de producao: nao estao no Git,
# nao entram em fixture, nao viram snapshot. E a regra dela, e vale tambem para
# teste. Mas sem NENHUM documento `ENTITLEMENT_REQUIRED` no store local seria
# impossivel testar entitlement, vazamento e disclosure — que sao exatamente os
# controles que mais precisam de teste.
# 
# A saida: documentos com as MESMAS chaves e a MESMA governanca dos reais
# (`EBOOK_RECHEIOS`, L1, ENTITLEMENT_REQUIRED, entitlement_scope preenchido) e
# texto inventado que nao ensina nada. O que se testa e a POLITICA, e a politica
# nao le o conteudo.
# =============================================================================

from brain.embeddings import DeterministicEmbedder

#: Texto inventado. Carrega os termos tecnicos que as buscas procuram, sem
#: nenhuma quantidade, nenhum passo e nenhuma receita executavel.
_CORPO_PAGO = {
    "EBOOK_RECHEIOS": (
        "# Recheios\n\n"
        "## Emulsao\n"
        "A quebra da emulsao acontece quando gordura e agua se separam na ganache.\n"
        "Texto sintetico de teste, sem gramagem e sem modo de preparo.\n\n"
        "## Pistache\n"
        "Sobre pasta de pistache em recheio. Texto sintetico de teste.\n\n"
        "## Brigadeiro\n"
        "Sobre brigadeiro gourmet como recheio. Texto sintetico de teste.\n"
    ),
    "EBOOK_CASQUINHAS": (
        "# Casquinhas\n\n"
        "## Temperagem\n"
        "Sobre metodos de temperagem e cristalizacao. Texto sintetico de teste.\n\n"
        "## Desmoldagem\n"
        "Sobre contracao e desmoldagem da casquinha. Texto sintetico de teste.\n"
    ),
    "EBOOK_LASCAS": (
        "# Lascas\n\n"
        "## Brilho\n"
        "Sobre brilho e opacidade na lasca de chocolate. Texto sintetico de teste.\n"
    ),
}

_OUTLINES = {
    "PRODUCT_OUTLINE_RECHEIOS": (
        "# Outline Recheios\n\n"
        "## O que o ebook cobre\n"
        "Recheios, ganache, brigadeiro e pasta de pistache. Sem formula.\n"
    ),
    "PRODUCT_OUTLINE_CASQUINHAS": (
        "# Outline Casquinhas\n\n## O que o ebook cobre\nCasquinhas e temperagem. Sem formula.\n"
    ),
    "PRODUCT_OUTLINE_LASCAS": ("# Outline Lascas\n\n## O que o ebook cobre\nLascas e brilho. Sem formula.\n"),
}

APROVADOR = "teste-f3"


def _publicar(repo, *, chave, titulo, corpo, layer, acesso, topics, escopo=None):
    documento = repo.create_document(
        source_id="fonte-teste-f3",
        title=titulo,
        layer=layer,
        status="DRAFT",
        content_access=acesso,
        checksum="",
        external_key=chave,
        topics=topics,
    )
    _, versao = repo.add_version(document_id=documento, body=corpo, created_by=APROVADOR)
    if escopo:
        repo.set_document_provenance(
            document_id=documento,
            source_authority="USER_AUTHORIZED_PRIMARY_SOURCE",
            provided_by="judith",
            entitlement_scope=escopo,
        )
    repo.set_status(document_id=documento, novo="TO_VALIDATE")
    repo.approve_version(document_id=documento, version=versao, approved_by=APROVADOR)
    return documento


def montar_brain_f3(engine):
    """Popula um engine com `docs/` + material pago sintetico. Tudo CONFIRMED.

    Recebe o engine em vez de cria-lo porque o TestClient do FastAPI atende em
    outra thread: `sqlite://` em memoria e por-thread e estoura ali. Quem testa
    rota passa um arquivo; o resto passa memoria.
    """

    from brain.approvals import apply_approvals
    from brain.backfill import run_backfill
    from brain.repository import KnowledgeRepository
    from db.migrations import run_migrations

    run_migrations(engine)
    repo = KnowledgeRepository(engine)
    run_backfill(repo)
    apply_approvals(repo)

    repo.upsert_source(
        source_id="fonte-teste-f3",
        kind="judith",
        origin="upload",
        owner="judith",
        title="Fixture F3",
    )
    for chave, corpo in _CORPO_PAGO.items():
        _publicar(
            repo,
            chave=chave,
            titulo=chave.replace("_", " ").title(),
            corpo=corpo,
            layer="L1",
            acesso="ENTITLEMENT_REQUIRED",
            topics=("tecnica", "chocolate", "ebook"),
            escopo=f"compra:{chave.lower()}",
        )
    for chave, corpo in _OUTLINES.items():
        _publicar(
            repo,
            chave=chave,
            titulo=chave.replace("_", " ").title(),
            corpo=corpo,
            layer="L3",
            acesso="PUBLIC",
            topics=("produto", "ebook"),
        )
    return repo


@pytest.fixture
def brain_f3():
    engine = create_engine("sqlite://")
    yield montar_brain_f3(engine)
    engine.dispose()


@pytest.fixture
def embedder():
    """Embedder offline. Nao tem semantica, e isso esta documentado."""

    from brain.retrieval import clear_query_cache

    clear_query_cache()
    yield DeterministicEmbedder()
    clear_query_cache()


@pytest.fixture
def brain_indexado(brain_f3, embedder):
    """O mesmo store, com o indice semantico ja construido."""

    from brain.embeddings import run_embedding_pipeline

    run_embedding_pipeline(brain_f3, embedder=embedder)
    return brain_f3
