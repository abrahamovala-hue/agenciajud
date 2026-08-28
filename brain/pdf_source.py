"""
Extracao de PDF para o Brain — pagina a pagina, com reparo de glifo provado.

O PROBLEMA REAL QUE ESTE MODULO RESOLVE
---------------------------------------

Os ebooks da Judith tem um defeito de `ToUnicode` no proprio arquivo: o
travessao (em-dash) e decodificado como o digito `4`. Isso NAO e bug de
parser — pypdf e pymupdf erram igual, porque ambos leem o mapa que o PDF
declara.

    "Formato Rosca 4 Rendimento: 24 bombons"   <- o primeiro 4 e um travessao
    "Rendimento: ~4 barras de 175g"            <- este 4 e um numero de verdade
    "4. Verifique o ponto"                     <- este 4 e um numero de passo

Substituir ` 4 ` por travessao no texto destruiria os dois ultimos. A
auditoria das 48 ocorrencias nos tres ebooks mostrou que uma regra textual
sempre erra em algum caso.

A DECISAO: GEOMETRIA, NAO HEURISTICA DE TEXTO
---------------------------------------------

Um em-dash tem, por definicao tipografica, largura de exatamente 1 em — ou
seja, largura igual ao corpo da fonte. Um digito tem cerca de 0,5-0,7 em.
Medindo o glifo no PDF a separacao e limpa e sem zona cinzenta:

    largura / tamanho_da_fonte >= 0.95   ->  travessao
    largura / tamanho_da_fonte  < 0.95   ->  digito 4 de verdade

Medido nos tres ebooks: travessoes deram exatamente 1.00; digitos deram 0.57
e 0.66. Nenhum valor caiu entre 0.66 e 1.00.

E por isso que `EM_DASH_RATIO` e 0.95 e nao um numero redondo escolhido no
olho: e o meio de uma faixa vazia larga, verificada em `tests/`.

O QUE ESTE MODULO NAO FAZ
-------------------------

Nao "corrige pela experiencia geral". Nenhum valor tecnico — temperatura,
gramagem, rendimento, validade — e alterado. O unico reparo e o do glifo
acima, ele e registrado em `warnings` com pagina e contagem, e o texto bruto
fica preservado ao lado do normalizado para que a decisao seja auditavel
depois.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Largura relativa a partir da qual um glifo "4" e, na verdade, um em-dash.
#: Ver docstring: faixa medida foi 0.57-0.66 para digito e 1.00 para dash.
EM_DASH_RATIO = 0.95

#: Glifos decorativos que o PDF nao mapeia para Unicode (icones, emoji). Sao
#: ruido visual, nao conteudo — removidos do texto normalizado e contados.
_GLYPH_PREFIX = "/g"

EM_DASH = "—"


class PdfExtractionError(RuntimeError):
    """Falha ao ler o PDF. Nunca silenciosa."""


#: Caracteres de controle que o PDF entrega e que nao sao conteudo.
#:
#: PostgreSQL recusa NUL (0x00) em campo `text` — "cannot contain NUL bytes".
#: SQLite aceita em silencio, e foi por isso que a suite local passou e a
#: primeira gravacao em producao falhou. O banco de verdade encontrou o que o
#: banco de teste escondeu.
#:
#: Os 27 NUL do acervo (26 em Lascas, 1 no snapshot do site) sao artefato de
#: extracao, nao texto: nenhum deles fica entre caracteres visiveis. Remove-los
#: nao altera nenhum valor tecnico — e a remocao e contada e reportada.
_CONTROL_KEEP = "\n\r\t"


def _strip_control(texto: str) -> tuple[str, int]:
    """Remove controles nao imprimiveis. Devolve (texto, quantos)."""

    if not any(ord(c) < 32 and c not in _CONTROL_KEEP for c in texto):
        return texto, 0
    limpo = "".join(c for c in texto if ord(c) >= 32 or c in _CONTROL_KEEP)
    return limpo, len(texto) - len(limpo)


@dataclass(frozen=True)
class PdfPage:
    page_number: int
    #: Texto exatamente como o parser devolveu. Nunca alterado.
    raw_text: str
    #: Texto com o reparo de glifo aplicado. E este que vira chunk.
    text: str
    #: Quantos travessoes foram restaurados nesta pagina.
    repaired_dashes: int = 0
    #: Quantos glifos nao mapeados foram removidos.
    dropped_glyphs: int = 0
    #: Quantos caracteres de controle foram removidos.
    dropped_controls: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class PdfDocument:
    filename: str
    path: str
    sha256: str
    size_bytes: int
    page_count: int
    pages: list[PdfPage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    #: Links reais (annotations), por pagina. Nunca inferidos do texto.
    links: dict[int, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def raw_text(self) -> str:
        return "\n".join(page.raw_text for page in self.pages)

    @property
    def normalized_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def empty_pages(self) -> list[int]:
        return [page.page_number for page in self.pages if page.is_empty]

    @property
    def repaired_dashes(self) -> int:
        return sum(page.repaired_dashes for page in self.pages)

    @property
    def dropped_controls(self) -> int:
        return sum(page.dropped_controls for page in self.pages)

    def summary(self) -> dict[str, Any]:
        return {
            "arquivo": self.filename,
            "sha256": self.sha256,
            "sha256_normalizado": self.normalized_sha256,
            "bytes": self.size_bytes,
            "paginas": self.page_count,
            "paginas_extraidas": len(self.pages),
            "paginas_sem_texto": self.empty_pages,
            "travessoes_restaurados": self.repaired_dashes,
            "glifos_removidos": sum(p.dropped_glyphs for p in self.pages),
            "controles_removidos": self.dropped_controls,
            "links": sum(len(v) for v in self.links.values()),
            "avisos": self.warnings,
        }


def _open_document(path: Path) -> Any:
    try:
        import pymupdf
    except ImportError as erro:  # pragma: no cover - depende do ambiente
        raise PdfExtractionError(
            "pymupdf nao esta instalado. A extracao de PDF e uma tarefa de ingestao "
            "(offline), nao de runtime de producao: instale com o extra 'ingest'."
        ) from erro

    try:
        return pymupdf.open(str(path))
    except Exception as erro:
        raise PdfExtractionError(f"nao foi possivel abrir {path.name}: {type(erro).__name__}: {erro}") from erro


def _repair_page(pagina: Any) -> tuple[str, str, int, int, int]:
    """Devolve (bruto, reparado, travessoes, glifos_removidos, controles).

    Reconstroi a pagina caractere a caractere para poder medir cada glifo. O
    texto bruto vem de `get_text()` para preservar exatamente o que o parser
    entregaria sem nenhuma intervencao nossa.
    """

    bruto = pagina.get_text() or ""
    detalhe = pagina.get_text("rawdict") or {}

    travessoes = 0
    partes: list[str] = []

    for bloco in detalhe.get("blocks", []):
        for linha in bloco.get("lines", []):
            for span in linha.get("spans", []):
                tamanho = span.get("size") or 0
                for caractere in span.get("chars", []):
                    simbolo = caractere.get("c", "")
                    if simbolo == "4" and tamanho:
                        x0, _, x1, _ = caractere.get("bbox", (0, 0, 0, 0))
                        if (x1 - x0) / tamanho >= EM_DASH_RATIO:
                            partes.append(EM_DASH)
                            travessoes += 1
                            continue
                    partes.append(simbolo)
                partes.append(" ")
            partes.append("\n")

    reconstruido = "".join(partes)

    # Sem travessao para reparar, o texto do parser e melhor: preserva a
    # quebra de linha original, que a reconstrucao caractere a caractere nao
    # tem como recuperar com fidelidade.
    escolhido = bruto if travessoes == 0 else reconstruido
    texto, removidos = _drop_unmapped(escolhido)
    texto, controles = _strip_control(texto)
    return bruto, texto, travessoes, removidos, controles


def _drop_unmapped(texto: str) -> tuple[str, int]:
    """Remove referencias de glifo nao mapeado (`/g109`). Conta quantas."""

    if _GLYPH_PREFIX not in texto:
        return texto, 0

    saida: list[str] = []
    removidos = 0
    indice = 0
    while indice < len(texto):
        if texto.startswith(_GLYPH_PREFIX, indice) and indice + 2 < len(texto) and texto[indice + 2].isalnum():
            fim = indice + 2
            while fim < len(texto) and texto[fim].isalnum():
                fim += 1
            removidos += 1
            indice = fim
            continue
        saida.append(texto[indice])
        indice += 1
    return "".join(saida), removidos


def _links_of(pagina: Any) -> list[str]:
    """URLs reais das annotations. Nunca deduzidas do texto visivel."""

    destinos: list[str] = []
    try:
        for link in pagina.get_links() or []:
            uri = link.get("uri")
            if uri:
                destinos.append(str(uri))
    except Exception:  # noqa: BLE001 - link quebrado nao invalida a pagina
        return destinos
    return destinos


def extract_pdf(path: str | Path) -> PdfDocument:
    """Extrai um PDF inteiro, pagina a pagina, com reparo de glifo auditavel."""

    caminho = Path(path)
    if not caminho.exists():
        raise PdfExtractionError(f"arquivo nao encontrado: {caminho}")

    dados = caminho.read_bytes()
    documento_pdf = _open_document(caminho)

    resultado = PdfDocument(
        filename=caminho.name,
        path=str(caminho),
        sha256=hashlib.sha256(dados).hexdigest(),
        size_bytes=len(dados),
        page_count=documento_pdf.page_count,
        metadata=dict(documento_pdf.metadata or {}),
    )

    for indice in range(documento_pdf.page_count):
        pagina = documento_pdf[indice]
        bruto, texto, travessoes, glifos, controles = _repair_page(pagina)
        resultado.pages.append(
            PdfPage(
                page_number=indice + 1,
                raw_text=bruto,
                text=texto,
                repaired_dashes=travessoes,
                dropped_glyphs=glifos,
                dropped_controls=controles,
            )
        )
        destinos = _links_of(pagina)
        if destinos:
            resultado.links[indice + 1] = destinos

    if resultado.empty_pages:
        resultado.warnings.append(
            f"paginas sem texto extraivel (provavelmente imagem): {resultado.empty_pages}. "
            "Exigem validacao visual antes de qualquer afirmacao sobre o conteudo delas."
        )
    if resultado.dropped_controls:
        resultado.warnings.append(
            f"{resultado.dropped_controls} caracteres de controle removidos (NUL e afins). "
            "PostgreSQL recusa NUL em campo text; sao artefato de extracao, nao conteudo. "
            "Texto bruto preservado."
        )
    if resultado.repaired_dashes:
        resultado.warnings.append(
            f"{resultado.repaired_dashes} travessoes restaurados a partir da largura do glifo "
            "(defeito de ToUnicode no PDF de origem). Texto bruto preservado."
        )

    return resultado
