"""
O site — snapshot em PDF e captura ao vivo. Duas fontes, nunca a mesma.

    official_website_snapshot   o PDF que a Judith gerou
    official_website_live       o que respondeu HTTP nesta execucao

Tratar as duas como "o site" seria o erro central desta fase: o snapshot prova
o estado no momento da captura, e a captura ao vivo prova o estado de hoje.
Quando divergem, quem vale para ESTADO COMERCIAL e o ao vivo verificado — mas
divergencia material vira CONFLICT, nao substituicao silenciosa.

CAPTURE_DATE
------------

So e preenchida quando comprovavel por metadado, nome de arquivo ou conteudo.
O PDF do site nao tem `/CreationDate` (metadata vem `None`), entao fica
UNKNOWN. O mtime do arquivo NAO conta: OneDrive reescreve mtime ao
sincronizar, e uma data errada e pior que nenhuma.

SEM REDE OBRIGATORIA
--------------------

`capture_live()` falha graciosamente. Se o ambiente nao tiver saida, a fase
continua com o snapshot e o relatorio registra `live_verification=FAILED`
e `currentness=TO_VALIDATE` — nunca "verificado hoje".
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from brain.pdf_source import PdfDocument

SITE_URL = "https://aprenda.atelierbemmeque.com/"

#: Paginas comerciais same-origin. Lista fechada: exploracao livre de um site
#: e uma superficie que nao precisamos abrir.
SITE_PATHS: tuple[str, ...] = (
    "",
    "lascas-premium",
    "recheios-profissionais",
    "casquinhas-profissionais",
)

_PRICE = re.compile(r"R\$\s?(\d+(?:[.,]\d{2})?)")
_JSONLD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
_TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)
_KIWIFY = re.compile(r"https://pay\.kiwify\.com\.br/[A-Za-z0-9]+")


@dataclass
class LiveCapture:
    url: str
    final_url: str | None = None
    http_status: int | None = None
    checksum: str | None = None
    captured_at: str | None = None
    products: list[dict[str, Any]] = field(default_factory=list)
    visible_prices: list[str] = field(default_factory=list)
    checkout_links: list[str] = field(default_factory=list)
    title: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.http_status == 200 and self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_type": "official_website_live",
            "url": self.url,
            "final_url": self.final_url,
            "http_status": self.http_status,
            "checksum": self.checksum,
            "captured_at": self.captured_at,
            "titulo": self.title,
            "produtos": self.products,
            "precos_visiveis": self.visible_prices,
            "checkouts": self.checkout_links,
            "erro": self.error,
        }


def _structured_products(html: str) -> list[dict[str, Any]]:
    """Produtos declarados em schema.org. Vazio quando nao houver."""

    produtos: list[dict[str, Any]] = []
    for bloco in _JSONLD.findall(html):
        try:
            dados = json.loads(bloco.strip())
        except (ValueError, TypeError):
            continue
        itens = dados.get("itemListElement") if isinstance(dados, dict) else None
        candidatos = itens if isinstance(itens, list) else [dados]
        for item in candidatos:
            if not isinstance(item, dict) or item.get("@type") != "Product":
                continue
            oferta = item.get("offers") or {}
            produtos.append(
                {
                    "nome": item.get("name"),
                    "preco_schema": (oferta or {}).get("price"),
                    "moeda": (oferta or {}).get("priceCurrency"),
                    "checkout": (oferta or {}).get("url"),
                    "disponibilidade": (oferta or {}).get("availability"),
                    "dias_de_garantia": ((oferta or {}).get("hasMerchantReturnPolicy") or {}).get(
                        "merchantReturnDays"
                    ),
                }
            )
    return produtos


def capture_live(path: str = "", *, timeout: int = 20) -> LiveCapture:
    """Le UMA pagina do site oficial. Nunca envia dado, nunca compra."""

    url = SITE_URL + path
    captura = LiveCapture(url=url)
    requisicao = urllib.request.Request(url, headers={"User-Agent": "JudithBrain/2.7 (leitura somente)"})
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            corpo = resposta.read()
            captura.http_status = resposta.status
            captura.final_url = resposta.geturl()
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        captura.error = f"{type(erro).__name__}: {erro}"
        return captura

    captura.captured_at = datetime.now(UTC).isoformat()
    captura.checksum = hashlib.sha256(corpo).hexdigest()
    html = corpo.decode("utf-8", errors="replace")
    titulo = _TITLE.search(html)
    captura.title = titulo.group(1).strip() if titulo else None
    captura.visible_prices = sorted(set(_PRICE.findall(html)))
    captura.checkout_links = sorted(set(_KIWIFY.findall(html)))
    captura.products = _structured_products(html)
    return captura


def capture_site(paths: tuple[str, ...] = SITE_PATHS) -> list[LiveCapture]:
    return [capture_live(caminho) for caminho in paths]


# --- snapshot em PDF --------------------------------------------------------


@dataclass
class SnapshotFacts:
    """Fatos comerciais extraidos do PDF do site."""

    prices: list[str] = field(default_factory=list)
    checkout_links: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    guarantee: str | None = None
    bonus: str | None = None
    collection_has_price: bool = False
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_type": "official_website_snapshot",
            "precos": self.prices,
            "checkouts": self.checkout_links,
            "links_internos": self.internal_links,
            "garantia": self.guarantee,
            "bonus": self.bonus,
            "colecao_tem_preco": self.collection_has_price,
            "avisos": self.warnings,
        }


def snapshot_facts(documento: PdfDocument) -> SnapshotFacts:
    """Le o PDF do site. So o que esta escrito — nada inferido."""

    fatos = SnapshotFacts()
    texto = documento.text
    fatos.prices = sorted(set(_PRICE.findall(texto)))

    todos = [url for urls in documento.links.values() for url in urls]
    # A identidade do checkout e o slug, nao a query. O PDF carrega
    # `?utm_source=organic&...` em todo link e o HTML ao vivo nao — comparar
    # com a query produzia CONFLICT em links que sao o mesmo checkout.
    fatos.checkout_links = sorted({u.split("?")[0] for u in todos if "kiwify" in u})
    # Link interno = mesmo site. Quando o PDF foi gerado de um ambiente local,
    # sao localhost — e isso precisa aparecer no relatorio, nao ser
    # silenciosamente descartado.
    fatos.internal_links = sorted({u.split("?")[0] for u in todos if "localhost" in u or "atelierbemmeque" in u})
    if any("localhost" in u for u in fatos.internal_links):
        fatos.warnings.append(
            "O PDF do site contem links internos apontando para localhost. Foi gerado a partir do "
            "ambiente de desenvolvimento, nao do site publicado: os destinos internos NAO sao URLs reais. "
            "O conteudo comercial permanece utilizavel; os links internos, nao."
        )

    garantia = re.search(r"Garantia[^.\n]{0,80}?(\d+)\s*dias", texto, re.IGNORECASE)
    if garantia:
        fatos.guarantee = f"{garantia.group(1)} dias"

    bonus = re.search(r"(\d+)\s*v[ií]deos?\s*b[oô]nus", texto, re.IGNORECASE)
    if bonus:
        fatos.bonus = f"{bonus.group(1)} videos bonus por ebook"

    # "Colecao completa" so e oferta se tiver preco OU checkout proprio. Ver
    # Passo 25: um botao de ancora nao e um produto.
    trecho = re.search(r"Cole[çc][ãa]o\s+[Cc]ompleta(.{0,600})", texto, re.DOTALL)
    fatos.collection_has_price = bool(trecho and _PRICE.search(trecho.group(1)))
    if trecho and not fatos.collection_has_price:
        fatos.warnings.append(
            "Secao 'Colecao Completa' existe no site mas NAO tem preco nem checkout proprio. "
            "Nao e uma oferta compravel — e uma secao de marketing que aponta para os ebooks individuais."
        )
    return fatos


def compare(snapshot: SnapshotFacts, live: list[LiveCapture]) -> list[dict[str, Any]]:
    """SITE_PDF x LIVE_SITE, fato a fato."""

    home = next((c for c in live if c.url.rstrip("/") == SITE_URL.rstrip("/")), None)
    acessivel = bool(home and home.ok)

    def acao(iguais: bool, tem_live: bool) -> str:
        if not tem_live:
            return "NEEDS_JUDITH"
        return "MATCH" if iguais else "CONFLICT"

    linhas: list[dict[str, Any]] = []

    precos_live = sorted(set(home.visible_prices)) if acessivel and home else []
    linhas.append(
        {
            "fato": "precos visiveis",
            "site_pdf": snapshot.prices,
            "live_site": precos_live,
            "match": snapshot.prices == precos_live,
            "canonical": "live_site" if acessivel else "site_pdf",
            "acao": acao(snapshot.prices == precos_live, acessivel),
        }
    )

    checkouts_live = sorted(set(home.checkout_links)) if acessivel and home else []
    linhas.append(
        {
            "fato": "links de checkout",
            "site_pdf": snapshot.checkout_links,
            "live_site": checkouts_live,
            "match": snapshot.checkout_links == checkouts_live,
            "canonical": "live_site" if acessivel else "site_pdf",
            "acao": acao(snapshot.checkout_links == checkouts_live, acessivel),
        }
    )

    schema_live = []
    if acessivel and home:
        schema_live = [f"{p['nome']}={p['preco_schema']}" for p in home.products]
    linhas.append(
        {
            "fato": "precos em schema.org",
            "site_pdf": ["ausente (PDF nao carrega JSON-LD)"],
            "live_site": schema_live,
            "match": None,
            "canonical": "live_site" if acessivel else "indisponivel",
            "acao": "LIVE_ONLY" if acessivel else "NEEDS_JUDITH",
        }
    )

    linhas.append(
        {
            "fato": "links internos",
            "site_pdf": snapshot.internal_links,
            "live_site": ["dominio real"] if acessivel else [],
            "match": False,
            "canonical": "live_site" if acessivel else "site_pdf",
            "acao": "SNAPSHOT_ONLY",
        }
    )

    linhas.append(
        {
            "fato": "colecao/combo comprável",
            "site_pdf": [str(snapshot.collection_has_price)],
            "live_site": ["False"] if acessivel else [],
            "match": acessivel and not snapshot.collection_has_price,
            "canonical": "live_site" if acessivel else "site_pdf",
            "acao": "MATCH" if acessivel and not snapshot.collection_has_price else "NEEDS_JUDITH",
        }
    )
    return linhas


def currentness(live: list[LiveCapture]) -> dict[str, str]:
    """O estado da verificacao. Nunca diz 'verificado hoje' sem ter verificado."""

    ok = [c for c in live if c.ok]
    if not ok:
        return {
            "live_verification": "FAILED",
            "currentness": "TO_VALIDATE",
            "observacao": (
                "Site ao vivo inacessivel neste ambiente. O PDF fornecido pela Judith e a melhor "
                "fonte comercial disponivel, e NAO foi verificado hoje."
            ),
        }
    return {
        "live_verification": "OK",
        "currentness": "VERIFIED",
        "observacao": f"{len(ok)}/{len(live)} paginas verificadas ao vivo.",
    }
