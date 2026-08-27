"""
Judith Brain — classificacao dos documentos que ja existem no repositorio.

Este modulo responde tres perguntas por documento, TODAS deterministicamente
a partir do caminho e da chave. Nenhum LLM, nenhuma inferencia de conteudo:

    layer          -> L1 / L2 / L3
    topics         -> etiquetas para filtro
    content_access -> quem pode ver o conteudo entregue

A CAMADA L0 SYSTEM (F2.5)
-------------------------

A F2 tinha tres camadas e uma pilha de documentos que nao cabiam em nenhuma:
as 21 fichas de agente, os protocolos, os models, os workflows, o roster. Eles
ficaram em L2 com topic `sistema`, o que era um remendo — L2 e "oficio curado"
e uma ficha de agente nao e oficio.

Agora eles tem camada propria. O ganho nao e organizacional, e de seguranca:
**L0 e o ultimo na precedencia** (`brain/conflicts.py`). Uma ficha de agente
que cita "R$ 47" como exemplo nunca pode virar fonte de preco. Enquanto
estavam em L2, competiam com o craft; agora nao competem com nada que fale do
negocio.

O que NAO virou L0, por instrucao explicita: preco, produto, politica e
tecnica da Judith. `brand/`, `sources/` e `BUSINESS_RULES` continuam L3.
`knowledge/craft/` continua L2 — aquilo e oficio de verdade, e o proprio
catalogo diz: "Conhecimento GERAL de oficio. Nao e fato sobre a Bem me Que."

"""

from __future__ import annotations

from brain.models import ContentAccess, Layer

# --- Camada por caminho -----------------------------------------------------
#
# Regras testadas em ordem; a primeira que casar vence. Prefixo de caminho,
# nunca conteudo — classificacao precisa ser reproduzivel.

_LAYER_RULES: tuple[tuple[str, Layer], ...] = (
    # L1 — material da propria Judith. A pasta existe e esta vazia por
    # decisao explicita (ver o README dela): os ebooks reais nao estao no
    # projeto e nao devem ser reconstruidos de memoria.
    ("JUDITH-AI-TEAM-V2/knowledge/judith/", "L1"),
    # L2 — oficio generico. O proprio catalogo ja diz destes: "Conhecimento
    # GERAL de oficio. Nao e fato sobre a Bem me Que."
    ("JUDITH-AI-TEAM-V2/knowledge/craft/", "L2"),
    # L0 — como a propria IA funciona. Fichas de agente, protocolos, models,
    # orquestracao. Os "playbooks" V1 entram aqui tambem: apesar do nome, sao
    # definicao de papel ("Voce e o Hook Finder da Bem me Que"), nao oficio.
    ("JUDITH-AI-TEAM-V2/agents/", "L0"),
    ("JUDITH-AI-TEAM-V2/protocol/", "L0"),
    ("JUDITH-AI-TEAM-V2/models/", "L0"),
    ("JUDITH-AI-TEAM-V2/workflows/", "L0"),
    ("JUDITH-AI-TEAM/agents/", "L0"),
    ("JUDITH-AI-TEAM/workflows/", "L0"),
    ("JUDITH-AI-TEAM/docs/", "L0"),
    # L3 — fato operacional do negocio.
    ("JUDITH-AI-TEAM/brand/", "L3"),
    ("JUDITH-AI-TEAM/sources/", "L3"),
)

#: Chaves cuja camada nao se resolve pelo caminho.
_LAYER_BY_KEY: dict[str, Layer] = {
    # Regra vinculante do negocio: preco, garantia, politica de venda.
    "BUSINESS_RULES": "L3",
    # Documentacao do projeto de IA, nao do negocio de chocolate.
    "PRD": "L0",
    "STATUS": "L0",
    "STATUS_V2": "L0",
    "AGENT_ROSTER": "L0",
    "ORCHESTRATION_V2": "L0",
    "HANDOFF_EXAMPLES": "L0",
    "WORKFLOWS_V2_INDEX": "L0",
    "EVALS_README": "L0",
    "VIDEO_EDIT_SPEC": "L0",
    "VIDEO_ENGINE_PLAN": "L0",
    "DECISION_CARD": "L0",
}

_DEFAULT_LAYER: Layer = "L2"


def layer_for(*, key: str, relative_path: str) -> Layer:
    if key in _LAYER_BY_KEY:
        return _LAYER_BY_KEY[key]
    caminho = relative_path.replace("\\", "/")
    for prefixo, camada in _LAYER_RULES:
        if caminho.startswith(prefixo):
            return camada
    return _DEFAULT_LAYER


# --- Topics -----------------------------------------------------------------

_TOPIC_RULES: tuple[tuple[str, str], ...] = (
    ("JUDITH-AI-TEAM-V2/knowledge/judith/", "judith"),
    ("JUDITH-AI-TEAM-V2/knowledge/craft/", "craft"),
    ("JUDITH-AI-TEAM-V2/agents/", "sistema"),
    ("JUDITH-AI-TEAM-V2/protocol/", "sistema"),
    ("JUDITH-AI-TEAM-V2/models/", "sistema"),
    ("JUDITH-AI-TEAM/agents/", "sistema"),
    ("JUDITH-AI-TEAM/brand/", "marca"),
    ("JUDITH-AI-TEAM/sources/", "pesquisa"),
    ("JUDITH-AI-TEAM/workflows/", "workflow"),
    ("JUDITH-AI-TEAM-V2/workflows/", "workflow"),
)

#: Topics adicionais por chave. `comercial` e o mais importante: e ele que
#: marca o que o Evidence Gate trata como afirmacao sobre preco/oferta.
_EXTRA_TOPICS: dict[str, tuple[str, ...]] = {
    "OFFERS": ("comercial", "preco", "oferta"),
    "PRODUCTS": ("comercial", "produto"),
    "BUSINESS_RULES": ("regra", "politica", "comercial"),
    "PRODUCT_PAGES_AUDIT": ("comercial", "produto"),
    "VOICE": ("tom",),
    "AUDIENCE": ("publico",),
    "VISUAL_IDENTITY": ("visual",),
    "CONTENT_PILLARS": ("editorial",),
    "BRAND": ("posicionamento",),
    "COMMENTS_FAQ": ("faq",),
    "COMPETITORS": ("concorrencia",),
    "AGENT_ROSTER": ("sistema",),
    "ORCHESTRATION_V2": ("sistema",),
    "STATUS": ("sistema",),
    "STATUS_V2": ("sistema",),
    "PRD": ("sistema",),
}


def topics_for(*, key: str, relative_path: str) -> tuple[str, ...]:
    caminho = relative_path.replace("\\", "/")
    topics: list[str] = []
    for prefixo, topic in _TOPIC_RULES:
        if caminho.startswith(prefixo):
            topics.append(topic)
            break
    topics.extend(_EXTRA_TOPICS.get(key, ()))
    # dedup preservando ordem
    return tuple(dict.fromkeys(topics))


# --- Content access (disclosure) --------------------------------------------
#
# O default e o mais restritivo. Hoje NADA no repositorio nasce PUBLIC: nem o
# BRAND.md e escrito para ser colado numa conversa. As unicas duas fontes que
# suporte e venda usam para responder sao OFFERS e PRODUCTS, e mesmo elas saem
# em trecho, nunca inteiras.
#
# ENTITLEMENT_REQUIRED ainda nao tem nenhum documento: os ebooks nao foram
# ingeridos. A regra existe pronta para quando forem.

_CONTENT_ACCESS_BY_KEY: dict[str, ContentAccess] = {
    "OFFERS": "SUPPORT_USE",
    "PRODUCTS": "SUPPORT_USE",
    "COMMENTS_FAQ": "SUPPORT_USE",
}

_DEFAULT_CONTENT_ACCESS: ContentAccess = "INTERNAL_ONLY"


def content_access_for(*, key: str, relative_path: str) -> ContentAccess:
    caminho = relative_path.replace("\\", "/")
    # Todo material que vier da pasta da Judith e pago ate prova em contrario.
    if caminho.startswith("JUDITH-AI-TEAM-V2/knowledge/judith/"):
        return "ENTITLEMENT_REQUIRED"
    return _CONTENT_ACCESS_BY_KEY.get(key, _DEFAULT_CONTENT_ACCESS)


# --- Kind da fonte ----------------------------------------------------------


def source_kind_for(layer: Layer) -> str:
    return {"L0": "system", "L1": "judith", "L2": "professional", "L3": "business"}[layer]
