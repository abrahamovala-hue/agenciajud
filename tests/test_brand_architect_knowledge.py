"""
Testes da camada de Knowledge do Brand Architect (deterministicos, sem LLM).

Incluem guardas de regressao para o CMO: a infra de Knowledge e compartilhada,
entao os campos novos (`caveat`, `excluded_sections`) precisam ser invisiveis
para quem nao os usa.
"""

from __future__ import annotations

import pytest

from agents.judith_team.brand_architect import brand_architect
from agents.knowledge_sources import (
    BRAND_ARCHITECT_DOCUMENTS,
    BRAND_ARCHITECT_MISSING_SOURCES,
    CMO_DOCUMENTS,
    CMO_MISSING_SOURCES,
    build_source_catalog,
    read_document,
    search_documents,
)

_TEMPLATE_SOURCES = {"VOICE", "AUDIENCE", "CONTENT_PILLARS", "VISUAL_IDENTITY"}


@pytest.mark.parametrize("source", BRAND_ARCHITECT_DOCUMENTS, ids=lambda s: s.key)
def test_documento_catalogado_existe_em_disco(source) -> None:
    assert source.path.exists(), f"{source.key} aponta para {source.relative_path}, que nao existe"


def test_whitelist_e_propria_e_diferente_da_do_cmo() -> None:
    """Cada agente tem a sua lista: o papel define o que ele pode ver."""

    ba_keys = {s.key for s in BRAND_ARCHITECT_DOCUMENTS}
    cmo_keys = {s.key for s in CMO_DOCUMENTS}

    assert "VISUAL_IDENTITY" in ba_keys and "VISUAL_IDENTITY" not in cmo_keys
    # Preco/prioridade de negocio nao sao papel do Brand Architect.
    assert not ba_keys & {"OFFERS", "PRD", "STATUS", "STATUS_V2"}


@pytest.mark.parametrize("key", sorted(_TEMPLATE_SOURCES))
def test_fontes_template_carregam_confiabilidade_e_ressalva(key: str) -> None:
    """Os 4 docs centrais de marca se declaram TEMPLATE no proprio arquivo."""

    source = next(s for s in BRAND_ARCHITECT_DOCUMENTS if s.key == key)
    assert source.reliability == "template"
    assert source.caveat, f"{key} e template e precisa dizer por que nao e verdade absoluta"

    conteudo = read_document(key, BRAND_ARCHITECT_DOCUMENTS)["conteudo"]
    assert "TEMPLATE" in conteudo.upper(), "o arquivo deixou de se declarar template - revisar o catalogo"


def test_busca_de_tom_devolve_voice_com_provenance() -> None:
    results = search_documents("tom de voz agressivo", BRAND_ARCHITECT_DOCUMENTS, BRAND_ARCHITECT_MISSING_SOURCES)
    voice = [doc for doc in results if doc.get("fonte") == "VOICE"]

    assert voice, "pergunta sobre tom precisa alcancar VOICE"
    assert voice[0]["confiabilidade"] == "template"
    assert voice[0]["ressalva"]


def test_pergunta_de_faturamento_aponta_para_analytics() -> None:
    """Faturamento esta fora do escopo: a busca precisa dizer de quem e."""

    results = search_documents("qual foi o faturamento ontem", BRAND_ARCHITECT_DOCUMENTS, BRAND_ARCHITECT_MISSING_SOURCES)
    gaps = [doc for doc in results if doc.get("status") == "FONTE_NAO_DISPONIVEL"]

    assert any(doc["peca_para"] == "analytics-bi-agent" for doc in gaps)


def test_pergunta_por_exemplos_aprovados_aponta_para_brand_reviewer() -> None:
    results = search_documents(
        "temos exemplos de pecas aprovadas e rejeitadas?",
        BRAND_ARCHITECT_DOCUMENTS,
        BRAND_ARCHITECT_MISSING_SOURCES,
    )
    assert any(doc.get("peca_para") == "brand-reviewer" for doc in results)


def test_brand_nao_expoe_bloco_de_tracking() -> None:
    """IDs de pixel/analytics nao tem uso em direcao de marca e nao devem circular."""

    conteudo = read_document("BRAND", BRAND_ARCHITECT_DOCUMENTS)["conteudo"]

    assert "Posicionamento" in conteudo, "o corte nao pode levar embora o conteudo util"
    assert "Facebook Pixel" not in conteudo
    assert "Tracking e Analytics" not in conteudo


def test_secao_excluida_tambem_some_da_busca() -> None:
    results = search_documents("facebook pixel hotjar clarity", BRAND_ARCHITECT_DOCUMENTS)
    assert all(doc.get("secao") != "Tracking e Analytics" for doc in results)


def test_catalogo_lista_fontes_faltantes_com_dono() -> None:
    catalog = build_source_catalog(BRAND_ARCHITECT_DOCUMENTS, BRAND_ARCHITECT_MISSING_SOURCES)
    assert catalog["fontes_nao_disponiveis"]
    assert all(gap["peca_para"] for gap in catalog["fontes_nao_disponiveis"])


def test_brand_architect_tem_tool_nativa_sem_vector_db() -> None:
    assert brand_architect.knowledge_retriever is not None
    assert brand_architect.search_knowledge is True
    assert brand_architect.knowledge is None
    assert brand_architect.tool_call_limit == 6
    assert brand_architect.pre_hooks and brand_architect.post_hooks


# --- Regressao do CMO: a infra e compartilhada, o comportamento nao muda ---


def test_payload_do_cmo_nao_ganhou_campos_novos() -> None:
    """Nenhum doc do CMO usa caveat/excluded_sections, entao o payload dele
    tem que continuar exatamente com as mesmas chaves de antes."""

    results = search_documents("preco do ebook e regras de publicacao", CMO_DOCUMENTS, CMO_MISSING_SOURCES)
    encontrados = [doc for doc in results if doc.get("status") is None]

    assert encontrados
    for doc in encontrados:
        assert set(doc) == {"fonte", "documento", "arquivo", "confiabilidade", "secao", "conteudo"}


def test_cmo_tambem_perdeu_o_bloco_de_tracking() -> None:
    """Excecao de seguranca aprovada depois: o bloco de IDs de tracking foi
    cortado tambem do catalogo do CMO. Todo o resto do BRAND continua la."""

    conteudo = read_document("BRAND", CMO_DOCUMENTS)["conteudo"]

    assert "Tracking e Analytics" not in conteudo
    assert "Facebook Pixel" not in conteudo
    assert "Posicionamento" in conteudo
    assert "Proposta de Valor" in conteudo
