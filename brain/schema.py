"""
Judith Brain — tabelas da fundacao de Knowledge (F2).

Cinco tabelas, nesta ordem de dependencia:

    sources  ->  documents  ->  versions  ->  chunks
                     \\-------------------/
                          conflicts

A separacao existe porque cada nivel responde uma pergunta diferente:

- **source**: de ONDE veio (repositorio, upload, URL) e de quem e.
- **document**: a unidade de conhecimento, com governanca (layer, status,
  vigencia, quem substituiu quem, quem pode ver).
- **version**: o CONTEUDO, imutavel depois de aprovado. Alteracao vira v+1;
  a anterior continua auditavel.
- **chunk**: o pedaco recuperavel, preservando estrutura (heading + ordinal).
- **conflict**: duas fontes CONFIRMED que se contradizem, preservadas ambas.

NAO ha tabela de embedding aqui. Isso e F3.

`status` e `layer` sao String, nao Enum do banco: mudar valor de ENUM em
Postgres exige ALTER TYPE, e isso e exatamente o tipo de migration dolorosa
que queremos evitar num schema que ainda vai crescer. A validacao vive em
`brain/models.py`, onde da para testar.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

SOURCES_TABLE = "judith_knowledge_sources"
DOCUMENTS_TABLE = "judith_knowledge_documents"
VERSIONS_TABLE = "judith_knowledge_versions"
CHUNKS_TABLE = "judith_knowledge_chunks"
CONFLICTS_TABLE = "judith_knowledge_conflicts"
ARTIFACTS_TABLE = "judith_knowledge_artifacts"

# Mesmo padrao da F1: JSONB indexavel no Postgres, JSON generico no SQLite
# dos testes. Um caminho de codigo so.
_JSON = JSONB().with_variant(JSON(), "sqlite")


def build_sources_table(metadata: MetaData) -> Table:
    return Table(
        SOURCES_TABLE,
        metadata,
        Column("source_id", String, primary_key=True, nullable=False),
        # judith | professional | business — ver brain/models.py:SourceKind
        Column("kind", String, nullable=False),
        # upload | manual | url | repository | sync
        Column("origin", String, nullable=False),
        # Quem responde por esta fonte. "judith" para material dela;
        # "sistema" para o que o proprio projeto produziu.
        Column("owner", String, nullable=False),
        Column("title", String, nullable=False),
        Column("description", Text, nullable=True),
        # Endereco de origem: caminho no repo, URL, id de upload. E o que
        # permite voltar ao original e reconferir.
        Column("source_ref", String, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Index(f"ix_{SOURCES_TABLE}_kind", "kind"),
        Index(f"ix_{SOURCES_TABLE}_origin", "origin"),
        Index(f"ix_{SOURCES_TABLE}_owner", "owner"),
    )


def build_documents_table(metadata: MetaData) -> Table:
    return Table(
        DOCUMENTS_TABLE,
        metadata,
        Column("document_id", String, primary_key=True, nullable=False),
        Column("source_id", String, nullable=False),
        # Caminho do arquivo de origem DESTE documento. A fonte guarda a raiz
        # (`docs/`); sem isto nao da para auditar de qual arquivo a linha veio.
        Column("source_ref", String, nullable=True),
        # A chave do DocumentSource antigo (BRAND, OFFERS, ...). E o que liga
        # o store novo ao caminho lexical de producao durante o periodo em que
        # os dois rodam em paralelo, e o que torna a comparacao possivel.
        Column("external_key", String, nullable=True),
        Column("title", String, nullable=False),
        Column("language", String, nullable=False, default="pt-BR"),
        # Checksum do conteudo da versao vigente. Detecta que o arquivo de
        # origem mudou sem passar pelo pipeline.
        Column("checksum", String, nullable=False),
        # L1 | L2 | L3
        Column("layer", String, nullable=False),
        # DRAFT | TO_VALIDATE | CONFIRMED | DEPRECATED
        Column("status", String, nullable=False),
        # INTERNAL_ONLY | SUPPORT_USE | PUBLIC | ENTITLEMENT_REQUIRED.
        # Governa DISCLOSURE, nao acesso: ver brain/models.py.
        Column("content_access", String, nullable=False),
        Column("topics", _JSON, nullable=True),
        # alto | medio | baixo — confianca na FONTE, nao validacao.
        Column("confidence", String, nullable=True),
        # --- F2.7: fonte primaria e conteudo pago ---------------------------
        # De onde vem a AUTORIDADE deste documento. USER_AUTHORIZED_PRIMARY_SOURCE
        # significa "a Judith entregou este arquivo como fonte atual", e NAO
        # "todas as afirmacoes dentro dele foram verificadas externamente".
        Column("source_authority", String, nullable=True),
        Column("provided_by", String, nullable=True),
        # Escopo de compra que libera o conteudo integral. NULL = nao e
        # material pago. Preenchido junto com content_access=ENTITLEMENT_REQUIRED.
        Column("entitlement_scope", String, nullable=True),
        # Artifact original (PDF) do qual este documento foi derivado.
        Column("artifact_id", String, nullable=True),
        Column("valid_from", DateTime(timezone=True), nullable=True),
        Column("valid_to", DateTime(timezone=True), nullable=True),
        # Qual versao esta vigente. Sem isto seria preciso um MAX() por
        # documento em toda busca.
        Column("current_version", Integer, nullable=False, default=1),
        # document_id que substituiu este. DEPRECATED nunca some: fica
        # apontando para o sucessor.
        Column("deprecated_by", String, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Index(f"ix_{DOCUMENTS_TABLE}_source_id", "source_id"),
        Index(f"ix_{DOCUMENTS_TABLE}_layer", "layer"),
        Index(f"ix_{DOCUMENTS_TABLE}_status", "status"),
        Index(f"ix_{DOCUMENTS_TABLE}_content_access", "content_access"),
        Index(f"ix_{DOCUMENTS_TABLE}_external_key", "external_key"),
    )


def build_versions_table(metadata: MetaData) -> Table:
    return Table(
        VERSIONS_TABLE,
        metadata,
        Column("version_id", String, primary_key=True, nullable=False),
        Column("document_id", String, nullable=False),
        Column("version", Integer, nullable=False),
        # O ORIGINAL. Nunca normalizado, nunca "limpo", nunca redigido.
        # Conteudo com segredo e BLOQUEADO na ingestao — nao guardado
        # mutilado se passando por original. Ver brain/security.py.
        Column("body", Text, nullable=False),
        Column("checksum", String, nullable=False),
        Column("change_reason", Text, nullable=True),
        Column("created_by", String, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        # Preenchidos SO por aprovacao humana explicita. Nenhum caminho de
        # codigo os preenche por inferencia.
        Column("approved_by", String, nullable=True),
        Column("approved_at", DateTime(timezone=True), nullable=True),
        UniqueConstraint("document_id", "version", name=f"uq_{VERSIONS_TABLE}_document_version"),
        Index(f"ix_{VERSIONS_TABLE}_document_id", "document_id"),
    )


def build_chunks_table(metadata: MetaData) -> Table:
    return Table(
        CHUNKS_TABLE,
        metadata,
        Column("chunk_id", String, primary_key=True, nullable=False),
        Column("version_id", String, nullable=False),
        # Ordem dentro do documento. Preserva a sequencia original mesmo
        # quando o resultado da busca vem embaralhado por score.
        Column("ordinal", Integer, nullable=False),
        Column("heading", String, nullable=True),
        Column("body", Text, nullable=False),
        Column("token_count", BigInteger, nullable=True),
        Column("topics", _JSON, nullable=True),
        # Herdado do documento no momento do chunking. Redundante de
        # proposito: o filtro de status na busca acontece sobre o chunk, sem
        # join, e um documento despromovido reescreve os chunks dele.
        Column("status", String, nullable=False),
        Column("checksum", String, nullable=False),
        # Marcas do scanner de injecao. Conteudo suspeito e SINALIZADO, nunca
        # reescrito — ver brain/security.py.
        Column("flags", _JSON, nullable=True),
        # --- F2.7: classificacao funcional e origem em pagina ---------------
        # RECIPE | TECHNIQUE | TROUBLESHOOTING | MARKETING_CLAIM | ... —
        # ver brain/models.py:ContentKind. Governa retrieval e disclosure.
        Column("content_kind", String, nullable=True),
        # Pagina do PDF de origem. NULL para chunk vindo de markdown.
        Column("page", Integer, nullable=True),
        # Todos os chunks da MESMA receita compartilham este id. E o que
        # impede um chunk com o fim da receita A e o inicio da B de existir
        # sem identificacao, e o que permite agrupar no retrieval.
        Column("recipe_id", String, nullable=True),
        Column("heading_path", String, nullable=True),
        # Herdado do documento. Redundante de proposito, como `status`: o
        # gate de disclosure decide por chunk, sem join.
        Column("entitlement_scope", String, nullable=True),
        Index(f"ix_{CHUNKS_TABLE}_version_id", "version_id"),
        Index(f"ix_{CHUNKS_TABLE}_status", "status"),
        Index(f"ix_{CHUNKS_TABLE}_recipe_id", "recipe_id"),
        Index(f"ix_{CHUNKS_TABLE}_content_kind", "content_kind"),
        UniqueConstraint("version_id", "ordinal", name=f"uq_{CHUNKS_TABLE}_version_ordinal"),
    )


def build_artifacts_table(metadata: MetaData) -> Table:
    """O arquivo ORIGINAL, byte a byte. Auditoria, nao retrieval.

    Por que os bytes moram no Postgres e nao num bucket: sao ~33 MB de PDF,
    uma vez. Introduzir S3/R2/MinIO para isso adicionaria credencial nova,
    ciclo de vida novo e um segundo lugar de onde conteudo pago pode vazar —
    custo real, em troca de nada que o banco ja nao resolva.

    REGRAS:

    - Imutavel. Nao ha UPDATE de `content` em lugar nenhum do codigo.
    - Nao entra em retrieval. Nenhum chunk aponta para ca; `chunks_for_search`
      nao conhece esta tabela.
    - Nunca vai para agente customer-facing, nem em resumo.
    - Existe para provar que o texto derivado corresponde ao original, e para
      permitir reprocessar sem depender do arquivo continuar no disco de
      alguem.
    """

    return Table(
        ARTIFACTS_TABLE,
        metadata,
        Column("artifact_id", String, primary_key=True, nullable=False),
        Column("source_id", String, nullable=False),
        Column("filename", String, nullable=False),
        Column("mime_type", String, nullable=False),
        # Hash do ARQUIVO. E a identidade: reingerir o mesmo arquivo nao cria
        # linha nova (ver KnowledgeRepository.store_artifact).
        Column("sha256", String, nullable=False),
        # Hash do TEXTO extraido. Muda se o extrator mudar, mesmo com o
        # arquivo igual — e o que torna um reprocessamento detectavel.
        Column("normalized_sha256", String, nullable=True),
        Column("size_bytes", BigInteger, nullable=False),
        Column("page_count", Integer, nullable=True),
        Column("content", LargeBinary, nullable=False),
        # USER_AUTHORIZED_PRIMARY_SOURCE | USER_PROVIDED_OFFICIAL_SITE_SNAPSHOT
        Column("source_authority", String, nullable=False),
        Column("provided_by", String, nullable=True),
        # Somente quando comprovavel por metadado/nome/conteudo. Caso
        # contrario fica NULL e o relatorio diz UNKNOWN — nao se inventa data.
        Column("capture_date", DateTime(timezone=True), nullable=True),
        Column("extraction_warnings", _JSON, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("sha256", name=f"uq_{ARTIFACTS_TABLE}_sha256"),
        Index(f"ix_{ARTIFACTS_TABLE}_source_id", "source_id"),
    )


def build_conflicts_table(metadata: MetaData) -> Table:
    """Dois conhecimentos que se contradizem. Ambos preservados.

    Nao existe coluna "vencedor" preenchida por codigo. Resolucao de fato
    comercial exige humano — ver brain/conflicts.py.
    """

    return Table(
        CONFLICTS_TABLE,
        metadata,
        Column("conflict_id", String, primary_key=True, nullable=False),
        Column("document_a", String, nullable=False),
        Column("document_b", String, nullable=False),
        Column("layer", String, nullable=False),
        Column("topic", String, nullable=True),
        # Que tipo de contradicao. Hoje so "valor_divergente" — deteccao
        # deterministica de valores comerciais diferentes para o mesmo item.
        Column("kind", String, nullable=False),
        Column("detail", _JSON, nullable=True),
        # OPEN | RESOLVED
        Column("status", String, nullable=False),
        Column("resolution", Text, nullable=True),
        Column("resolved_by", String, nullable=True),
        Column("resolved_at", DateTime(timezone=True), nullable=True),
        Column("detected_at", DateTime(timezone=True), nullable=False),
        Index(f"ix_{CONFLICTS_TABLE}_status", "status"),
        Index(f"ix_{CONFLICTS_TABLE}_layer", "layer"),
        UniqueConstraint("document_a", "document_b", "kind", "topic", name=f"uq_{CONFLICTS_TABLE}_pair"),
    )


def build_all(metadata: MetaData) -> list[Table]:
    """Todas as tabelas da fundacao, na ordem de dependencia."""

    return [
        build_sources_table(metadata),
        build_documents_table(metadata),
        build_versions_table(metadata),
        build_chunks_table(metadata),
        build_conflicts_table(metadata),
        build_artifacts_table(metadata),
    ]
