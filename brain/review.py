"""
Review Queue — o pacote que a Judith precisa para decidir.

ESTE MODULO NAO APROVA NADA.

Nao ha import de `approve_version` aqui, e ha teste garantindo que rodar o
packet inteiro nao muda o status de nenhum documento. A recomendacao e uma
LEITURA, nao uma acao — quem aprova e a Judith, e o nome dela fica gravado.

O que o packet responde, por documento:

    o que e, de onde veio, em que estado esta, quem pode ver,
    o que dentro dele depende de uma decisao que so ela pode tomar,
    e qual seria a recomendacao.

A parte que importa e a penultima. Um documento nao e aprovado inteiro por
engano: os pontos que exigem a Judith sao listados um a um, com a linha onde
aparecem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from brain.models import CONTENT_ACCESS_MEANING, LAYER_NAMES

Recommendation = str  # APPROVE | EDIT | KEEP_TO_VALIDATE | KEEP_DRAFT

#: Os 6 primeiros da fila. Escolhidos por impacto: sao os que respondem
#: pergunta de cliente sobre preco, produto, politica e tom.
FIRST_QUEUE: tuple[str, ...] = (
    "BUSINESS_RULES",
    "PRODUCTS",
    "OFFERS",
    "COMMENTS_FAQ",
    "VOICE",
    "BRAND",
)

#: Marcadores que apontam decisao pendente DENTRO do texto. Cada ocorrencia
#: vira um item da lista "precisa da Judith", com numero de linha.
_DECISION_MARKERS: tuple[tuple[str, str], ...] = (
    ("A VERIFICAR", "bloco marcado para verificacao"),
    ("A VALIDAR", "bloco marcado para validacao"),
    ("STATUS: TEMPLATE", "o documento inteiro se declara template"),
    ("a ser preenchid", "secao declarada incompleta"),
    ("Inferido do", "conteudo inferido, nao informado pela Judith"),
    ("se existir", "existencia do item nao confirmada"),
    ("<!--", "comentario de rascunho no meio do conteudo"),
)

_MONEY = re.compile(r"R\$\s?\d")
_LINK = re.compile(r"https?://\S+")


@dataclass
class ReviewItem:
    key: str
    title: str
    layer: str
    layer_name: str
    summary: str
    reliability: str
    caveat: str
    status: str
    content_access: str
    content_access_meaning: str
    topics: list[str]
    source_ref: str
    version: int
    chunks: int
    conflicts: list[str] = field(default_factory=list)
    needs_judith: list[dict[str, Any]] = field(default_factory=list)
    recommendation: Recommendation = "KEEP_TO_VALIDATE"
    rationale: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "layer": self.layer,
            "layer_name": self.layer_name,
            "summary": self.summary,
            "reliability": self.reliability,
            "caveat": self.caveat,
            "status_atual": self.status,
            "content_access": self.content_access,
            "content_access_significa": self.content_access_meaning,
            "topics": self.topics,
            "arquivo": self.source_ref,
            "versao": self.version,
            "chunks": self.chunks,
            "possiveis_conflitos": self.conflicts,
            "precisa_da_judith": self.needs_judith,
            "recomendacao": self.recommendation,
            "por_que": self.rationale,
        }


def _pontos_que_exigem_judith(corpo: str) -> list[dict[str, Any]]:
    achados: list[dict[str, Any]] = []
    for numero, linha in enumerate(corpo.splitlines(), start=1):
        for marcador, motivo in _DECISION_MARKERS:
            if marcador.casefold() in linha.casefold():
                achados.append({"linha": numero, "motivo": motivo, "trecho": linha.strip()[:160]})
                break
    return achados


def _conflitos_possiveis(chave: str, corpo: str, todos: dict[str, str]) -> list[str]:
    """Onde mais o mesmo valor comercial aparece.

    Nao afirma contradicao — aponta onde olhar. Dois documentos que citam o
    mesmo preco podem estar de acordo; o problema e quando um muda e o outro
    fica para tras.
    """

    if not _MONEY.search(corpo):
        return []
    return sorted(outra for outra, texto in todos.items() if outra != chave and _MONEY.search(texto))


def _recomendar(*, reliability: str, status: str, pendencias: list[dict[str, Any]], tem_link: bool) -> tuple[str, str]:
    """A recomendacao. Uma leitura, nunca uma acao.

    Conservadora de proposito: na duvida, KEEP. O custo de uma aprovacao
    errada (preco errado chegando na cliente) e muito maior que o custo de
    uma revisao a mais.
    """

    if reliability == "template":
        return (
            "KEEP_DRAFT",
            (
                "O documento se declara TEMPLATE e foi inferido do site/Instagram. "
                "Aprovar isso seria transformar suposicao em fato da marca."
            ),
        )

    if pendencias:
        quantos = len(pendencias)
        return (
            "EDIT",
            (
                f"Conteudo util, mas {quantos} ponto(s) dentro dele dependem de uma decisao sua "
                "(marcados A VERIFICAR / a preencher). Resolver esses pontos antes de aprovar "
                "evita que o documento entre com um buraco no meio."
            ),
        )

    if tem_link:
        return (
            "APPROVE",
            (
                "Conteudo estavel, sem pendencia marcada. Vale conferir uma vez se precos e links "
                "ainda batem com a plataforma antes de confirmar."
            ),
        )

    return (
        "APPROVE",
        "Conteudo estavel, sem pendencia marcada e sem dado volatil. Pronto para sua leitura final.",
    )


def build_review_packet(
    repository: Any,
    keys: tuple[str, ...] = FIRST_QUEUE,
) -> list[ReviewItem]:
    """Monta o pacote de revisao. NAO altera status de nada."""

    from brain.backfill import _catalogo

    catalogo = _catalogo()
    corpos: dict[str, str] = {}
    for chave in keys:
        documento = catalogo.get(chave)
        if documento is not None and documento.path.exists():
            corpos[chave] = documento.path.read_text(encoding="utf-8")

    itens: list[ReviewItem] = []
    for chave in keys:
        documento = catalogo.get(chave)
        if documento is None:
            continue

        linha = repository.get_document_by_external_key(chave)
        if linha is None:
            continue

        versao = repository.get_current_version(linha["document_id"])
        corpo = corpos.get(chave, "")
        pendencias = _pontos_que_exigem_judith(corpo)
        recomendacao, motivo = _recomendar(
            reliability=documento.reliability,
            status=str(linha["status"]),
            pendencias=pendencias,
            tem_link=bool(_LINK.search(corpo)),
        )

        itens.append(
            ReviewItem(
                key=chave,
                title=documento.title,
                layer=str(linha["layer"]),
                layer_name=LAYER_NAMES.get(str(linha["layer"]), "?"),  # type: ignore[arg-type]
                summary=documento.summary,
                reliability=documento.reliability,
                caveat=documento.caveat,
                status=str(linha["status"]),
                content_access=str(linha["content_access"]),
                content_access_meaning=CONTENT_ACCESS_MEANING.get(str(linha["content_access"]), "?"),  # type: ignore[arg-type]
                topics=list(linha["topics"] or []),
                source_ref=documento.relative_path,
                version=int(versao["version"]) if versao else 0,
                chunks=len(repository.get_chunks(versao["version_id"])) if versao else 0,
                conflicts=_conflitos_possiveis(chave, corpo, corpos),
                needs_judith=pendencias,
                recommendation=recomendacao,
                rationale=motivo,
            )
        )

    return itens


def packet_summary(itens: list[ReviewItem]) -> dict[str, Any]:
    por_recomendacao: dict[str, list[str]] = {}
    for item in itens:
        por_recomendacao.setdefault(item.recommendation, []).append(item.key)
    return {
        "documentos": len(itens),
        "por_recomendacao": por_recomendacao,
        "pontos_que_exigem_judith": sum(len(item.needs_judith) for item in itens),
        "status_alterados": 0,
    }
