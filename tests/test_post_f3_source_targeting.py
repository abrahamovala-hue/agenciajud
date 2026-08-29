"""
POST-F3 — source targeting canonico por intencao.

O QUE ESTA CORRECAO E, E O QUE ELA NAO E
----------------------------------------

Ela NAO mexe em ranking. `_pontuar`, `TOPIC_BOOST`, RRF, pesos, piso vetorial,
top-k e candidate pool ficam exatamente como estavam. A reserva acontece
DEPOIS da fusao, sobre a lista ja ordenada, e o candidato reservado sai dessa
mesma lista.

O problema que ela resolve: canonicalidade era representada por um bonus
aditivo fixo (+5) dentro de um score lexical ilimitado. Como a query e escrita
livremente pelo LLM, a magnitude do score varia a cada execucao e a correcao
nao varia junto — entao OFFERS nao tinha entrada garantida no top-k para uma
pergunta de preco. Medido em producao: falhava em ~1 de cada 4, nas DUAS
pernas.

A ORDEM QUE ESTES TESTES DEFENDEM
---------------------------------

    autorizacao  >  canonicalidade  >  ranking

Canonicalidade nunca abre porta. A vaga reservada e escolhida dentro de
`_elegiveis`, que ja aplicou camada, status, whitelist, topic e politica do
agente. Uma fonte proibida nao esta na lista, entao nao ha o que reservar —
e ha teste para isso.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from brain.access_policy import resolve_access
from brain.retrieval import (
    CANONICAL_TOPICS,
    DEFAULT_LIMIT,
    MAX_PER_DOCUMENT,
    TOPIC_BOOST,
    _canonical_pick,
    _diversify,
    canonical_targets,
    search,
)

VENDEDOR = "sales-conversion-agent"
SUPORTE = "customer-support-agent"

#: As quatro formulacoes medidas em producao (secao 9 do pedido).
QUATRO_FRASES = (
    "Olá qual o preço do ebook das casquinhas profissionais?",
    "quanto custa o ebook de casquinhas?",
    "qual o valor do ebook de recheios?",
    "oi, quero saber o preço dos ebooks",
)


def _fontes(resultado):
    return [h.provenance.external_key or h.provenance.document_id for h in resultado.hits]


def _buscar(repo, embedder, pergunta, *, agente=VENDEDOR, alvo=True, modo="hybrid", **kwargs):
    return search(
        agent_id=agente,
        query=pergunta,
        repository=repo,
        mode=modo,
        embedder=embedder,
        canonical_targeting=alvo,
        **kwargs,
    )


# =============================================================================
# A REGRA
# =============================================================================


class TestRegra:
    def test_o_topic_canonico_e_derivado_da_intencao(self) -> None:
        """Nada de `if intent == "preco"`: a relacao ja existe na taxonomia."""

        assert canonical_targets("quanto custa o ebook?") == frozenset({"preco"})
        assert canonical_targets("qual o preço?") == frozenset({"preco"})

    def test_intencao_sem_fonte_canonica_nao_tem_alvo(self) -> None:
        assert canonical_targets("minha ganache separou") == frozenset()
        assert canonical_targets("qual o tom de voz da marca?") == frozenset()

    def test_pergunta_sem_intencao_nao_tem_alvo(self) -> None:
        assert canonical_targets("bom dia") == frozenset()

    def test_o_topic_canonico_existe_no_acervo(self, brain_f3) -> None:
        """A regra nao pode citar um topic que nenhum documento declara."""

        declarados = set()
        for documento in brain_f3.list_documents():
            declarados.update(documento["topics"] or ())
        assert CANONICAL_TOPICS <= declarados, f"topic canonico sem dono: {CANONICAL_TOPICS - declarados}"

    def test_preco_e_exclusivo_de_offers(self, brain_f3) -> None:
        """A escolha de `preco` (e nao `oferta`) depende desta exclusividade."""

        donos = {
            str(d["external_key"]) for d in brain_f3.list_documents() if "preco" in (d["topics"] or ())
        }
        assert donos == {"OFFERS"}, donos


# =============================================================================
# A + B — OFFERS entra
# =============================================================================


class TestOffersEntra:
    def test_a_price_com_offers_elegivel_traz_offers(self, brain_indexado, embedder) -> None:
        for frase in QUATRO_FRASES:
            resultado = _buscar(brain_indexado, embedder, frase)
            assert "OFFERS" in _fontes(resultado), f"{frase} -> {_fontes(resultado)}"

    def test_b_candidato_canonico_em_ultimo_lugar_ainda_recebe_vaga(self) -> None:
        """O caso exato que motivou a correcao, isolado do acervo.

        A fonte canonica em ULTIMO no ranking, atras de tres documentos com
        score muito maior. Sem a reserva ela nao entra; com ela, entra — e o
        top-k continua sendo 4.
        """

        linhas = [
            (43, {"chunk_id": "p1", "document_id": "PRODUCTS", "topics": ["produto"]}),
            (41, {"chunk_id": "p2", "document_id": "PRODUCTS", "topics": ["produto"]}),
            (38, {"chunk_id": "s1", "document_id": "SITE", "topics": ["site"]}),
            (35, {"chunk_id": "s2", "document_id": "SITE", "topics": ["site"]}),
            (30, {"chunk_id": "o1", "document_id": "OUTLINE", "topics": ["ebook"]}),
            (25, {"chunk_id": "of", "document_id": "OFFERS", "topics": ["preco", "oferta"]}),
        ]

        sem = [linha["document_id"] for _, linha in _diversify(linhas, limit=4)]
        com = [linha["document_id"] for _, linha in _diversify(linhas, limit=4, canonical_topics=frozenset({"preco"}))]

        assert "OFFERS" not in sem, "o teste so significa algo se o ranking bruto perder OFFERS"
        assert "OFFERS" in com
        assert len(com) == 4

    def test_b_o_resgate_e_visivel_na_observabilidade(self, brain_indexado, embedder) -> None:
        """Quando o acervo local ja da OFFERS por ranking, o flag diz isso."""

        for frase in QUATRO_FRASES:
            sem = _buscar(brain_indexado, embedder, frase, alvo=False)
            com = _buscar(brain_indexado, embedder, frase, alvo=True)
            assert "OFFERS" in _fontes(com), frase
            # `selected` e True exatamente quando a reserva MUDOU o resultado.
            assert com.canonical_target_selected == ("OFFERS" not in _fontes(sem)), frase

    def test_a_vaga_reservada_e_o_melhor_candidato_daquela_fonte(self, brain_indexado, embedder) -> None:
        resultado = _buscar(brain_indexado, embedder, QUATRO_FRASES[0])
        offers = [h for h in resultado.hits if h.provenance.external_key == "OFFERS"]
        assert offers, "OFFERS precisa estar no resultado"


# =============================================================================
# C + D — autorizacao vence canonicalidade
# =============================================================================


class TestAutorizacaoVence:
    def test_c_offers_fora_da_whitelist_nao_entra(self, brain_indexado, embedder) -> None:
        """Canonica mas proibida continua proibida."""

        politica = resolve_access(VENDEDOR)
        sem_offers = replace(
            politica, external_keys=frozenset(k for k in (politica.external_keys or ()) if k != "OFFERS")
        )
        for frase in QUATRO_FRASES:
            resultado = search(
                agent_id=VENDEDOR,
                query=frase,
                repository=brain_indexado,
                mode="hybrid",
                embedder=embedder,
                access=sem_offers,
                canonical_targeting=True,
            )
            assert "OFFERS" not in _fontes(resultado), f"{frase} vazou OFFERS proibida"
            assert resultado.canonical_target_available is False

    def test_c_status_nao_aprovado_tambem_barra(self, brain_indexado, embedder) -> None:
        """DEPRECATED e canonica igual — e continua fora de producao."""

        alvo = brain_indexado.get_document_by_external_key("OFFERS")
        brain_indexado.set_status(document_id=alvo["document_id"], novo="DEPRECATED")

        resultado = _buscar(brain_indexado, embedder, QUATRO_FRASES[0])
        assert "OFFERS" not in _fontes(resultado)
        assert resultado.canonical_target_available is False

    def test_d_sem_candidato_canonico_nao_inventa(self, brain_indexado, embedder) -> None:
        politica = resolve_access(VENDEDOR)
        sem_offers = replace(
            politica, external_keys=frozenset(k for k in (politica.external_keys or ()) if k != "OFFERS")
        )
        resultado = search(
            agent_id=VENDEDOR,
            query=QUATRO_FRASES[0],
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
            access=sem_offers,
        )
        assert resultado.hits, "sem alvo, o ranking normal continua respondendo"
        assert resultado.canonical_target_selected is False
        assert all(h.provenance.external_key != "OFFERS" for h in resultado.hits)

    def test_a_reserva_so_escolhe_dentro_dos_elegiveis(self, brain_indexado) -> None:
        """Prova estrutural: `_canonical_pick` nao conhece o acervo."""

        assert _canonical_pick([], frozenset({"preco"})) is None
        pontuados = [(10, {"topics": ["produto"], "document_id": "d1"})]
        assert _canonical_pick(pontuados, frozenset({"preco"})) is None
        pontuados.append((1, {"topics": ["preco"], "document_id": "d2"}))
        assert _canonical_pick(pontuados, frozenset({"preco"})) == 1


# =============================================================================
# E — nao forcar onde nao cabe
# =============================================================================


class TestNaoForca:
    @pytest.mark.parametrize(
        "pergunta",
        [
            "minha ganache separou",
            "qual o tom de voz da marca?",
            "o que o ebook de recheios ensina?",
            "bom dia, tudo bem?",
        ],
    )
    def test_e_query_sem_intencao_de_preco_nao_reserva(self, brain_indexado, embedder, pergunta: str) -> None:
        resultado = _buscar(brain_indexado, embedder, pergunta, agente=SUPORTE)
        assert resultado.canonical_target_requested == []
        assert resultado.canonical_target_selected is False

    def test_sem_alvo_o_resultado_e_identico_ao_de_antes(self, brain_indexado, embedder) -> None:
        """Sem intencao canonica, o caminho e byte a byte o anterior."""

        com = _buscar(brain_indexado, embedder, "minha ganache separou", agente=SUPORTE, alvo=True)
        sem = _buscar(brain_indexado, embedder, "minha ganache separou", agente=SUPORTE, alvo=False)
        assert _fontes(com) == _fontes(sem)


# =============================================================================
# F + G + H — os limites continuam valendo
# =============================================================================


class TestLimites:
    def test_f_top_k_continua_quatro(self, brain_indexado, embedder) -> None:
        for frase in QUATRO_FRASES:
            resultado = _buscar(brain_indexado, embedder, frase)
            assert len(resultado.hits) <= DEFAULT_LIMIT == 4, f"{frase} -> {len(resultado.hits)}"

    def test_f_limite_explicito_e_respeitado(self, brain_indexado, embedder) -> None:
        for limite in (1, 2, 3, 4, 6):
            resultado = _buscar(brain_indexado, embedder, QUATRO_FRASES[0], limit=limite)
            assert len(resultado.hits) <= limite

    def test_g_teto_por_documento_continua_valendo(self, brain_indexado, embedder) -> None:
        for frase in QUATRO_FRASES:
            resultado = _buscar(brain_indexado, embedder, frase)
            contagem: dict[str, int] = {}
            for hit in resultado.hits:
                contagem[hit.provenance.document_id] = contagem.get(hit.provenance.document_id, 0) + 1
            assert all(n <= MAX_PER_DOCUMENT for n in contagem.values()), contagem

    def test_h_teto_por_receita_continua_valendo(self, brain_indexado, embedder) -> None:
        resultado = _buscar(
            brain_indexado, embedder, "quanto custa a receita de pistache do ebook?", agente=SUPORTE
        )
        receitas = [h.provenance.recipe_id for h in resultado.hits if h.provenance.recipe_id]
        assert len(receitas) == len(set(receitas)), receitas

    def test_a_vaga_reservada_conta_nos_mesmos_tetos(self) -> None:
        """Reservar nao e escapar da diversidade: e ocupar uma vaga dela.

        Pool com documentos suficientes para que a SEGUNDA passada de
        `_diversify` nao precise disparar. Essa passada ignora os tetos de
        proposito — para nunca devolver menos resultados que `limit` — e isso
        e comportamento anterior a esta correcao, nao efeito dela.
        """

        linhas = [
            (30, {"chunk_id": "a", "document_id": "PRODUTO", "topics": ["produto"]}),
            (29, {"chunk_id": "b", "document_id": "PRODUTO", "topics": ["produto"]}),
            (28, {"chunk_id": "c", "document_id": "PRODUTO", "topics": ["produto"]}),
            (27, {"chunk_id": "e", "document_id": "SITE", "topics": ["site"]}),
            (26, {"chunk_id": "f", "document_id": "SITE", "topics": ["site"]}),
            (1, {"chunk_id": "d", "document_id": "OFERTA", "topics": ["preco"]}),
        ]
        escolhidos = _diversify(linhas, limit=4, canonical_topics=frozenset({"preco"}))
        documentos = [linha["document_id"] for _, linha in escolhidos]

        assert len(escolhidos) == 4
        assert documentos.count("PRODUTO") <= MAX_PER_DOCUMENT, documentos
        assert "OFERTA" in documentos

    def test_a_segunda_passada_continua_ignorando_tetos(self) -> None:
        """Trava do comportamento PRE-EXISTENTE, para nao confundir com a reserva."""

        linhas = [
            (30, {"chunk_id": "a", "document_id": "PRODUTO", "topics": []}),
            (29, {"chunk_id": "b", "document_id": "PRODUTO", "topics": []}),
            (28, {"chunk_id": "c", "document_id": "PRODUTO", "topics": []}),
            (27, {"chunk_id": "d", "document_id": "PRODUTO", "topics": []}),
        ]
        # Sem alvo nenhum: quatro chunks do mesmo documento saem mesmo assim.
        assert len(_diversify(linhas, limit=4)) == 4


# =============================================================================
# I — o ranking bruto nao foi tocado
# =============================================================================


class TestRankingIntocado:
    def test_i_candidatos_lexicais_e_vetoriais_identicos(self, brain_indexado, embedder) -> None:
        for frase in QUATRO_FRASES:
            com = _buscar(brain_indexado, embedder, frase, alvo=True)
            sem = _buscar(brain_indexado, embedder, frase, alvo=False)

            assert com.lexical_candidates == sem.lexical_candidates
            assert com.vector_candidates == sem.vector_candidates
            assert com.vector_scores == sem.vector_scores
            assert com.eligible_chunks == sem.eligible_chunks
            assert com.retrieval_mode == sem.retrieval_mode

    def test_i_as_constantes_de_ranking_nao_mudaram(self) -> None:
        from brain.embeddings import OpenAIEmbedder
        from brain.fusion import DEFAULT_WEIGHTS, RRF_K
        from brain.retrieval import CANDIDATE_POOL_FACTOR, LEXICAL_WEIGHT, VECTOR_SCORE_FLOOR, VECTOR_WEIGHT

        assert TOPIC_BOOST == 5
        assert VECTOR_SCORE_FLOOR == 0.60
        assert OpenAIEmbedder().score_floor == 0.60
        assert LEXICAL_WEIGHT == VECTOR_WEIGHT == 1.0
        assert DEFAULT_WEIGHTS == {"lexical": 1.0, "vetorial": 1.0}
        assert RRF_K == 60
        assert DEFAULT_LIMIT == 4
        assert CANDIDATE_POOL_FACTOR == 5
        assert MAX_PER_DOCUMENT == 2

    def test_diversify_sem_alvo_e_o_comportamento_anterior(self) -> None:
        linhas = [
            (10, {"chunk_id": "a", "document_id": "d1", "topics": ["preco"]}),
            (9, {"chunk_id": "b", "document_id": "d1", "topics": []}),
            (8, {"chunk_id": "c", "document_id": "d1", "topics": []}),
            (7, {"chunk_id": "d", "document_id": "d2", "topics": []}),
        ]
        assert _diversify(linhas, limit=4) == _diversify(linhas, limit=4, canonical_topics=frozenset())


# =============================================================================
# J — provenance e observabilidade
# =============================================================================


class TestProvenanceEObservabilidade:
    def test_j_a_vaga_reservada_carrega_provenance_completa(self, brain_indexado, embedder) -> None:
        resultado = _buscar(brain_indexado, embedder, QUATRO_FRASES[0])
        documentos = {d["fonte"]: d for d in resultado.as_documents()}
        assert "OFFERS" in documentos

        offers = documentos["OFFERS"]
        for campo in ("documento", "camada", "status", "versao", "origem", "tipo_de_fonte", "secao", "topics"):
            assert campo in offers, campo
        assert offers["status"] == "CONFIRMED"
        assert offers["aprovado_por"], "a vaga reservada nao pode driblar aprovacao"

    def test_da_para_distinguir_ranking_de_targeting(self, brain_indexado, embedder) -> None:
        resultado = _buscar(brain_indexado, embedder, QUATRO_FRASES[0])
        obs = resultado.observability()

        assert obs["canonical_target_requested"] == ["preco"]
        assert obs["canonical_target_available"] is True
        assert isinstance(obs["canonical_target_selected"], bool)

    def test_a_observabilidade_nao_carrega_conteudo(self, brain_indexado, embedder) -> None:
        texto = repr(_buscar(brain_indexado, embedder, QUATRO_FRASES[0]).observability()).lower()
        for proibido in ("sintetico", "emulsao", "pistache", "casquinhas profissionais"):
            assert proibido not in texto, proibido

    def test_os_campos_novos_estao_na_allowlist(self) -> None:
        from brain.retrieval_trace import record, reset, start_trace, trace_summary
        from orchestration.execution_repository import _OUTCOME_ALLOWLIST

        reset()
        start_trace()
        record(
            {
                "retrieval_mode": "HYBRID",
                "canonical_target_requested": ["preco"],
                "canonical_target_available": True,
                "canonical_target_selected": True,
            }
        )
        faltando = set(trace_summary()) - set(_OUTCOME_ALLOWLIST)
        reset()
        assert not faltando, f"campos fora da allowlist do ExecutionLog: {faltando}"


# =============================================================================
# 9 — as quatro frases, a regressao que importa
# =============================================================================


class TestQuatroFrases:
    def test_offers_em_quatro_de_quatro(self, brain_indexado, embedder) -> None:
        faltando = [f for f in QUATRO_FRASES if "OFFERS" not in _fontes(_buscar(brain_indexado, embedder, f))]
        assert faltando == [], f"OFFERS ausente em: {faltando}"

    def test_vale_nos_dois_modos(self, brain_indexado, embedder) -> None:
        """A garantia nao pode depender de RAG_MODE."""

        for modo in ("current", "hybrid"):
            for frase in QUATRO_FRASES:
                resultado = _buscar(brain_indexado, embedder, frase, modo=modo)
                assert "OFFERS" in _fontes(resultado), f"{modo}/{frase} -> {_fontes(resultado)}"

    def test_a_frase_da_judith_e_golden(self) -> None:
        from brain.eval_hybrid_rag import GOLDEN

        assert "ola qual o preco do ebook das casquinhas profissionais?" in GOLDEN

    def test_as_quatro_estao_no_eval(self) -> None:
        from brain.eval_hybrid_rag import HYBRID_RAG_V1

        perguntas = {c.query.strip().lower() for c in HYBRID_RAG_V1}
        for frase in QUATRO_FRASES:
            # o dataset guarda a forma sem acento; a comparacao usa o mesmo fold
            from agents.knowledge_sources import _normalize

            assert any(_normalize(p) == _normalize(frase) for p in perguntas), frase
