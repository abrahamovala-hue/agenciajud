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
de codigo que faca isso: `confirm_document()` exige `approved_by` de um
humano nomeado, e nada no backfill chama essa funcao.

**CAN_KNOW != CAN_REVEAL.** Poder consultar um conteudo para responder certo
nao autoriza entregar o conteudo. Um agente de suporte precisa saber o que o
ebook ensina para nao contradizer o produto; isso nao o autoriza a colar o
capitulo na conversa. As duas perguntas tem respostas separadas em
`DisclosureDecision`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

# --- Camadas ----------------------------------------------------------------

Layer = Literal["L1", "L2", "L3"]
LAYERS: tuple[Layer, ...] = get_args(Layer)

LAYER_NAMES: dict[Layer, str] = {
    "L1": "JUDITH — o que a Judith sabe, pensa, ensina ou definiu",
    "L2": "PROFESSIONAL — conhecimento de oficio curado deliberadamente",
    "L3": "BUSINESS — fato operacional do negocio (produto, preco, politica)",
}

# --- Fonte ------------------------------------------------------------------

SourceKind = Literal["judith", "professional", "business"]
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

# --- Disclosure (conteudo pago) ---------------------------------------------

ContentAccess = Literal["INTERNAL_ONLY", "SUPPORT_USE", "PUBLIC", "ENTITLEMENT_REQUIRED"]
CONTENT_ACCESS_LEVELS: tuple[ContentAccess, ...] = get_args(ContentAccess)

CONTENT_ACCESS_MEANING: dict[ContentAccess, str] = {
    "INTERNAL_ONLY": "So para raciocinio interno. Nunca vai para a cliente, nem resumido.",
    "SUPPORT_USE": "Suporte e venda podem usar para responder. Entrega em trecho curto, nunca integral.",
    "PUBLIC": "Pode ser entregue como esta. Preco e link publicos entram aqui.",
    "ENTITLEMENT_REQUIRED": "Material pago. Conhecivel internamente; entrega exige compra verificada.",
}

#: Teto de caracteres que SUPPORT_USE pode entregar de uma vez.
#: E o unico mecanismo determinístico de "nao despeje o produto inteiro" que
#: existe: instrucao no prompt e pedido, corte e garantia.
SUPPORT_USE_EXCERPT_CHARS = 600


@dataclass(frozen=True)
class DisclosureDecision:
    """O que o agente pode fazer com um conteudo que ele PODE consultar."""

    can_know: bool
    can_reveal: bool
    #: Quantos caracteres do corpo podem ser entregues. None = sem limite.
    excerpt_chars: int | None
    reason: str

    @property
    def withheld(self) -> bool:
        """True quando o corpo nao deve nem chegar ao agente."""

        return not self.can_know


def transition_allowed(atual: DocStatus, novo: DocStatus) -> bool:
    return novo in ALLOWED_TRANSITIONS[atual]


def decide_disclosure(
    *,
    content_access: ContentAccess,
    agent_is_customer_facing: bool,
    agent_can_know_paid: bool,
    entitlement_verified: bool = False,
) -> DisclosureDecision:
    """Resolve CAN_KNOW e CAN_REVEAL. Deterministico, sem LLM.

    `entitlement_verified` existe para o dia em que houver verificacao de
    compra. Hoje nenhum chamador passa True — nao ha integracao de pagamento,
    e fingir que ha seria pior do que nao ter.
    """

    if content_access == "PUBLIC":
        return DisclosureDecision(True, True, None, "Conteudo publico.")

    if content_access == "INTERNAL_ONLY":
        # Conhecivel por quem trabalha internamente; nunca entregue.
        return DisclosureDecision(
            can_know=True,
            can_reveal=False,
            excerpt_chars=0,
            reason="Documento interno: serve para decidir, nunca para entregar a cliente.",
        )

    if content_access == "SUPPORT_USE":
        if not agent_is_customer_facing:
            return DisclosureDecision(True, False, 0, "Uso de suporte: agente nao fala com cliente.")
        return DisclosureDecision(
            can_know=True,
            can_reveal=True,
            excerpt_chars=SUPPORT_USE_EXCERPT_CHARS,
            reason=f"Uso de suporte: no maximo {SUPPORT_USE_EXCERPT_CHARS} caracteres por vez, nunca o documento inteiro.",
        )

    # ENTITLEMENT_REQUIRED
    if not agent_can_know_paid:
        return DisclosureDecision(
            can_know=False,
            can_reveal=False,
            excerpt_chars=0,
            reason="Material pago: este agente nao tem permissao nem para consultar.",
        )
    if entitlement_verified:
        return DisclosureDecision(True, True, None, "Material pago com compra verificada.")
    return DisclosureDecision(
        can_know=True,
        can_reveal=False,
        excerpt_chars=0,
        reason=(
            "Material pago: pode ser consultado para responder corretamente, mas o conteudo "
            "nao pode ser entregue sem compra verificada. Nao existe verificacao de compra ainda."
        ),
    )
