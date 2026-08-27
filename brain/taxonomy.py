"""
Judith Brain — classificacao dos documentos que ja existem no repositorio.

Este modulo responde tres perguntas por documento, TODAS deterministicamente
a partir do caminho e da chave. Nenhum LLM, nenhuma inferencia de conteudo:

    layer          -> L1 / L2 / L3
    topics         -> etiquetas para filtro
    content_access -> quem pode ver o conteudo entregue

UMA DECISAO QUE PRECISA DE VOCE
-------------------------------

As tres camadas do briefing sao L1 (Judith), L2 (profissional curado) e L3
(fato do negocio). O corpus atual tem uma quarta natureza que nao cabe bem em
nenhuma: as 21 fichas de agente, os protocolos, os models e o roster. Eles nao
sao fato comercial (L3) nem oficio generico (L2) — sao a documentacao do
proprio sistema.

Estao classificados como **L2 com topic `sistema`**, e nao como L3, por uma
razao concreta: em `brain/conflicts.py` a precedencia poe Business acima de
tudo. Se um protocolo entrasse como L3, uma regra de processo poderia ganhar
de um preco. Como L2 + topic `sistema`, eles ficam filtraveis e fora do
caminho do fato comercial.

Se a Judith quiser uma camada propria para isso (um L0/SYSTEM), a mudanca e
uma migration aditiva e uma linha aqui.
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
    # L2 + sistema — documentacao do proprio time de agentes.
    ("JUDITH-AI-TEAM-V2/agents/", "L2"),
    ("JUDITH-AI-TEAM-V2/protocol/", "L2"),
    ("JUDITH-AI-TEAM-V2/models/", "L2"),
    ("JUDITH-AI-TEAM/agents/", "L2"),
    # L3 — fato operacional do negocio.
    ("JUDITH-AI-TEAM/brand/", "L3"),
    ("JUDITH-AI-TEAM/sources/", "L3"),
)

#: Chaves cuja camada nao se resolve pelo caminho.
_LAYER_BY_KEY: dict[str, Layer] = {
    "BUSINESS_RULES": "L3",
    "PRD": "L3",
    "STATUS": "L3",
    "STATUS_V2": "L2",
    "AGENT_ROSTER": "L2",
    "ORCHESTRATION_V2": "L2",
    "HANDOFF_EXAMPLES": "L2",
    "WORKFLOWS_V2_INDEX": "L2",
    "EVALS_README": "L2",
    "VIDEO_EDIT_SPEC": "L2",
    "VIDEO_ENGINE_PLAN": "L3",
    "DECISION_CARD": "L3",
}

_DEFAULT_LAYER: Layer = "L2"


def layer_for(*, key: str, relative_path: str) -> Layer:
    if key in _LAYER_BY_KEY:
        return _LAYER_BY_KEY[key]
    caminho = relative_path.replace("\\", "/")
    for prefixo, camada in _LAYER_RULES:
        if caminho.startswith(prefixo):
            return camada
    # Workflows V1 e o resto de JUDITH-AI-TEAM.
    if caminho.startswith("JUDITH-AI-TEAM/workflows/"):
        return "L2"
    return _DEFAULT_LAYER


# --- Topics -----------------------------------------------------------------

_TOPIC_RULES: tuple[tuple[str, str], ...] = (
    ("JUDITH-AI-TEAM-V2/knowledge/judith/", "judith"),
    ("JUDITH-AI-TEAM-V2/knowledge/craft/", "craft"),
    ("JUDITH-AI-TEAM-V2/agents/", "sistema"),
    ("JUDITH-AI-TEAM-V2/protocol/", "sistema"),
    ("JUDITH-AI-TEAM-V2/models/", "sistema"),
    ("JUDITH-AI-TEAM/agents/", "playbook"),
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
    return {"L1": "judith", "L2": "professional", "L3": "business"}[layer]
