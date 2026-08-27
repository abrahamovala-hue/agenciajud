"""
Segmentacao de receitas — a unidade semantica do ebook de Recheios.

POR QUE ISTO EXISTE SEPARADO DO CHUNKING GENERICO
-------------------------------------------------

`brain/chunking.py` corta markdown por cabecalho. Um ebook em PDF nao tem
cabecalho de markdown: tem pagina, e uma receita e uma pagina (as vezes
duas). Cortar por caractere misturaria o fim de uma receita com o inicio da
proxima — e ai um retrieval sobre "ganache de framboesa" devolveria a
gramagem do whisky. Esse e o erro que este modulo existe para tornar
impossivel.

O INVARIANTE
------------

O ebook declara o proprio indice na pagina 3. Nao inferimos a lista de
receitas do corpo: lemos o SUMARIO e depois exigimos que as paginas batam com
ele. Se a extracao produzir um numero diferente de 20, `RecipeSetError` e
levantada e a ingestao PARA — silenciosamente ingerir 19 receitas seria pior
do que falhar, porque o agente passaria a afirmar um catalogo errado com
confianca.

RECEITA CONTINUADA
------------------

"Brigadeiro Gourmet com Bolo de Cenoura" ocupa duas paginas: a segunda se
declara "Parte 2". As duas paginas pertencem a MESMA `recipe_id` — sao dois
chunks de uma receita, nao duas receitas.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

#: As quatro categorias do ebook, na ordem do sumario, com a contagem que o
#: proprio documento declara. Usadas como invariante, nao como sugestao.
EXPECTED_CATEGORIES: dict[str, int] = {
    "GANACHES": 7,
    "BRIGADEIROS GOURMET": 3,
    "GIANDUIAS": 8,
    "CARAMELOS": 2,
}

EXPECTED_RECIPE_COUNT = 20

_YIELD = re.compile(r"Formato\s+(?P<formato>.+?)\s*—\s*Rendimento:\s*(?P<rendimento>.+?)\s*$", re.IGNORECASE)
_PART = re.compile(r"—\s*Parte\s*(\d+)", re.IGNORECASE)
_INDEX_ITEM = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
_VALIDADE = re.compile(r"Validade:\s*(?P<valor>[^.]*\.?)", re.IGNORECASE)
_DECORACAO = re.compile(r"Decora[çc][ãa]o:\s*(?P<valor>.+?)(?=\s*Validade:|$)", re.IGNORECASE | re.DOTALL)


class RecipeSetError(RuntimeError):
    """A extracao nao bateu com o indice declarado pelo proprio ebook."""


def _fold(texto: str) -> str:
    """Minusculo sem acento — so para COMPARAR nomes, nunca para gravar."""

    normal = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in normal if not unicodedata.combining(c)).casefold().strip()


@dataclass
class Recipe:
    recipe_id: str
    category: str
    name: str
    formato: str | None
    rendimento: str | None
    description: str
    ingredients: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    decoration: str | None = None
    validade: str | None = None
    vegan: bool = False
    pages: list[int] = field(default_factory=list)
    #: Corpo integral da receita, ja normalizado. CONTEUDO PAGO.
    body: str = ""

    def outline(self) -> dict[str, Any]:
        """O que pode ser dito sobre a receita SEM entregar a receita.

        Nome, categoria, formato e rendimento descrevem o produto; a lista de
        ingredientes com gramagem e o modo de preparo, nao. Esta e a fronteira
        entre PRODUCTS e conteudo pago, e ela mora aqui para que exista um so
        lugar onde ela possa ser auditada.
        """

        return {
            "recipe_id": self.recipe_id,
            "categoria": self.category,
            "nome": self.name,
            "formato": self.formato,
            "rendimento": self.rendimento,
            "vegano": self.vegan,
            "paginas": list(self.pages),
            "quantidade_de_ingredientes": len(self.ingredients),
            "quantidade_de_passos": len(self.steps),
        }


def parse_index(page_text: str) -> dict[str, list[str]]:
    """Le o SUMARIO. Devolve categoria -> nomes, na ordem declarada."""

    indice: dict[str, list[str]] = {}
    atual: str | None = None
    for linha in page_text.splitlines():
        limpa = linha.strip()
        if not limpa:
            continue
        for categoria in EXPECTED_CATEGORIES:
            if _fold(limpa) == _fold(categoria):
                atual = categoria
                indice.setdefault(categoria, [])
                break
        else:
            achado = _INDEX_ITEM.match(limpa)
            if achado and atual:
                indice[atual].append(achado.group(2))
    return indice


def _slug(nome: str) -> str:
    base = _fold(nome)
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


#: Uma linha ainda e prosa da descricao se for longa (o texto quebra por volta
#: de 65 caracteres) ou se for a cauda curta de uma frase — "em po.". Um
#: rotulo de bloco ("Ingredientes", "Recheio", "Casca:", "Pasta de Pecan")
#: nunca termina em pontuacao final, e e por isso que a regra separa os dois
#: sem precisar de uma lista de rotulos: a lista real varia por receita e
#: colide com nomes de ingrediente ("Pasta de" e rotulo numa pagina e
#: ingrediente em outra).
_PROSE_MIN_CHARS = 35
_SENTENCE_END = (".", "!", "?")


def _is_prose(linha: str) -> bool:
    return len(linha) > _PROSE_MIN_CHARS or linha.endswith(_SENTENCE_END)


def _split_sections(linhas: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Divide a regiao pos-cabecalho em (descricao, ingredientes, passos).

    Nao tenta identificar QUAL bloco de ingrediente e qual: tudo entre o fim
    da descricao e "Modo de Preparo" e regiao de ingrediente. Os rotulos
    internos ("Casca:", "Pasta de Pecan") ficam preservados dentro dela.
    """

    descricao: list[str] = []
    ingredientes: list[str] = []
    passos: list[str] = []

    estado = "descricao"
    for linha in linhas:
        if _fold(linha).startswith("modo de preparo"):
            estado = "passos"
            continue
        if estado == "descricao":
            if _is_prose(linha):
                descricao.append(linha)
                continue
            estado = "ingredientes"
        if estado == "ingredientes":
            ingredientes.append(linha)
        else:
            passos.append(linha)

    return descricao, ingredientes, passos


def _clean_steps(linhas: list[str]) -> list[str]:
    """Remonta os passos.

    No PDF o numero do passo vem DEPOIS do texto (a ordem de leitura do
    layout coloca a coluna do numero por ultimo). Entao juntamos as linhas de
    texto ate encontrar o `N.` que as fecha.
    """

    passos: list[str] = []
    acumulado: list[str] = []
    for linha in linhas:
        if re.fullmatch(r"\d+\.", linha.strip()):
            if acumulado:
                passos.append(" ".join(acumulado).strip())
                acumulado = []
            continue
        acumulado.append(linha.strip())
    if acumulado:
        resto = " ".join(acumulado).strip()
        if resto:
            passos.append(resto)
    return [p for p in passos if p]


def parse_recipes(pages: list[Any], *, index: dict[str, list[str]]) -> list[Recipe]:
    """Segmenta as paginas de receita. Exige bater com o indice."""

    esperados: list[tuple[str, str]] = [(cat, nome) for cat, nomes in index.items() for nome in nomes]
    receitas: list[Recipe] = []
    atual: Recipe | None = None

    for pagina in pages:
        linhas = [linha.strip() for linha in pagina.text.splitlines() if linha.strip()]
        if not linhas:
            continue
        categoria = next((c for c in EXPECTED_CATEGORIES if _fold(linhas[0]) == _fold(c)), None)
        if categoria is None:
            continue

        corpo = linhas[1:]
        # Nome pode quebrar em varias linhas ate a linha de Formato/Rendimento.
        nome_partes: list[str] = []
        formato = rendimento = None
        resto: list[str] = []
        for posicao, linha in enumerate(corpo):
            achado = _YIELD.search(linha)
            if achado:
                formato = achado.group("formato").strip()
                rendimento = achado.group("rendimento").strip()
                anterior = linha[: achado.start()].strip()
                if anterior:
                    nome_partes.append(anterior)
                resto = corpo[posicao + 1 :]
                break
            nome_partes.append(linha)
        else:
            resto = []

        nome_bruto = " ".join(nome_partes).strip()
        continuacao = bool(_PART.search(nome_bruto))
        nome = _PART.sub("", nome_bruto).strip(" —-:&")
        nome = re.sub(r"\s+", " ", nome)

        if continuacao and atual is not None:
            atual.pages.append(pagina.page_number)
            atual.body += "\n" + pagina.text
            descricao, ingredientes, passos = _split_sections(resto)
            atual.ingredients.extend(i for i in ingredientes if i)
            atual.steps.extend(_clean_steps(passos))
            continue

        descricao, ingredientes, passos = _split_sections(resto)
        texto_todo = pagina.text
        decoracao = _DECORACAO.search(texto_todo)
        validade = _VALIDADE.search(texto_todo)

        atual = Recipe(
            recipe_id=f"recheios::{_slug(nome)}",
            category=categoria,
            name=nome,
            formato=formato,
            rendimento=rendimento,
            description=" ".join(descricao).strip(),
            ingredients=[i for i in ingredientes if i],
            steps=_clean_steps(passos),
            decoration=" ".join(decoracao.group("valor").split()) if decoracao else None,
            validade=" ".join(validade.group("valor").split()) if validade else None,
            vegan="vegano" in _fold(texto_todo),
            pages=[pagina.page_number],
            body=texto_todo,
        )
        receitas.append(atual)

    _validate(receitas, esperados)
    return receitas


def _validate(receitas: list[Recipe], esperados: list[tuple[str, str]]) -> None:
    """Falha alto e claro. Ingerir um catalogo errado e pior do que parar."""

    if len(receitas) != EXPECTED_RECIPE_COUNT:
        nomes = [r.name for r in receitas]
        raise RecipeSetError(
            f"esperava {EXPECTED_RECIPE_COUNT} receitas, extraiu {len(receitas)}. Extraidas: {nomes}"
        )

    por_categoria: dict[str, int] = {}
    for receita in receitas:
        por_categoria[receita.category] = por_categoria.get(receita.category, 0) + 1
    if por_categoria != EXPECTED_CATEGORIES:
        raise RecipeSetError(f"distribuicao por categoria divergente: esperava {EXPECTED_CATEGORIES}, veio {por_categoria}")

    if esperados:
        declarados = {_fold(nome) for _, nome in esperados}
        extraidos = {_fold(r.name) for r in receitas}
        faltando = declarados - extraidos
        sobrando = extraidos - declarados
        if faltando or sobrando:
            raise RecipeSetError(
                f"nomes divergem do sumario. Faltando no corpo: {sorted(faltando)}. "
                f"Nao declarados no sumario: {sorted(sobrando)}."
            )


def recipe_report(receitas: list[Recipe]) -> dict[str, Any]:
    """Prova de completude sem expor conteudo pago."""

    por_categoria: dict[str, int] = {}
    for receita in receitas:
        por_categoria[receita.category] = por_categoria.get(receita.category, 0) + 1
    return {
        "receitas": len(receitas),
        "por_categoria": por_categoria,
        "veganas": sum(1 for r in receitas if r.vegan),
        "com_validade": sum(1 for r in receitas if r.validade),
        "com_decoracao": sum(1 for r in receitas if r.decoration),
        "paginas_cobertas": sorted({p for r in receitas for p in r.pages}),
        "sem_ingredientes": [r.name for r in receitas if not r.ingredients],
        "sem_passos": [r.name for r in receitas if not r.steps],
    }
