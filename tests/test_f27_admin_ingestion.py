"""
F2.7 — a rota administrativa de ingestao.

O que estes testes protegem, em ordem de importancia:

1. A rota NAO EXISTE sem a flag. Nao e uma checagem no handler — o endpoint
   nao e registrado.
2. Ela nunca e anonima.
3. Ela nao aprova nada.
4. Ela nao devolve conteudo pago, nem em erro.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin_ingestion import ENV_FLAG, ROUTE, install_admin_ingestion, is_enabled


@pytest.fixture
def desligado(monkeypatch):
    monkeypatch.delenv(ENV_FLAG, raising=False)


@pytest.fixture
def ligado(monkeypatch):
    monkeypatch.setenv(ENV_FLAG, "true")


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Knowledge store isolado, plugado no bootstrap."""

    from sqlalchemy import create_engine

    from brain import bootstrap
    from brain.repository import KnowledgeRepository

    engine = create_engine(f"sqlite:///{tmp_path / 'admin.sqlite'}")
    repositorio = KnowledgeRepository(engine)
    repositorio.ensure_tables()
    bootstrap.set_knowledge_repository(repositorio)
    yield repositorio
    bootstrap.set_knowledge_repository(None)


def _app(settings=None) -> tuple[FastAPI, bool]:
    from app.security import build_api_settings

    base = FastAPI()
    ativa = install_admin_ingestion(base, settings or build_api_settings())
    return base, ativa


DOCUMENTO = {
    "external_key": "EBOOK_TESTE",
    "title": "Ebook de teste",
    "body": "# Ebook\n\nConteudo tecnico.\n",
    "layer": "L1",
    "content_access": "ENTITLEMENT_REQUIRED",
    "source_id": "src_teste",
    "source_authority": "USER_AUTHORIZED_PRIMARY_SOURCE",
    "entitlement_scope": "ebook_teste",
    "source_ref": "externo:teste.pdf",
    "topics": ["ebook"],
    "chunks": [
        {"body": "Pagina 1 do ebook.", "page": 1, "content_kind": "TECHNIQUE", "heading": "Intro"},
        {"body": "Pagina 2 do ebook.", "page": 2, "content_kind": "RECIPE", "recipe_id": "r::1"},
    ],
    "artifact": {
        "filename": "teste.pdf",
        "sha256": "a" * 64,
        "size_bytes": 1234,
        "page_count": 2,
        "source_authority": "USER_AUTHORIZED_PRIMARY_SOURCE",
        "provided_by": "Judith",
    },
}


class TestAFlagGovernaAExistencia:
    def test_sem_flag_a_rota_nao_e_registrada(self, desligado) -> None:
        base, ativa = _app()

        assert ativa is False
        assert is_enabled() is False
        assert all(getattr(r, "path", None) != ROUTE for r in base.routes)

    def test_sem_flag_a_rota_responde_404(self, desligado) -> None:
        base, _ = _app()
        cliente = TestClient(base)

        assert cliente.post(ROUTE, json={"documents": []}).status_code == 404

    def test_com_flag_a_rota_existe(self, ligado) -> None:
        base, ativa = _app()

        assert ativa is True
        assert any(getattr(r, "path", None) == ROUTE for r in base.routes)


class TestNuncaAnonima:
    def test_sem_bearer_recusa(self, ligado, monkeypatch) -> None:
        from agno.os.settings import AgnoAPISettings

        base, _ = _app(AgnoAPISettings(os_security_key="chave-de-teste"))
        cliente = TestClient(base)

        resposta = cliente.post(ROUTE, json={"documents": []})
        assert resposta.status_code in (401, 403)

    def test_bearer_errado_recusa(self, ligado) -> None:
        from agno.os.settings import AgnoAPISettings

        base, _ = _app(AgnoAPISettings(os_security_key="chave-de-teste"))
        cliente = TestClient(base)

        resposta = cliente.post(
            ROUTE, json={"documents": []}, headers={"Authorization": "Bearer errada"}
        )
        assert resposta.status_code in (401, 403)


class TestGravacao:
    @pytest.fixture
    def cliente(self, ligado, store):
        from agno.os.settings import AgnoAPISettings

        base, _ = _app(AgnoAPISettings(os_security_key=""))
        return TestClient(base), store

    def test_grava_documento_chunks_e_artifact(self, cliente) -> None:
        http, repositorio = cliente

        resposta = http.post(ROUTE, json={"documents": [DOCUMENTO]})
        assert resposta.status_code == 200, resposta.text

        corpo = resposta.json()
        assert len(corpo["documentos"]) == 1
        assert corpo["documentos"][0]["chunks"] == 2
        assert len(corpo["artifacts"]) == 1

        gravado = repositorio.get_document_by_external_key("EBOOK_TESTE")
        assert gravado is not None
        assert gravado["content_access"] == "ENTITLEMENT_REQUIRED"
        assert gravado["entitlement_scope"] == "ebook_teste"
        assert gravado["source_authority"] == "USER_AUTHORIZED_PRIMARY_SOURCE"

    def test_nada_vira_confirmed(self, cliente) -> None:
        http, _ = cliente

        corpo = http.post(ROUTE, json={"documents": [DOCUMENTO]}).json()
        assert corpo["confirmados_automaticamente"] == 0
        assert all(d["status"] == "TO_VALIDATE" for d in corpo["documentos"])

    def test_idempotente(self, cliente) -> None:
        http, repositorio = cliente

        http.post(ROUTE, json={"documents": [DOCUMENTO]})
        antes = repositorio.counts()
        segundo = http.post(ROUTE, json={"documents": [DOCUMENTO]}).json()

        assert repositorio.counts() == antes
        assert segundo["documentos"][0]["mudou"] is False

    def test_conteudo_alterado_cria_versao_nova(self, cliente) -> None:
        http, repositorio = cliente

        http.post(ROUTE, json={"documents": [DOCUMENTO]})
        alterado = {**DOCUMENTO, "body": DOCUMENTO["body"] + "\nLinha nova.\n"}
        segundo = http.post(ROUTE, json={"documents": [alterado]}).json()

        assert segundo["documentos"][0]["versao"] == 2
        assert segundo["documentos"][0]["mudou"] is True

    def test_resposta_nao_devolve_o_corpo(self, cliente) -> None:
        """Contagem, hash e id. Nunca o conteudo que acabou de ser gravado."""

        http, _ = cliente

        bruto = http.post(ROUTE, json={"documents": [DOCUMENTO]}).text
        assert "Conteudo tecnico" not in bruto
        assert "Pagina 1 do ebook" not in bruto

    def test_chunk_preserva_pagina_e_receita(self, cliente) -> None:
        http, repositorio = cliente

        http.post(ROUTE, json={"documents": [DOCUMENTO]})
        documento = repositorio.get_document_by_external_key("EBOOK_TESTE")
        versao = repositorio.get_current_version(documento["document_id"])
        pedacos = repositorio.get_chunks(versao["version_id"])

        assert [p["page"] for p in pedacos] == [1, 2]
        assert [p["content_kind"] for p in pedacos] == ["TECHNIQUE", "RECIPE"]
        assert pedacos[1]["recipe_id"] == "r::1"


class TestNaoAceitaSql:
    def test_o_payload_nao_tem_campo_de_comando(self) -> None:
        """Se um dia alguem adicionar `sql` ou `query`, isto quebra.

        Uma rota administrativa que executa comando arbitrario e um backdoor
        com aparencia de ferramenta.
        """

        from app.admin_ingestion import DocumentPayload, IngestionPayload

        campos = set(IngestionPayload.model_fields) | set(DocumentPayload.model_fields)
        for proibido in ("sql", "query", "command", "exec", "script", "eval"):
            assert proibido not in campos, proibido
