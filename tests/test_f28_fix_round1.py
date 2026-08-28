"""
F2.8 fix round 1 — J1 (intent/topic boost), J2 (contexto), J3 (rota social).

O caso que originou tudo, do teste humano no celular:

    "quanto custa Casquinhas e Recheios?"
      PRODUCTS  score 12   (repete o nome dos produtos)
      OFFERS    score  4   posicao 15 de 27   <- fora do top-k

O preco existia, estava aprovado e o agente tinha acesso. Ele so nao era
encontrado. Estes testes existem para que isso nao volte.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from brain import query_context as qc
from brain.retrieval import TOPIC_BOOST, detect_intent_topics, search

PRECO = ["quanto custa Casquinhas e Recheios?", "qual o preco do ebook?", "quanto e Casquinhas?",
         "qual o valor dos ebooks?", "tem desconto?"]


@pytest.fixture(scope="module")
def store():
    """Store com os documentos de `docs/` aprovados — sem depender dos PDFs."""

    from brain.approvals import apply_approvals
    from brain.backfill import run_backfill
    from brain.repository import KnowledgeRepository
    from db.migrations import run_migrations

    engine = create_engine("sqlite://")
    run_migrations(engine)
    repositorio = KnowledgeRepository(engine)
    run_backfill(repositorio)
    apply_approvals(repositorio)
    yield repositorio
    engine.dispose()


@pytest.fixture(autouse=True)
def contexto_limpo():
    qc.reset()
    yield
    qc.reset()


def _fontes(store, agent_id: str, query: str) -> list[str]:
    resultado = search(agent_id=agent_id, query=query, repository=store, limit=4, include_body=False)
    return [h.provenance.external_key or "" for h in resultado.hits]


# =============================================================================
# J1 — intent/topic-aware retrieval
# =============================================================================


class TestJ1PrecoEncontraOffers:
    @pytest.mark.parametrize("query", PRECO)
    @pytest.mark.parametrize("agente", ["sales-conversion-agent", "community-dm-agent"])
    def test_pergunta_de_preco_traz_offers(self, store, agente: str, query: str) -> None:
        assert "OFFERS" in _fontes(store, agente, query), f"{agente} / {query}"

    def test_o_caso_do_teste_humano(self, store) -> None:
        """O MOBILE_FAIL_01 literal."""

        assert "OFFERS" in _fontes(store, "sales-conversion-agent", "quanto custa Casquinhas e Recheios?")

    def test_garantia_traz_offers(self, store) -> None:
        assert "OFFERS" in _fontes(store, "community-dm-agent", "tem garantia?")


class TestJ1NaoQuebraOResto:
    def test_sem_intencao_nao_ha_boost(self) -> None:
        """Pergunta sem intencao reconhecida mantem o comportamento anterior."""

        assert detect_intent_topics("oii") == frozenset()
        assert detect_intent_topics("obrigada!") == frozenset()
        assert detect_intent_topics("kkkk") == frozenset()

    def test_intencao_comercial_vence_a_tecnica(self) -> None:
        """"casquinha" e "recheio" sao nome de produto E palavra tecnica.

        Quando as duas intencoes casam, preco vence: quem escreve "quanto
        custa" esta perguntando preco. A uniao dos topics impulsionava as
        fichas de produto e afogava OFFERS — foi o que travou o primeiro
        conserto.
        """

        topics = detect_intent_topics("quanto custa Casquinhas e Recheios?")
        assert topics == frozenset({"preco", "oferta"})
        assert "ebook" not in topics

    def test_intencao_tecnica_continua_valendo(self) -> None:
        topics = detect_intent_topics("minha ganache separou")
        assert "tecnica" in topics

    def test_comercial_nao_carrega_o_topic_comercial(self) -> None:
        """PRODUCTS tambem e `comercial`; incluir esse topic amplificava o erro."""

        assert "comercial" not in detect_intent_topics("quanto custa?")

    def test_boost_e_pequeno_e_somado(self) -> None:
        """Nao substitui o score lexical — apenas reordena o que ja passou."""

        assert 0 < TOPIC_BOOST <= 6


@pytest.mark.skipif(
    not __import__("brain.primary_sources", fromlist=["DEFAULT_SOURCE_DIR"]).DEFAULT_SOURCE_DIR.exists(),
    reason="PDFs da Judith ficam fora do repositorio",
)
class TestJ1NaoExpulsaConteudoTecnico:
    @pytest.fixture(scope="class")
    @classmethod
    def store_completo(cls, tmp_path_factory):
        from brain.approvals import apply_approvals
        from brain.backfill import run_backfill
        from brain.ingestion import ingest_primary_sources
        from brain.repository import KnowledgeRepository
        from db.migrations import run_migrations

        caminho = tmp_path_factory.mktemp("j1") / "j1.sqlite"
        engine = create_engine(f"sqlite:///{caminho}")
        run_migrations(engine)
        repositorio = KnowledgeRepository(engine)
        run_backfill(repositorio)
        ingest_primary_sources(repositorio)
        apply_approvals(repositorio)
        return repositorio

    @pytest.mark.parametrize(
        "query", ["minha ganache separou", "me explica temperagem", "como deixar o bombom brilhante"]
    )
    def test_pergunta_tecnica_traz_ebook(self, store_completo, query: str) -> None:
        fontes = _fontes(store_completo, "customer-support-agent", query)
        assert any(f.startswith("EBOOK") for f in fontes), f"{query} -> {fontes}"


# =============================================================================
# J2 — contexto de conversa na query
# =============================================================================


class TestJ2Elipse:
    @pytest.mark.parametrize(
        "mensagem", ["entao so os ingredientes", "e o preco?", "e esse?", "qual deles?", "e o outro?", "e tem como salvar?"]
    )
    def test_mensagem_eliptica_e_reconhecida(self, mensagem: str) -> None:
        assert qc.is_elliptical(mensagem), mensagem

    @pytest.mark.parametrize(
        "mensagem",
        [
            "me passa a receita de pistache",
            "qual a diferenca entre Casquinhas e Recheios?",
            "minha ganache separou",
            "quanto custa o ebook de recheios?",
        ],
    )
    def test_pergunta_completa_nao_e_eliptica(self, mensagem: str) -> None:
        """Enriquecer uma pergunta que ja se sustenta mudaria uma busca certa."""

        assert not qc.is_elliptical(mensagem), mensagem


class TestJ2Enriquecimento:
    def test_follow_up_herda_o_turno_anterior(self) -> None:
        qc.set_session("s1")
        qc.remember("me passa a receita de pistache")

        consulta, enriquecida = qc.enrich("entao so os ingredientes")

        assert enriquecida is True
        assert "pistache" in consulta
        assert "ingredientes" in consulta

    def test_preco_apos_comparacao(self, store) -> None:
        qc.set_session("s2")
        qc.remember("qual a diferenca entre Casquinhas e Recheios?")

        consulta, enriquecida = qc.enrich("e o preco?")
        assert enriquecida is True
        assert "Casquinhas" in consulta and "Recheios" in consulta
        assert "OFFERS" in _fontes(store, "sales-conversion-agent", consulta)

    def test_sem_turno_anterior_nao_inventa_contexto(self) -> None:
        qc.set_session("s3")
        consulta, enriquecida = qc.enrich("e o preco?")

        assert enriquecida is False
        assert consulta == "e o preco?"

    def test_pergunta_completa_nao_e_tocada(self) -> None:
        qc.set_session("s4")
        qc.remember("quanto custa Casquinhas?")

        consulta, enriquecida = qc.enrich("minha ganache separou")
        assert enriquecida is False
        assert consulta == "minha ganache separou"

    def test_eliptica_nao_vira_contexto(self) -> None:
        """Guardar "entao so os ingredientes" faria o turno seguinte herdar nada."""

        qc.set_session("s5")
        qc.remember("me passa a receita de pistache")
        qc.remember("entao so os ingredientes")

        consulta, _ = qc.enrich("e agora?")
        assert "pistache" in consulta

    def test_sessoes_nao_se_misturam(self) -> None:
        qc.set_session("cliente-a")
        qc.remember("quanto custa Casquinhas?")
        qc.set_session("cliente-b")

        _, enriquecida = qc.enrich("e o preco?")
        assert enriquecida is False, "contexto de uma cliente vazou para outra"

    def test_sem_sessao_nao_enriquece(self) -> None:
        qc.set_session(None)
        qc.remember("me passa a receita de pistache")

        assert qc.enrich("entao so os ingredientes") == ("entao so os ingredientes", False)


class TestJ2TrocaDeAssunto:
    @pytest.mark.parametrize(
        "mensagem",
        ["mudando de assunto, minha ganache separou", "outra coisa: tem garantia?", "agora sobre o preco"],
    )
    def test_virada_explicita_nao_e_elipse(self, mensagem: str) -> None:
        assert qc.muda_de_assunto(mensagem)
        assert not qc.is_elliptical(mensagem)

    def test_contexto_comercial_nao_contamina_tecnico(self, store) -> None:
        qc.set_session("s6")
        qc.remember("quanto custa Casquinhas?")

        consulta, enriquecida = qc.enrich("mudando de assunto, minha ganache separou")

        assert enriquecida is False
        assert "custa" not in consulta

    def test_virada_limpa_o_contexto_guardado(self) -> None:
        qc.set_session("s7")
        qc.remember("quanto custa Casquinhas?")
        qc.remember("mudando de assunto, minha ganache separou")

        consulta, _ = qc.enrich("e agora?")
        assert "custa" not in consulta


# =============================================================================
# J3 — a rota social nao proibe mais consultar
# =============================================================================


class TestJ3RotaSocial:
    def _prompt_social(self) -> str:
        """O PROMPT, sem os comentarios.

        A primeira versao deste teste lia o fonte inteiro e falhava por causa
        do comentario que explica a remocao — o comentario cita a frase
        removida. O que importa e o que chega ao modelo.
        """

        import inspect

        from orchestration.workflows import answer_dm

        fonte = inspect.getsource(answer_dm._build_workflow)
        return "\n".join(linha for linha in fonte.splitlines() if not linha.lstrip().startswith("#"))

    def test_nao_proibe_mais_consultar(self) -> None:
        """A proibicao contradizia a arquitetura BRAIN_NATIVE."""

        assert "nao precisa consultar documento" not in self._prompt_social()

    def test_manda_consultar_quando_ha_pergunta_factual(self) -> None:
        fonte = self._prompt_social()
        assert "CONSULTE antes de responder" in fonte

    def test_small_talk_continua_sem_consulta_obrigatoria(self) -> None:
        assert "nao precisa consultar nada" in self._prompt_social()

    def test_regra_de_nao_afirmar_sem_fonte_sobrevive(self) -> None:
        assert "sem ter aberto a fonte" in self._prompt_social()


# =============================================================================
# Regressao das garantias que nao podem ter mudado
# =============================================================================


class TestNadaDeSegurancaMudou:
    def test_cutover_nao_amplia_permissao(self, monkeypatch) -> None:
        monkeypatch.setenv("BRAIN_NATIVE_AGENTS", "sales-conversion-agent")
        from brain.access_policy import resolve_access

        acesso = resolve_access("sales-conversion-agent")
        assert acesso.can_know_paid is False
        assert "EBOOK_RECHEIOS" not in (acesso.external_keys or ())

    def test_boost_nao_abre_documento_proibido(self, store) -> None:
        """O boost soma DEPOIS dos filtros — nunca concede acesso."""

        fontes = _fontes(store, "sales-conversion-agent", "quanto custa a receita de ganache?")
        assert not any(f.startswith("EBOOK") for f in fontes)

    def test_contexto_nao_burla_o_disclosure(self) -> None:
        """Recuperar com contexto nao autoriza entregar o que foi recuperado."""

        from brain.disclosure_gate import evaluate

        resposta = (
            "A ganache leva 100 g de chocolate branco, 50 g de creme, 20 g de leite em po, "
            "10 g de glucose e 10 g de manteiga."
        )
        assert evaluate(resposta).decision == "BLOCK"
