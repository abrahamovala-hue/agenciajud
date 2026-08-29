"""
RAG_MODE — a chave reversivel do Hybrid RAG.

    current         so lexical. Exatamente o comportamento anterior a F3.
    hybrid_shadow   calcula o hibrido, MEDE, e devolve o resultado lexical.
    hybrid          o hibrido decide o resultado.

Mesmo desenho de `brain/cutover.py`, e pelo mesmo motivo: reverter precisa ser
apagar uma variavel de ambiente e redeployar. Nao rebuild, nao migration, nao
DROP. Um rollback que exige commit as tres da manha e um rollback que ninguem
faz.

O DEFAULT E `current`
---------------------

Variavel ausente, vazia ou com valor desconhecido cai em `current`. Um erro de
digitacao em `RAG_MODE` nao pode ligar silenciosamente um caminho de retrieval
novo — nem desligar um que ja estava validado, mas ligar por engano e o risco
maior, entao o desconhecido cai no lado conservador e o log diz.

POR QUE `hybrid_shadow` DEVOLVE O RESULTADO LEXICAL
---------------------------------------------------

Shadow que muda a resposta nao e shadow. Em `hybrid_shadow` o vetor e
consultado, a fusao e calculada e tudo isso e registrado — mas quem sai do
`search()` e o top-k lexical, byte a byte igual ao de `current`. E o unico
jeito de medir o hibrido com trafego real sem apostar a conversa da cliente
nele.
"""

from __future__ import annotations

from os import getenv
from typing import Literal

ENV_VAR = "RAG_MODE"

Mode = Literal["current", "hybrid_shadow", "hybrid"]

MODES: tuple[Mode, ...] = ("current", "hybrid_shadow", "hybrid")

DEFAULT: Mode = "current"


def rag_mode() -> Mode:
    """O modo declarado. Desconhecido vira `current`."""

    declarado = (getenv(ENV_VAR) or "").strip().lower()
    if declarado in MODES:
        return declarado  # type: ignore[return-value]
    return DEFAULT


def uses_vector(mode: Mode | None = None) -> bool:
    """O vetor e consultado? Verdade nos dois modos hibridos."""

    return (mode or rag_mode()) in ("hybrid_shadow", "hybrid")


def vector_decides(mode: Mode | None = None) -> bool:
    """O vetor influencia o que SAI? So no modo `hybrid`."""

    return (mode or rag_mode()) == "hybrid"


def rag_mode_report() -> dict[str, object]:
    """Estado do modo, para o log de boot."""

    modo = rag_mode()
    declarado = (getenv(ENV_VAR) or "").strip()
    return {
        "rag_mode": modo,
        "origem": "env" if declarado else "default",
        "declarado": declarado or None,
        "valor_ignorado": declarado if declarado and declarado.lower() not in MODES else None,
        "consulta_vetor": uses_vector(modo),
        "vetor_decide": vector_decides(modo),
    }
