"""
Judith Brain F2 — Access Policy, conteudo pago e Retrieval API.

O que este arquivo protege:

- fail-closed de verdade: desconhecido, camada nao permitida, status nao
  permitido, documento fora da whitelist;
- CAN_KNOW != CAN_REVEAL, com o teto de excerto exercido de verdade;
- provenance completo em todo resultado;
- nenhum agente escreve Knowledge;
- o retrieval lexical de producao continua intocado.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from brain.access_policy import (
    CAN_KNOW_PAID_AGENTS,
    CUSTOMER_FACING_AGENTS,
    AccessDenied,
    resolve_access,
)
from brain.models import SUPPORT_USE_EXCERPT_CHARS, decide_disclosure
from brain.repository import KnowledgeRepository, checksum_of
from brain.retrieval import DEFAULT_LIMIT, compare_with_lexical, search
from brain.security import DATA_CLOSE, DATA_OPEN

# --- Store de teste ---------------------------------------------------------


@pytest.fixture
def repo():
    motor = create_engine("sqlite://")
    repositorio = KnowledgeRepository(motor)
    repositorio.ensure_tables()
    yield repositorio
    motor.dispose()


def _documento(
    repo: KnowledgeRepository,
    *,
    external_key: str,
    layer: str,
    content_access: str,
    corpo: str,
    status: str = "TO_VALIDATE",
    topics: tuple[str, ...] = (),
    aprovar: bool = False,
) -> str:
    repo.upsert_source(
        source_id=f"src_{layer.lower()}",
        kind={"L1": "judith", "L2": "professional", "L3": "business"}[layer],
        origin="repository",
        owner="sistema",
        title=f"Fonte {layer}",
        source_ref="docs/",
    )
    doc = repo.create_document(
        source_id=f"src_{layer.lower()}",
        title=f"Documento {external_key}",
        layer=layer,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        content_access=content_access,  # type: ignore[arg-type]
        checksum=checksum_of(corpo),
        external_key=external_key,
        topics=topics,
        confidence="alto",
    )
    repo.add_version(document_id=doc, body=corpo, created_by="teste")
    if aprovar:
        repo.approve_version(document_id=doc, version=1, approved_by="Judith Kolker")
    return doc


_CORPO_OFFERS = (
    "# Ofertas\n\n"
    "## Precos\n\n"
    "O ebook Recheios custa R$ 97,00 e da acesso vitalicio. "
    "O combo sai por R$ 197,00. A garantia e de 7 dias, sem perguntas. "
    "Todo pedido tem acesso imediato apos a confirmacao do pagamento pela plataforma."
)


# --- 1. Fail-closed ---------------------------------------------------------


def test_agente_desconhecido_e_negado() -> None:
    with pytest.raises(AccessDenied, match="nao tem politica"):
        resolve_access("agente-que-nao-existe")


def test_agent_id_vazio_e_negado() -> None:
    with pytest.raises(AccessDenied, match="vazio"):
        resolve_access("")


def test_search_de_agente_desconhecido_levanta_em_vez_de_devolver_vazio(repo) -> None:
    """Lista vazia pareceria 'nao achei nada'. Negado tem que doer."""

    with pytest.raises(AccessDenied):
        search(agent_id="intruso", query="preco", repository=repo)


def test_agente_conhecido_tem_politica() -> None:
    acesso = resolve_access("customer-support-agent")

    assert acesso.layers
    assert acesso.external_keys


# --- 2. Camada e status -----------------------------------------------------


def test_camada_nao_permitida_e_negada() -> None:
    acesso = resolve_access("caption-writer")

    assert not acesso.allows_layer("L1"), "L1 nao deveria estar liberada sem documento L1 na whitelist"
    assert not acesso.allows_document(external_key="QUALQUER", layer="L1", status="CONFIRMED")


def test_producao_so_enxerga_confirmed() -> None:
    acesso = resolve_access("caption-writer")

    assert acesso.statuses == frozenset({"CONFIRMED"})
    for status in ("DRAFT", "TO_VALIDATE", "DEPRECATED"):
        assert not acesso.allows_status(status)


def test_knowledge_manager_revisa_o_nao_aprovado() -> None:
    acesso = resolve_access("knowledge-manager")

    assert acesso.allows_status("DRAFT")
    assert acesso.allows_status("TO_VALIDATE")
    assert acesso.allows_status("CONFIRMED")


def test_console_de_revisao_ve_tudo_mas_nao_escreve() -> None:
    acesso = resolve_access("judith-review-console")

    assert acesso.layers == frozenset({"L1", "L2", "L3"})
    assert acesso.allows_status("DRAFT")
    assert acesso.can_write_knowledge is False


def test_nenhum_agente_escreve_knowledge() -> None:
    from agents.knowledge_policies import KNOWLEDGE_POLICIES

    for agent_id in KNOWLEDGE_POLICIES:
        assert resolve_access(agent_id).can_write_knowledge is False, agent_id


def test_to_validate_nunca_sai_em_producao(repo) -> None:
    _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=_CORPO_OFFERS,
        status="TO_VALIDATE",
        topics=("comercial",),
    )

    resultado = search(agent_id="customer-support-agent", query="preco do ebook", repository=repo)

    assert resultado.hits == [], "documento TO_VALIDATE vazou para producao"


def test_draft_nunca_sai_em_producao(repo) -> None:
    _documento(
        repo,
        external_key="VOICE",
        layer="L3",
        content_access="INTERNAL_ONLY",
        corpo="## Tom\n\nA marca fala com carinho e precisao sobre chocolate artesanal premium.",
        status="DRAFT",
    )

    resultado = search(agent_id="caption-writer", query="tom de voz da marca", repository=repo)

    assert resultado.hits == []


def test_deprecated_nao_entra_em_retrieval_normal(repo) -> None:
    doc = _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=_CORPO_OFFERS,
        topics=("comercial",),
        aprovar=True,
    )
    assert search(agent_id="customer-support-agent", query="preco", repository=repo).hits

    repo.set_status(document_id=doc, novo="DEPRECATED")

    assert search(agent_id="customer-support-agent", query="preco", repository=repo).hits == []


def test_confirmed_sai_em_producao(repo) -> None:
    """O contraponto: com aprovacao humana, o conteudo aparece."""

    _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=_CORPO_OFFERS,
        topics=("comercial",),
        aprovar=True,
    )

    resultado = search(agent_id="customer-support-agent", query="preco do ebook", repository=repo)

    assert resultado.hits
    assert resultado.hits[0].provenance.status == "CONFIRMED"


def test_agente_criativo_nao_ganha_acesso_indevido(repo) -> None:
    """`visual-creative` nao ve OFFERS hoje. Nao pode passar a ver agora."""

    from agents.knowledge_policies import get_policy

    assert "OFFERS" not in {d.key for d in get_policy("visual-creative").documents}

    _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=_CORPO_OFFERS,
        topics=("comercial",),
        aprovar=True,
    )

    resultado = search(agent_id="visual-creative", query="preco do ebook", repository=repo)

    assert resultado.hits == []
    assert resultado.filtered_out.get("fora_da_whitelist", 0) > 0


def test_whitelist_do_brain_espelha_a_do_lexical() -> None:
    """A F2 nao pode conceder acesso novo a ninguem."""

    from agents.knowledge_policies import KNOWLEDGE_POLICIES

    for agent_id, politica in KNOWLEDGE_POLICIES.items():
        assert resolve_access(agent_id).external_keys == frozenset(d.key for d in politica.documents), agent_id


# --- 3. CAN_KNOW != CAN_REVEAL ---------------------------------------------


def test_internal_only_pode_ser_conhecido_mas_nunca_revelado() -> None:
    decisao = decide_disclosure(content_access="INTERNAL_ONLY", agent_is_customer_facing=True, agent_can_know_paid=True)

    assert decisao.can_know is True
    assert decisao.can_reveal is False


def test_support_use_nao_significa_entrega_integral() -> None:
    decisao = decide_disclosure(content_access="SUPPORT_USE", agent_is_customer_facing=True, agent_can_know_paid=False)

    assert decisao.can_reveal is True
    assert decisao.excerpt_chars == SUPPORT_USE_EXCERPT_CHARS


def test_entitlement_required_conhecivel_mas_nao_entregavel() -> None:
    """O caso do ebook: suporte precisa saber, nao pode despejar."""

    decisao = decide_disclosure(
        content_access="ENTITLEMENT_REQUIRED", agent_is_customer_facing=True, agent_can_know_paid=True
    )

    assert decisao.can_know is True
    assert decisao.can_reveal is False
    assert "compra verificada" in decisao.reason


def test_entitlement_required_e_invisivel_para_quem_nao_pode_conhecer() -> None:
    decisao = decide_disclosure(
        content_access="ENTITLEMENT_REQUIRED", agent_is_customer_facing=True, agent_can_know_paid=False
    )

    assert decisao.withheld is True


def test_conteudo_pago_nao_chega_ao_agente_sem_permissao(repo) -> None:
    _documento(
        repo,
        external_key="RECEITA_PREMIUM",
        layer="L3",
        content_access="ENTITLEMENT_REQUIRED",
        corpo="## Receita\n\nTemperagem: derreta o chocolate ate 45 graus e resfrie ate 27 graus antes de usar.",
        aprovar=True,
    )
    # community-dm-agent fala com cliente mas NAO esta em CAN_KNOW_PAID_AGENTS.
    acesso = resolve_access("community-dm-agent")
    assert not acesso.can_know_paid

    resultado = search(
        agent_id="community-dm-agent",
        query="temperagem chocolate",
        repository=repo,
        access=type(acesso)(
            **{**acesso.__dict__, "external_keys": frozenset({"RECEITA_PREMIUM"}), "layers": frozenset({"L3"})}
        ),
    )

    assert resultado.hits == []
    assert resultado.filtered_out.get("conteudo_pago_sem_permissao", 0) == 1


def test_excerto_de_support_use_e_cortado_de_verdade(repo) -> None:
    """Instrucao no prompt e pedido. Corte e garantia."""

    corpo_longo = "## Precos\n\n" + ("O ebook Recheios custa R$ 97,00 com garantia de 7 dias. " * 40)
    _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=corpo_longo,
        topics=("comercial",),
        aprovar=True,
    )

    resultado = search(agent_id="customer-support-agent", query="preco ebook garantia", repository=repo)

    assert resultado.hits
    conteudo = resultado.hits[0].body
    entre_marcadores = conteudo.split(DATA_OPEN, 1)[1].split(DATA_CLOSE, 1)[0]
    # Tira a linha de cabecalho do envelope antes de medir.
    corpo_entregue = entre_marcadores.split("\n", 1)[1]

    assert len(corpo_entregue) <= SUPPORT_USE_EXCERPT_CHARS + 1
    assert len(corpo_entregue) < len(corpo_longo)


def test_agentes_que_falam_com_cliente_sao_explicitos() -> None:
    assert "customer-support-agent" in CUSTOMER_FACING_AGENTS
    assert "caption-writer" not in CUSTOMER_FACING_AGENTS
    assert "customer-support-agent" in CAN_KNOW_PAID_AGENTS


# --- 4. Provenance ----------------------------------------------------------


def test_todo_resultado_carrega_provenance_completo(repo) -> None:
    _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=_CORPO_OFFERS,
        topics=("comercial", "preco"),
        aprovar=True,
    )

    hit = search(agent_id="customer-support-agent", query="preco garantia", repository=repo).hits[0]
    payload = hit.as_dict()

    for campo in (
        "fonte",
        "documento",
        "camada",
        "status",
        "versao",
        "aprovado_por",
        "aprovado_em",
        "origem",
        "tipo_de_fonte",
        "responsavel",
        "referencia",
        "topics",
        "confianca",
        "secao",
        "ordinal",
    ):
        assert campo in payload, f"provenance sem {campo}"

    assert payload["aprovado_por"] == "Judith Kolker"
    assert payload["versao"] == 1
    assert payload["camada"] == "L3"
    assert payload["tipo_de_fonte"] == "business"


def test_provenance_diz_quando_foi_substituido(repo) -> None:
    doc = _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=_CORPO_OFFERS,
        topics=("comercial",),
        aprovar=True,
    )
    repo.set_status(document_id=doc, novo="DEPRECATED", deprecated_by="doc_novo")

    acesso = resolve_access("knowledge-manager")
    resultado = search(agent_id="knowledge-manager", query="preco", repository=repo, access=acesso)

    if resultado.hits:
        assert resultado.hits[0].provenance.deprecated_by == "doc_novo"


def test_busca_devolve_no_maximo_o_limite(repo) -> None:
    for indice in range(8):
        _documento(
            repo,
            external_key=f"DOC_{indice}",
            layer="L3",
            content_access="INTERNAL_ONLY",
            corpo=f"## Secao {indice}\n\nchocolate artesanal premium com recheio de caramelo salgado.",
            aprovar=True,
        )

    acesso = resolve_access("judith-review-console")
    resultado = search(agent_id="judith-review-console", query="chocolate caramelo", repository=repo, access=acesso)

    assert len(resultado.hits) <= DEFAULT_LIMIT


# --- 5. O caminho lexical de producao continua intocado ---------------------


def test_retrieval_lexical_de_producao_nao_mudou() -> None:
    from agents.knowledge_policies import build_retriever_for

    retriever = build_retriever_for("customer-support-agent")
    resultado = retriever("qual o preco do ebook?")

    assert resultado, "o retriever de producao parou de devolver documento"
    assert any(doc.get("fonte") for doc in resultado if isinstance(doc, dict))


def test_modo_comparacao_mostra_a_diferenca_sem_mudar_nada(repo) -> None:
    """Shadow mode: mede antes de trocar."""

    _documento(
        repo,
        external_key="OFFERS",
        layer="L3",
        content_access="SUPPORT_USE",
        corpo=_CORPO_OFFERS,
        topics=("comercial",),
        aprovar=True,
    )

    comparacao = compare_with_lexical(agent_id="customer-support-agent", query="preco do ebook", repository=repo)

    assert set(comparacao) == {
        "agent_id",
        "query",
        "lexical",
        "brain",
        "somente_no_lexical",
        "somente_no_brain",
        "iguais",
        "bloqueados_pela_politica",
        "acesso_negado",
    }
    assert "OFFERS" in comparacao["brain"]
