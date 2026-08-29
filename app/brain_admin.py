"""
Rotas administrativas do Brain — diagnostico, indexacao e avaliacao.

POR QUE ISTO EXISTE
-------------------

O Postgres de producao so responde em `postgres.railway.internal`: sem proxy
TCP, sem dominio, sem `railway ssh` desta maquina. Os caminhos foram testados
na F2.7 e nenhum alcanca o banco. Mas a F3 precisa de tres coisas que so
existem LA DENTRO:

1. **Prova do estado real.** Versao do Postgres, extensoes disponiveis,
   indices, contagem de chunks. Inferir a partir da tag da imagem seria
   adivinhar; a instrucao e provar.
2. **Rodar o pipeline de embedding.** Os ebooks pagos vivem so no Postgres de
   producao — nao estao no Git, por regra da Judith. Indexar de fora exigiria
   tirar conteudo pago do banco, que e exatamente o que nao se faz.
3. **Rodar o eval sobre o acervo real.** Um shadow que roda so contra `docs/`
   mediria um corpus que nao existe em producao.

AS MESMAS QUATRO RESTRICOES DA INGESTAO ADMINISTRATIVA
------------------------------------------------------

1. **Nao amplia a superficie anonima.** Bearer pela dependencia nativa do
   Agno, igual a todo router administrativo.
2. **Nao existe por padrao.** Sem `BRAIN_ADMIN_ENABLED=true` as rotas nao sao
   registradas — nao e uma checagem dentro do handler, o endpoint nao aparece.
3. **Nao aceita SQL.** Os corpos sao flags e limites. Nao ha caminho para
   comando arbitrario; isso transformaria a rota num backdoor com aparencia
   de ferramenta.
4. **Nao devolve conteudo.** Contagem, id, hash, metrica e nome de fonte. Nem
   corpo de chunk, nem receita, nem ingrediente, nem vetor. Um endpoint de
   diagnostico que devolve texto e um vazamento com dashboard.

O QUE ELAS NAO FAZEM
--------------------

Nao aprovam documento. Nao mudam status. Nao apagam nada. Nao alteram
`RAG_MODE` — o modo e variavel de ambiente e muda por deploy, para que a
mudanca fique no historico da Railway e nao numa chamada HTTP sem rastro.
"""

from __future__ import annotations

from os import getenv
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

ENV_FLAG = "BRAIN_ADMIN_ENABLED"
ROUTE_STATUS = "/admin/brain/status"
ROUTE_EMBEDDINGS = "/admin/brain/embeddings"
ROUTE_EVAL = "/admin/brain/eval"


def is_enabled() -> bool:
    """As rotas so existem quando declaradas. Default fechado."""

    return (getenv(ENV_FLAG) or "").strip().lower() in ("1", "true", "yes")


class EmbeddingRequest(BaseModel):
    """Controle do pipeline. Nenhum campo aceita conteudo."""

    dry_run: bool = False
    #: Teto de textos novos por chamada. Serve para indexar um acervo grande
    #: em fatias, sem uma requisicao HTTP de varios minutos.
    batch_limit: int | None = Field(default=None, ge=1, le=5000)


class EvalRequest(BaseModel):
    #: "current", "hybrid" ou "compare" (roda os dois e devolve o delta).
    mode: str = "compare"
    limit: int = Field(default=4, ge=1, le=10)
    apenas_golden: bool = False
    #: Inclui o detalhe por caso. Fontes e metricas — nunca corpo.
    detalhado: bool = False
    #: Botoes de calibragem do hibrido. Existem para VARRER valores contra o
    #: acervo real e escolher por medicao — os defaults do codigo continuam
    #: sendo os do modulo, e mudar producao continua sendo commit.
    vector_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    lexical_weight: float | None = Field(default=None, ge=0.0, le=10.0)
    vector_weight: float | None = Field(default=None, ge=0.0, le=10.0)


def _diagnostico_do_banco(engine: Any) -> dict[str, Any]:
    """Fatos do servidor. Consultas de catalogo, somente leitura.

    Cada bloco e independente: um catalogo que nao existe no dialeto (o SQLite
    dos testes nao tem `pg_extension`) devolve o proprio erro no campo em vez
    de derrubar o diagnostico inteiro.
    """

    from sqlalchemy import text

    relatorio: dict[str, Any] = {"dialeto": engine.dialect.name}

    def consulta(nome: str, sql: str, transformar: Any) -> None:
        try:
            with engine.begin() as conexao:
                relatorio[nome] = transformar(conexao.execute(text(sql)).all())
        except Exception as erro:  # noqa: BLE001
            relatorio[nome] = f"indisponivel ({type(erro).__name__})"

    consulta("versao", "SELECT version()", lambda linhas: str(linhas[0][0]) if linhas else None)
    consulta(
        "usuario_e_banco",
        "SELECT current_user, current_database(), current_schema()",
        lambda linhas: dict(zip(("usuario", "banco", "schema"), map(str, linhas[0]), strict=False)) if linhas else None,
    )
    consulta(
        "pgvector_disponivel",
        "SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'vector'",
        lambda linhas: (
            {
                "nome": str(linhas[0][0]),
                "versao_disponivel": str(linhas[0][1]),
                "versao_instalada": str(linhas[0][2]) if linhas[0][2] else None,
            }
            if linhas
            else None
        ),
    )
    consulta(
        "extensoes_instaladas",
        "SELECT extname, extversion FROM pg_extension ORDER BY extname",
        lambda linhas: {str(nome): str(versao) for nome, versao in linhas},
    )
    consulta(
        "tabelas_do_brain",
        """
        SELECT c.relname,
               COALESCE(s.n_live_tup, 0) AS linhas,
               pg_total_relation_size(c.oid) AS bytes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE c.relkind = 'r' AND c.relname LIKE 'judith\\_%'
        ORDER BY c.relname
        """,
        lambda linhas: {
            str(nome): {"linhas_estimadas": int(linhas_), "bytes": int(bytes_)} for nome, linhas_, bytes_ in linhas
        },
    )
    consulta(
        "indices_do_brain",
        """
        SELECT indexname, tablename, indexdef
        FROM pg_indexes
        WHERE tablename LIKE 'judith\\_%'
        ORDER BY tablename, indexname
        """,
        lambda linhas: [{"indice": str(i), "tabela": str(t), "definicao": str(d)} for i, t, d in linhas],
    )
    return relatorio


def install_brain_admin(base_app: FastAPI, settings: Any) -> bool:
    """Registra as rotas se a flag permitir. Devolve se registrou."""

    if not is_enabled():
        return False

    from app.security import build_auth_dependency

    auth = build_auth_dependency(settings)

    def _repositorio() -> Any:
        from brain.bootstrap import get_knowledge_repository

        repositorio = get_knowledge_repository()
        if repositorio is None:  # pragma: no cover - so acontece se o boot falhou
            raise HTTPException(status_code=503, detail="knowledge store indisponivel")
        return repositorio

    @base_app.get(
        ROUTE_STATUS,
        tags=["Admin"],
        operation_id="brain_status",
        dependencies=[Depends(auth)],
    )
    async def status() -> dict[str, Any]:
        from agents.knowledge_scope import scope_report
        from brain.approvals import audit_drift
        from brain.cutover import cutover_report
        from brain.embeddings import DEFAULT_DIMENSION, DEFAULT_MODEL
        from brain.rag_mode import rag_mode_report
        from db.migrations import applied_versions

        repositorio = _repositorio()
        engine = repositorio.engine

        try:
            aplicadas = applied_versions(engine, repositorio.schema)
        except Exception as erro:  # noqa: BLE001
            aplicadas = {"erro": f"{type(erro).__name__}"}  # type: ignore[assignment]

        indexaveis = len(repositorio.chunks_for_embedding())
        estatisticas = repositorio.embedding_stats()
        cobertos = len(repositorio.embedded_checksums(embedding_model=DEFAULT_MODEL))

        return {
            "banco": _diagnostico_do_banco(engine),
            "migrations_aplicadas": aplicadas,
            "contagens": repositorio.counts(),
            "por_status": repositorio.status_report(),
            "indice_semantico": {
                **estatisticas,
                "modelo_de_producao": DEFAULT_MODEL,
                "dimensao_de_producao": DEFAULT_DIMENSION,
                "chunks_indexaveis": indexaveis,
                "checksums_cobertos": cobertos,
                "cobertura": round(cobertos / indexaveis, 4) if indexaveis else None,
            },
            "rag_mode": rag_mode_report(),
            "cutover": cutover_report(),
            "legacy_scope": scope_report(),
            "aprovacoes_com_deriva": [d["fonte"] for d in audit_drift(repositorio)],
        }

    @base_app.post(
        ROUTE_EMBEDDINGS,
        tags=["Admin"],
        operation_id="brain_run_embeddings",
        dependencies=[Depends(auth)],
    )
    async def embeddings(payload: EmbeddingRequest) -> dict[str, Any]:
        from brain.embeddings import run_embedding_pipeline

        relatorio = run_embedding_pipeline(
            _repositorio(),
            dry_run=payload.dry_run,
            batch_limit=payload.batch_limit,
        )
        return {"dry_run": payload.dry_run, **relatorio.as_dict()}

    @base_app.post(
        ROUTE_EVAL,
        tags=["Admin"],
        operation_id="brain_run_eval",
        dependencies=[Depends(auth)],
    )
    async def eval_rag(payload: EvalRequest) -> dict[str, Any]:
        from brain.eval_hybrid_rag import compare_modes, rag_summary, run_rag_eval

        repositorio = _repositorio()
        pesos = (
            {"lexical": payload.lexical_weight or 1.0, "vetorial": payload.vector_weight or 1.0}
            if (payload.lexical_weight is not None or payload.vector_weight is not None)
            else None
        )

        if payload.mode == "compare":
            resultado = compare_modes(
                repositorio,
                limit=payload.limit,
                vector_floor=payload.vector_floor,
                weights=pesos,
            )
            if not payload.detalhado:
                resultado.pop("diferencas", None)
            return resultado

        if payload.mode not in ("current", "hybrid", "hybrid_shadow"):
            raise HTTPException(status_code=400, detail="mode deve ser current, hybrid, hybrid_shadow ou compare")

        casos = run_rag_eval(
            repositorio,
            mode=payload.mode,
            limit=payload.limit,
            apenas_golden=payload.apenas_golden,
            vector_floor=payload.vector_floor,
            weights=pesos,
        )
        corpo: dict[str, Any] = {"modo": payload.mode, **rag_summary(casos)}
        if payload.detalhado:
            corpo["casos"] = [c.as_dict() for c in casos]
        return corpo

    return True
