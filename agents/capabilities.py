"""
Capability Policy — o que cada agente esta AUTORIZADO a fazer.

Camada separada de Knowledge e de Instructions, de proposito:

- `instructions` dizem COMO agir — e sao texto que o modelo pode contornar;
- `KNOWLEDGE_POLICIES` dizem O QUE consultar;
- `CAPABILITY_POLICY` (aqui) diz O QUE PODE FAZER — e e verificado em codigo.

Por que nao confiar so em instructions: "voce nunca da desconto" e uma frase
no prompt. Um pedido insistente, um jailbreak ou uma alucinacao contornam
frase. Nao contornam um dict que responde DENIED.

100% deterministico, sem LLM — mesma decisao de design do
`orchestration/quality_control.py` e do `orchestration/evidence_gate.py`.

Fail-closed em toda porta:
- agente desconhecido -> erro explicito, nunca "permitido por omissao";
- capability desconhecida -> erro explicito;
- capability nao declarada para o agente -> DENIED.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from agents.knowledge_policies import KNOWLEDGE_POLICIES

Decision = Literal["ALLOWED", "DENIED", "HUMAN_REQUIRED"]


class Capability(str, Enum):
    """Acoes que um agente pode tentar executar.

    Taxonomia colada na arquitetura REAL: cada item ou ja existe no sistema,
    ou tem uma Tool prevista que vai precisar dele (ver TOOL_REQUIREMENTS).
    """

    # --- Leitura ---
    READ_KNOWLEDGE = "READ_KNOWLEDGE"
    READ_BUSINESS_DATA = "READ_BUSINESS_DATA"
    READ_CUSTOMER_DATA = "READ_CUSTOMER_DATA"
    READ_ANALYTICS = "READ_ANALYTICS"

    # --- Conversa com cliente ---
    ANSWER_CUSTOMER = "ANSWER_CUSTOMER"
    PREPARE_SUPPORT_RESPONSE = "PREPARE_SUPPORT_RESPONSE"
    PREPARE_SALES_RESPONSE = "PREPARE_SALES_RESPONSE"

    # --- Producao de conteudo ---
    CREATE_CONTENT = "CREATE_CONTENT"
    EDIT_CONTENT = "EDIT_CONTENT"
    REVIEW_CONTENT = "REVIEW_CONTENT"
    CREATE_VIDEO_SPEC = "CREATE_VIDEO_SPEC"
    RENDER_VIDEO = "RENDER_VIDEO"

    # --- Analise e proposta ---
    CREATE_REPORT = "CREATE_REPORT"
    PROPOSE_STRATEGY = "PROPOSE_STRATEGY"
    PROPOSE_OFFER = "PROPOSE_OFFER"
    PROPOSE_AGENT_IMPROVEMENT = "PROPOSE_AGENT_IMPROVEMENT"
    MANAGE_KNOWLEDGE_SOURCES = "MANAGE_KNOWLEDGE_SOURCES"

    # --- Relacionamento ---
    CREATE_FOLLOW_UP = "CREATE_FOLLOW_UP"

    # --- Sensiveis: nunca ALLOWED para agente nenhum ---
    CHANGE_PRICE = "CHANGE_PRICE"
    GRANT_DISCOUNT = "GRANT_DISCOUNT"
    GRANT_REFUND = "GRANT_REFUND"
    CHANGE_POLICY = "CHANGE_POLICY"
    PUBLISH_CONTENT = "PUBLISH_CONTENT"
    SEND_CAMPAIGN = "SEND_CAMPAIGN"
    PROMOTE_AGENT_VERSION = "PROMOTE_AGENT_VERSION"


# Capabilities que NENHUM agente pode ter como ALLOWED, em nenhuma
# circunstancia. Compromisso financeiro, mudanca de regra de negocio e
# qualquer coisa publica sao decisao da Judith — nao de um modelo.
# Ha teste que falha se alguem conceder ALLOWED a uma destas.
NEVER_AUTONOMOUS: frozenset[Capability] = frozenset(
    {
        Capability.CHANGE_PRICE,
        Capability.GRANT_DISCOUNT,
        Capability.GRANT_REFUND,
        Capability.CHANGE_POLICY,
        Capability.PUBLISH_CONTENT,
        Capability.SEND_CAMPAIGN,
        Capability.PROMOTE_AGENT_VERSION,
        Capability.RENDER_VIDEO,
    }
)

# Todo agente de negocio pode ler a propria whitelist de Knowledge. Nao ha
# risco: a whitelist ja limita O QUE ele alcanca.
_BASE: dict[Capability, Decision] = {Capability.READ_KNOWLEDGE: "ALLOWED"}


def _policy(**capabilities: Decision) -> dict[Capability, Decision]:
    return {**_BASE, **{Capability[name]: decision for name, decision in capabilities.items()}}


# ---------------------------------------------------------------------------
# Politica por agente
# ---------------------------------------------------------------------------
#
# Regra de leitura: o que NAO esta listado e DENIED. A lista e o que o papel
# precisa, nao o que seria conveniente.

CAPABILITY_POLICY: dict[str, dict[Capability, Decision]] = {
    # --- Direcao ---
    "cmo": _policy(
        READ_ANALYTICS="ALLOWED",
        PROPOSE_STRATEGY="ALLOWED",
        CREATE_REPORT="ALLOWED",
        PROPOSE_OFFER="HUMAN_REQUIRED",
        CHANGE_PRICE="HUMAN_REQUIRED",
        PUBLISH_CONTENT="HUMAN_REQUIRED",
        SEND_CAMPAIGN="HUMAN_REQUIRED",
    ),
    "brand-architect": _policy(
        PROPOSE_STRATEGY="ALLOWED",
        REVIEW_CONTENT="ALLOWED",
        PUBLISH_CONTENT="DENIED",  # aprovacao final e brand-reviewer + Judith
    ),
    "marketing-director": _policy(
        READ_ANALYTICS="ALLOWED",
        PROPOSE_STRATEGY="ALLOWED",
        CREATE_REPORT="ALLOWED",
        PROPOSE_OFFER="HUMAN_REQUIRED",
        SEND_CAMPAIGN="HUMAN_REQUIRED",
        PUBLISH_CONTENT="HUMAN_REQUIRED",
    ),
    # --- Content & Social ---
    "social-media-manager": _policy(
        READ_ANALYTICS="ALLOWED",
        CREATE_CONTENT="ALLOWED",
        PUBLISH_CONTENT="HUMAN_REQUIRED",
    ),
    "market-trend-intelligence": _policy(CREATE_REPORT="ALLOWED"),
    "hook-finder": _policy(CREATE_CONTENT="ALLOWED"),
    "script-writer": _policy(CREATE_CONTENT="ALLOWED", EDIT_CONTENT="ALLOWED"),
    "caption-writer": _policy(CREATE_CONTENT="ALLOWED", EDIT_CONTENT="ALLOWED"),
    "visual-creative": _policy(CREATE_CONTENT="ALLOWED"),
    "video-editor": _policy(
        CREATE_VIDEO_SPEC="ALLOWED",
        # Renderizar e efeito externo (gasta recurso, produz arquivo). O Agent
        # decide a edicao; acionar o motor Remotion e outra coisa.
        RENDER_VIDEO="HUMAN_REQUIRED",
    ),
    # --- Growth & Sales ---
    "offer-funnel-strategist": _policy(
        READ_ANALYTICS="ALLOWED",
        PROPOSE_OFFER="ALLOWED",  # propor e o trabalho dele
        CHANGE_PRICE="HUMAN_REQUIRED",  # aplicar, nao
        GRANT_DISCOUNT="HUMAN_REQUIRED",
    ),
    "sales-conversion-agent": _policy(
        PREPARE_SALES_RESPONSE="ALLOWED",
        ANSWER_CUSTOMER="ALLOWED",
        READ_CUSTOMER_DATA="ALLOWED",
        GRANT_DISCOUNT="HUMAN_REQUIRED",
        CHANGE_PRICE="DENIED",
    ),
    "crm-lifecycle-agent": _policy(
        READ_CUSTOMER_DATA="ALLOWED",
        CREATE_FOLLOW_UP="ALLOWED",  # redigir
        SEND_CAMPAIGN="HUMAN_REQUIRED",  # disparar
    ),
    # --- Customer Experience ---
    "community-dm-agent": _policy(
        ANSWER_CUSTOMER="ALLOWED",
        READ_CUSTOMER_DATA="ALLOWED",
    ),
    "customer-support-agent": _policy(
        PREPARE_SUPPORT_RESPONSE="ALLOWED",
        ANSWER_CUSTOMER="ALLOWED",
        READ_CUSTOMER_DATA="ALLOWED",
        GRANT_REFUND="HUMAN_REQUIRED",  # BUSINESS_RULES 11
        CHANGE_POLICY="DENIED",
    ),
    # --- Intelligence ---
    "analytics-bi-agent": _policy(
        READ_ANALYTICS="ALLOWED",
        READ_BUSINESS_DATA="ALLOWED",
        CREATE_REPORT="ALLOWED",
    ),
    "customer-insights-agent": _policy(
        READ_CUSTOMER_DATA="ALLOWED",
        CREATE_REPORT="ALLOWED",
    ),
    "knowledge-manager": _policy(
        MANAGE_KNOWLEDGE_SOURCES="ALLOWED",
        CREATE_REPORT="ALLOWED",
        # Governa fontes, mas nao decide qual fato de negocio e verdadeiro.
        CHANGE_POLICY="DENIED",
    ),
    "ai-performance-evals-agent": _policy(
        READ_ANALYTICS="ALLOWED",
        CREATE_REPORT="ALLOWED",
        PROPOSE_AGENT_IMPROVEMENT="ALLOWED",
        PROMOTE_AGENT_VERSION="HUMAN_REQUIRED",
    ),
    # --- Governanca ---
    "brand-reviewer": _policy(
        REVIEW_CONTENT="ALLOWED",
        # Aprova para a Judith, nao para o publico.
        PUBLISH_CONTENT="DENIED",
    ),
}


# ---------------------------------------------------------------------------
# Tool Authorization (Fase 7) — preparado, sem integracao real
# ---------------------------------------------------------------------------
#
# Toda Tool futura declara a capability que exige. Antes de executar:
#   agent_id + required_capability -> check(...) -> ALLOWED?
# Nenhuma destas Tools existe hoje. O mapa existe para que a integracao
# nasca ja com a checagem, em vez de ganhar autorizacao depois.

TOOL_REQUIREMENTS: dict[str, Capability] = {
    "InstagramPublishTool": Capability.PUBLISH_CONTENT,
    "InstagramInsightsReader": Capability.READ_ANALYTICS,
    "KiwifySalesReader": Capability.READ_BUSINESS_DATA,
    "KiwifyRefundTool": Capability.GRANT_REFUND,
    "CrmContactReader": Capability.READ_CUSTOMER_DATA,
    "CrmCampaignSender": Capability.SEND_CAMPAIGN,
    "RemotionRenderTool": Capability.RENDER_VIDEO,
    "PriceUpdateTool": Capability.CHANGE_PRICE,
}


class UnknownAgentError(KeyError):
    """agent_id sem politica de capability declarada."""


class UnknownCapabilityError(KeyError):
    """capability que nao existe na taxonomia."""


@dataclass(frozen=True)
class CapabilityCheck:
    """Resultado de uma verificacao. `permitted` so e True em ALLOWED."""

    agent_id: str
    capability: Capability
    decision: Decision
    reason: str

    @property
    def permitted(self) -> bool:
        return self.decision == "ALLOWED"

    @property
    def needs_human(self) -> bool:
        return self.decision == "HUMAN_REQUIRED"


def check(agent_id: str, capability: Capability | str, *, human_approved: bool = False) -> CapabilityCheck:
    """Pode este agente executar esta acao?

    `human_approved` só pode vir de uma aprovacao humana REAL do runtime
    (ex.: `HumanReview` do Agno). Texto do LLM dizendo "a Judith aprovou"
    nunca chega aqui — quem chama e codigo, nao modelo.
    """

    if isinstance(capability, str):
        try:
            capability = Capability(capability)
        except ValueError as exc:
            validas = ", ".join(sorted(c.value for c in Capability))
            raise UnknownCapabilityError(f'capability "{capability}" nao existe. Validas: {validas}') from exc

    if agent_id not in CAPABILITY_POLICY:
        conhecidos = ", ".join(sorted(CAPABILITY_POLICY))
        raise UnknownAgentError(f'agente "{agent_id}" nao tem politica de capability. Conhecidos: {conhecidos}')

    # Nao declarado = DENIED. A politica lista o que o papel precisa; o resto
    # nao e permitido por omissao.
    decision = CAPABILITY_POLICY[agent_id].get(capability, "DENIED")

    if decision == "HUMAN_REQUIRED" and human_approved:
        return CapabilityCheck(
            agent_id, capability, "ALLOWED", "exigia aprovacao humana e ela foi registrada pelo runtime"
        )

    reasons = {
        "ALLOWED": "autorizado pela politica do agente",
        "DENIED": "nao autorizado para este papel",
        "HUMAN_REQUIRED": "exige aprovacao humana explicita",
    }
    return CapabilityCheck(agent_id, capability, decision, reasons[decision])


def capabilities_of(agent_id: str) -> dict[Capability, Decision]:
    """Politica completa de um agente (para auditoria e documentacao)."""

    if agent_id not in CAPABILITY_POLICY:
        raise UnknownAgentError(f'agente "{agent_id}" nao tem politica de capability')
    return dict(CAPABILITY_POLICY[agent_id])


def required_capability_for(tool_name: str) -> Capability | None:
    """Capability exigida por uma Tool futura. None se a Tool e desconhecida."""

    return TOOL_REQUIREMENTS.get(tool_name)


# Toda politica cobre exatamente os mesmos agentes que a de Knowledge. Sem
# isto, um agente novo poderia ganhar Knowledge sem ganhar politica — e o
# check falharia em runtime, nao no import.
assert set(CAPABILITY_POLICY) == set(KNOWLEDGE_POLICIES), (
    "CAPABILITY_POLICY e KNOWLEDGE_POLICIES precisam cobrir os mesmos agentes: "
    f"so em capability={set(CAPABILITY_POLICY) - set(KNOWLEDGE_POLICIES)}, "
    f"so em knowledge={set(KNOWLEDGE_POLICIES) - set(CAPABILITY_POLICY)}"
)
