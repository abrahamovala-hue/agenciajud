"""
F3 — Hybrid RAG: schema, pipeline, fusao, filtros, diversidade, observabilidade.

O QUE ESTES TESTES PODEM E NAO PODEM PROVAR
-------------------------------------------

Eles rodam com `DeterministicEmbedder`, que projeta tokens por hash e NAO tem
semantica: "ganache" e "emulsao" ficam longe uma da outra. Isso e proposital e
precisa ficar escrito, porque a tentacao de escrever
`test_busca_semantica_encontra_sinonimo` aqui e grande — e o teste passaria por
acidente ou falharia por acidente, sem relacao com o modelo real.

Entao: aqui se prova ENCANAMENTO — idempotencia, filtro, fusao, diversidade,
provenance, rollback, degradacao. A afirmacao "a busca semantica encontra
sinonimo" so vale medida com o modelo real, e por isso ela e medida no shadow
de producao (`/admin/brain/eval`), nao aqui.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from brain.embeddings import (
    DEFAULT_DIMENSION,
    DEFAULT_MODEL,
    DeterministicEmbedder,
    cosine,
    embedding_identity,
    normalize,
    run_embedding_pipeline,
)
from brain.fusion import RRF_K, reciprocal_rank_fusion
from brain.rag_mode import rag_mode, rag_mode_report, uses_vector, vector_decides
from brain.repository import KnowledgeRepository, checksum_of
from brain.retrieval import search
from brain.schema import EMBEDDINGS_TABLE
from db.migrations import MIGRATIONS, applied_versions, rollback, run_migrations

VENDEDOR = "sales-conversion-agent"
SUPORTE = "customer-support-agent"


# =============================================================================
# PGVECTOR / SCHEMA
# =============================================================================


class TestSchema:
    def test_migration_005_esta_registrada(self) -> None:
        versoes = {m.version: m for m in MIGRATIONS}
        assert 5 in versoes
        assert versoes[5].name == "vector_index"

    def test_migration_005_e_reversivel(self) -> None:
        assert next(m for m in MIGRATIONS if m.version == 5).reversible

    def test_cria_a_tabela_de_embeddings(self) -> None:
        engine = create_engine("sqlite://")
        run_migrations(engine)
        assert inspect(engine).has_table(EMBEDDINGS_TABLE)

    def test_rollback_derruba_so_o_indice(self) -> None:
        """Reverter a F3 nao pode levar conhecimento junto."""

        engine = create_engine("sqlite://")
        run_migrations(engine)
        inspetor = inspect(engine)
        antes = {t for t in inspetor.get_table_names() if t.startswith("judith_knowledge")}

        rollback(engine, 5)

        depois = {t for t in inspect(engine).get_table_names() if t.startswith("judith_knowledge")}
        assert antes - depois == {EMBEDDINGS_TABLE}
        assert 5 not in applied_versions(engine)

    def test_a_chave_e_checksum_mais_modelo(self) -> None:
        """A identidade nao pode ser `chunk_id`: ele e recriado a cada escrita."""

        engine = create_engine("sqlite://")
        run_migrations(engine)
        repo = KnowledgeRepository(engine)
        constraints = {c.name for c in repo.embeddings.constraints if c.name}
        assert f"uq_{EMBEDDINGS_TABLE}_checksum_model" in constraints

    def test_chunks_for_search_devolve_checksum(self, brain_f3) -> None:
        linhas = brain_f3.chunks_for_search(statuses=frozenset({"CONFIRMED"}), layers=frozenset({"L1", "L2", "L3"}))
        assert linhas
        assert all(linha.get("checksum") for linha in linhas)


# =============================================================================
# EMBEDDING PIPELINE + IDEMPOTENCY
# =============================================================================


class TestPipeline:
    def test_indexa_e_reporta(self, brain_f3, embedder) -> None:
        relatorio = run_embedding_pipeline(brain_f3, embedder=embedder)
        assert relatorio.novos > 0
        assert relatorio.erros == []
        assert relatorio.as_dict()["cobertura"] == 1.0

    def test_rodar_de_novo_nao_reindexa(self, brain_f3, embedder) -> None:
        primeira = run_embedding_pipeline(brain_f3, embedder=embedder)
        segunda = run_embedding_pipeline(brain_f3, embedder=embedder)

        assert segunda.novos == 0
        assert segunda.ja_indexados == segunda.chunks_elegiveis
        assert primeira.chunks_elegiveis == segunda.chunks_elegiveis

    def test_dry_run_nao_grava(self, brain_f3, embedder) -> None:
        relatorio = run_embedding_pipeline(brain_f3, embedder=embedder, dry_run=True)
        assert relatorio.novos == 0
        assert brain_f3.embedding_stats()["vetores"] == 0

    def test_texto_repetido_embute_uma_vez(self, brain_f3, embedder) -> None:
        run_embedding_pipeline(brain_f3, embedder=embedder)
        estatisticas = brain_f3.embedding_stats()
        assert estatisticas["vetores"] == estatisticas["checksums_distintos_em_chunks"]

    def test_conteudo_alterado_gera_vetor_novo(self, brain_f3, embedder) -> None:
        run_embedding_pipeline(brain_f3, embedder=embedder)
        antes = brain_f3.embedding_stats()["vetores"]

        documento = brain_f3.get_document_by_external_key("PRODUCT_OUTLINE_LASCAS")
        brain_f3.add_version(
            document_id=documento["document_id"],
            body="# Outline Lascas\n\n## Novo\nConteudo diferente para forcar checksum novo.\n",
            created_by="teste-f3",
        )

        relatorio = run_embedding_pipeline(brain_f3, embedder=embedder)
        assert relatorio.novos >= 1
        assert brain_f3.embedding_stats()["vetores"] > antes

    def test_modelo_diferente_e_indice_diferente(self, brain_f3, embedder) -> None:
        run_embedding_pipeline(brain_f3, embedder=embedder)
        outro = DeterministicEmbedder(model="outro-modelo-v9", dimension=32)
        relatorio = run_embedding_pipeline(brain_f3, embedder=outro)

        assert relatorio.novos > 0, "trocar de modelo precisa reindexar"
        assert set(brain_f3.embedding_stats()["por_modelo"]) == {embedder.model, "outro-modelo-v9"}

    def test_batch_limit_fatia(self, brain_f3, embedder) -> None:
        relatorio = run_embedding_pipeline(brain_f3, embedder=embedder, batch_limit=3)
        assert relatorio.novos == 3

    def test_falha_do_provedor_nao_levanta(self, brain_f3) -> None:
        class Quebrado:
            model = "quebrado"
            dimension = 8

            def embed(self, texts):
                raise RuntimeError("provedor fora do ar")

        relatorio = run_embedding_pipeline(brain_f3, embedder=Quebrado())
        assert relatorio.novos == 0
        assert relatorio.erros and "RuntimeError" in relatorio.erros[0]

    def test_erro_nao_carrega_conteudo(self, brain_f3) -> None:
        """Mensagem de erro nao pode virar canal de vazamento."""

        class Quebrado:
            model = "quebrado"
            dimension = 8

            def embed(self, texts):
                raise RuntimeError(texts[0])  # tenta levar o corpo junto

        relatorio = run_embedding_pipeline(brain_f3, embedder=Quebrado())
        assert relatorio.erros
        assert "emulsao" not in " ".join(relatorio.erros).lower()
        assert "pistache" not in " ".join(relatorio.erros).lower()

    def test_identidade_e_o_mesmo_sha_do_chunk(self) -> None:
        assert embedding_identity("abc") == checksum_of("abc")

    def test_indexa_todo_status(self, brain_f3, embedder) -> None:
        """Indexar nao e publicar: TO_VALIDATE tambem entra no indice."""

        indexaveis = {linha["chunk_id"] for linha in brain_f3.chunks_for_embedding()}
        confirmados = {
            linha["chunk_id"]
            for linha in brain_f3.chunks_for_search(
                statuses=frozenset({"CONFIRMED"}), layers=frozenset({"L0", "L1", "L2", "L3"})
            )
        }
        assert indexaveis > confirmados


# =============================================================================
# VETORES
# =============================================================================


class TestVetores:
    def test_normalize_produz_norma_um(self) -> None:
        vetor = normalize([3.0, 4.0])
        assert cosine(vetor, vetor) == pytest.approx(1.0)
        assert sum(v * v for v in vetor) == pytest.approx(1.0)

    def test_cosine_de_vetores_iguais_e_um(self) -> None:
        assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_cosine_de_ortogonais_e_zero(self) -> None:
        assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_cosine_tolera_entrada_degenerada(self) -> None:
        assert cosine([], [1.0]) == 0.0
        assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
        assert cosine([1.0, 2.0], [1.0]) == 0.0

    def test_embedder_deterministico_e_estavel(self, embedder) -> None:
        assert embedder.embed(["ganache"]) == embedder.embed(["ganache"])

    def test_producao_declara_modelo_e_dimensao(self) -> None:
        assert DEFAULT_MODEL == "text-embedding-3-small"
        assert DEFAULT_DIMENSION == 1536


# =============================================================================
# HYBRID FUSION
# =============================================================================


class TestFusao:
    def test_primeiro_das_duas_pernas_vence(self) -> None:
        fundido = reciprocal_rank_fusion({"lexical": ["a", "b"], "vetorial": ["a", "c"]})
        assert fundido[0].key == "a"

    def test_score_e_a_soma_das_reciprocas(self) -> None:
        fundido = reciprocal_rank_fusion({"lexical": ["a"], "vetorial": ["a"]})
        assert fundido[0].score == pytest.approx(2 / (RRF_K + 1))

    def test_perna_ausente_nao_contribui(self) -> None:
        fundido = {i.key: i for i in reciprocal_rank_fusion({"lexical": ["a"], "vetorial": ["b"]})}
        assert set(fundido["a"].ranks) == {"lexical"}
        assert set(fundido["b"].ranks) == {"vetorial"}

    def test_e_deterministico(self) -> None:
        entrada = {"lexical": ["a", "b", "c"], "vetorial": ["c", "a"]}
        assert [i.key for i in reciprocal_rank_fusion(entrada)] == [
            i.key for i in reciprocal_rank_fusion(entrada)
        ]

    def test_repetido_na_mesma_perna_conta_uma_vez(self) -> None:
        fundido = reciprocal_rank_fusion({"lexical": ["a", "a", "a"]})
        assert len(fundido) == 1
        assert fundido[0].ranks == {"lexical": 1}

    def test_explica_a_posicao(self) -> None:
        fundido = reciprocal_rank_fusion({"lexical": ["a"], "vetorial": ["b", "a"]})
        explicacao = next(i for i in fundido if i.key == "a").explain()
        assert "lexical #1" in explicacao
        assert "vetorial #2" in explicacao

    def test_entrada_vazia_devolve_vazio(self) -> None:
        assert reciprocal_rank_fusion({"lexical": [], "vetorial": []}) == []


# =============================================================================
# RAG_MODE / ROLLBACK
# =============================================================================


class TestRagMode:
    def test_default_e_current(self, monkeypatch) -> None:
        monkeypatch.delenv("RAG_MODE", raising=False)
        assert rag_mode() == "current"
        assert not uses_vector()
        assert not vector_decides()

    def test_valor_desconhecido_cai_no_default(self, monkeypatch) -> None:
        monkeypatch.setenv("RAG_MODE", "hibrido-turbo")
        assert rag_mode() == "current"
        assert rag_mode_report()["valor_ignorado"] == "hibrido-turbo"

    def test_shadow_consulta_mas_nao_decide(self, monkeypatch) -> None:
        monkeypatch.setenv("RAG_MODE", "hybrid_shadow")
        assert uses_vector()
        assert not vector_decides()

    def test_hybrid_decide(self, monkeypatch) -> None:
        monkeypatch.setenv("RAG_MODE", "hybrid")
        assert uses_vector()
        assert vector_decides()

    def test_apagar_a_variavel_reverte(self, monkeypatch) -> None:
        monkeypatch.setenv("RAG_MODE", "hybrid")
        assert vector_decides()
        monkeypatch.delenv("RAG_MODE")
        assert rag_mode() == "current"


# =============================================================================
# SHADOW MODE
# =============================================================================


class TestShadow:
    def _buscar(self, repo, modo, embedder, agente=VENDEDOR, pergunta="quanto custa o ebook das casquinhas?"):
        return search(agent_id=agente, query=pergunta, repository=repo, mode=modo, embedder=embedder)

    def test_shadow_devolve_o_mesmo_que_current(self, brain_indexado, embedder) -> None:
        atual = self._buscar(brain_indexado, "current", embedder)
        sombra = self._buscar(brain_indexado, "hybrid_shadow", embedder)

        assert [h.provenance.external_key for h in atual.hits] == [h.provenance.external_key for h in sombra.hits]

    def test_shadow_registra_o_que_o_hibrido_teria_feito(self, brain_indexado, embedder) -> None:
        sombra = self._buscar(brain_indexado, "hybrid_shadow", embedder)
        assert sombra.retrieval_mode == "HYBRID_SHADOW"
        assert sombra.shadow_keys
        assert sombra.vector_candidates > 0

    def test_current_nao_toca_no_indice(self, brain_indexado, embedder) -> None:
        atual = self._buscar(brain_indexado, "current", embedder)
        assert atual.retrieval_mode == "LEXICAL"
        assert atual.vector_candidates == 0
        assert atual.vector_skip_reason == "rag_mode=current"
        assert atual.embedding_model is None

    def test_hybrid_marca_o_modo(self, brain_indexado, embedder) -> None:
        assert self._buscar(brain_indexado, "hybrid", embedder).retrieval_mode == "HYBRID"


# =============================================================================
# DEGRADACAO
# =============================================================================


class TestDegradacao:
    def test_sem_indice_o_hibrido_vira_lexical(self, brain_f3, embedder) -> None:
        """Indice vazio nao pode virar busca vazia."""

        resultado = search(
            agent_id=VENDEDOR,
            query="quanto custa o ebook das casquinhas?",
            repository=brain_f3,
            mode="hybrid",
            embedder=embedder,
        )
        assert resultado.hits, "degradou para lexical, entao ainda tem que responder"
        assert resultado.retrieval_mode == "LEXICAL_DEGRADADO"
        assert "indexado" in (resultado.vector_skip_reason or "")

    def test_provedor_fora_do_ar_nao_derruba_a_busca(self, brain_indexado) -> None:
        class Quebrado:
            model = DeterministicEmbedder().model
            dimension = 64

            def embed(self, texts):
                raise RuntimeError("timeout")

        resultado = search(
            agent_id=VENDEDOR,
            query="quanto custa?",
            repository=brain_indexado,
            mode="hybrid",
            embedder=Quebrado(),
        )
        assert resultado.hits
        assert resultado.retrieval_mode == "LEXICAL_DEGRADADO"
        assert "provedor" in (resultado.vector_skip_reason or "")

    def test_indice_ilegivel_nao_derruba_a_busca(self, brain_indexado, embedder) -> None:
        class RepoQuebrado:
            def __init__(self, real):
                self._real = real

            def chunks_for_search(self, **kwargs):
                return self._real.chunks_for_search(**kwargs)

            def embeddings_for_checksums(self, *args, **kwargs):
                raise RuntimeError("conexao caiu")

        resultado = search(
            agent_id=VENDEDOR,
            query="quanto custa?",
            repository=RepoQuebrado(brain_indexado),
            mode="hybrid",
            embedder=embedder,
        )
        assert resultado.hits
        assert "indice indisponivel" in (resultado.vector_skip_reason or "")


# =============================================================================
# DIVERSIDADE
# =============================================================================


class TestDiversidade:
    def test_teto_por_documento_vale_no_hibrido(self, brain_indexado, embedder) -> None:
        from brain.retrieval import MAX_PER_DOCUMENT

        resultado = search(
            agent_id=SUPORTE,
            query="temperagem casquinha ganache emulsao",
            repository=brain_indexado,
            limit=4,
            mode="hybrid",
            embedder=embedder,
        )
        contagem: dict[str, int] = {}
        for hit in resultado.hits:
            contagem[hit.provenance.document_id] = contagem.get(hit.provenance.document_id, 0) + 1
        assert all(n <= MAX_PER_DOCUMENT for n in contagem.values()), contagem

    def test_diversidade_nao_reduz_o_numero_de_resultados(self, brain_indexado, embedder) -> None:
        atual = search(agent_id=SUPORTE, query="ganache", repository=brain_indexado, mode="current")
        hibrido = search(
            agent_id=SUPORTE, query="ganache", repository=brain_indexado, mode="hybrid", embedder=embedder
        )
        assert len(hibrido.hits) >= len(atual.hits)


# =============================================================================
# OBSERVABILIDADE
# =============================================================================


class TestObservabilidade:
    def test_o_resultado_explica_cada_posicao(self, brain_indexado, embedder) -> None:
        resultado = search(
            agent_id=VENDEDOR,
            query="quanto custa o ebook das casquinhas?",
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
        )
        assert resultado.hits
        for hit in resultado.hits:
            assert hit.ranking is not None
            assert "explicacao" in hit.ranking
            assert hit.ranking["posicoes"]

    def test_observability_nao_carrega_conteudo(self, brain_indexado, embedder) -> None:
        resultado = search(
            agent_id=SUPORTE,
            query="pistache emulsao",
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
        )
        texto = repr(resultado.observability()).lower()
        assert "sintetico" not in texto, "corpo do chunk vazou na observabilidade"
        assert "quebra da emulsao" not in texto

    def test_observability_traz_o_que_diagnostica(self, brain_indexado, embedder) -> None:
        obs = search(
            agent_id=VENDEDOR, query="quanto custa?", repository=brain_indexado, mode="hybrid", embedder=embedder
        ).observability()
        for campo in (
            "retrieval_mode",
            "rag_mode",
            "lexical_candidates",
            "vector_candidates",
            "final_candidates",
            "embedding_model",
            "documentos_distintos",
            "latency_ms",
        ):
            assert campo in obs, campo

    def test_rastro_e_coletado_por_execucao(self, brain_indexado, embedder) -> None:
        from brain.retrieval_trace import get_trace, reset, start_trace, trace_summary

        reset()
        assert trace_summary() == {}, "sem buffer aberto nao se registra nada"

        start_trace()
        search(agent_id=VENDEDOR, query="quanto custa?", repository=brain_indexado, mode="hybrid", embedder=embedder)
        search(agent_id=VENDEDOR, query="tem desconto?", repository=brain_indexado, mode="hybrid", embedder=embedder)

        assert len(get_trace()) == 2
        resumo = trace_summary()
        assert resumo["retrieval_calls"] == 2
        assert resumo["rag_mode"] == "hybrid"
        reset()

    def test_resumo_do_rastro_nao_carrega_query(self, brain_indexado, embedder) -> None:
        from brain.retrieval_trace import reset, start_trace, trace_summary

        reset()
        start_trace()
        search(
            agent_id=SUPORTE,
            query="me passa a receita de pistache",
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
        )
        assert "pistache" not in repr(trace_summary()).lower()
        reset()

    def test_campos_do_rastro_estao_na_allowlist(self) -> None:
        """O que o resumo produz precisa poder ser persistido — ou some."""

        from brain.retrieval_trace import reset, start_trace, trace_summary
        from orchestration.execution_repository import _OUTCOME_ALLOWLIST

        reset()
        start_trace()
        from brain.retrieval_trace import record

        record({"retrieval_mode": "HYBRID", "rag_mode": "hybrid", "latency_ms": 1})
        faltando = set(trace_summary()) - set(_OUTCOME_ALLOWLIST)
        reset()
        assert not faltando, f"campos fora da allowlist do ExecutionLog: {faltando}"


# =============================================================================
# TIPOS QUE SO APARECEM EM PRODUCAO
# =============================================================================


class TestTiposDoDialeto:
    """O SQLite dos testes devolve `float`; o pgvector devolve `numpy.float32`.

    Essa diferenca derrubou a rota de eval em producao com
    `PydanticSerializationError: Unable to serialize unknown type:
    <class 'numpy.float32'>` — depois de a suite inteira passar em verde.

    Estes testes injetam o tipo de producao no dialeto de teste. E a unica
    forma honesta de cobrir a diferenca sem um Postgres na suite.
    """

    def test_cosine_devolve_float_de_python(self) -> None:
        import numpy as np

        resultado = cosine([np.float32(1.0), np.float32(0.0)], [np.float32(1.0), np.float32(0.0)])
        assert type(resultado) is float

    def test_busca_com_vetor_numpy_serializa(self, brain_indexado, embedder) -> None:
        """Reproduz o dialeto de producao: vetor de numpy vindo do banco."""

        import json

        import numpy as np

        real = brain_indexado.embeddings_for_checksums

        class RepoComNumpy:
            def __init__(self, base):
                self._base = base

            def chunks_for_search(self, **kwargs):
                return self._base.chunks_for_search(**kwargs)

            def embeddings_for_checksums(self, checksums, *, embedding_model):
                return {
                    chave: np.array(vetor, dtype=np.float32)
                    for chave, vetor in real(checksums, embedding_model=embedding_model).items()
                }

        resultado = search(
            agent_id=VENDEDOR,
            query="quanto custa o ebook das casquinhas?",
            repository=RepoComNumpy(brain_indexado),
            mode="hybrid",
            embedder=embedder,
        )
        assert resultado.hits
        # Se algum numero derivado do cosseno for numpy, isto estoura.
        json.dumps(resultado.observability())
        json.dumps(resultado.vector_scores)

    def test_o_repositorio_converte_na_fronteira(self, brain_indexado) -> None:
        from brain.embeddings import DEFAULT_MODEL, DeterministicEmbedder

        modelo = DeterministicEmbedder().model
        assert modelo != DEFAULT_MODEL

        linhas = brain_indexado.chunks_for_embedding()
        vetores = brain_indexado.embeddings_for_checksums(
            {str(linhas[0]["checksum"])}, embedding_model=modelo
        )
        for vetor in vetores.values():
            assert all(type(v) is float for v in vetor)


# =============================================================================
# PISO DE SIMILARIDADE
# =============================================================================


class TestPisoDeSimilaridade:
    """O piso e o que impede a perna vetorial de responder quando nao sabe.

    Cosseno nao tem nocao de "nao sei": perguntado sobre algo que o Brain nao
    tem, ele devolve o que estiver menos distante. O valor de producao foi
    calibrado por varredura contra o acervo real — ver a nota em
    `VECTOR_SCORE_FLOOR`. Aqui se prova que ele e APLICADO, nao qual e.
    """

    def test_o_piso_de_producao_esta_declarado(self) -> None:
        from brain.retrieval import LEXICAL_WEIGHT, VECTOR_SCORE_FLOOR, VECTOR_WEIGHT

        assert 0.0 < VECTOR_SCORE_FLOOR < 1.0
        assert LEXICAL_WEIGHT == VECTOR_WEIGHT, "assimetria de peso foi medida e reprovada"

    def test_o_piso_pertence_ao_modelo(self) -> None:
        """Trocar de embedder tem que trocar o piso junto, ou nao trocar nada."""

        from brain.embeddings import OpenAIEmbedder
        from brain.retrieval import VECTOR_SCORE_FLOOR

        assert OpenAIEmbedder().score_floor == VECTOR_SCORE_FLOOR
        assert DeterministicEmbedder().score_floor == 0.0, (
            "o embedder de teste vive numa escala de cosseno diferente (0.04-0.35); "
            "aplicar o piso de producao nele silenciaria a perna vetorial inteira"
        )

    def test_search_usa_o_piso_do_embedder(self, brain_indexado) -> None:
        # Instancia, nao subclasse: `DeterministicEmbedder` e um dataclass, e o
        # `__init__` dele sobrescreveria um atributo de classe herdado.
        exigente = DeterministicEmbedder()
        exigente.score_floor = 0.99

        resultado = search(
            agent_id=VENDEDOR,
            query="quanto custa?",
            repository=brain_indexado,
            mode="hybrid",
            embedder=exigente,
        )
        assert resultado.vector_candidates == 0

    def test_piso_alto_silencia_a_perna_vetorial(self, brain_indexado, embedder) -> None:
        resultado = search(
            agent_id=VENDEDOR,
            query="quanto custa?",
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
            vector_floor=0.999,
        )
        assert resultado.vector_candidates == 0
        assert resultado.hits, "sem vetor, o lexical continua respondendo"

    def test_piso_zero_deixa_tudo_passar(self, brain_indexado, embedder) -> None:
        com_piso = search(
            agent_id=VENDEDOR,
            query="quanto custa?",
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
            vector_floor=0.5,
        )
        sem_piso = search(
            agent_id=VENDEDOR,
            query="quanto custa?",
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
            vector_floor=0.0,
        )
        assert sem_piso.vector_candidates >= com_piso.vector_candidates

    def test_todo_candidato_vetorial_respeita_o_piso(self, brain_indexado, embedder) -> None:
        resultado = search(
            agent_id=SUPORTE,
            query="ganache emulsao temperagem",
            repository=brain_indexado,
            mode="hybrid",
            embedder=embedder,
            vector_floor=0.3,
        )
        assert all(score > 0.3 for score in resultado.vector_scores)

    def test_pesos_mudam_a_ordem_e_nao_a_permissao(self, brain_indexado, embedder) -> None:
        from brain.access_policy import resolve_access

        permitido = set(resolve_access(VENDEDOR).external_keys or ())
        for pesos in ({"lexical": 1.0, "vetorial": 1.0}, {"lexical": 5.0, "vetorial": 0.1}):
            resultado = search(
                agent_id=VENDEDOR,
                query="ganache pistache emulsao",
                repository=brain_indexado,
                mode="hybrid",
                embedder=embedder,
                weights=pesos,
            )
            fontes = {h.provenance.external_key or h.provenance.document_id for h in resultado.hits}
            assert fontes <= permitido
