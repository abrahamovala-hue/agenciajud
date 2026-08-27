"""
Backfill — leva o catalogo de `DocumentSource` para o store do Brain.

O QUE NAO ACONTECE AQUI
-----------------------

- `docs/` nao e tocado. Continua sendo a fonte da verdade.
- `agents/knowledge_sources.py` nao e tocado. Continua sendo producao.
- Nenhum agente muda de comportamento. O store roda em paralelo.
- **Nada vira CONFIRMED.** Nenhuma linha deste arquivo chama
  `approve_version()`.

A REGRA DE STATUS
-----------------

`reliability` (vigente/snapshot/template) e uma afirmacao sobre a FONTE.
`status` (DRAFT/TO_VALIDATE/CONFIRMED) e uma afirmacao sobre APROVACAO
HUMANA. Traduzir uma na outra seria inventar aprovacao.

A busca por evidencia de validacao no repositorio encontrou o oposto: os
documentos que falam de validacao dizem "A VALIDAR COM JUDITH", "pendente de
validacao", "a ser preenchida com Judith". Nao ha nenhum documento marcado
como aprovado por ela.

Entao o mapeamento e:

    reliability=template  ou caveat de pendencia  ->  DRAFT
    reliability=snapshot                          ->  TO_VALIDATE
    reliability=vigente                           ->  TO_VALIDATE
    (nenhuma condicao)                            ->  CONFIRMED

DRAFT para template porque o proprio documento se declara incompleto — ele
nao esta pronto nem para ser revisado por inteiro. TO_VALIDATE para o resto
porque o conteudo esta pronto para a Judith olhar, mas ela nao olhou.

CONSEQUENCIA, DECLARADA E NAO ESCONDIDA: com zero documentos CONFIRMED,
`brain.search()` em modo producao devolve VAZIO. E por isso que o caminho
lexical continua sendo producao — e por isso que a F2 nao faz cutover.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from brain.repository import KnowledgeRepository, checksum_of
from brain.security import SecretDetectedError, scan_injection
from brain.taxonomy import content_access_for, layer_for, source_kind_for, topics_for

#: Marcadores que indicam que o documento se declara pendente. A presenca de
#: qualquer um rebaixa para DRAFT.
_PENDENCY_MARKERS = (
    "a validar",
    "a verificar",
    "pendente de validacao",
    "pendente de validação",
    "nao validad",
    "não validad",
    "a ser preenchid",
    "template",
    "propostos, nao validados",
    "propostos, não validados",
    "nao confirmad",
    "não confirmad",
)


def _tem_pendencia(texto: str) -> bool:
    baixo = (texto or "").casefold()
    return any(marcador in baixo for marcador in _PENDENCY_MARKERS)


def status_for(*, reliability: str, caveat: str) -> str:
    """Traduz confiabilidade da fonte em status de validacao.

    NUNCA devolve CONFIRMED. Isso e proposital e ha teste garantindo.
    """

    if reliability == "template" or _tem_pendencia(caveat):
        return "DRAFT"
    return "TO_VALIDATE"


def confidence_for(reliability: str) -> str:
    """Confianca na FONTE — nao e validacao, e nao vira uma."""

    return {"vigente": "alto", "snapshot": "medio", "template": "baixo"}.get(reliability, "medio")


@dataclass
class DocumentMap:
    """O mapa DocumentSource -> source -> document -> version -> chunks."""

    external_key: str
    relative_path: str
    source_id: str
    document_id: str
    version_id: str
    version: int
    layer: str
    status: str
    content_access: str
    topics: list[str]
    chunks: int
    checksum: str
    flagged_chunks: int = 0
    reconciled: dict[str, tuple[str, str]] = field(default_factory=dict)
    """O que mudou de classificacao sem mudar o conteudo. Vazio no caso normal."""


@dataclass
class BackfillReport:
    mapped: list[DocumentMap] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    missing_on_disk: list[str] = field(default_factory=list)
    skipped_unchanged: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.mapped)

    def by_status(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for item in self.mapped:
            contagem[item.status] = contagem.get(item.status, 0) + 1
        return contagem

    def by_layer(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for item in self.mapped:
            contagem[item.layer] = contagem.get(item.layer, 0) + 1
        return contagem

    def by_content_access(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for item in self.mapped:
            contagem[item.content_access] = contagem.get(item.content_access, 0) + 1
        return contagem

    def summary(self) -> dict[str, Any]:
        return {
            "documentos": self.total,
            "por_status": self.by_status(),
            "por_camada": self.by_layer(),
            "por_content_access": self.by_content_access(),
            "chunks": sum(item.chunks for item in self.mapped),
            "chunks_sinalizados": sum(item.flagged_chunks for item in self.mapped),
            "bloqueados_por_segredo": len(self.blocked),
            "ausentes_em_disco": len(self.missing_on_disk),
            "inalterados": len(self.skipped_unchanged),
            "reclassificados": sum(1 for item in self.mapped if item.reconciled),
            "confirmados_automaticamente": 0,
        }


def _catalogo() -> dict[str, Any]:
    """Todas as fontes distintas, dos tres catalogos que existem hoje."""

    from agents.knowledge_policies import DOCUMENTS
    from agents.knowledge_sources import BRAND_ARCHITECT_DOCUMENTS, CMO_DOCUMENTS

    reunido: dict[str, Any] = {}
    # O compartilhado vem primeiro: e o que os 20 agentes usam. Os catalogos
    # do CMO e do Brand Architect sao subconjunto por caminho, e onde a chave
    # coincide a definicao compartilhada prevalece.
    for documento in list(DOCUMENTS.values()) + list(CMO_DOCUMENTS) + list(BRAND_ARCHITECT_DOCUMENTS):
        reunido.setdefault(documento.key, documento)
    return reunido


def run_backfill(repository: KnowledgeRepository, *, created_by: str = "backfill-f2") -> BackfillReport:
    """Espelha o catalogo atual no store. Idempotente por checksum.

    Rodar de novo sem mudanca no disco nao cria versao nova — so documento
    cujo conteudo mudou ganha v+1.
    """

    relatorio = BackfillReport()

    for chave, documento in sorted(_catalogo().items()):
        if not documento.path.exists():
            relatorio.missing_on_disk.append(chave)
            continue

        conteudo = documento.path.read_text(encoding="utf-8")
        checksum = checksum_of(conteudo)
        camada = layer_for(key=chave, relative_path=documento.relative_path)
        topics = topics_for(key=chave, relative_path=documento.relative_path)
        acesso = content_access_for(key=chave, relative_path=documento.relative_path)
        status = status_for(reliability=documento.reliability, caveat=documento.caveat)

        source_id = f"src_repo_{camada.lower()}"
        repository.upsert_source(
            source_id=source_id,
            kind=source_kind_for(camada),
            origin="repository",
            owner="sistema",
            title=f"Repositorio Judith AI — camada {camada}",
            description="Documentos versionados em docs/ do proprio projeto.",
            source_ref="docs/",
        )

        existente = repository.get_document_by_external_key(chave)
        if existente and existente["checksum"] == checksum:
            # Conteudo igual, mas a CLASSIFICACAO pode ter mudado (a L0 da
            # F2.5 e exatamente esse caso). Sem isto, o documento ficaria com
            # a camada velha para sempre, porque o checksum nunca muda.
            alteracoes = repository.reconcile_metadata(
                document_id=existente["document_id"],
                layer=camada,
                topics=topics,
                content_access=acesso,
                source_ref=documento.relative_path,
                title=documento.title,
            )
            atual = repository.get_current_version(existente["document_id"])
            relatorio.skipped_unchanged.append(chave)
            if atual:
                relatorio.mapped.append(
                    DocumentMap(
                        external_key=chave,
                        relative_path=documento.relative_path,
                        source_id=source_id,
                        document_id=existente["document_id"],
                        version_id=atual["version_id"],
                        version=int(atual["version"]),
                        layer=camada,
                        status=str(existente["status"]),
                        content_access=acesso,
                        topics=list(topics),
                        chunks=0,
                        checksum=checksum,
                        reconciled=alteracoes,
                    )
                )
            continue

        if existente is None:
            document_id = repository.create_document(
                source_id=source_id,
                title=documento.title,
                layer=camada,
                status=status,  # type: ignore[arg-type]
                content_access=acesso,
                checksum=checksum,
                external_key=chave,
                source_ref=documento.relative_path,
                topics=topics,
                confidence=confidence_for(documento.reliability),
            )
        else:
            document_id = existente["document_id"]

        try:
            version_id, versao = repository.add_version(
                document_id=document_id,
                body=conteudo,
                created_by=created_by,
                change_reason=f"Backfill F2 a partir de {documento.relative_path}",
                source_ref=documento.relative_path,
            )
        except SecretDetectedError as erro:
            # Bloqueado: nada foi gravado para este documento. O relatorio diz
            # tipo e linha, nunca o valor.
            relatorio.blocked.append(
                {
                    "fonte": chave,
                    "arquivo": documento.relative_path,
                    "achados": [{"tipo": f.kind, "linha": f.line} for f in erro.findings],
                }
            )
            continue

        pedacos = repository.get_chunks(version_id)
        relatorio.mapped.append(
            DocumentMap(
                external_key=chave,
                relative_path=documento.relative_path,
                source_id=source_id,
                document_id=document_id,
                version_id=version_id,
                version=versao,
                layer=camada,
                status=status,
                content_access=acesso,
                topics=list(topics),
                chunks=len(pedacos),
                checksum=checksum,
                flagged_chunks=sum(1 for p in pedacos if p.get("flags")),
            )
        )

    return relatorio


def injection_report(repository: KnowledgeRepository) -> list[dict[str, Any]]:
    """Chunks marcados pelo scanner de injecao. Conteudo intacto."""

    from sqlalchemy import select

    with repository.engine.begin() as conexao:
        linhas = conexao.execute(
            select(
                repository.chunks.c.chunk_id,
                repository.chunks.c.heading,
                repository.chunks.c.flags,
                repository.documents.c.external_key,
            )
            .select_from(
                repository.chunks.join(
                    repository.versions, repository.chunks.c.version_id == repository.versions.c.version_id
                ).join(
                    repository.documents,
                    repository.versions.c.document_id == repository.documents.c.document_id,
                )
            )
            .where(repository.chunks.c.flags.isnot(None))
        ).mappings()
        return [dict(linha) for linha in linhas]


def verify_originals(repository: KnowledgeRepository) -> list[str]:
    """Confere que o corpo gravado bate byte a byte com o arquivo de origem.

    Prova que nada foi "limpo" no caminho. Devolve as chaves divergentes.
    """

    divergentes: list[str] = []
    for chave, documento in sorted(_catalogo().items()):
        if not documento.path.exists():
            continue
        gravado = repository.get_document_by_external_key(chave)
        if gravado is None:
            continue
        versao = repository.get_current_version(gravado["document_id"])
        if versao is None:
            continue
        if versao["body"] != documento.path.read_text(encoding="utf-8"):
            divergentes.append(chave)
    return divergentes


def scan_catalog_for_injection() -> dict[str, list[dict[str, Any]]]:
    """Varre o catalogo em disco sem gravar nada. Util para inspecao previa."""

    achados: dict[str, list[dict[str, Any]]] = {}
    for chave, documento in sorted(_catalogo().items()):
        if not documento.path.exists():
            continue
        deteccao = scan_injection(documento.path.read_text(encoding="utf-8"))
        if deteccao.suspicious:
            achados[chave] = deteccao.as_json()
    return achados
