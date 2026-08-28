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

from agno.utils.log import log_error, log_info, log_warning

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

        # O escopo do legacy e a unica coisa entre `docs/` no container e 77
        # documentos novos aparecendo para 20 agentes. Vai para o log de boot
        # para que o estado seja verificavel sem abrir o banco.
        from agents.knowledge_scope import scope_report

        escopo = scope_report()
        log_info(f"legacy knowledge scope: {escopo['scope']} (origem={escopo['origem']})")

        relatorio = run_backfill(repositorio)
        resumo = relatorio.summary()

        # F2.8: aplica o manifesto de aprovacoes ANTES de reportar o estado,
        # para que o log diga o estado ja aprovado. Nao levanta: documento que
        # nao aprovou continua TO_VALIDATE, e TO_VALIDATE nao sai em producao.
        from brain.approvals import apply_approvals, audit_drift
        from brain.cutover import cutover_report

        aprovacoes = apply_approvals(repositorio)
        log_info(
            f"aprovacoes: {len(aprovacoes['aprovadas'])} aplicadas, "
            f"{len(aprovacoes['ignoradas'])} ignoradas, {len(aprovacoes['erros'])} erros"
        )
        for erro_aprovacao in aprovacoes["erros"]:
            log_error(f"aprovacao falhou: {erro_aprovacao}")

        # Conteudo que mudou DEPOIS de aprovado. E o unico caminho por onde
        # texto nao lido por um humano sairia em producao — precisa gritar.
        deriva = audit_drift(repositorio)
        if deriva:
            log_error(
                f"APROVACAO DESATUALIZADA em {len(deriva)} documento(s): "
                f"{[d['fonte'] for d in deriva]} estao CONFIRMED mas a versao vigente nunca foi aprovada."
            )
        else:
            log_info("aprovacoes conferem com o conteudo vigente (sem deriva)")

        corte = cutover_report()
        log_info(f"brain cutover: {corte['total']} agentes nativos {corte['brain_native']} (origem={corte['origem']})")
        if corte["pulados_na_ordem_recomendada"]:
            log_warning(
                f"cutover fora da ordem recomendada: {corte['pulados_na_ordem_recomendada']} "
                "foram pulados. Nao e erro, mas foi intencional?"
            )
        log_info(
            f"judith brain: {resumo['documentos']} documentos, {resumo['chunks']} chunks, "
            f"status={resumo['por_status']}, camadas={resumo['por_camada']}, "
            f"bloqueados_por_segredo={resumo['bloqueados_por_segredo']}, "
            f"reclassificados={resumo['reclassificados']}, "
            f"confirmados_automaticamente={resumo['confirmados_automaticamente']}"
        )
        if relatorio.blocked:
            for item in relatorio.blocked:
                tipos = ", ".join(f"{a['tipo']}@linha{a['linha']}" for a in item["achados"])
                log_error(f"judith brain: ingestao BLOQUEADA de {item['fonte']} ({item['arquivo']}): {tipos}")
    except Exception as exc:  # noqa: BLE001
        log_error(f"judith brain: nao foi possivel preparar o knowledge store: {type(exc).__name__}: {exc}")
