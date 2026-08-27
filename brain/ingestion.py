"""
Ingestao das fontes primarias — do disco ao store, com prova.

    PDF  ->  artifact (bytes originais)
         ->  document EBOOK_*            L1, ENTITLEMENT_REQUIRED
         ->  document PRODUCT_OUTLINE_*  L3, PUBLIC   (derivado, seguro)

IDEMPOTENCIA
------------

Duas camadas, e as duas importam:

- **artifact**: chave e o sha256 do arquivo. Reingerir o mesmo PDF nao cria
  linha nova nem sobrescreve bytes.
- **document**: `add_version` so e chamado quando o checksum do texto muda.
  Rodar de novo sem trocar o PDF nao cria v+1.

O QUE NAO ACONTECE AQUI
-----------------------

- Nada vira CONFIRMED. Nenhuma chamada a `approve_version()`.
- Nenhum PDF e escrito no repositorio.
- Nenhum corpo de receita entra em log: o relatorio carrega contagem e hash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from brain.primary_sources import (
    APPROVAL_REASON,
    DEFAULT_SOURCE_DIR,
    Discovery,
    build_ebook_chunks,
    build_outline,
    completeness,
    discover,
    load_recipes,
)
from brain.repository import KnowledgeRepository, checksum_of

#: Os documentos derivados seguros. Chave do ebook -> chave do outline.
OUTLINE_KEYS: dict[str, str] = {
    "EBOOK_RECHEIOS": "PRODUCT_OUTLINE_RECHEIOS",
    "EBOOK_CASQUINHAS": "PRODUCT_OUTLINE_CASQUINHAS",
    "EBOOK_LASCAS": "PRODUCT_OUTLINE_LASCAS",
}

SOURCE_ID_PRIMARY = "src_judith_primary"
SOURCE_ID_SITE = "src_site_snapshot"


@dataclass
class IngestionReport:
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)
    completeness: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovery: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "artifacts": len(self.artifacts),
            "artifacts_novos": sum(1 for a in self.artifacts if a["criado"]),
            "documentos": len(self.documents),
            "documentos_pagos": sum(1 for d in self.documents if d["content_access"] == "ENTITLEMENT_REQUIRED"),
            "chunks": sum(d["chunks"] for d in self.documents),
            "inalterados": self.skipped,
            "erros": self.errors,
            "confirmados_automaticamente": 0,
        }


def _ensure_sources(repository: KnowledgeRepository) -> None:
    repository.upsert_source(
        source_id=SOURCE_ID_PRIMARY,
        kind="judith",
        origin="upload",
        owner="judith",
        title="Fontes primarias fornecidas por Judith",
        description=(
            "PDFs dos ebooks entregues pela Judith como fonte primaria atual. "
            "Propriedade intelectual paga: nunca versionada em Git."
        ),
        source_ref="externo:judith sources/",
    )
    repository.upsert_source(
        source_id=SOURCE_ID_SITE,
        kind="business",
        origin="upload",
        owner="judith",
        title="Snapshot do site oficial fornecido por Judith",
        description="PDF do site aprenda.atelierbemmeque.com gerado pela propria Judith.",
        source_ref="externo:judith sources/",
    )


def _upsert_document(
    repository: KnowledgeRepository,
    *,
    external_key: str,
    title: str,
    body: str,
    layer: str,
    content_access: str,
    source_id: str,
    topics: tuple[str, ...],
    source_authority: str,
    entitlement_scope: str | None,
    artifact_id: str | None,
    source_ref: str,
    chunks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cria ou versiona. Devolve o que aconteceu, sem conteudo."""

    checksum = checksum_of(body)
    existente = repository.get_document_by_external_key(external_key)

    if existente and existente["checksum"] == checksum:
        atual = repository.get_current_version(existente["document_id"])
        return {
            "external_key": external_key,
            "document_id": existente["document_id"],
            "status": str(existente["status"]),
            "content_access": content_access,
            "versao": int(atual["version"]) if atual else 0,
            "chunks": len(repository.get_chunks(atual["version_id"])) if atual else 0,
            "mudou": False,
        }

    if existente is None:
        document_id = repository.create_document(
            source_id=source_id,
            title=title,
            layer=layer,  # type: ignore[arg-type]
            # TO_VALIDATE, nunca CONFIRMED: a fonte e autorizada pela Judith,
            # o conteudo derivado ainda nao foi revisado linha a linha por ela.
            status="TO_VALIDATE",
            content_access=content_access,  # type: ignore[arg-type]
            checksum=checksum,
            external_key=external_key,
            source_ref=source_ref,
            topics=topics,
            confidence="alto",
        )
    else:
        document_id = existente["document_id"]

    repository.set_document_provenance(
        document_id=document_id,
        source_authority=source_authority,
        provided_by="Judith",
        entitlement_scope=entitlement_scope,
        artifact_id=artifact_id,
    )

    version_id, versao = repository.add_version(
        document_id=document_id,
        body=body,
        created_by="ingestion-f27",
        change_reason=APPROVAL_REASON,
        source_ref=source_ref,
        # Chunk de PDF nao se corta por cabecalho de markdown. Quando o
        # chamador entrega os pedacos prontos, o cortador generico e pulado.
        rechunk=chunks is None,
    )

    if chunks is not None:
        for pedaco in chunks:
            pedaco.setdefault("document_id", document_id)
        quantidade = repository.write_chunks(version_id=version_id, status="TO_VALIDATE", chunks=chunks)
    else:
        quantidade = len(repository.get_chunks(version_id))

    return {
        "external_key": external_key,
        "document_id": document_id,
        "status": "TO_VALIDATE",
        "content_access": content_access,
        "versao": versao,
        "chunks": quantidade,
        "mudou": True,
    }


def ingest_primary_sources(
    repository: KnowledgeRepository,
    *,
    folder: str | Path = DEFAULT_SOURCE_DIR,
    discovery: Discovery | None = None,
) -> IngestionReport:
    """Ingere os PDFs da pasta externa. Idempotente."""

    relatorio = IngestionReport()
    achados = discovery or discover(folder)
    relatorio.discovery = achados.report()
    _ensure_sources(repository)

    for item in achados.classified:
        spec = item.spec
        assert spec is not None
        documento = item.document
        eh_ebook = spec.entitlement_scope is not None
        source_id = SOURCE_ID_PRIMARY if eh_ebook else SOURCE_ID_SITE

        try:
            receitas = load_recipes(documento) if spec.key == "EBOOK_RECHEIOS" else None
        except Exception as erro:  # noqa: BLE001
            # Invariante de receita quebrado PARA este documento. Ingerir um
            # catalogo errado seria pior do que nao ingerir.
            relatorio.errors.append(f"{spec.key}: {type(erro).__name__}: {erro}")
            continue

        artifact_id, criado = repository.store_artifact(
            source_id=source_id,
            filename=documento.filename,
            content=Path(documento.path).read_bytes(),
            sha256=documento.sha256,
            page_count=documento.page_count,
            normalized_sha256=documento.normalized_sha256,
            source_authority=spec.authority,
            provided_by="Judith",
            # UNKNOWN: nenhum dos PDFs carrega data de captura comprovavel.
            capture_date=None,
            extraction_warnings=documento.warnings or None,
        )
        relatorio.artifacts.append(
            {
                "artifact_id": artifact_id,
                "fonte": spec.key,
                "filename": documento.filename,
                "sha256": documento.sha256,
                "paginas": documento.page_count,
                "bytes": documento.size_bytes,
                "criado": criado,
                "capture_date": "UNKNOWN",
            }
        )

        if eh_ebook:
            pedacos = build_ebook_chunks(documento, spec=spec, recipes=receitas)
            resultado = _upsert_document(
                repository,
                external_key=spec.key,
                title=spec.title,
                body=documento.text,
                layer="L1",
                content_access="ENTITLEMENT_REQUIRED",
                source_id=source_id,
                topics=("ebook", "tecnica", "chocolate"),
                source_authority=spec.authority,
                entitlement_scope=spec.entitlement_scope,
                artifact_id=artifact_id,
                source_ref=f"externo:{documento.filename}",
                chunks=pedacos,
            )
            relatorio.documents.append(resultado)
            if not resultado["mudou"]:
                relatorio.skipped.append(spec.key)

            outline = build_outline(documento, spec=spec, recipes=receitas)
            derivado = _upsert_document(
                repository,
                external_key=OUTLINE_KEYS[spec.key],
                title=f"{spec.title} — ficha do produto",
                body=outline,
                layer="L3",
                content_access="PUBLIC",
                source_id=source_id,
                topics=("produto", "ebook"),
                source_authority="DERIVED_DOCUMENT",
                entitlement_scope=None,
                artifact_id=artifact_id,
                source_ref=f"derivado de externo:{documento.filename}",
            )
            relatorio.documents.append(derivado)
            relatorio.completeness.append(completeness(documento, spec=spec, recipes=receitas))
        else:
            resultado = _upsert_document(
                repository,
                external_key=spec.key,
                title=spec.title,
                body=documento.text,
                layer="L3",
                content_access="PUBLIC",
                source_id=source_id,
                topics=("site", "oferta", "produto"),
                source_authority=spec.authority,
                entitlement_scope=None,
                artifact_id=artifact_id,
                source_ref=f"externo:{documento.filename}",
                chunks=build_ebook_chunks(documento, spec=spec),
            )
            relatorio.documents.append(resultado)
            relatorio.completeness.append(completeness(documento, spec=spec))

    return relatorio
