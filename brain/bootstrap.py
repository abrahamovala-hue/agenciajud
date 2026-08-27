"""
Boot do Judith Brain — schema e espelho do catalogo.

Roda depois das migrations, no boot do processo. Duas garantias:

1. **Nunca derruba o servico.** Falha aqui vira log de erro e o AgentOS sobe
   igual: o caminho lexical de producao nao depende deste store. Um Brain que
   nao subiu e um problema; um WhatsApp que parou de responder por causa dele
   seria um problema muito maior.

2. **Idempotente por checksum.** Documento cujo arquivo nao mudou nao gera
   versao nova. Deploy sem mudanca em `docs/` nao move nada.

Por que o backfill roda no boot e nao num comando separado: `docs/` continua
sendo a fonte da verdade, e o store e um espelho derivado dela. Deixar os dois
divergirem ate alguem lembrar de rodar um script e como o Brain fica errado.
"""

from __future__ import annotations

from typing import Any

from agno.utils.log import log_error, log_info

_repository: Any = None


def set_knowledge_repository(repository: Any) -> None:
    global _repository
    _repository = repository


def get_knowledge_repository() -> Any:
    """Repositorio de Knowledge apoiado no Postgres do AgentOS.

    Construido na primeira chamada — importar este modulo nao abre conexao.
    """

    global _repository
    if _repository is None:
        from brain.repository import KnowledgeRepository
        from db import get_postgres_db

        db = get_postgres_db()
        _repository = KnowledgeRepository(db.db_engine, schema=db.db_schema)
    return _repository


def ensure_knowledge_store(db: Any) -> None:
    """Prepara o store e espelha o catalogo. Nunca levanta."""

    try:
        from brain.backfill import run_backfill
        from brain.repository import KnowledgeRepository

        repositorio = KnowledgeRepository(db.db_engine, schema=db.db_schema)
        set_knowledge_repository(repositorio)

        relatorio = run_backfill(repositorio)
        resumo = relatorio.summary()
        log_info(
            f"judith brain: {resumo['documentos']} documentos, {resumo['chunks']} chunks, "
            f"status={resumo['por_status']}, camadas={resumo['por_camada']}, "
            f"bloqueados_por_segredo={resumo['bloqueados_por_segredo']}, "
            f"confirmados_automaticamente={resumo['confirmados_automaticamente']}"
        )
        if relatorio.blocked:
            for item in relatorio.blocked:
                tipos = ", ".join(f"{a['tipo']}@linha{a['linha']}" for a in item["achados"])
                log_error(f"judith brain: ingestao BLOQUEADA de {item['fonte']} ({item['arquivo']}): {tipos}")
    except Exception as exc:  # noqa: BLE001
        log_error(f"judith brain: nao foi possivel preparar o knowledge store: {type(exc).__name__}: {exc}")
