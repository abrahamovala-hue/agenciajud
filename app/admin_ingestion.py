"""
Ingestao administrativa one-shot — o unico caminho ate o Postgres privado.

POR QUE ISTO EXISTE
-------------------

O Postgres de producao so responde em `postgres.railway.internal`. Nao ha
proxy TCP, nao ha dominio, e criar um seria expor o banco a internet para
resolver um problema de importacao — exatamente o que nao se deve fazer.

Os caminhos foram testados, nao presumidos:

    Railway MCP (tools)   inspecao e variaveis; sem exec, sem query
    Railway AI agent      so leitura de arquivo no container
    railway ssh           exige chave ed25519 que nao existe nesta maquina
    proxy TCP no Postgres nao configurado (e nao vamos configurar)

Sobrou o mecanismo minimo: o proprio app, que ja vive dentro da rede privada
e ja tem `DATABASE_URL`, aceita o conteudo ja extraido por uma rota
autenticada e grava usando o MESMO repositorio da ingestao local.

AS QUATRO RESTRICOES QUE ISTO RESPEITA
--------------------------------------

1. **Nao amplia a superficie anonima.** A rota exige Bearer pela dependencia
   nativa do Agno — a mesma de todo router administrativo. `/health` e o
   webhook da Meta continuam sendo as unicas rotas anonimas.

2. **Nao existe por padrao.** Sem `ADMIN_INGESTION_ENABLED=true` a rota nao e
   registrada. Nao e uma checagem dentro do handler: o endpoint simplesmente
   nao aparece no app. Liga-se para importar, desliga-se depois.

3. **Nao aceita SQL.** O corpo e um documento com conteudo e chunks. Nao ha
   caminho para executar comando arbitrario — isso transformaria a rota num
   backdoor com aparencia de ferramenta.

4. **Nao loga conteudo.** O retorno e contagem, hash e id. Uma receita paga
   nunca aparece em log, nem em erro.

O QUE ELA NAO FAZ
-----------------

Nao aprova nada. Documento entra TO_VALIDATE, como na ingestao local. Nao ha
import de `approve_version` aqui.
"""

from __future__ import annotations

from os import getenv
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

ENV_FLAG = "ADMIN_INGESTION_ENABLED"
ROUTE = "/admin/knowledge/primary-sources"


def is_enabled() -> bool:
    """A rota so existe quando declarada. Default fechado."""

    return (getenv(ENV_FLAG) or "").strip().lower() in ("1", "true", "yes")


class ChunkPayload(BaseModel):
    body: str
    heading: str | None = None
    heading_path: str | None = None
    page: int | None = None
    content_kind: str | None = None
    recipe_id: str | None = None
    entitlement_scope: str | None = None


class ArtifactPayload(BaseModel):
    """Metadados do PDF original. Os BYTES sao opcionais.

    O original legal vive na pasta da Judith. O que producao precisa para
    auditar e a identidade: sha256, paginas, tamanho. Subir 33 MB de PDF por
    HTTP para provar um hash que ja viaja no corpo seria custo sem ganho.
    """

    filename: str
    sha256: str
    size_bytes: int
    page_count: int | None = None
    normalized_sha256: str | None = None
    source_authority: str
    provided_by: str | None = None


class DocumentPayload(BaseModel):
    external_key: str
    title: str
    body: str
    layer: str
    content_access: str
    source_id: str
    source_kind: str = "judith"
    source_title: str = "Fontes primarias fornecidas por Judith"
    topics: list[str] = Field(default_factory=list)
    source_authority: str
    entitlement_scope: str | None = None
    source_ref: str = ""
    chunks: list[ChunkPayload] = Field(default_factory=list)
    artifact: ArtifactPayload | None = None


class IngestionPayload(BaseModel):
    documents: list[DocumentPayload]


def _resumo(documento: DocumentPayload, resultado: dict[str, Any]) -> dict[str, Any]:
    """O que volta para o chamador. Contagem e hash, nunca conteudo."""

    return {
        "external_key": documento.external_key,
        "document_id": resultado["document_id"],
        "versao": resultado["versao"],
        "chunks": resultado["chunks"],
        "status": resultado["status"],
        "content_access": documento.content_access,
        "mudou": resultado["mudou"],
        "checksum": resultado["checksum"],
    }


def install_admin_ingestion(base_app: FastAPI, settings: Any) -> bool:
    """Registra a rota se a flag permitir. Devolve se registrou."""

    if not is_enabled():
        return False

    from app.security import build_auth_dependency

    auth = build_auth_dependency(settings)

    @base_app.post(
        ROUTE,
        tags=["Admin"],
        operation_id="ingest_primary_sources",
        dependencies=[Depends(auth)],
    )
    async def ingest(payload: IngestionPayload) -> dict[str, Any]:
        from brain.bootstrap import get_knowledge_repository
        from brain.repository import checksum_of

        repositorio = get_knowledge_repository()
        if repositorio is None:  # pragma: no cover - so acontece se o boot falhou
            raise HTTPException(status_code=503, detail="knowledge store indisponivel")

        gravados: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []

        for documento in payload.documents:
            repositorio.upsert_source(
                source_id=documento.source_id,
                kind=documento.source_kind,
                origin="upload",
                owner="judith",
                title=documento.source_title,
                description="Fonte primaria enviada pela ingestao administrativa one-shot.",
                source_ref="externo:judith sources/",
            )

            artifact_id = None
            if documento.artifact is not None:
                artifact_id, criado = repositorio.store_artifact(
                    source_id=documento.source_id,
                    filename=documento.artifact.filename,
                    # Sem bytes: a identidade e o hash, e o original fica com
                    # a Judith. `content` aceita vazio para este caso.
                    content=b"",
                    sha256=documento.artifact.sha256,
                    page_count=documento.artifact.page_count,
                    normalized_sha256=documento.artifact.normalized_sha256,
                    source_authority=documento.artifact.source_authority,
                    provided_by=documento.artifact.provided_by,
                )
                artifacts.append(
                    {
                        "artifact_id": artifact_id,
                        "filename": documento.artifact.filename,
                        "sha256": documento.artifact.sha256,
                        "paginas": documento.artifact.page_count,
                        "criado": criado,
                    }
                )

            checksum = checksum_of(documento.body)
            existente = repositorio.get_document_by_external_key(documento.external_key)

            if existente and existente["checksum"] == checksum:
                atual = repositorio.get_current_version(existente["document_id"])
                gravados.append(
                    _resumo(
                        documento,
                        {
                            "document_id": existente["document_id"],
                            "versao": int(atual["version"]) if atual else 0,
                            "chunks": len(repositorio.get_chunks(atual["version_id"])) if atual else 0,
                            "status": str(existente["status"]),
                            "mudou": False,
                            "checksum": checksum,
                        },
                    )
                )
                continue

            if existente is None:
                document_id = repositorio.create_document(
                    source_id=documento.source_id,
                    title=documento.title,
                    layer=documento.layer,
                    status="TO_VALIDATE",
                    content_access=documento.content_access,
                    checksum=checksum,
                    external_key=documento.external_key,
                    source_ref=documento.source_ref,
                    topics=tuple(documento.topics),
                    confidence="alto",
                )
            else:
                document_id = existente["document_id"]

            repositorio.set_document_provenance(
                document_id=document_id,
                source_authority=documento.source_authority,
                provided_by="Judith",
                entitlement_scope=documento.entitlement_scope,
                artifact_id=artifact_id,
            )

            version_id, versao = repositorio.add_version(
                document_id=document_id,
                body=documento.body,
                created_by="admin-ingestion-f27",
                change_reason="Ingestao administrativa one-shot a partir da fonte primaria.",
                source_ref=documento.source_ref,
                rechunk=not documento.chunks,
            )

            if documento.chunks:
                pedacos = [{**c.model_dump(), "document_id": document_id} for c in documento.chunks]
                quantidade = repositorio.write_chunks(
                    version_id=version_id, status="TO_VALIDATE", chunks=pedacos
                )
            else:
                quantidade = len(repositorio.get_chunks(version_id))

            gravados.append(
                _resumo(
                    documento,
                    {
                        "document_id": document_id,
                        "versao": versao,
                        "chunks": quantidade,
                        "status": "TO_VALIDATE",
                        "mudou": True,
                        "checksum": checksum,
                    },
                )
            )

        return {
            "documentos": gravados,
            "artifacts": artifacts,
            "totais": repositorio.counts(),
            "confirmados_automaticamente": 0,
        }

    return True
