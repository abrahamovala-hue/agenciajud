"""
F3 — as rotas administrativas do Brain.

Mesmas garantias da rota de ingestao da F2.7, e pelos mesmos motivos:

1. As rotas NAO EXISTEM sem a flag. Nao e checagem no handler — nao ha rota.
2. Nunca sao anonimas.
3. Nao aceitam SQL.
4. Nao devolvem conteudo — nem chunk, nem receita, nem vetor.

O item 4 e o mais facil de perder numa rota de diagnostico: e tentador
devolver "os 3 chunks mais parecidos" para depurar ranking. Isso seria um
vazamento com dashboard, e por isso ha teste especifico contra o corpo dos
documentos pagos aparecer em qualquer resposta.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.brain_admin import (
    ENV_FLAG,
    ROUTE_EMBEDDINGS,
    ROUTE_EVAL,
    ROUTE_EXECUTIONS,
    ROUTE_STATUS,
    install_brain_admin,
    is_enabled,
)

CHAVE = "chave-de-teste-f3-com-tamanho-suficiente-para-o-agno"


@pytest.fixture
def ligado(monkeypatch):
    monkeypatch.setenv(ENV_FLAG, "true")
    monkeypatch.setenv("OS_SECURITY_KEY", CHAVE)
    monkeypatch.setenv("BRAIN_EMBEDDER", "deterministic")


@pytest.fixture
def store(tmp_path):
    """Store em ARQUIVO, nao em memoria.

    O TestClient atende o handler numa thread de trabalho, e uma conexao
    `sqlite://` em memoria pertence a thread que a criou. Arquivo resolve sem
    inventar pool custom.
    """

    from sqlalchemy import create_engine

    from brain import bootstrap
    from brain.embeddings import DeterministicEmbedder, run_embedding_pipeline
    from tests.conftest import montar_brain_f3

    engine = create_engine(
        f"sqlite:///{tmp_path / 'brain_admin.sqlite'}", connect_args={"check_same_thread": False}
    )
    repo = montar_brain_f3(engine)
    run_embedding_pipeline(repo, embedder=DeterministicEmbedder())

    anterior = bootstrap._repository
    bootstrap.set_knowledge_repository(repo)
    yield repo
    bootstrap.set_knowledge_repository(anterior)
    engine.dispose()


def _app() -> tuple[FastAPI, bool]:
    from app.security import build_api_settings

    base = FastAPI()
    return base, install_brain_admin(base, build_api_settings())


def _cliente(base):
    return TestClient(base)


AUTORIZADO = {"Authorization": f"Bearer {CHAVE}"}


class TestFlag:
    def test_desligada_por_padrao(self, monkeypatch) -> None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
        assert not is_enabled()

    def test_sem_a_flag_a_rota_nao_e_registrada(self, monkeypatch) -> None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
        base, ativa = _app()
        assert not ativa
        caminhos = {r.path for r in base.routes}
        assert ROUTE_STATUS not in caminhos
        assert ROUTE_EMBEDDINGS not in caminhos
        assert ROUTE_EVAL not in caminhos

    def test_com_a_flag_as_tres_existem(self, ligado) -> None:
        base, ativa = _app()
        assert ativa
        caminhos = {r.path for r in base.routes}
        assert {ROUTE_STATUS, ROUTE_EMBEDDINGS, ROUTE_EVAL} <= caminhos


class TestAutenticacao:
    def test_status_exige_bearer(self, ligado, store) -> None:
        base, _ = _app()
        assert _cliente(base).get(ROUTE_STATUS).status_code in (401, 403)

    def test_embeddings_exige_bearer(self, ligado, store) -> None:
        base, _ = _app()
        assert _cliente(base).post(ROUTE_EMBEDDINGS, json={}).status_code in (401, 403)

    def test_eval_exige_bearer(self, ligado, store) -> None:
        base, _ = _app()
        assert _cliente(base).post(ROUTE_EVAL, json={}).status_code in (401, 403)

    def test_chave_errada_e_recusada(self, ligado, store) -> None:
        base, _ = _app()
        resposta = _cliente(base).get(ROUTE_STATUS, headers={"Authorization": "Bearer errada"})
        assert resposta.status_code in (401, 403)


class TestStatus:
    def test_traz_o_diagnostico(self, ligado, store) -> None:
        base, _ = _app()
        corpo = _cliente(base).get(ROUTE_STATUS, headers=AUTORIZADO).json()

        assert corpo["banco"]["dialeto"] == "sqlite"
        assert corpo["contagens"]["chunks"] > 0
        assert corpo["rag_mode"]["rag_mode"] in ("current", "hybrid_shadow", "hybrid")
        assert "indice_semantico" in corpo
        assert corpo["migrations_aplicadas"]

    def test_catalogo_indisponivel_nao_derruba(self, ligado, store) -> None:
        """SQLite nao tem `pg_extension`. O campo diz isso em vez de estourar."""

        base, _ = _app()
        corpo = _cliente(base).get(ROUTE_STATUS, headers=AUTORIZADO).json()
        assert "indisponivel" in str(corpo["banco"]["pgvector_disponivel"])

    def test_nao_devolve_conteudo(self, ligado, store) -> None:
        base, _ = _app()
        texto = _cliente(base).get(ROUTE_STATUS, headers=AUTORIZADO).text.lower()
        for proibido in ("emulsao", "pistache", "brigadeiro", "sintetico"):
            assert proibido not in texto, proibido


class TestEmbeddings:
    def test_dry_run_nao_grava(self, ligado, store) -> None:
        base, _ = _app()
        antes = store.embedding_stats()["vetores"]
        corpo = _cliente(base).post(ROUTE_EMBEDDINGS, json={"dry_run": True}, headers=AUTORIZADO).json()

        assert corpo["dry_run"] is True
        assert corpo["novos"] == 0
        assert store.embedding_stats()["vetores"] == antes

    def test_reporta_contagem_e_nao_conteudo(self, ligado, store) -> None:
        base, _ = _app()
        resposta = _cliente(base).post(ROUTE_EMBEDDINGS, json={}, headers=AUTORIZADO)

        assert resposta.status_code == 200
        assert "chunks_elegiveis" in resposta.json()
        for proibido in ("emulsao", "pistache", "sintetico"):
            assert proibido not in resposta.text.lower()

    def test_batch_limit_tem_teto(self, ligado, store) -> None:
        base, _ = _app()
        assert _cliente(base).post(ROUTE_EMBEDDINGS, json={"batch_limit": 99999}, headers=AUTORIZADO).status_code == 422

    def test_nao_aceita_sql(self, ligado, store) -> None:
        """O corpo nao tem campo por onde comando arbitrario entre."""

        base, _ = _app()
        resposta = _cliente(base).post(
            ROUTE_EMBEDDINGS,
            json={"dry_run": True, "sql": "DROP TABLE judith_knowledge_chunks"},
            headers=AUTORIZADO,
        )
        assert resposta.status_code == 200
        assert store.counts()["chunks"] > 0


class TestEval:
    def test_compare_devolve_delta(self, ligado, store) -> None:
        base, _ = _app()
        corpo = _cliente(base).post(ROUTE_EVAL, json={"mode": "compare"}, headers=AUTORIZADO).json()

        assert "current" in corpo
        assert "hybrid" in corpo
        assert "delta" in corpo
        assert "regressoes_golden" in corpo

    def test_modo_invalido_e_recusado(self, ligado, store) -> None:
        base, _ = _app()
        assert _cliente(base).post(ROUTE_EVAL, json={"mode": "turbo"}, headers=AUTORIZADO).status_code == 400

    def test_apenas_golden_reduz_o_conjunto(self, ligado, store) -> None:
        base, _ = _app()
        cliente = _cliente(base)
        todos = cliente.post(ROUTE_EVAL, json={"mode": "current"}, headers=AUTORIZADO).json()
        golden = cliente.post(
            ROUTE_EVAL, json={"mode": "current", "apenas_golden": True}, headers=AUTORIZADO
        ).json()
        assert golden["casos"] < todos["casos"]

    def test_eval_nao_devolve_conteudo(self, ligado, store) -> None:
        base, _ = _app()
        resposta = _cliente(base).post(ROUTE_EVAL, json={"mode": "hybrid", "detalhado": True}, headers=AUTORIZADO)

        assert resposta.status_code == 200
        texto = resposta.text.lower()
        for proibido in ("emulsao", "quebra da", "sintetico", "brigadeiro gourmet"):
            assert proibido not in texto, proibido

    def test_o_eval_nao_altera_o_acervo(self, ligado, store) -> None:
        base, _ = _app()
        antes = store.counts()
        _cliente(base).post(ROUTE_EVAL, json={"mode": "compare"}, headers=AUTORIZADO)
        assert store.counts() == antes


class TestExecutions:
    """A rota que fecha o laco: o hibrido rodou mesmo num atendimento real?"""

    @pytest.fixture
    def com_execucao(self, store, tmp_path):
        # A fixture global aponta o ExecutionLog para `sqlite://` em memoria,
        # que pertence a thread que a criou — e o TestClient atende em outra.
        # Arquivo, como no `store`.
        from sqlalchemy import create_engine

        from orchestration.execution_log import ExecutionLog
        from orchestration.execution_repository import (
            ExecutionRepository,
            get_execution_repository,
            persist_execution,
            set_execution_repository,
        )

        engine = create_engine(
            f"sqlite:///{tmp_path / 'exec.sqlite'}", connect_args={"check_same_thread": False}
        )
        repositorio = ExecutionRepository(engine)
        repositorio.ensure_table()
        # Guardar o anterior e obrigatorio: a fixture autouse da suite aponta
        # a persistencia para memoria por teste, e deixar o global apontando
        # para um engine ja descartado vaza estado para quem rodar depois.
        anterior_exec = get_execution_repository()
        set_execution_repository(repositorio)

        log = ExecutionLog(workflow="ANSWER_DM", channel="whatsapp")
        log.session_id = "wa:ANSWER_DM:wa_teste"
        log.user_ref = "wa_teste"
        log.inputs["message"] = "quanto custa o ebook de pistache com receita completa?"
        log.result = "Resposta da cliente que NAO pode aparecer na rota."
        log.outputs.update(
            {
                "evidence_status": "PASS",
                "outbound_allowed": True,
                "sources_opened": ["OFFERS"],
                "retrieval_mode": ["HYBRID"],
                "rag_mode": "hybrid",
                "vector_candidates": 7,
                "outbound_message": "texto que tambem nao pode sair",
            }
        )
        log.finish(status="completed")
        persist_execution(log)
        yield store
        set_execution_repository(anterior_exec)
        engine.dispose()

    def test_exige_bearer(self, ligado, store) -> None:
        base, _ = _app()
        assert _cliente(base).get(ROUTE_EXECUTIONS).status_code in (401, 403)

    def test_devolve_a_telemetria(self, ligado, com_execucao) -> None:
        base, _ = _app()
        corpo = _cliente(base).get(ROUTE_EXECUTIONS, headers=AUTORIZADO).json()

        assert corpo["total_registrado"] >= 1
        primeira = corpo["execucoes"][0]
        assert primeira["workflow"] == "ANSWER_DM"
        assert primeira["telemetria"]["rag_mode"] == "hybrid"
        assert primeira["telemetria"]["retrieval_mode"] == ["HYBRID"]

    def test_nao_devolve_conversa(self, ligado, com_execucao) -> None:
        """O teste que impede a rota de diagnostico de virar vazamento."""

        base, _ = _app()
        texto = _cliente(base).get(ROUTE_EXECUTIONS, headers=AUTORIZADO).text.lower()

        for proibido in ("pistache", "resposta da cliente", "outbound_message", "receita completa", "inputs"):
            assert proibido not in texto, proibido

    def test_limite_tem_teto(self, ligado, com_execucao) -> None:
        base, _ = _app()
        corpo = _cliente(base).get(f"{ROUTE_EXECUTIONS}?limit=9999", headers=AUTORIZADO).json()
        assert len(corpo["execucoes"]) <= 25


class TestTelemetriaDeTargeting:
    """A projecao da rota tem que acompanhar a allowlist do ExecutionLog.

    As duas listas sao independentes, e ficaram fora de sincronia: os campos de
    source targeting eram persistidos e nao apareciam na rota. O smoke mostrava
    OFFERS no resultado sem dizer se ela venceu o ranking ou recebeu a vaga
    reservada — que e exatamente a pergunta que a rota existe para responder.
    """

    def test_a_rota_projeta_o_que_o_rastro_produz(self) -> None:
        from app.brain_admin import _CAMPOS_DE_OUTCOME
        from brain.retrieval_trace import record, reset, start_trace, trace_summary

        reset()
        start_trace()
        record(
            {
                "retrieval_mode": "HYBRID",
                "rag_mode": "hybrid",
                "canonical_target_requested": ["preco"],
                "canonical_target_available": True,
                "canonical_target_selected": True,
            }
        )
        produzidos = set(trace_summary())
        reset()

        faltando = produzidos - set(_CAMPOS_DE_OUTCOME)
        assert not faltando, f"o rastro produz campos que a rota nao mostra: {faltando}"

    def test_a_projecao_cabe_na_allowlist(self) -> None:
        """E o inverso: a rota nao pode mostrar o que nao pode ser persistido."""

        from app.brain_admin import _CAMPOS_DE_OUTCOME
        from orchestration.execution_repository import _OUTCOME_ALLOWLIST

        assert set(_CAMPOS_DE_OUTCOME) <= set(_OUTCOME_ALLOWLIST)
