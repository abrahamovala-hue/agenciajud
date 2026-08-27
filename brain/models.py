"""
Judith Brain — vocabulario de dominio.

Tudo aqui e Literal + dataclass, sem banco e sem LLM. Existe para que as
regras de governanca sejam testaveis isoladamente.

A DISTINCAO QUE SUSTENTA O RESTO
--------------------------------

**reliability != validation.** `reliability` (vigente/snapshot/template) e
uma propriedade da FONTE: o quanto aquele documento se propoe a ser estavel.
`status` (DRAFT/TO_VALIDATE/CONFIRMED/DEPRECATED) e uma afirmacao sobre
APROVACAO HUMANA. Um documento pode ser perfeitamente estavel e nunca ter
sido lido pela Judith.

Nenhuma funcao deste modulo promove nada para CONFIRMED. Nao existe caminho
de codigo que faca isso: a unica porta e `KnowledgeRepository.approve_version()`,
que exige um humano nomeado, e o backfill nao a chama.

CAN_KNOW NAO E UMA COISA SO
---------------------------

Poder consultar um conteudo para responder certo nao autoriza entregar o
conteudo — mas tambem nao proibe tudo. Um agente de suporte precisa saber o
que o ebook ensina para nao contradizer o produto, pode dizer "esse ebook
cobre temperagem com pontos exatos de temperatura", pode citar uma frase
curta, e nao pode entregar o metodo nem a receita.

Isso e um leque, nao um booleano. `DisclosurePolicy` separa:

    can_know                  consultar para raciocinar
    can_summarize             descrever o conteudo com as proprias palavras
    can_quote                 citar literalmente, dentro de max_verbatim_chars
    can_reveal_full_method    entregar a tecnica completa
    can_reveal_full_recipe    entregar a receita completa
    requires_entitlement      so com compra verificada

O QUE MUDOU NA F2.5, E O QUE ISSO CUSTA
---------------------------------------

A F2 protegia material pago truncando o corpo em 600 caracteres antes de
entregar ao agente. Determinístico, mas errado como mecanismo principal:
mutila o contexto de quem precisa RACIOCINAR sobre o conteudo e, mesmo
assim, nao impede o modelo de parafrasear o que sobrou.

Agora a protecao mora em tres lugares, nesta ordem de forca:

1. **Acesso** — conteudo que o agente nao pode conhecer nao e entregue.
   Continua determinístico, e continua sendo a garantia real.
2. **Policy explicita** — viaja junto do trecho, dizendo o que pode sair.
3. **`max_verbatim_chars`** — teto de CITACAO LITERAL, verificavel por
   `verbatim_violation()`.

O custo, dito com todas as letras: (2) depende de o modelo obedecer. A
checagem que tornaria isso determinístico seria um gate pos-geracao, no
espirito do Evidence Gate — fora do escopo da F2.5. `verbatim_violation()`
ja existe para esse gate chamar quando for construido.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

# --- Camadas ----------------------------------------------------------------

Layer = Literal["L0", "L1", "L2", "L3"]
LAYERS: tuple[Layer, ...] = get_args(Layer)

LAYER_NAMES: dict[Layer, str] = {
    "L0": "SYSTEM — como a propria IA funciona (fichas, protocolos, evals, arquitetura)",
    "L1": "JUDITH — o que a Judith sabe, pensa, ensina ou definiu",
    "L2": "PROFESSIONAL — conhecimento de oficio curado deliberadamente",
    "L3": "BUSINESS — fato operacional do negocio (produto, preco, politica)",
}

#: L0 existe para NAO competir com verdade comercial. Um protocolo de
#: colaboracao nao pode ganhar de um preco, nem quando cita um. Por isso ele
#: entra por ultimo na precedencia (brain/conflicts.py) e nao serve como
#: evidencia sobre o negocio.
SYSTEM_LAYER: Layer = "L0"

# --- Fonte ------------------------------------------------------------------

SourceKind = Literal["system", "judith", "professional", "business"]
SOURCE_KINDS: tuple[SourceKind, ...] = get_args(SourceKind)

Origin = Literal["upload", "manual", "url", "repository", "sync"]
ORIGINS: tuple[Origin, ...] = get_args(Origin)

# --- Ciclo de validacao -----------------------------------------------------

DocStatus = Literal["DRAFT", "TO_VALIDATE", "CONFIRMED", "DEPRECATED"]
DOC_STATUSES: tuple[DocStatus, ...] = get_args(DocStatus)

#: O unico status que sai em producao. Nao e configuravel por agente comum.
PRODUCTION_STATUSES: frozenset[str] = frozenset({"CONFIRMED"})

#: Quem revisa ve o que ainda nao foi aprovado. DEPRECATED entra aqui porque
#: revisar inclui olhar o que foi substituido e por que.
REVIEW_STATUSES: frozenset[str] = frozenset({"DRAFT", "TO_VALIDATE", "CONFIRMED", "DEPRECATED"})

#: Transicoes permitidas. DEPRECATED nao volta atras: reabilitar conteudo
#: substituido exige documento novo, para que a linha do tempo nao minta.
ALLOWED_TRANSITIONS: dict[DocStatus, frozenset[DocStatus]] = {
    "DRAFT": frozenset({"TO_VALIDATE", "DEPRECATED"}),
    "TO_VALIDATE": frozenset({"CONFIRMED", "DRAFT", "DEPRECATED"}),
    "CONFIRMED": frozenset({"DEPRECATED", "TO_VALIDATE"}),
    "DEPRECATED": frozenset(),
}

Confidence = Literal["alto", "medio", "baixo"]

# --- Autoridade da fonte (F2.7) ---------------------------------------------

SourceAuthority = Literal[
    "USER_AUTHORIZED_PRIMARY_SOURCE",
    "USER_PROVIDED_OFFICIAL_SITE_SNAPSHOT",
    "OFFICIAL_WEBSITE_LIVE",
    "DERIVED_DOCUMENT",
]
SOURCE_AUTHORITIES: tuple[SourceAuthority, ...] = get_args(SourceAuthority)

#: O QUE AUTORIDADE SIGNIFICA — e o que ela nao significa.
#:
#: A Judith entregar um PDF confirma que ela PUBLICA e ENSINA aquilo. Nao
#: confirma que toda afirmacao externa escrita la dentro e verdadeira. "O
#: mercado de chocolate premium cresce" continua sendo AUTHORIAL_CLAIM mesmo
#: vindo de uma fonte primaria autorizada.
#:
#: Confundir os dois transformaria a autorizacao da Judith em verificacao
#: factual do mundo, que ela nunca deu.
AUTHORITY_MEANING: dict[SourceAuthority, str] = {
    "USER_AUTHORIZED_PRIMARY_SOURCE": (
        "Arquivo do proprio produto, entregue pela Judith como fonte atual. Prova o que ela "
        "publica e ensina; nao prova afirmacao externa contida nele."
    ),
    "USER_PROVIDED_OFFICIAL_SITE_SNAPSHOT": (
        "Captura do site oficial feita pela Judith. Prova o estado do site no momento da captura; "
        "nao prova o estado de hoje."
    ),
    "OFFICIAL_WEBSITE_LIVE": "Site oficial lido ao vivo, com status HTTP e checksum registrados.",
    "DERIVED_DOCUMENT": "Documento construido a partir de outras fontes. Nunca vence uma fonte primaria.",
}

# --- Classificacao funcional do trecho (F2.7) -------------------------------

#: Para que serve o trecho. Governa retrieval (diversidade, precedencia) e
#: disclosure (o que pode sair). Deliberadamente pequeno: e classificacao
#: operacional, nao ontologia.
ContentKind = Literal[
    "PRODUCT_METADATA",
    "AUTHORIAL_TEACHING",
    "TECHNIQUE",
    "RECIPE",
    "TROUBLESHOOTING",
    "STORAGE_VALIDITY",
    "TOOLS_EQUIPMENT",
    "SALES_GUIDANCE",
    "MARKETING_CLAIM",
    "AUTHORIAL_CLAIM",
    "CROSS_PROMOTION",
    "AUTHORIAL_MESSAGE",
    "COMMERCIAL_TERMS",
    "POLICY",
    "FAQ",
]
CONTENT_KINDS: tuple[ContentKind, ...] = get_args(ContentKind)

#: Os tipos cujo corpo integral reconstroi o produto pago. O gate de
#: disclosure trata estes com o rigor maximo — ver brain/disclosure_gate.py.
PROTECTED_KINDS: frozenset[str] = frozenset({"RECIPE", "TECHNIQUE", "AUTHORIAL_TEACHING"})

#: Os tipos que NAO sao fato verificado sobre o mundo, mesmo vindos de fonte
#: primaria. Um agente pode citar que a Judith diz isso; nao pode afirmar como
#: fato proprio, e nunca como promessa de resultado.
UNVERIFIED_KINDS: frozenset[str] = frozenset({"MARKETING_CLAIM", "AUTHORIAL_CLAIM", "SALES_GUIDANCE"})

# --- Disclosure -------------------------------------------------------------

ContentAccess = Literal["INTERNAL_ONLY", "SUPPORT_USE", "PUBLIC", "ENTITLEMENT_REQUIRED"]
CONTENT_ACCESS_LEVELS: tuple[ContentAccess, ...] = get_args(ContentAccess)

CONTENT_ACCESS_MEANING: dict[ContentAccess, str] = {
    "INTERNAL_ONLY": "So para raciocinio interno. Nunca vai para a cliente, nem resumido.",
    "SUPPORT_USE": "Suporte e venda podem usar e sintetizar. Citacao literal curta.",
    "PUBLIC": "Pode ser entregue como esta. Preco e link publicos entram aqui.",
    "ENTITLEMENT_REQUIRED": (
        "Material pago. Conhecivel e sintetizavel por quem atende; metodo e receita completos exigem compra verificada."
    ),
}

#: Teto de CITACAO LITERAL, por nivel. Nao e truncamento do que o agente le —
#: e quanto do texto original pode sair entre aspas. Numero pequeno de
#: proposito: citacao curta prova a fonte; citacao longa entrega o produto.
DEFAULT_VERBATIM_LIMITS: dict[ContentAccess, int | None] = {
    "PUBLIC": None,  # sem limite
    "SUPPORT_USE": 320,
    "ENTITLEMENT_REQUIRED": 200,
    "INTERNAL_ONLY": 0,
}


@dataclass(frozen=True)
class DisclosurePolicy:
    """O que pode sair de um conteudo que o agente pode consultar."""

    can_know: bool
    can_summarize: bool
    can_quote: bool
    #: Maximo de caracteres de citacao LITERAL. None = sem limite; 0 = nada.
    max_verbatim_chars: int | None
    can_reveal_full_method: bool
    can_reveal_full_recipe: bool
    requires_entitlement: bool
    reason: str

    @property
    def withheld(self) -> bool:
        """True quando o corpo nao deve nem chegar ao agente."""

        return not self.can_know

    def as_dict(self) -> dict[str, object]:
        return {
            "pode_consultar": self.can_know,
            "pode_sintetizar": self.can_summarize,
            "pode_citar": self.can_quote,
            "maximo_de_citacao_literal": self.max_verbatim_chars,
            "pode_entregar_metodo_completo": self.can_reveal_full_method,
            "pode_entregar_receita_completa": self.can_reveal_full_recipe,
            "exige_compra_verificada": self.requires_entitlement,
            "motivo": self.reason,
        }


def transition_allowed(atual: DocStatus, novo: DocStatus) -> bool:
    return novo in ALLOWED_TRANSITIONS[atual]


def _limite(content_access: ContentAccess, override: int | None) -> int | None:
    return DEFAULT_VERBATIM_LIMITS[content_access] if override is None else override


def decide_disclosure(
    *,
    content_access: ContentAccess,
    agent_is_customer_facing: bool,
    agent_can_know_paid: bool,
    entitlement_verified: bool = False,
    max_verbatim_chars: int | None = None,
) -> DisclosurePolicy:
    """Resolve a policy de divulgacao. Deterministico, sem LLM.

    `entitlement_verified` existe para o dia em que houver verificacao de
    compra. Hoje nenhum chamador passa True — nao ha integracao de pagamento,
    e fingir que ha seria pior do que nao ter.
    """

    limite = _limite(content_access, max_verbatim_chars)

    if content_access == "PUBLIC":
        return DisclosurePolicy(
            can_know=True,
            can_summarize=True,
            can_quote=True,
            max_verbatim_chars=limite,
            can_reveal_full_method=True,
            can_reveal_full_recipe=True,
            requires_entitlement=False,
            reason="Conteudo publico: pode ser entregue como esta.",
        )

    if content_access == "INTERNAL_ONLY":
        # Conhecivel por quem trabalha internamente; nada sai — nem resumo.
        # Resumir um documento interno para a cliente E revelar o documento.
        return DisclosurePolicy(
            can_know=True,
            can_summarize=False,
            can_quote=False,
            max_verbatim_chars=0,
            can_reveal_full_method=False,
            can_reveal_full_recipe=False,
            requires_entitlement=False,
            reason="Documento interno: serve para decidir, nunca para entregar a cliente, nem resumido.",
        )

    if content_access == "SUPPORT_USE":
        if not agent_is_customer_facing:
            return DisclosurePolicy(
                can_know=True,
                can_summarize=False,
                can_quote=False,
                max_verbatim_chars=0,
                can_reveal_full_method=False,
                can_reveal_full_recipe=False,
                requires_entitlement=False,
                reason="Uso de suporte: este agente nao fala com a cliente, entao nao entrega nada.",
            )
        return DisclosurePolicy(
            can_know=True,
            can_summarize=True,
            can_quote=True,
            max_verbatim_chars=limite,
            # Mesmo em SUPPORT_USE: descrever a oferta nao e despejar o
            # material. Metodo e receita completos nunca saem por aqui.
            can_reveal_full_method=False,
            can_reveal_full_recipe=False,
            requires_entitlement=False,
            reason=(
                f"Uso de suporte: pode explicar e sintetizar; citacao literal ate {limite} caracteres. "
                "Metodo e receita completos ficam de fora."
            ),
        )

    # ENTITLEMENT_REQUIRED
    if not agent_can_know_paid:
        return DisclosurePolicy(
            can_know=False,
            can_summarize=False,
            can_quote=False,
            max_verbatim_chars=0,
            can_reveal_full_method=False,
            can_reveal_full_recipe=False,
            requires_entitlement=True,
            reason="Material pago: este agente nao tem permissao nem para consultar.",
        )

    if entitlement_verified:
        return DisclosurePolicy(
            can_know=True,
            can_summarize=True,
            can_quote=True,
            max_verbatim_chars=None,
            can_reveal_full_method=True,
            can_reveal_full_recipe=True,
            requires_entitlement=True,
            reason="Material pago com compra verificada.",
        )

    # O default conservador do material pago: da para atender bem sem
    # entregar o produto.
    return DisclosurePolicy(
        can_know=True,
        can_summarize=True,
        can_quote=True,
        max_verbatim_chars=limite,
        can_reveal_full_method=False,
        can_reveal_full_recipe=False,
        requires_entitlement=True,
        reason=(
            "Material pago: pode ser consultado e descrito para responder corretamente, com citacao "
            f"literal de ate {limite} caracteres. Metodo e receita completos exigem compra verificada, "
            "e nao existe verificacao de compra ainda."
        ),
    )


def verbatim_violation(text: str, policy: DisclosurePolicy) -> bool:
    """O texto passa do teto de citacao literal?

    Existe para o gate de saida que ainda nao foi construido. Nenhum caminho
    da F2.5 o chama para bloquear — declarar isso e mais honesto do que
    deixar parecer que a checagem ja esta ligada.
    """

    if not policy.can_quote:
        return bool(text.strip())
    if policy.max_verbatim_chars is None:
        return False
    return len(text) > policy.max_verbatim_chars
