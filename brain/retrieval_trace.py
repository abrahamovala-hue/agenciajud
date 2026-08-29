"""
Rastro do retrieval — o que a busca fez, por execucao.

    answer_dm  ->  start_trace()          abre o buffer
    search()   ->  record(...)            anota, uma vez por busca
    answer_dm  ->  trace_summary()        le e joga no ExecutionLog

POR QUE ISTO NAO REPETE O ERRO DO MOBILE_FAIL_02
------------------------------------------------

Naquele caso a provenance viajava por um caminho e o extrator lia outro. A
licao nao foi "nunca tenha um canal lateral" — foi "provenance tem UMA fonte".
Ela continua tendo: `SearchHit.provenance` vira `fonte` no payload da tool, e
`sources_opened` continua saindo dali e so dali.

Este modulo carrega DIAGNOSTICO, nao evidencia: qual perna rodou, quantos
candidatos, qual modelo, quanto demorou. Se ele sumir, `sources_opened`, o
Evidence Gate e a resposta ficam exatamente iguais — o que se perde e a
capacidade de explicar depois por que um trecho apareceu.

E ele existe justamente porque o payload nao serve para isso: `search()` e
chamada por DUAS portas (a tool `buscar_conhecimento` e o retriever nativo
`search_knowledge_base`), e o retriever devolve uma lista crua, sem envelope
onde caiba telemetria. Anotar dentro de `search()` cobre as duas.

O BUFFER E COMPARTILHADO POR REFERENCIA, DE PROPOSITO
-----------------------------------------------------

`ContextVar` propaga para baixo, nunca para cima: valor gravado dentro de uma
thread de trabalho nao volta para quem a criou. Guardar uma LISTA e mutar essa
lista resolve — o objeto e o mesmo dos dois lados. E o mesmo motivo pelo qual
`asyncio.to_thread` copia o contexto e ainda assim isto funciona.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

#: Teto de anotacoes por execucao. Um agente com `tool_call_limit=6` nao passa
#: disso; o teto existe para que um loop inesperado nao cresca sem limite.
MAX_ANOTACOES = 12

_trace: ContextVar[list[dict[str, Any]] | None] = ContextVar("brain_retrieval_trace", default=None)


def start_trace() -> list[dict[str, Any]]:
    """Abre um buffer para esta execucao e devolve a referencia."""

    buffer: list[dict[str, Any]] = []
    _trace.set(buffer)
    return buffer


def record(observabilidade: dict[str, Any]) -> None:
    """Anota uma busca. Silencioso quando nao ha buffer aberto.

    Sem buffer significa "ninguem esta medindo" — teste, script, eval. Nao e
    erro e nao pode virar excecao no meio de um atendimento.
    """

    buffer = _trace.get()
    if buffer is None or len(buffer) >= MAX_ANOTACOES:
        return
    buffer.append(observabilidade)


def get_trace() -> list[dict[str, Any]]:
    return list(_trace.get() or ())


def reset() -> None:
    _trace.set(None)


def trace_summary() -> dict[str, Any]:
    """Resumo para o ExecutionLog. Enumeraveis e contagens, nada mais.

    Nao carrega a query, nao carrega corpo, nao carrega vetor. `shadow_sources`
    e lista de CHAVE de documento — a mesma classe de dado que `sources_opened`,
    que ja e persistida.
    """

    anotacoes = get_trace()
    if not anotacoes:
        return {}

    latencias = [a.get("latency_ms") for a in anotacoes if isinstance(a.get("latency_ms"), int)]
    sombra: list[str] = []
    for anotacao in anotacoes:
        sombra.extend(str(s) for s in anotacao.get("shadow_sources") or ())

    return {
        "retrieval_mode": sorted({str(a.get("retrieval_mode")) for a in anotacoes if a.get("retrieval_mode")}),
        "rag_mode": next((str(a["rag_mode"]) for a in anotacoes if a.get("rag_mode")), None),
        "embedding_model": next((str(a["embedding_model"]) for a in anotacoes if a.get("embedding_model")), None),
        "retrieval_calls": len(anotacoes),
        "lexical_candidates": sum(int(a.get("lexical_candidates") or 0) for a in anotacoes),
        "vector_candidates": sum(int(a.get("vector_candidates") or 0) for a in anotacoes),
        "final_candidates": sum(int(a.get("final_candidates") or 0) for a in anotacoes),
        "document_diversity": max((int(a.get("documentos_distintos") or 0) for a in anotacoes), default=0),
        "shadow_sources": list(dict.fromkeys(sombra)),
        "retrieval_latency_ms": max(latencias) if latencias else None,
        "vector_skip_reason": next(
            (str(a["vector_skip_reason"]) for a in anotacoes if a.get("vector_skip_reason")), None
        ),
    }
