"""
Fontes primarias — os PDFs que a Judith entregou, do disco ao Brain.

DUAS REPRESENTACOES POR EBOOK, E POR QUE
----------------------------------------

    EBOOK_<X>            L1, ENTITLEMENT_REQUIRED   conteudo tecnico integral
    PRODUCT_OUTLINE_<X>  L3, PUBLIC                 o que da para dizer sem entregar

A primeira e o que a cliente comprou. A segunda e o que a marca fala em
publico sobre o que ela comprou. Sao coisas diferentes e por isso sao
documentos diferentes, com politicas diferentes — em vez de um documento so
com um campo dizendo "cuidado".

O outline e DERIVADO da fonte primaria, nunca escrito a mao: `build_outline()`
so pode citar o que saiu do PDF, e o que ele pode citar esta limitado a
`Recipe.outline()` e aos cabecalhos de pagina. Nao ha caminho neste modulo
que copie ingrediente com gramagem ou passo de preparo para o outline.

IDENTIFICACAO POR CONTEUDO, NAO POR NOME
----------------------------------------

Os arquivos chegaram com nomes como `Lascas-and-Barras-de-Chocolate-Premium
(1) (1).pdf`. Depender disso quebraria no dia em que a Judith renomear ou
reexportar. `identify()` olha a primeira pagina e a contagem de paginas.

O QUE ESTE MODULO NAO FAZ
-------------------------

Nao aprova nada. Nenhuma chamada a `approve_version()`. Os documentos entram
como TO_VALIDATE (fonte primaria autorizada, conteudo ainda nao revisado
linha a linha pela Judith) e sobem para CONFIRMED so pela porta humana.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from brain.pdf_source import PdfDocument, extract_pdf
from brain.recipes import EXPECTED_CATEGORIES, Recipe, parse_index, parse_recipes, recipe_report

#: A pasta onde a Judith deixou as fontes. FORA do repositorio, de proposito:
#: e propriedade intelectual paga e nunca pode ser alcancada por `git add`
#: nem por `COPY` do Dockerfile.
DEFAULT_SOURCE_DIR = Path(r"C:\Users\Abraham\OneDrive\PROJETO JUDITH\judith sources")

PRIMARY = "USER_AUTHORIZED_PRIMARY_SOURCE"
SITE_SNAPSHOT = "USER_PROVIDED_OFFICIAL_SITE_SNAPSHOT"

APPROVAL_REASON = (
    "Fonte primaria atual fornecida explicitamente por Judith para ingestao no Judith Brain em 2026-08-27."
)


def _fold(texto: str) -> str:
    normal = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in normal if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class SourceSpec:
    """Uma fonte esperada, reconhecida pelo conteudo."""

    key: str
    title: str
    #: Marcadores que precisam aparecer na primeira pagina. Identidade por
    #: conteudo — o nome do arquivo nao participa.
    signature: tuple[str, ...]
    authority: str
    entitlement_scope: str | None = None
    expected_pages: int | None = None
    subtitle: str | None = None

    def matches(self, documento: PdfDocument) -> bool:
        if not documento.pages:
            return False
        cabeca = _fold(documento.pages[0].text)
        return all(_fold(marca) in cabeca for marca in self.signature)


#: As quatro fontes.
#:
#: As assinaturas sao FRASES da capa, nao palavras soltas. A primeira versao
#: usava ("recheios", "profissionais") e o PDF do site casou com ela — a
#: homepage diz "Ebooks completos de recheios..." e "TECNICAS PROFISSIONAIS".
#: Palavra solta nao identifica documento num acervo em que todos falam do
#: mesmo assunto; subtitulo de capa identifica.
#:
#: `expected_pages` e conferencia, nao requisito: divergir gera aviso no
#: relatorio, nao excecao — a Judith pode reexportar com uma pagina a mais.
EXPECTED_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        key="EBOOK_RECHEIOS",
        title="Recheios Profissionais",
        signature=("recheios", "tecnicas, texturas e combinacoes"),
        authority=PRIMARY,
        entitlement_scope="ebook_recheios_profissionais",
        expected_pages=25,
    ),
    SourceSpec(
        key="EBOOK_CASQUINHAS",
        title="Casquinhas Profissionais",
        signature=("casquinhas profissionais", "temperagem, moldagem, brilho"),
        authority=PRIMARY,
        entitlement_scope="ebook_casquinhas_profissionais",
        expected_pages=25,
    ),
    SourceSpec(
        key="EBOOK_LASCAS",
        title="O Segredo do Chocolate",
        subtitle="Lascas & Barras de Chocolate Premium",
        signature=("o segredo do chocolate", "lascas & barras"),
        authority=PRIMARY,
        entitlement_scope="ebook_lascas_barras_premium",
        expected_pages=31,
    ),
    SourceSpec(
        key="SITE_SNAPSHOT",
        title="Snapshot do site oficial (fornecido por Judith)",
        signature=("compra segura", "acesso imediato"),
        authority=SITE_SNAPSHOT,
        entitlement_scope=None,
    ),
)


# --- classificacao funcional de pagina --------------------------------------
#
# Regras em ORDEM: a primeira que casar vence. Escritas sobre o cabecalho da
# pagina, que neste conjunto de PDFs e estavel e descritivo. Deterministico,
# sem LLM, e testavel — ver tests/test_f27_primary_sources.py.

_KIND_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CROSS_PROMOTION", ("proximo passo",)),
    ("AUTHORIAL_MESSAGE", ("obrigada por confiar", "uma mensagem para voce", "conclusao")),
    ("PRODUCT_METADATA", ("aulas bonus", "o que voce vai aprender", "sumario", "indice", "bem-vindo")),
    ("TROUBLESHOOTING", ("erros mais comuns", "principais defeitos", "erros comuns", "defeitos e solucoes")),
    ("STORAGE_VALIDITY", ("como armazenar", "validade e armazenamento", "armazenar as sobras")),
    ("TOOLS_EQUIPMENT", ("utensilios", "organizacao da bancada", "materiais para")),
    (
        "SALES_GUIDANCE",
        (
            "como precificar",
            "como vender",
            "embalagens para",
            "como fotografar",
            "ficha de produto",
            "por que vender",
            "da sobra ao produto",
            "aparencia premium",
        ),
    ),
    ("RECIPE", ("ganaches", "brigadeiros gourmet", "gianduias", "caramelos")),
)

#: Quando nenhuma regra casa. TECHNIQUE e o default correto para estes tres
#: ebooks: sao livros tecnicos, e o miolo deles e tecnica.
_DEFAULT_KIND = "TECHNIQUE"


#: O site nao e um ebook. As regras de ebook classificariam a homepage como
#: TECHNIQUE ("temperagem") e a pagina de produto como RECIPE ("ganaches") —
#: o que faria uma pagina de venda parecer conteudo tecnico pago no
#: retrieval. Um catalogo comercial tem tipos proprios.
_SITE_KIND_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("POLICY", ("politica de privacidade", "termos de uso", "privacidade", "condicoes")),
    ("FAQ", ("perguntas frequentes", "tire suas duvidas", "ainda com duvida")),
    ("COMMERCIAL_TERMS", ("oferta", "garantia", "colecao completa", "acesso imediato", "comprar", "de r$")),
    ("PRODUCT_METADATA", ("o que voce vai aprender", "tecnicas ensinadas", "ebooks individuais", "escolha o ebook")),
    ("MARKETING_CLAIM", ("prova social", "transformacao", "sobre a autora", "o que estao dizendo")),
)

_SITE_DEFAULT_KIND = "COMMERCIAL_TERMS"


def classify_page(texto: str, *, site: bool = False) -> str:
    """Tipo funcional de uma pagina. Primeira regra que casa vence."""

    regras = _SITE_KIND_RULES if site else _KIND_RULES
    padrao = _SITE_DEFAULT_KIND if site else _DEFAULT_KIND
    # O site tem cabecalhos em letra espacada ("O F E R T A"); comparar so as
    # 4 primeiras linhas perderia a secao. Olhar a pagina inteira num
    # catalogo comercial e barato e mais fiel.
    cabeca = _fold(texto if site else " ".join(texto.splitlines()[:4]))
    cabeca = re.sub(r"(?<=\b\w) (?=\w\b)", "", cabeca)
    for tipo, marcas in regras:
        if any(marca in cabeca for marca in marcas):
            return tipo
    return padrao


# --- descoberta -------------------------------------------------------------


@dataclass
class DiscoveredSource:
    spec: SourceSpec | None
    document: PdfDocument
    #: Preenchido quando o arquivo nao casa com nenhuma fonte esperada. O
    #: arquivo NAO e ingerido nesse caso — e reportado para decisao humana.
    unclassified_reason: str | None = None

    @property
    def key(self) -> str:
        return self.spec.key if self.spec else f"NAO_CLASSIFICADO::{self.document.filename}"


@dataclass
class Discovery:
    found: list[DiscoveredSource] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def classified(self) -> list[DiscoveredSource]:
        return [item for item in self.found if item.spec is not None]

    def by_key(self, key: str) -> DiscoveredSource | None:
        return next((item for item in self.classified if item.spec and item.spec.key == key), None)

    def report(self) -> dict[str, Any]:
        return {
            "arquivos": [
                {
                    "filename": item.document.filename,
                    "classificado_como": item.spec.key if item.spec else None,
                    "autoridade": item.spec.authority if item.spec else None,
                    "sha256": item.document.sha256,
                    "bytes": item.document.size_bytes,
                    "paginas": item.document.page_count,
                    "motivo": item.unclassified_reason,
                }
                for item in self.found
            ],
            "fontes_ausentes": self.missing,
            "arquivos_nao_pdf": self.extra_files,
            "avisos": self.warnings,
        }


def discover(folder: str | Path = DEFAULT_SOURCE_DIR) -> Discovery:
    """Le a pasta e identifica cada PDF pelo conteudo.

    Arquivo que nao casa com nenhuma fonte esperada NAO e ingerido: entra no
    relatorio como nao classificado. Ingerir silenciosamente um PDF
    desconhecido seria exatamente o tipo de coisa que essa fase existe para
    impedir.
    """

    raiz = Path(folder)
    resultado = Discovery()
    if not raiz.exists():
        resultado.warnings.append(f"pasta de fontes nao encontrada: {raiz}")
        resultado.missing = [spec.key for spec in EXPECTED_SOURCES]
        return resultado

    for caminho in sorted(raiz.iterdir()):
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() != ".pdf":
            resultado.extra_files.append(caminho.name)
            continue

        documento = extract_pdf(caminho)
        candidatos = [s for s in EXPECTED_SOURCES if s.matches(documento)]
        motivo = None
        spec = None
        if not candidatos:
            motivo = "primeira pagina nao casa com nenhuma fonte esperada"
        elif len(candidatos) > 1:
            # Ambiguidade nao vira "escolhe o primeiro". Duas fontes casando
            # com o mesmo arquivo significa que a assinatura esta errada, e
            # adivinhar aqui ingeriria o documento errado com o rotulo certo.
            motivo = f"ambiguo: casou com {[s.key for s in candidatos]}. Nao ingerido."
            resultado.warnings.append(f"{caminho.name}: {motivo}")
        else:
            spec = candidatos[0]

        if spec is not None and spec.expected_pages and spec.expected_pages != documento.page_count:
            resultado.warnings.append(
                f"{spec.key}: esperava {spec.expected_pages} paginas, veio {documento.page_count}. "
                "Ingestao continua; a contagem real e a que vale."
            )
        resultado.found.append(DiscoveredSource(spec=spec, document=documento, unclassified_reason=motivo))

    encontradas = {item.spec.key for item in resultado.classified}
    resultado.missing = [spec.key for spec in EXPECTED_SOURCES if spec.key not in encontradas]
    if resultado.extra_files:
        resultado.warnings.append(
            f"arquivos nao-PDF ignorados (nao ingeridos): {resultado.extra_files}"
        )
    return resultado


# --- montagem dos chunks ----------------------------------------------------


def _page_heading(texto: str) -> str:
    """Titulo da pagina, sem arrastar o corpo junto.

    Titulo quebra em duas linhas com frequencia ("Como armazenar" /
    "bombons"), entao pegar so a primeira perderia metade. Mas pegar duas
    sempre arrastaria o inicio do paragrafo. A segunda linha so entra se ela
    tambem parecer titulo: curta e sem pontuacao de fim de frase.
    """

    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    if not linhas:
        return ""
    # "PAGINA 12" e numeracao interna do ebook de Lascas, nao titulo.
    inicio = 1 if re.fullmatch(r"P[AÁ]GINA\s*\d+.*", linhas[0], re.IGNORECASE) else 0
    if inicio >= len(linhas):
        return ""
    partes = [linhas[inicio]]
    seguinte = linhas[inicio + 1] if inicio + 1 < len(linhas) else ""
    if seguinte and len(seguinte) <= 45 and not seguinte.endswith((".", "!", "?", ":", '"')):
        partes.append(seguinte)
    return " ".join(partes).strip()[:180]


def build_ebook_chunks(
    documento: PdfDocument,
    *,
    spec: SourceSpec,
    recipes: list[Recipe] | None = None,
) -> list[dict[str, Any]]:
    """Um chunk por pagina, exceto receita, que e agrupada por `recipe_id`.

    A receita de "Bolo de Cenoura" ocupa duas paginas; as duas viram chunks
    que compartilham o mesmo `recipe_id`. Nenhum chunk mistura o fim de uma
    receita com o inicio de outra, porque o corte e por pagina e a pagina
    nunca contem duas receitas.
    """

    por_pagina: dict[int, Recipe] = {}
    for receita in recipes or ():
        for pagina in receita.pages:
            por_pagina[pagina] = receita

    eh_site = spec.authority == SITE_SNAPSHOT
    pedacos: list[dict[str, Any]] = []
    for pagina in documento.pages:
        if pagina.is_empty:
            continue
        receita = por_pagina.get(pagina.page_number)
        if receita:
            tipo = "RECIPE"
        elif pagina.page_number == 1 and not eh_site:
            # A capa e identidade do produto, sempre. Sem esta regra a capa de
            # Recheios ("...bombons com aparencia premium") cai em
            # SALES_GUIDANCE por causa de "aparencia premium".
            tipo = "PRODUCT_METADATA"
        else:
            tipo = classify_page(pagina.text, site=eh_site)
        pedacos.append(
            {
                "body": pagina.text,
                "heading": receita.name if receita else _page_heading(pagina.text),
                "heading_path": f"{spec.title} > {receita.category}" if receita else spec.title,
                "page": pagina.page_number,
                "content_kind": tipo,
                "recipe_id": receita.recipe_id if receita else None,
                "entitlement_scope": spec.entitlement_scope,
            }
        )
    return pedacos


# --- conhecimento seguro derivado -------------------------------------------


def build_outline(
    documento: PdfDocument,
    *,
    spec: SourceSpec,
    recipes: list[Recipe] | None = None,
) -> str:
    """SAFE PRODUCT KNOWLEDGE — markdown derivado, sem conteudo pago.

    O que entra: identidade, escopo, temas, contagens, bonus comprovado.
    O que NAO entra, e nao existe caminho de codigo aqui para isso entrar:
    ingrediente com gramagem, passo de preparo, curva de temperatura
    especifica, corpo de pagina.
    """

    linhas: list[str] = [
        f"# {spec.title}",
        "",
    ]
    if spec.subtitle:
        linhas += [f"**Subtitulo:** {spec.subtitle}", ""]

    linhas += [
        "> Documento DERIVADO da fonte primaria em PDF fornecida pela Judith.",
        "> Descreve o produto; nao reproduz o conteudo pago.",
        "",
        "## Identidade",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Nome oficial | {spec.title} |",
    ]
    if spec.subtitle:
        linhas.append(f"| Subtitulo | {spec.subtitle} |")
    linhas += [
        "| Autora | Judith Kolker |",
        "| Marca | Bem me Que |",
        "| Formato | Ebook digital em PDF |",
        f"| Paginas | {documento.page_count} |",
        f"| Escopo de acesso pago | `{spec.entitlement_scope}` |",
        "",
    ]

    if recipes:
        contagem: dict[str, int] = {}
        for receita in recipes:
            contagem[receita.category] = contagem.get(receita.category, 0) + 1
        linhas += [
            "## Receitas",
            "",
            f"**{len(recipes)} receitas** em **{len(contagem)} categorias**.",
            "",
            "| Categoria | Receitas |",
            "|---|---|",
        ]
        for categoria in EXPECTED_CATEGORIES:
            if categoria in contagem:
                linhas.append(f"| {categoria.title()} | {contagem[categoria]} |")
        linhas += ["", "### Nomes das receitas", ""]
        for categoria in EXPECTED_CATEGORIES:
            nomes = [r.name for r in recipes if r.category == categoria]
            if nomes:
                linhas.append(f"**{categoria.title()}:** " + "; ".join(nomes))
                linhas.append("")
        veganas = [r.name for r in recipes if r.vegan]
        if veganas:
            linhas += [f"**Com opcao vegana declarada no ebook:** {'; '.join(veganas)}", ""]

    temas = _themes(documento, recipes=recipes)
    if temas:
        linhas += ["## Temas abordados", ""]
        linhas += [f"- {tema}" for tema in temas]
        linhas.append("")

    bonus = _proven_bonus(documento)
    if bonus:
        linhas += ["## Bonus comprovado pelo proprio PDF", ""]
        linhas += [f"- {item}" for item in bonus["itens"]]
        linhas += ["", f"**Acesso:** {bonus['acesso']}", f"**Comprovado na pagina:** {bonus['pagina']}", ""]
    else:
        linhas += [
            "## Bonus",
            "",
            "O PDF deste ebook nao documenta aulas bonus. Nao inferir bonus a partir de outro produto.",
            "",
        ]

    linhas += [
        "## Procedencia",
        "",
        f"- Autoridade: `{spec.authority}`",
        "- Fornecido por: Judith",
        f"- Arquivo: `{documento.filename}`",
        f"- SHA-256 do original: `{documento.sha256}`",
        f"- Paginas processadas: {len(documento.pages)}/{documento.page_count}",
        f"- Motivo da autorizacao: {APPROVAL_REASON}",
        "",
    ]
    return "\n".join(linhas)


def _themes(documento: PdfDocument, *, recipes: list[Recipe] | None) -> list[str]:
    """Temas = os cabecalhos das paginas que NAO sao receita.

    Um cabecalho descreve o assunto sem entregar o metodo. E por isso que ele
    pode sair e o corpo da pagina nao.
    """

    paginas_de_receita = {p for r in recipes or () for p in r.pages}
    temas: list[str] = []
    vistos: set[str] = set()
    for pagina in documento.pages:
        if pagina.page_number in paginas_de_receita or pagina.is_empty:
            continue
        titulo = _page_heading(pagina.text)
        if not titulo or len(titulo) < 4:
            continue
        chave = _fold(titulo)
        if chave in vistos:
            continue
        vistos.add(chave)
        temas.append(titulo)
    return temas


_LESSON_MARKER = re.compile(r"^\W*Aula\s*(\d+)\s*$", re.IGNORECASE)

#: Uma linha ainda faz parte do TITULO da aula se for curta e nao terminar
#: frase. O paragrafo que fecha a secao ("Essas aulas foram pensadas para te
#: ajudar a praticar...") e longo, e e assim que ele para de ser confundido
#: com o titulo da ultima aula.
_LESSON_TITLE_MAX = 50


def _parse_bonus_lessons(texto: str) -> list[tuple[str, str]]:
    """Aulas bonus declaradas na pagina. Varredura explicita, nao regex denso.

    O titulo quebra em ate duas linhas no PDF ("Como reaproveitar sobras
    limpas de" / "chocolate da producao de bombons"); capturar so a primeira
    entregaria um bonus com o nome cortado. Bonus e promessa de entrega, e
    promessa cortada pela metade e pior do que nenhuma.
    """

    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    aulas: list[tuple[str, str]] = []
    indice = 0
    while indice < len(linhas):
        marcador = _LESSON_MARKER.match(linhas[indice])
        if not marcador:
            indice += 1
            continue
        titulo: list[str] = []
        indice += 1
        while indice < len(linhas):
            linha = linhas[indice]
            if _LESSON_MARKER.match(linha):
                break
            if len(linha) > _LESSON_TITLE_MAX or linha.endswith((".", "!", "?")):
                break
            titulo.append(linha)
            indice += 1
        if titulo:
            aulas.append((marcador.group(1), " ".join(titulo)))
    return aulas


def _proven_bonus(documento: PdfDocument) -> dict[str, Any] | None:
    """Bonus SO se o proprio PDF provar. Ver Passo 28: bonus e promessa.

    Nao ha inferencia entre produtos: o ebook de Lascas documentar 4 aulas nao
    diz nada sobre Casquinhas ou Recheios.
    """

    for pagina in documento.pages:
        texto = pagina.text
        if "bonus" not in _fold(texto) and "bônus" not in texto.lower():
            continue
        itens = _parse_bonus_lessons(texto)
        if not itens:
            continue
        vitalicio = "vitalic" in _fold(texto)
        return {
            "itens": [f"Aula {numero}: {titulo.strip()}" for numero, titulo in itens],
            "acesso": (
                "Acesso vitalicio na area de membros (declarado no proprio PDF)."
                if vitalicio
                else "Acesso nao especificado nesta pagina."
            ),
            "pagina": pagina.page_number,
        }
    return None


# --- relatorio de completude ------------------------------------------------


def completeness(documento: PdfDocument, *, spec: SourceSpec, recipes: list[Recipe] | None = None) -> dict[str, Any]:
    """Prova de que o PDF foi processado inteiro. Sem conteudo, so numeros."""

    relatorio: dict[str, Any] = {
        "fonte": spec.key,
        "arquivo": documento.filename,
        "sha256_original": documento.sha256,
        "sha256_texto_normalizado": documento.normalized_sha256,
        "paginas_declaradas": documento.page_count,
        "paginas_processadas": len(documento.pages),
        "paginas_sem_texto": documento.empty_pages,
        "travessoes_restaurados": documento.repaired_dashes,
        "avisos_de_normalizacao": documento.warnings,
    }
    if recipes is not None:
        relatorio["receitas"] = recipe_report(recipes)
    bonus = _proven_bonus(documento)
    relatorio["bonus_comprovado"] = len(bonus["itens"]) if bonus else 0
    return relatorio


def load_recipes(documento: PdfDocument) -> list[Recipe]:
    """Receitas do ebook de Recheios. Levanta se o invariante quebrar."""

    indice = parse_index(documento.pages[2].text) if len(documento.pages) > 2 else {}
    return parse_recipes(documento.pages, index=indice)
