"""
F2.8 — aprovacoes e cutover controlado.

As duas propriedades que estes testes existem para travar:

1. Nenhum documento chega a CONFIRMED sem estar escrito no manifesto.
2. Cutover e reversivel apagando um nome de uma variavel de ambiente.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from brain.approvals import APPROVALS, APPROVER, NOT_APPROVED, apply_approvals, audit_drift
from brain.cutover import RECOMMENDED_ORDER, brain_native_agents, cutover_report, is_brain_native
from brain.repository import KnowledgeRepository


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    repositorio = KnowledgeRepository(engine)
    repositorio.ensure_tables()
    repositorio.upsert_source(
        source_id="src", kind="judith", origin="upload", owner="judith", title="fonte de teste"
    )
    yield repositorio
    engine.dispose()


def _documento(repositorio, chave: str, corpo: str = "conteudo\n") -> str:
    from brain.repository import checksum_of

    doc = repositorio.create_document(
        source_id="src",
        title=chave,
        layer="L3",
        status="TO_VALIDATE",
        content_access="PUBLIC",
        checksum=checksum_of(corpo),
        external_key=chave,
    )
    repositorio.add_version(document_id=doc, body=corpo, created_by="teste")
    return doc


class TestManifesto:
    def test_aprovador_e_uma_pessoa_nomeada(self) -> None:
        """Aprovacao anonima seria indistinguivel de aprovacao automatica."""

        assert APPROVER.strip()
        assert "judith" in APPROVER.lower()
        assert all(a.approved_by.strip() for a in APPROVALS)

    def test_toda_aprovacao_tem_motivo(self) -> None:
        assert all(len(a.reason) > 30 for a in APPROVALS), "motivo generico nao explica a decisao"

    def test_o_que_nao_e_aprovado_esta_declarado(self) -> None:
        """Ausencia precisa ser decisao legivel, nao esquecimento."""

        assert "OFFER_STRATEGY_INTERNAL" in NOT_APPROVED
        aprovados = {a.external_key for a in APPROVALS}
        assert not (aprovados & set(NOT_APPROVED)), "documento nao pode estar nas duas listas"

    def test_interno_nunca_e_aprovado(self) -> None:
        assert "OFFER_STRATEGY_INTERNAL" not in {a.external_key for a in APPROVALS}


class TestAplicacao:
    def test_aprova_o_que_esta_no_manifesto(self, store) -> None:
        _documento(store, "OFFERS")
        relatorio = apply_approvals(store)

        assert [a["fonte"] for a in relatorio["aprovadas"]] == ["OFFERS"]
        assert store.get_document_by_external_key("OFFERS")["status"] == "CONFIRMED"

    def test_nao_aprova_o_que_nao_esta(self, store) -> None:
        _documento(store, "OFFER_STRATEGY_INTERNAL")
        apply_approvals(store)

        assert store.get_document_by_external_key("OFFER_STRATEGY_INTERNAL")["status"] == "TO_VALIDATE"

    def test_idempotente(self, store) -> None:
        _documento(store, "OFFERS")
        apply_approvals(store)
        segundo = apply_approvals(store)

        assert segundo["aprovadas"] == []
        assert any(i["motivo"] == "ja aprovado" for i in segundo["ignoradas"])

    def test_grava_quem_aprovou(self, store) -> None:
        doc = _documento(store, "PRODUCTS")
        apply_approvals(store)
        versao = store.get_current_version(doc)

        assert versao["approved_by"] == APPROVER
        assert versao["approved_at"] is not None

    def test_documento_ausente_nao_quebra(self, store) -> None:
        relatorio = apply_approvals(store)

        assert relatorio["erros"] == []
        assert all(i["motivo"] == "documento nao existe no store" for i in relatorio["ignoradas"])


class TestDerivaDeAprovacao:
    def test_conteudo_alterado_apos_aprovacao_e_denunciado(self, store) -> None:
        """O furo real: v+1 nasce sem aprovacao mas o documento segue CONFIRMED."""

        doc = _documento(store, "OFFERS")
        apply_approvals(store)
        assert audit_drift(store) == []

        store.add_version(document_id=doc, body="conteudo alterado\n", created_by="teste")

        deriva = audit_drift(store)
        assert len(deriva) == 1
        assert deriva[0]["fonte"] == "OFFERS"
        assert deriva[0]["versao_vigente"] == 2

    def test_nao_re_aprova_sozinho(self, store) -> None:
        """A versao nova exige um humano que a leu."""

        doc = _documento(store, "OFFERS")
        apply_approvals(store)
        store.add_version(document_id=doc, body="conteudo alterado\n", created_by="teste")

        apply_approvals(store)
        assert store.get_current_version(doc)["approved_by"] is None


class TestCutover:
    def test_default_e_ninguem(self, monkeypatch) -> None:
        monkeypatch.delenv("BRAIN_NATIVE_AGENTS", raising=False)

        assert brain_native_agents() == frozenset()
        assert not is_brain_native("customer-support-agent")
        assert cutover_report()["origem"] == "default"

    def test_promocao_por_env(self, monkeypatch) -> None:
        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "knowledge-manager, customer-support-agent")

        assert is_brain_native("knowledge-manager")
        assert is_brain_native("customer-support-agent")
        assert not is_brain_native("sales-conversion-agent")

    def test_reverter_e_apagar_o_nome(self, monkeypatch) -> None:
        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "knowledge-manager")
        assert is_brain_native("knowledge-manager")

        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "")
        assert brain_native_agents() == frozenset()
        assert not is_brain_native("knowledge-manager")

    def test_ordem_pulada_e_reportada(self, monkeypatch) -> None:
        """Promover venda sem promover suporte nao e erro, mas precisa aparecer."""

        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "sales-conversion-agent")
        relatorio = cutover_report()

        assert "knowledge-manager" in relatorio["pulados_na_ordem_recomendada"]
        assert "customer-support-agent" in relatorio["pulados_na_ordem_recomendada"]

    def test_ordem_recomendada_comeca_por_quem_revisa(self) -> None:
        assert RECOMMENDED_ORDER[0] == "knowledge-manager"
        assert RECOMMENDED_ORDER[1] == "customer-support-agent"


class TestTroasDoAgentePromovido:
    def test_agente_promovido_recebe_tools_do_brain(self, monkeypatch) -> None:
        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "customer-support-agent")
        from agents.knowledge_policies import build_knowledge_tools_for

        nomes = {t.name for t in build_knowledge_tools_for("customer-support-agent")}
        assert nomes == {"listar_fontes_disponiveis", "buscar_conhecimento"}

    def test_agente_nao_promovido_continua_no_lexical(self, monkeypatch) -> None:
        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "customer-support-agent")
        from agents.knowledge_policies import build_knowledge_tools_for

        nomes = {t.name for t in build_knowledge_tools_for("caption-writer")}
        assert nomes == {"listar_fontes_disponiveis", "ler_documento"}

    def test_cutover_nao_amplia_permissao(self, monkeypatch) -> None:
        """Trocar o caminho nao pode conceder documento novo."""

        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "sales-conversion-agent")
        from brain.access_policy import resolve_access

        acesso = resolve_access("sales-conversion-agent")
        assert acesso.can_know_paid is False
        assert "EBOOK_RECHEIOS" not in (acesso.external_keys or ())

    def test_brain_indisponivel_nao_derruba_a_tool(self, monkeypatch) -> None:
        """Sem banco, a tool responde declarando a falha — nao levanta."""

        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "customer-support-agent")
        from agents.knowledge_policies import build_knowledge_tools_for
        from brain import bootstrap

        anterior = bootstrap._repository
        bootstrap.set_knowledge_repository(object())  # sem os metodos esperados
        try:
            ferramentas = {t.name: t for t in build_knowledge_tools_for("customer-support-agent")}
            resposta = ferramentas["buscar_conhecimento"].entrypoint("qualquer coisa")
            assert resposta["status"] == "BRAIN_INDISPONIVEL"
            assert resposta["resultados"] == []
        finally:
            bootstrap.set_knowledge_repository(anterior)
