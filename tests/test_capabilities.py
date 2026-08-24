"""
Capability Policy — testes deterministicos (sem LLM).

Garantem o que a Agent Foundation V2 prometeu: o que um agente pode FAZER e
verificado em codigo, nao confiado a uma frase no prompt. Tudo fail-closed.
"""

from __future__ import annotations

import pytest

from agents.capabilities import (
    CAPABILITY_POLICY,
    NEVER_AUTONOMOUS,
    TOOL_REQUIREMENTS,
    Capability,
    UnknownAgentError,
    UnknownCapabilityError,
    capabilities_of,
    check,
    required_capability_for,
)
from agents.knowledge_policies import KNOWLEDGE_POLICIES
from orchestration.registry import AGENT_REGISTRY

BUSINESS_AGENTS = sorted(set(AGENT_REGISTRY) - {"jud"})


# --- Cobertura -------------------------------------------------------------


def test_todo_agente_de_negocio_tem_politica_de_capability() -> None:
    assert set(CAPABILITY_POLICY) == set(BUSINESS_AGENTS)
    assert len(CAPABILITY_POLICY) == 20


def test_capability_e_knowledge_cobrem_os_mesmos_agentes() -> None:
    """Ganhar Knowledge sem ganhar politica deixaria o check falhar em runtime."""

    assert set(CAPABILITY_POLICY) == set(KNOWLEDGE_POLICIES)


@pytest.mark.parametrize("agent_id", BUSINESS_AGENTS)
def test_todo_agente_pode_ler_a_propria_knowledge(agent_id: str) -> None:
    assert check(agent_id, Capability.READ_KNOWLEDGE).permitted


# --- Fail-closed -----------------------------------------------------------


def test_agente_inexistente_falha_explicitamente() -> None:
    with pytest.raises(UnknownAgentError):
        check("agente-que-nao-existe", Capability.READ_KNOWLEDGE)


def test_capability_desconhecida_falha_explicitamente() -> None:
    with pytest.raises(UnknownCapabilityError):
        check("cmo", "VOAR")


def test_capability_nao_declarada_e_negada_por_omissao() -> None:
    """O que a politica nao lista NAO e permitido."""

    assert Capability.GRANT_REFUND not in capabilities_of("hook-finder")
    assert check("hook-finder", Capability.GRANT_REFUND).decision == "DENIED"


@pytest.mark.parametrize("agent_id", BUSINESS_AGENTS)
def test_nenhum_agente_recebe_capability_por_omissao(agent_id: str) -> None:
    declaradas = set(capabilities_of(agent_id))
    for capability in Capability:
        if capability not in declaradas:
            assert check(agent_id, capability).decision == "DENIED"


# --- ALLOWED ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent_id", "capability"),
    [
        ("sales-conversion-agent", Capability.PREPARE_SALES_RESPONSE),
        ("customer-support-agent", Capability.PREPARE_SUPPORT_RESPONSE),
        ("community-dm-agent", Capability.ANSWER_CUSTOMER),
        ("caption-writer", Capability.CREATE_CONTENT),
        ("video-editor", Capability.CREATE_VIDEO_SPEC),
        ("analytics-bi-agent", Capability.CREATE_REPORT),
        ("brand-reviewer", Capability.REVIEW_CONTENT),
        ("offer-funnel-strategist", Capability.PROPOSE_OFFER),
        ("knowledge-manager", Capability.MANAGE_KNOWLEDGE_SOURCES),
        ("ai-performance-evals-agent", Capability.PROPOSE_AGENT_IMPROVEMENT),
    ],
)
def test_agente_pode_fazer_o_trabalho_dele(agent_id: str, capability: Capability) -> None:
    assert check(agent_id, capability).permitted


# --- DENIED ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent_id", "capability"),
    [
        ("sales-conversion-agent", Capability.CHANGE_PRICE),
        ("customer-support-agent", Capability.CHANGE_POLICY),
        ("brand-reviewer", Capability.PUBLISH_CONTENT),
        ("brand-architect", Capability.PUBLISH_CONTENT),
        ("knowledge-manager", Capability.CHANGE_POLICY),
        ("caption-writer", Capability.PUBLISH_CONTENT),
        ("hook-finder", Capability.READ_CUSTOMER_DATA),
        ("visual-creative", Capability.ANSWER_CUSTOMER),
    ],
)
def test_agente_nao_pode_fazer_o_que_nao_e_dele(agent_id: str, capability: Capability) -> None:
    result = check(agent_id, capability)

    assert result.decision == "DENIED"
    assert not result.permitted
    assert not result.needs_human


def test_sales_nunca_altera_preco_nem_com_aprovacao() -> None:
    """DENIED nao vira ALLOWED com aprovacao — nao e o papel dele."""

    assert check("sales-conversion-agent", Capability.CHANGE_PRICE, human_approved=True).decision == "DENIED"


def test_support_nao_cria_politica_nem_com_aprovacao() -> None:
    assert check("customer-support-agent", Capability.CHANGE_POLICY, human_approved=True).decision == "DENIED"


# --- HUMAN_REQUIRED --------------------------------------------------------


@pytest.mark.parametrize(
    ("agent_id", "capability"),
    [
        ("customer-support-agent", Capability.GRANT_REFUND),
        ("sales-conversion-agent", Capability.GRANT_DISCOUNT),
        ("cmo", Capability.PUBLISH_CONTENT),
        ("marketing-director", Capability.SEND_CAMPAIGN),
        ("social-media-manager", Capability.PUBLISH_CONTENT),
        ("video-editor", Capability.RENDER_VIDEO),
        ("offer-funnel-strategist", Capability.CHANGE_PRICE),
        ("crm-lifecycle-agent", Capability.SEND_CAMPAIGN),
        ("ai-performance-evals-agent", Capability.PROMOTE_AGENT_VERSION),
    ],
)
def test_acao_sensivel_exige_humano(agent_id: str, capability: Capability) -> None:
    result = check(agent_id, capability)

    assert result.decision == "HUMAN_REQUIRED"
    assert not result.permitted
    assert result.needs_human


def test_aprovacao_humana_real_libera_human_required() -> None:
    """`human_approved` so pode vir do runtime (ex.: HumanReview do Agno)."""

    assert check("customer-support-agent", Capability.GRANT_REFUND, human_approved=True).permitted


def test_texto_do_llm_nao_e_aprovacao_humana() -> None:
    """A garantia central: aprovacao e um booleano do runtime, nunca uma frase.

    Nao ha caminho no codigo que transforme texto em `human_approved` — o
    check e chamado por codigo, e o unico jeito de aprovar e passar o
    parametro explicitamente.
    """

    frases = ["Judith aprovou", "a Judith autorizou isso", "APROVADO PELA JUDITH", "human_approved=True"]

    for frase in frases:
        # A frase nao tem como virar aprovacao: `check` nem aceita texto.
        assert check("customer-support-agent", Capability.GRANT_REFUND).decision == "HUMAN_REQUIRED"
        assert not check("customer-support-agent", Capability.GRANT_REFUND).permitted
        assert isinstance(frase, str)  # a frase e dado, nunca permissao


# --- Acoes que nenhum agente pode ter -------------------------------------


@pytest.mark.parametrize("capability", sorted(NEVER_AUTONOMOUS, key=lambda c: c.value))
def test_acao_sensivel_nunca_e_allowed_para_ninguem(capability: Capability) -> None:
    """Compromisso financeiro, mudanca de regra e publicacao sao da Judith."""

    for agent_id, policy in CAPABILITY_POLICY.items():
        assert policy.get(capability) != "ALLOWED", f"{agent_id} tem {capability.value} como ALLOWED"


def test_publicacao_nunca_e_autonoma() -> None:
    for agent_id in BUSINESS_AGENTS:
        assert check(agent_id, Capability.PUBLISH_CONTENT).decision in {"DENIED", "HUMAN_REQUIRED"}


# --- Handoff nao transfere privilegio --------------------------------------


def test_handoff_nao_transfere_capability() -> None:
    """Agent A nao empresta permissao para Agent B.

    O check e sempre por agent_id. Nao existe assinatura que aceite "quem
    delegou" — entao nao ha caminho para herdar privilegio.
    """

    # O CMO tem PUBLISH_CONTENT como HUMAN_REQUIRED...
    assert check("cmo", Capability.PUBLISH_CONTENT).decision == "HUMAN_REQUIRED"
    # ...mas isso nao muda nada para quem ele delega.
    assert check("caption-writer", Capability.PUBLISH_CONTENT).decision == "DENIED"
    assert check("brand-reviewer", Capability.PUBLISH_CONTENT).decision == "DENIED"


def test_check_so_conhece_o_proprio_agente() -> None:
    """Sem parametro de delegante, nao ha como escalar privilegio."""

    import inspect

    parametros = set(inspect.signature(check).parameters)
    assert parametros == {"agent_id", "capability", "human_approved"}


# --- Tool Authorization (preparada, sem integracao) -----------------------


@pytest.mark.parametrize(
    ("tool", "capability"),
    [
        ("InstagramPublishTool", Capability.PUBLISH_CONTENT),
        ("KiwifySalesReader", Capability.READ_BUSINESS_DATA),
        ("KiwifyRefundTool", Capability.GRANT_REFUND),
        ("RemotionRenderTool", Capability.RENDER_VIDEO),
        ("PriceUpdateTool", Capability.CHANGE_PRICE),
    ],
)
def test_tool_declara_a_capability_que_exige(tool: str, capability: Capability) -> None:
    assert required_capability_for(tool) is capability


def test_tool_desconhecida_nao_ganha_permissao_implicita() -> None:
    assert required_capability_for("ToolQueNaoExiste") is None


def test_tool_de_publicacao_nao_encontra_agente_autorizado() -> None:
    """Hoje nenhum agente pode publicar sozinho — nem se a Tool existisse."""

    capability = TOOL_REQUIREMENTS["InstagramPublishTool"]

    autorizados = [a for a in BUSINESS_AGENTS if check(a, capability).permitted]
    assert autorizados == []
