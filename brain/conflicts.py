"""
Judith Brain — representacao de conflito entre conhecimentos.

O QUE ESTE MODULO **NAO** FAZ
-----------------------------

Nao decide qual conhecimento e verdade. Nao chama LLM. Nao resolve conflito
de fato comercial automaticamente — nem quando "parece obvio".

O motivo e concreto: se dois documentos CONFIRMED dizem precos diferentes
para o mesmo produto, o codigo nao tem como saber qual foi atualizado por
ultimo com intencao e qual ficou para tras por esquecimento. Escolher um
seria inventar uma decisao de negocio. O certo e preservar os dois, marcar, e
levar para revisao humana.

PRECEDENCIA (para conflito ENTRE autoridades)
---------------------------------------------

    1. Business CONFIRMED     (fato operacional do negocio)
    2. Judith CONFIRMED       (o que a Judith ensina/definiu)
    3. Professional CONFIRMED (oficio curado)
    4. System                 (como a IA funciona — nunca sobre o negocio)
    5. modelo geral           (fora do Brain)

Isso resolve "o craft diz X, o BUSINESS_RULES diz Y" — vence o negocio.

O que a precedencia NAO resolve, e nao deve esconder: conflito DENTRO da
mesma autoridade. Dois documentos L3 CONFIRMED que se contradizem sao um
problema real do negocio, nao um empate a ser desfeito por regra.

DETECCAO
--------

Deliberadamente estreita e deterministica: valores monetarios divergentes
para o mesmo produto, entre documentos da mesma camada, ambos CONFIRMED.
Preferimos detectar pouco e certo a detectar muito e errado — falso positivo
em governanca de conhecimento vira ruido que ninguem mais olha.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from brain.models import Layer

#: Ordem de autoridade. Menor numero = mais forte.
#:
#: L0 (SYSTEM) e o ultimo de proposito: documentacao de como a IA funciona
#: nunca pode ganhar de um fato do negocio. Uma ficha de agente que menciona
#: um preco de exemplo nao vira fonte de preco.
LAYER_PRECEDENCE: dict[Layer, int] = {"L3": 1, "L1": 2, "L2": 3, "L0": 4}

#: Camadas onde resolucao automatica e PROIBIDA, mesmo que o codigo
#: soubesse decidir. Fato comercial errado chega na cliente como preco errado.
NO_AUTO_RESOLVE_LAYERS: frozenset[str] = frozenset({"L3"})

_MONEY = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:[.,]\d{2})?)")


def precedence(layer: str) -> int:
    """Posicao na hierarquia. Camada desconhecida vai para o fim."""

    return LAYER_PRECEDENCE.get(layer, 99)  # type: ignore[arg-type]


def outranks(layer_a: str, layer_b: str) -> bool:
    return precedence(layer_a) < precedence(layer_b)


def can_auto_resolve(layer: str) -> bool:
    """False para fato comercial. Sempre."""

    return layer not in NO_AUTO_RESOLVE_LAYERS


@dataclass(frozen=True)
class ConflictCandidate:
    document_a: str
    document_b: str
    layer: str
    topic: str | None
    kind: str
    detail: dict[str, Any]


def _valores_monetarios(texto: str) -> set[str]:
    return {m.group(1).replace(".", "").replace(",", ".") for m in _MONEY.finditer(texto or "")}


def detect_value_conflicts(documentos: list[dict[str, Any]]) -> list[ConflictCandidate]:
    """Acha valores comerciais divergentes entre documentos CONFIRMED.

    `documentos` sao dicts com pelo menos: document_id, layer, status, topics
    e body (o corpo da versao vigente).

    So compara documentos com o topic `comercial`: procurar divergencia de
    numero em texto de craft produziria ruido puro.
    """

    comerciais = [
        d
        for d in documentos
        if d.get("status") == "CONFIRMED" and "comercial" in (d.get("topics") or []) and d.get("body")
    ]

    candidatos: list[ConflictCandidate] = []
    for indice, primeiro in enumerate(comerciais):
        for segundo in comerciais[indice + 1 :]:
            if primeiro.get("layer") != segundo.get("layer"):
                # Autoridades diferentes: a precedencia resolve, nao e conflito.
                continue
            valores_a = _valores_monetarios(str(primeiro["body"]))
            valores_b = _valores_monetarios(str(segundo["body"]))
            if not valores_a or not valores_b or valores_a == valores_b:
                continue
            if valores_a & valores_b:
                # Ha sobreposicao: provavelmente um documento cita o outro.
                continue
            candidatos.append(
                ConflictCandidate(
                    document_a=str(primeiro["document_id"]),
                    document_b=str(segundo["document_id"]),
                    layer=str(primeiro["layer"]),
                    topic="comercial",
                    kind="valor_divergente",
                    detail={
                        "valores_a": sorted(valores_a),
                        "valores_b": sorted(valores_b),
                        "observacao": "Valores comerciais sem nenhuma interseccao entre documentos da mesma camada.",
                    },
                )
            )
    return candidatos


def record_conflict(repository: Any, candidato: ConflictCandidate) -> str:
    """Grava o conflito. Ambos os documentos continuam intactos e vigentes."""

    conflict_id = f"cft_{uuid.uuid4().hex[:16]}"
    with repository.engine.begin() as conexao:
        existente = conexao.execute(
            select(repository.conflicts.c.conflict_id).where(
                repository.conflicts.c.document_a == candidato.document_a,
                repository.conflicts.c.document_b == candidato.document_b,
                repository.conflicts.c.kind == candidato.kind,
                repository.conflicts.c.topic == candidato.topic,
            )
        ).scalar_one_or_none()
        if existente:
            return str(existente)

        conexao.execute(
            insert(repository.conflicts).values(
                conflict_id=conflict_id,
                document_a=candidato.document_a,
                document_b=candidato.document_b,
                layer=candidato.layer,
                topic=candidato.topic,
                kind=candidato.kind,
                detail=candidato.detail,
                status="OPEN",
                resolution=None,
                resolved_by=None,
                resolved_at=None,
                detected_at=datetime.now(UTC),
            )
        )
    return conflict_id


def resolve_conflict(repository: Any, *, conflict_id: str, resolution: str, resolved_by: str) -> None:
    """Fecha um conflito. Exige nome humano, e recusa fato comercial sem ele.

    Nao existe caminho automatico para ca: nenhuma funcao deste modulo chama
    `resolve_conflict`.
    """

    if not (resolved_by or "").strip():
        raise ValueError("resolved_by e obrigatorio: conflito nao se resolve sozinho")

    with repository.engine.begin() as conexao:
        linha = conexao.execute(
            select(repository.conflicts.c.layer).where(repository.conflicts.c.conflict_id == conflict_id)
        ).scalar_one_or_none()
        if linha is None:
            raise ValueError(f"conflito {conflict_id} nao existe")

        conexao.execute(
            update(repository.conflicts)
            .where(repository.conflicts.c.conflict_id == conflict_id)
            .values(
                status="RESOLVED",
                resolution=resolution,
                resolved_by=resolved_by.strip(),
                resolved_at=datetime.now(UTC),
            )
        )


def open_conflicts(repository: Any) -> list[dict[str, Any]]:
    with repository.engine.begin() as conexao:
        return [
            dict(linha)
            for linha in conexao.execute(
                select(repository.conflicts).where(repository.conflicts.c.status == "OPEN")
            ).mappings()
        ]
