"""
Testes da camada de Knowledge do CMO (deterministicos, sem LLM).

Cobrem o que a rodada de refinamento individual do CMO garantiu:
- todo documento catalogado existe de verdade em disco;
- a busca encontra a fonte certa para perguntas reais;
- fonte inexistente e declarada como tal, com o agente responsavel;
- o CMO ganhou a tool nativa do Agno sem ligar vector DB.
"""

from __future__ import annotations

import pytest

from agents.judith_team.cmo import cmo
from agents.knowledge_sources import (
    CMO_DOCUMENTS,
    CMO_MISSING_SOURCES,
    build_source_catalog,
    read_document,
    search_documents,
)


@pytest.mark.parametrize("source", CMO_DOCUMENTS, ids=lambda s: s.key)
def test_documento_catalogado_existe_em_disco(source) -> None:
    """Catalogar um documento que nao existe faria o CMO citar fonte fantasma."""

    assert source.path.exists(), f"{source.key} aponta para {source.relative_path}, que nao existe"


def test_chaves_do_catalogo_sao_unicas() -> None:
    keys = [source.key for source in CMO_DOCUMENTS]
    assert len(keys) == len(set(keys))


def test_busca_por_preco_encontra_offers_ou_products() -> None:
    results = search_documents("qual o preco do ebook", CMO_DOCUMENTS, CMO_MISSING_SOURCES)
    fontes = {doc.get("fonte") for doc in results}
    assert fontes & {"OFFERS", "PRODUCTS"}


def test_pergunta_sobre_receita_declara_fonte_indisponivel() -> None:
    results = search_documents("quanto vendemos ontem", CMO_DOCUMENTS, CMO_MISSING_SOURCES)
    indisponiveis = [doc for doc in results if doc.get("status") == "FONTE_NAO_DISPONIVEL"]

    assert indisponiveis, "pergunta sobre venda precisa sinalizar que nao ha fonte de receita"
    assert any(doc["peca_para"] == "analytics-bi-agent" for doc in indisponiveis)


def test_pergunta_sobre_kpi_declara_fonte_indisponivel() -> None:
    results = search_documents("kpi de engajamento desta semana", CMO_DOCUMENTS, CMO_MISSING_SOURCES)
    assert any(doc.get("fonte") == "KPIS_ATUAIS" for doc in results)


def test_busca_sem_correspondencia_nao_devolve_lista_vazia() -> None:
    """Lista vazia convidaria o modelo a preencher a lacuna sozinho.

    A query precisa ser genuinamente inexistente: a busca casa por SUBSTRING,
    entao uma palavra comum como "termo" acerta dentro de "meio-termo" e o
    teste passaria a medir outra coisa.
    """

    results = search_documents("zzzqqq wxyvbk qqzzxx", CMO_DOCUMENTS)
    assert results and results[0]["status"] == "NENHUM_RESULTADO"


def test_ler_documento_com_chave_invalida_lista_chaves_validas() -> None:
    result = read_document("NAO_EXISTE", CMO_DOCUMENTS)
    assert result["status"] == "CHAVE_INVALIDA"
    assert "OFFERS" in result["chaves_validas"]


def test_ler_documento_devolve_conteudo_real() -> None:
    result = read_document("business_rules", CMO_DOCUMENTS)
    assert result["status"] == "OK"
    assert "Nenhum conteúdo é publicado sem aprovação explícita da Judith" in result["conteudo"]


def test_catalogo_expoe_fontes_faltantes_com_responsavel() -> None:
    catalog = build_source_catalog(CMO_DOCUMENTS, CMO_MISSING_SOURCES)
    assert catalog["fontes_nao_disponiveis"], "o catalogo precisa dizer o que NAO existe"
    assert all(gap["peca_para"] for gap in catalog["fontes_nao_disponiveis"])


def test_cmo_tem_tool_nativa_de_busca_sem_vector_db() -> None:
    """A tool `search_knowledge_base` do Agno so aparece com retriever + search_knowledge.

    O `knowledge is None` e proposital: nenhuma tabela pgvector foi criada
    nesta rodada (ver agents/knowledge_sources.py).
    """

    assert cmo.knowledge_retriever is not None
    assert cmo.search_knowledge is True
    assert cmo.knowledge is None


def test_cmo_mantem_guardrails_e_limite_de_tool_calls() -> None:
    assert cmo.pre_hooks and cmo.post_hooks
    assert cmo.tool_call_limit == 6
