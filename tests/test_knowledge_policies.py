"""
Testes estruturais da camada de Knowledge do time (deterministicos, sem LLM).

Garantem o que a etapa arquitetural prometeu: todo agente de negocio consulta
fontes reais, dentro da propria whitelist, com proveniencia, e sem conseguir
transformar documento inexistente em evidencia.
"""

from __future__ import annotations

import pytest

from agents.knowledge_policies import (
    DOCUMENTS,
    KNOWLEDGE_POLICIES,
    MISSING,
    UnknownAgentPolicyError,
    build_knowledge_tools_for,
    build_retriever_for,
    get_policy,
)
from agents.knowledge_sources import DocumentSource, build_source_catalog, read_document, search_documents
from orchestration.registry import AGENT_REGISTRY

# `jud` e o tira-duvidas de Agno no WhatsApp, nao um agente de negocio da
# Judith AI - fica deliberadamente fora desta camada.
BUSINESS_AGENT_IDS = sorted(set(AGENT_REGISTRY) - {"jud"})


# --- Cobertura -------------------------------------------------------------


def test_todo_agente_de_negocio_tem_politica() -> None:
    assert set(BUSINESS_AGENT_IDS) == set(KNOWLEDGE_POLICIES)
    assert len(KNOWLEDGE_POLICIES) == 20


@pytest.mark.parametrize("agent_id", BUSINESS_AGENT_IDS)
def test_agente_tem_knowledge_ligada(agent_id: str) -> None:
    agent = AGENT_REGISTRY[agent_id]

    assert agent.knowledge_retriever is not None, f"{agent_id} sem retriever"
    assert agent.search_knowledge is True, f"{agent_id} nao expoe search_knowledge_base"
    assert agent.tool_call_limit == 6, f"{agent_id} sem limite de tool calls"
    assert len(agent.tools or []) == 2, f"{agent_id} deveria ter listar_fontes + ler_documento"
    # Nenhum vector DB foi criado nesta fase.
    assert agent.knowledge is None, f"{agent_id} nao deveria ter Knowledge vetorial"


@pytest.mark.parametrize("agent_id", BUSINESS_AGENT_IDS)
def test_politica_nao_e_vazia_e_nao_tem_duplicata(agent_id: str) -> None:
    policy = get_policy(agent_id)
    keys = [source.key for source in policy.documents]

    assert keys, f"{agent_id} sem nenhuma fonte"
    assert len(keys) == len(set(keys)), f"{agent_id} tem fonte repetida"


def test_agente_desconhecido_falha_explicitamente() -> None:
    with pytest.raises(UnknownAgentPolicyError):
        get_policy("agente-que-nao-existe")


def test_ids_continuam_unicos() -> None:
    assert len(AGENT_REGISTRY) == 21
    assert len(set(AGENT_REGISTRY)) == 21


# --- Fontes reais ----------------------------------------------------------


@pytest.mark.parametrize("key", sorted(DOCUMENTS))
def test_documento_do_catalogo_existe_em_disco(key: str) -> None:
    """Catalogar um arquivo inexistente faria o agente citar fonte fantasma."""

    source = DOCUMENTS[key]
    assert source.path.exists(), f"{key} aponta para {source.relative_path}, que nao existe"


@pytest.mark.parametrize("agent_id", BUSINESS_AGENT_IDS)
def test_toda_fonte_permitida_existe(agent_id: str) -> None:
    for source in get_policy(agent_id).documents:
        assert source.path.exists(), f"{agent_id} pode pedir {source.key}, que nao existe em disco"


def test_documento_inexistente_nao_vira_evidencia() -> None:
    fantasma = DocumentSource(
        key="FANTASMA",
        title="Documento que nao existe",
        relative_path="JUDITH-AI-TEAM/NAO_EXISTE.md",
        summary="fonte inventada para o teste",
    )

    # Nao aparece na busca...
    resultados = search_documents("chocolate premium marca", (fantasma,))
    assert resultados[0]["status"] == "NENHUM_RESULTADO"

    # ...e a leitura direta falha de forma explicita, sem devolver conteudo.
    leitura = read_document("FANTASMA", (fantasma,))
    assert leitura["status"] == "ARQUIVO_AUSENTE"
    assert "conteudo" not in leitura


def test_conteudo_devolvido_corresponde_ao_arquivo_real() -> None:
    """Toda referencia retornada tem que ser texto que esta mesmo no disco."""

    for agent_id in BUSINESS_AGENT_IDS:
        policy = get_policy(agent_id)
        for doc in search_documents("marca produto cliente conteudo", policy.documents, policy.missing_sources):
            if doc.get("status"):
                continue
            arquivo = DOCUMENTS.get(doc["fonte"]) or next(s for s in policy.documents if s.key == doc["fonte"])
            assert doc["conteudo"][:200] in arquivo.path.read_text(encoding="utf-8")


# --- Isolamento entre agentes ---------------------------------------------


@pytest.mark.parametrize(
    ("agent_id", "fonte_proibida"),
    [
        ("caption-writer", "VIDEO_EDIT_SPEC"),
        ("video-editor", "OFFERS"),
        ("hook-finder", "OFFERS"),
        ("customer-support-agent", "VISUAL_IDENTITY"),
        ("visual-creative", "COMMENTS_FAQ"),
        ("crm-lifecycle-agent", "PLAYBOOK_HOOK"),
        ("brand-architect", "OFFERS"),
    ],
)
def test_agente_nao_le_fonte_fora_da_whitelist(agent_id: str, fonte_proibida: str) -> None:
    policy = get_policy(agent_id)
    assert fonte_proibida not in {s.key for s in policy.documents}

    resultado = read_document(fonte_proibida, policy.documents)
    assert resultado["status"] == "CHAVE_INVALIDA"
    assert "conteudo" not in resultado


def test_busca_nunca_alcanca_fonte_fora_da_whitelist() -> None:
    """O video-editor nao deve conseguir chegar em preco por busca livre."""

    policy = get_policy("video-editor")
    resultados = search_documents("preco desconto link de compra kiwify", policy.documents, policy.missing_sources)

    assert all(doc.get("fonte") != "OFFERS" for doc in resultados)


def test_nenhum_agente_recebe_o_catalogo_inteiro() -> None:
    """Whitelist explicita: ninguem pesquisa o repositorio todo."""

    total = len(DOCUMENTS)
    for agent_id in BUSINESS_AGENT_IDS:
        permitidas = len(get_policy(agent_id).documents)
        assert permitidas < total, f"{agent_id} enxerga o catalogo inteiro"


# --- Proveniencia ----------------------------------------------------------


@pytest.mark.parametrize("key", ["VOICE", "AUDIENCE", "CONTENT_PILLARS", "VISUAL_IDENTITY", "INSTAGRAM_AUDIT"])
def test_template_e_identificado(key: str) -> None:
    source = DOCUMENTS[key]

    assert source.reliability == "template"
    assert source.caveat, f"{key} e template e precisa dizer por que nao e verdade confirmada"
    assert "TEMPLATE" in source.path.read_text(encoding="utf-8").upper()


def test_ressalva_de_offers_acompanha_o_conflito_real() -> None:
    """A ressalva de OFFERS aponta o que de fato esta em aberto.

    Ate a F2.7 era a colecao completa, marcada 'A VERIFICAR'. Isso foi
    RESOLVIDO documentalmente: o site nao tem preco nem checkout de colecao,
    entao ela nao e oferta. O que ficou aberto e outra coisa — o site publica
    R$ 47 no texto e 25.00 no schema.org para o mesmo produto.

    Este teste existe para garantir que a ressalva descreve a pendencia
    VIGENTE, e nao uma que ja foi respondida.
    """

    source = DOCUMENTS["OFFERS"]
    texto = source.path.read_text(encoding="utf-8")

    assert "A VERIFICAR" not in texto.upper(), "a pendencia da colecao foi resolvida"
    assert "UNAVAILABLE" in texto, "a colecao precisa estar declarada como indisponivel"
    assert source.caveat, "OFFERS precisa dizer o que ainda esta em aberto"
    assert "25.00" in source.caveat, "a ressalva precisa apontar o conflito de preco vigente"


def test_ressalva_viaja_junto_do_trecho_buscado() -> None:
    policy = get_policy("caption-writer")
    resultados = search_documents("tom de voz da marca", policy.documents, policy.missing_sources)
    voice = [doc for doc in resultados if doc.get("fonte") == "VOICE"]

    assert voice
    assert voice[0]["confiabilidade"] == "template"
    assert voice[0]["ressalva"]


def test_bloco_de_tracking_nao_circula() -> None:
    """IDs de pixel/analytics nao servem a nenhum agente de negocio."""

    for agent_id in BUSINESS_AGENT_IDS:
        policy = get_policy(agent_id)
        if not any(s.key == "BRAND" for s in policy.documents):
            continue
        conteudo = read_document("BRAND", policy.documents)["conteudo"]
        assert "Facebook Pixel" not in conteudo, f"{agent_id} recebe IDs de tracking"


# --- FONTE_NAO_DISPONIVEL --------------------------------------------------


@pytest.mark.parametrize(
    ("agent_id", "pergunta", "dono"),
    [
        ("analytics-bi-agent", "quanto vendemos ontem", "analytics-bi-agent"),
        ("caption-writer", "quais posts performaram melhor", "analytics-bi-agent"),
        ("social-media-manager", "qual o calendario desta semana", "social-media-manager"),
        ("customer-insights-agent", "o que as clientes falam nas DMs", "customer-insights-agent"),
        ("crm-lifecycle-agent", "quantos leads temos no pipeline", "crm-lifecycle-agent"),
        ("brand-reviewer", "temos exemplos de pecas aprovadas antes", "brand-reviewer"),
    ],
)
def test_fonte_inexistente_e_declarada_com_dono(agent_id: str, pergunta: str, dono: str) -> None:
    policy = get_policy(agent_id)
    resultados = search_documents(pergunta, policy.documents, policy.missing_sources)
    lacunas = [doc for doc in resultados if doc.get("status") == "FONTE_NAO_DISPONIVEL"]

    assert lacunas, f"{agent_id}: '{pergunta}' precisa sinalizar que a fonte nao existe"
    assert any(doc["peca_para"] == dono for doc in lacunas)
    assert all(doc["motivo"] for doc in lacunas)


def test_toda_lacuna_declara_dono_e_motivo() -> None:
    for gap in MISSING.values():
        assert gap.ask_agent and gap.reason and gap.keywords


# --- Listar != consultar ---------------------------------------------------


def test_listar_fontes_nao_devolve_conteudo() -> None:
    policy = get_policy("brand-reviewer")
    catalogo = build_source_catalog(policy.documents, policy.missing_sources)

    for entrada in catalogo["documentos_disponiveis"]:
        assert "conteudo" not in entrada
    assert catalogo["fontes_nao_disponiveis"]


def test_ler_documento_devolve_conteudo_e_listar_nao() -> None:
    policy = get_policy("brand-reviewer")
    assert "conteudo" in read_document("VOICE", policy.documents)


def test_tools_do_agente_sao_as_duas_esperadas() -> None:
    nomes = [t.name for t in build_knowledge_tools_for("script-writer")]
    assert nomes == ["listar_fontes_disponiveis", "ler_documento"]


def test_retriever_respeita_a_politica_do_agente() -> None:
    retriever = build_retriever_for("hook-finder")
    fontes = {doc.get("fonte") for doc in retriever("preco do ebook")}

    assert "OFFERS" not in fontes, "hook-finder nao tem OFFERS na whitelist"
