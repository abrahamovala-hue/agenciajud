"""
KnowledgeRepository — o unico modulo que sabe SQL sobre Knowledge.

Mesmo desenho da F1: recebe um Engine em vez de construir um, para que teste
e producao percorram o mesmo caminho de codigo.

O QUE ESTE REPOSITORIO SE RECUSA A FAZER
----------------------------------------

- **Nao aprova nada.** `approved_by`/`approved_at` so sao gravados por
  `approve_version()`, que exige um nome humano. Nenhuma outra funcao os
  toca, e o backfill nao chama essa.
- **Nao reescreve versao aprovada.** `add_version()` cria v+1; nunca faz
  UPDATE no corpo de uma versao existente. A anterior continua legivel.
- **Nao apaga documento DEPRECATED.** Ele fica, apontando para o sucessor.
- **Nao grava conteudo com segredo.** `add_version()` chama o scanner antes
  de qualquer INSERT e levanta se achar.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import MetaData, Table, and_, delete, insert, select, update
from sqlalchemy.engine import Engine

from brain.chunking import chunk_markdown
from brain.models import (
    ContentAccess,
    DocStatus,
    Layer,
    transition_allowed,
)
from brain.schema import (
    build_artifacts_table,
    build_chunks_table,
    build_conflicts_table,
    build_documents_table,
    build_sources_table,
    build_versions_table,
)
from brain.security import assert_no_secrets, scan_injection


def _now() -> datetime:
    return datetime.now(UTC)


def _id(prefixo: str) -> str:
    return f"{prefixo}_{uuid.uuid4().hex[:16]}"


def checksum_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class KnowledgeRepository:
    def __init__(self, engine: Engine, *, schema: str | None = None) -> None:
        self.engine = engine
        self.schema = schema
        self.metadata = MetaData(schema=schema)
        self.sources: Table = build_sources_table(self.metadata)
        self.documents: Table = build_documents_table(self.metadata)
        self.versions: Table = build_versions_table(self.metadata)
        self.chunks: Table = build_chunks_table(self.metadata)
        self.conflicts: Table = build_conflicts_table(self.metadata)
        self.artifacts: Table = build_artifacts_table(self.metadata)

    # --- schema ------------------------------------------------------------

    def ensure_tables(self) -> None:
        """Cria as tabelas se faltarem. Em producao quem cria e a migration."""

        self.metadata.create_all(self.engine, checkfirst=True)

    # --- escrita -----------------------------------------------------------

    def upsert_source(
        self,
        *,
        source_id: str,
        kind: str,
        origin: str,
        owner: str,
        title: str,
        description: str = "",
        source_ref: str = "",
    ) -> str:
        agora = _now()
        with self.engine.begin() as conexao:
            existe = conexao.execute(
                select(self.sources.c.source_id).where(self.sources.c.source_id == source_id)
            ).first()
            valores = {
                "kind": kind,
                "origin": origin,
                "owner": owner,
                "title": title,
                "description": description,
                "source_ref": source_ref,
                "updated_at": agora,
            }
            if existe:
                conexao.execute(update(self.sources).where(self.sources.c.source_id == source_id).values(**valores))
            else:
                conexao.execute(insert(self.sources).values(source_id=source_id, created_at=agora, **valores))
        return source_id

    def create_document(
        self,
        *,
        source_id: str,
        title: str,
        layer: Layer,
        status: DocStatus,
        content_access: ContentAccess,
        checksum: str,
        external_key: str | None = None,
        source_ref: str | None = None,
        language: str = "pt-BR",
        topics: tuple[str, ...] = (),
        confidence: str | None = None,
        document_id: str | None = None,
    ) -> str:
        agora = _now()
        doc_id = document_id or _id("doc")
        with self.engine.begin() as conexao:
            conexao.execute(
                insert(self.documents).values(
                    document_id=doc_id,
                    source_id=source_id,
                    source_ref=source_ref,
                    external_key=external_key,
                    title=title,
                    language=language,
                    checksum=checksum,
                    layer=layer,
                    status=status,
                    content_access=content_access,
                    topics=list(topics),
                    confidence=confidence,
                    valid_from=agora,
                    valid_to=None,
                    current_version=0,
                    deprecated_by=None,
                    created_at=agora,
                    updated_at=agora,
                )
            )
        return doc_id

    def add_version(
        self,
        *,
        document_id: str,
        body: str,
        created_by: str,
        change_reason: str = "",
        source_ref: str = "",
        rechunk: bool = True,
    ) -> tuple[str, int]:
        """Grava uma versao NOVA. Nunca sobrescreve a anterior.

        Bloqueia se o conteudo carregar segredo — e nao grava versao redigida
        no lugar. Ver `brain/security.py` para o porque.
        """

        assert_no_secrets(body, source_ref=source_ref or document_id)

        agora = _now()
        with self.engine.begin() as conexao:
            atual = conexao.execute(
                select(self.documents.c.current_version, self.documents.c.status).where(
                    self.documents.c.document_id == document_id
                )
            ).first()
            if atual is None:
                raise ValueError(f"documento {document_id} nao existe")

            proxima = int(atual[0] or 0) + 1
            version_id = _id("ver")
            conexao.execute(
                insert(self.versions).values(
                    version_id=version_id,
                    document_id=document_id,
                    version=proxima,
                    body=body,
                    checksum=checksum_of(body),
                    change_reason=change_reason,
                    created_by=created_by,
                    created_at=agora,
                    approved_by=None,
                    approved_at=None,
                )
            )
            conexao.execute(
                update(self.documents)
                .where(self.documents.c.document_id == document_id)
                .values(current_version=proxima, checksum=checksum_of(body), updated_at=agora)
            )
            status_documento = str(atual[1])

        if rechunk:
            self.rebuild_chunks(version_id=version_id, body=body, status=status_documento, document_id=document_id)
        return version_id, proxima

    def rebuild_chunks(self, *, version_id: str, body: str, status: str, document_id: str) -> int:
        """(Re)cria os chunks de uma versao. O corpo original nao e alterado."""

        topics = self._document_topics(document_id)
        pedacos = chunk_markdown(body)

        with self.engine.begin() as conexao:
            conexao.execute(delete(self.chunks).where(self.chunks.c.version_id == version_id))
            for pedaco in pedacos:
                deteccao = scan_injection(pedaco.body)
                conexao.execute(
                    insert(self.chunks).values(
                        chunk_id=_id("chk"),
                        version_id=version_id,
                        ordinal=pedaco.ordinal,
                        heading=pedaco.heading,
                        body=pedaco.body,
                        token_count=pedaco.token_count,
                        topics=list(topics),
                        status=status,
                        checksum=pedaco.checksum,
                        flags=deteccao.as_json() or None,
                    )
                )
        return len(pedacos)

    # --- F2.7: artifact original -------------------------------------------

    def store_artifact(
        self,
        *,
        source_id: str,
        filename: str,
        content: bytes,
        sha256: str,
        mime_type: str = "application/pdf",
        page_count: int | None = None,
        normalized_sha256: str | None = None,
        source_authority: str = "USER_AUTHORIZED_PRIMARY_SOURCE",
        provided_by: str | None = None,
        capture_date: datetime | None = None,
        extraction_warnings: list[str] | None = None,
    ) -> tuple[str, bool]:
        """Guarda o arquivo original. Idempotente por sha256.

        Devolve (artifact_id, criado). Reingerir o MESMO arquivo devolve o id
        existente e `criado=False` — o artifact e imutavel, entao nao ha
        UPDATE de `content` aqui nem em lugar nenhum.
        """

        with self.engine.begin() as conexao:
            existente = conexao.execute(
                select(self.artifacts.c.artifact_id).where(self.artifacts.c.sha256 == sha256)
            ).first()
            if existente:
                return str(existente[0]), False

            artifact_id = _id("art")
            conexao.execute(
                insert(self.artifacts).values(
                    artifact_id=artifact_id,
                    source_id=source_id,
                    filename=filename,
                    mime_type=mime_type,
                    sha256=sha256,
                    normalized_sha256=normalized_sha256,
                    size_bytes=len(content),
                    page_count=page_count,
                    content=content,
                    source_authority=source_authority,
                    provided_by=provided_by,
                    capture_date=capture_date,
                    extraction_warnings=extraction_warnings,
                    created_at=_now(),
                )
            )
        return artifact_id, True

    def get_artifact_metadata(self, artifact_id: str) -> dict[str, Any] | None:
        """Metadados do artifact, SEM os bytes.

        Separado de proposito: quase todo uso quer provar identidade (hash,
        paginas, tamanho), nao ler o PDF. Carregar 14 MB para isso seria
        desperdicio, e mais um lugar por onde conteudo pago circula sem
        necessidade.
        """

        colunas = [c for c in self.artifacts.c if c.name != "content"]
        with self.engine.begin() as conexao:
            linha = conexao.execute(
                select(*colunas).where(self.artifacts.c.artifact_id == artifact_id)
            ).mappings().first()
            return dict(linha) if linha else None

    def list_artifacts(self) -> list[dict[str, Any]]:
        colunas = [c for c in self.artifacts.c if c.name != "content"]
        with self.engine.begin() as conexao:
            return [dict(linha) for linha in conexao.execute(select(*colunas)).mappings()]

    def artifact_bytes(self, artifact_id: str) -> bytes | None:
        """Os bytes originais. Unico caminho — usado por reprocessamento.

        Nao existe rota de API que exponha isto, e nenhum agente o chama.
        """

        with self.engine.begin() as conexao:
            linha = conexao.execute(
                select(self.artifacts.c.content).where(self.artifacts.c.artifact_id == artifact_id)
            ).first()
            return bytes(linha[0]) if linha else None

    # --- F2.7: chunks ja segmentados ---------------------------------------

    def write_chunks(self, *, version_id: str, status: str, chunks: list[dict[str, Any]]) -> int:
        """Grava chunks que JA vieram segmentados por quem entende o formato.

        `rebuild_chunks` corta markdown por cabecalho. Um ebook em PDF nao tem
        cabecalho de markdown — a unidade e a receita, e quem sabe onde uma
        receita termina e `brain/recipes.py`, nao um cortador generico. Por
        isso este caminho existe: o chamador entrega os pedacos prontos, com
        `recipe_id` e `page`, e aqui so acontece a persistencia.
        """

        topics_por_documento: dict[str, list[str]] = {}
        with self.engine.begin() as conexao:
            conexao.execute(delete(self.chunks).where(self.chunks.c.version_id == version_id))
            for ordinal, pedaco in enumerate(chunks, start=1):
                corpo = str(pedaco["body"])
                deteccao = scan_injection(corpo)
                documento = str(pedaco.get("document_id") or "")
                if documento and documento not in topics_por_documento:
                    topics_por_documento[documento] = self._document_topics(documento)
                conexao.execute(
                    insert(self.chunks).values(
                        chunk_id=_id("chk"),
                        version_id=version_id,
                        ordinal=ordinal,
                        heading=pedaco.get("heading"),
                        body=corpo,
                        token_count=max(1, len(corpo) // 4),
                        topics=list(pedaco.get("topics") or topics_por_documento.get(documento, [])),
                        status=status,
                        checksum=checksum_of(corpo),
                        flags=deteccao.as_json() or None,
                        content_kind=pedaco.get("content_kind"),
                        page=pedaco.get("page"),
                        recipe_id=pedaco.get("recipe_id"),
                        heading_path=pedaco.get("heading_path"),
                        entitlement_scope=pedaco.get("entitlement_scope"),
                    )
                )
        return len(chunks)

    def set_document_provenance(
        self,
        *,
        document_id: str,
        source_authority: str | None = None,
        provided_by: str | None = None,
        entitlement_scope: str | None = None,
        artifact_id: str | None = None,
    ) -> None:
        """Preenche a procedencia. Nao toca status nem conteudo."""

        valores = {
            chave: valor
            for chave, valor in (
                ("source_authority", source_authority),
                ("provided_by", provided_by),
                ("entitlement_scope", entitlement_scope),
                ("artifact_id", artifact_id),
            )
            if valor is not None
        }
        if not valores:
            return
        with self.engine.begin() as conexao:
            conexao.execute(
                update(self.documents).where(self.documents.c.document_id == document_id).values(**valores)
            )

    def reconcile_metadata(
        self,
        *,
        document_id: str,
        layer: str,
        topics: tuple[str, ...],
        content_access: str,
        source_ref: str | None,
        title: str,
    ) -> dict[str, tuple[str, str]]:
        """Alinha classificacao sem criar versao nova.

        Camada, topics e content_access sao DERIVADOS da taxonomia, nao do
        conteudo. Quando a taxonomia muda (a L0 da F2.5, por exemplo), o
        checksum do arquivo continua igual e o backfill pularia o documento —
        deixando a classificacao velha no banco para sempre.

        Devolve o que mudou, para o relatorio nao ser silencioso. Status NUNCA
        entra aqui: status e aprovacao humana, nao classificacao.
        """

        atual = self.get_document(document_id)
        if atual is None:
            raise ValueError(f"documento {document_id} nao existe")

        alteracoes: dict[str, tuple[str, str]] = {}
        novos: dict[str, Any] = {}
        for campo, novo_valor in (
            ("layer", layer),
            ("content_access", content_access),
            ("source_ref", source_ref),
            ("title", title),
        ):
            if atual.get(campo) != novo_valor:
                alteracoes[campo] = (str(atual.get(campo)), str(novo_valor))
                novos[campo] = novo_valor

        if list(atual.get("topics") or []) != list(topics):
            alteracoes["topics"] = (str(atual.get("topics")), str(list(topics)))
            novos["topics"] = list(topics)

        if not novos:
            return {}

        novos["updated_at"] = _now()
        with self.engine.begin() as conexao:
            conexao.execute(update(self.documents).where(self.documents.c.document_id == document_id).values(**novos))
        # Os chunks carregam topics; realinha sem tocar no corpo.
        if "topics" in novos:
            versoes = self._version_ids(document_id)
            if versoes:
                with self.engine.begin() as conexao:
                    conexao.execute(
                        update(self.chunks).where(self.chunks.c.version_id.in_(versoes)).values(topics=list(topics))
                    )
        return alteracoes

    def _version_ids(self, document_id: str) -> list[str]:
        with self.engine.begin() as conexao:
            return [
                str(v)
                for v in conexao.execute(
                    select(self.versions.c.version_id).where(self.versions.c.document_id == document_id)
                ).scalars()
            ]

    def set_status(
        self,
        *,
        document_id: str,
        novo: DocStatus,
        deprecated_by: str | None = None,
        _via_aprovacao: bool = False,
    ) -> None:
        """Muda o status respeitando o ciclo de vida. DEPRECATED e terminal.

        CONFIRMED nao passa por aqui. A tabela de transicoes permite
        TO_VALIDATE -> CONFIRMED porque essa e a transicao legitima; o que
        nao pode e ela acontecer sem aprovacao humana registrada. `_via_aprovacao`
        e privado e so `approve_version()` o usa — nao existe outra porta.
        """

        if novo == "CONFIRMED" and not _via_aprovacao:
            raise ValueError(
                "CONFIRMED so pode ser atingido por approve_version(), que exige aprovacao humana nomeada. "
                "Nao existe promocao automatica para CONFIRMED."
            )

        with self.engine.begin() as conexao:
            atual = conexao.execute(
                select(self.documents.c.status).where(self.documents.c.document_id == document_id)
            ).scalar_one_or_none()
            if atual is None:
                raise ValueError(f"documento {document_id} nao existe")
            if not transition_allowed(atual, novo):  # type: ignore[arg-type]
                raise ValueError(f"transicao de status proibida: {atual} -> {novo}")

            valores: dict[str, Any] = {"status": novo, "updated_at": _now()}
            if novo == "DEPRECATED":
                valores["valid_to"] = _now()
                if deprecated_by:
                    valores["deprecated_by"] = deprecated_by
            conexao.execute(update(self.documents).where(self.documents.c.document_id == document_id).values(**valores))
            # Os chunks carregam o status para que a busca filtre sem join.
            versoes = (
                conexao.execute(select(self.versions.c.version_id).where(self.versions.c.document_id == document_id))
                .scalars()
                .all()
            )
            if versoes:
                conexao.execute(update(self.chunks).where(self.chunks.c.version_id.in_(versoes)).values(status=novo))

    def approve_version(self, *, document_id: str, version: int, approved_by: str) -> None:
        """A UNICA porta para CONFIRMED. Exige nome humano.

        `approved_by` vazio levanta: aprovacao anonima seria indistinguivel de
        aprovacao automatica, que e exatamente o que nao pode existir.
        """

        if not (approved_by or "").strip():
            raise ValueError("approved_by e obrigatorio: nao existe aprovacao anonima nem automatica")

        agora = _now()
        with self.engine.begin() as conexao:
            resultado = conexao.execute(
                update(self.versions)
                .where(and_(self.versions.c.document_id == document_id, self.versions.c.version == version))
                .values(approved_by=approved_by.strip(), approved_at=agora)
            )
            if resultado.rowcount == 0:
                raise ValueError(f"versao {version} do documento {document_id} nao existe")
        self.set_status(document_id=document_id, novo="CONFIRMED", _via_aprovacao=True)

    # --- leitura -----------------------------------------------------------

    def _document_topics(self, document_id: str) -> list[str]:
        with self.engine.begin() as conexao:
            valor = conexao.execute(
                select(self.documents.c.topics).where(self.documents.c.document_id == document_id)
            ).scalar_one_or_none()
        return list(valor or [])

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conexao:
            linha = (
                conexao.execute(select(self.documents).where(self.documents.c.document_id == document_id))
                .mappings()
                .first()
            )
        return dict(linha) if linha else None

    def get_document_by_external_key(self, external_key: str) -> dict[str, Any] | None:
        with self.engine.begin() as conexao:
            linha = (
                conexao.execute(select(self.documents).where(self.documents.c.external_key == external_key))
                .mappings()
                .first()
            )
        return dict(linha) if linha else None

    def list_documents(self, *, layer: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        consulta = select(self.documents)
        if layer:
            consulta = consulta.where(self.documents.c.layer == layer)
        if status:
            consulta = consulta.where(self.documents.c.status == status)
        with self.engine.begin() as conexao:
            return [dict(linha) for linha in conexao.execute(consulta.order_by(self.documents.c.title)).mappings()]

    def get_versions(self, document_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as conexao:
            return [
                dict(linha)
                for linha in conexao.execute(
                    select(self.versions)
                    .where(self.versions.c.document_id == document_id)
                    .order_by(self.versions.c.version)
                ).mappings()
            ]

    def get_current_version(self, document_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conexao:
            versao_atual = conexao.execute(
                select(self.documents.c.current_version).where(self.documents.c.document_id == document_id)
            ).scalar_one_or_none()
            if not versao_atual:
                return None
            linha = (
                conexao.execute(
                    select(self.versions).where(
                        and_(self.versions.c.document_id == document_id, self.versions.c.version == versao_atual)
                    )
                )
                .mappings()
                .first()
            )
        return dict(linha) if linha else None

    def chunks_for_search(self, *, statuses: frozenset[str], layers: frozenset[str]) -> list[dict[str, Any]]:
        """Chunks candidatos, ja com a provenance junto.

        Um join so, feito aqui, para que o retrieval nao precise conhecer o
        formato das tabelas.
        """

        consulta = (
            select(
                self.chunks.c.chunk_id,
                self.chunks.c.ordinal,
                self.chunks.c.heading,
                self.chunks.c.body,
                self.chunks.c.token_count,
                self.chunks.c.flags,
                self.chunks.c.status.label("chunk_status"),
                self.chunks.c.content_kind,
                self.chunks.c.page,
                self.chunks.c.recipe_id,
                self.chunks.c.heading_path,
                self.chunks.c.entitlement_scope,
                self.versions.c.version_id,
                self.versions.c.version,
                self.versions.c.approved_by,
                self.versions.c.approved_at,
                self.documents.c.document_id,
                self.documents.c.external_key,
                self.documents.c.title,
                self.documents.c.layer,
                self.documents.c.status,
                self.documents.c.content_access,
                self.documents.c.topics,
                self.documents.c.confidence,
                self.documents.c.valid_to,
                self.documents.c.deprecated_by,
                self.documents.c.source_authority,
                self.documents.c.provided_by,
                self.sources.c.source_id,
                self.sources.c.kind.label("source_kind"),
                self.sources.c.origin,
                self.sources.c.owner,
                self.sources.c.source_ref,
            )
            .select_from(
                self.chunks.join(self.versions, self.chunks.c.version_id == self.versions.c.version_id)
                .join(self.documents, self.versions.c.document_id == self.documents.c.document_id)
                .join(self.sources, self.documents.c.source_id == self.sources.c.source_id)
            )
            .where(self.documents.c.status.in_(tuple(statuses)))
            .where(self.documents.c.layer.in_(tuple(layers)))
            # So a versao vigente entra em busca. As anteriores continuam
            # gravadas para auditoria, nao para retrieval.
            .where(self.versions.c.version == self.documents.c.current_version)
        )
        with self.engine.begin() as conexao:
            return [dict(linha) for linha in conexao.execute(consulta).mappings()]

    def get_chunks(self, version_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as conexao:
            return [
                dict(linha)
                for linha in conexao.execute(
                    select(self.chunks).where(self.chunks.c.version_id == version_id).order_by(self.chunks.c.ordinal)
                ).mappings()
            ]

    def counts(self) -> dict[str, int]:
        from sqlalchemy import func

        with self.engine.begin() as conexao:
            return {
                "sources": int(conexao.execute(select(func.count()).select_from(self.sources)).scalar_one()),
                "documents": int(conexao.execute(select(func.count()).select_from(self.documents)).scalar_one()),
                "versions": int(conexao.execute(select(func.count()).select_from(self.versions)).scalar_one()),
                "chunks": int(conexao.execute(select(func.count()).select_from(self.chunks)).scalar_one()),
                "conflicts": int(conexao.execute(select(func.count()).select_from(self.conflicts)).scalar_one()),
            }

    def status_report(self) -> dict[str, int]:
        from sqlalchemy import func

        with self.engine.begin() as conexao:
            linhas = conexao.execute(
                select(self.documents.c.status, func.count()).group_by(self.documents.c.status)
            ).all()
        return {str(status): int(quantidade) for status, quantidade in linhas}
