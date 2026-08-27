"""
Judith Brain — chunking que preserva estrutura.

Regra: NUNCA cortar a cada N caracteres. Um corte cego separa a pergunta da
resposta, o ingrediente da quantidade, a regra da excecao — e depois nenhum
retrieval consegue juntar de novo.

Hierarquia de corte, sempre da maior unidade semantica para a menor:

    1. secao `## `        -> a unidade natural do markdown deste repositorio
    2. subsecao `### `    -> quando a secao passa do teto
    3. paragrafo (linha em branco)
    4. bloco de lista inteiro, nunca no meio de um item

So se um paragrafo unico passar do teto e que ele vai inteiro num chunk, com
`oversized=True`. Preferimos um chunk grande a um chunk mutilado — o teto e
uma heuristica, a integridade do texto nao e.

Blocos de codigo (``` ... ```) nunca sao divididos.

Sem embedding. `token_count` e estimativa (~4 chars/token em portugues), so
para dimensionar custo depois; nao alimenta decisao nenhuma agora.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

#: Teto por chunk. Escolhido para caber com folga em qualquer janela e ainda
#: assim manter uma secao inteira junta — os documentos deste repo tem 1-14 KB.
MAX_CHUNK_CHARS = 2400

#: Abaixo disto um chunk vira ruido: e absorvido pelo anterior.
MIN_CHUNK_CHARS = 80

LEAD_HEADING = "(inicio do documento)"

_CODE_FENCE = re.compile(r"^\s*```")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    heading: str
    body: str
    token_count: int
    checksum: str
    #: True quando um unico paragrafo estourou o teto e foi mantido inteiro.
    oversized: bool = False

    @property
    def chars(self) -> int:
        return len(self.body)


def checksum_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """~4 caracteres por token. Estimativa, e declarada como tal."""

    return max(1, len(text) // 4)


def _split_headed_sections(content: str, marker: str, lead: str) -> list[tuple[str, str]]:
    """Divide por `marker` ('## ' ou '### '), respeitando bloco de codigo."""

    secoes: list[tuple[str, list[str]]] = []
    titulo = lead
    atual: list[str] = []
    dentro_de_codigo = False

    for linha in content.splitlines():
        if _CODE_FENCE.match(linha):
            dentro_de_codigo = not dentro_de_codigo
        # Cabecalho dentro de bloco de codigo e conteudo, nao estrutura.
        if not dentro_de_codigo and linha.startswith(marker):
            if any(l.strip() for l in atual):
                secoes.append((titulo, atual))
            titulo = linha[len(marker) :].strip()
            atual = []
        else:
            atual.append(linha)

    if any(l.strip() for l in atual):
        secoes.append((titulo, atual))

    return [(t, "\n".join(corpo).strip()) for t, corpo in secoes]


def _split_paragraphs(text: str) -> list[str]:
    """Quebra em paragrafos, mantendo bloco de codigo inteiro."""

    blocos: list[str] = []
    atual: list[str] = []
    dentro_de_codigo = False

    for linha in text.splitlines():
        if _CODE_FENCE.match(linha):
            dentro_de_codigo = not dentro_de_codigo
            atual.append(linha)
            continue
        if not dentro_de_codigo and not linha.strip():
            if any(l.strip() for l in atual):
                blocos.append("\n".join(atual).strip())
            atual = []
        else:
            atual.append(linha)

    if any(l.strip() for l in atual):
        blocos.append("\n".join(atual).strip())
    return blocos


def _agrupar(paragrafos: list[str], teto: int) -> list[tuple[str, bool]]:
    """Junta paragrafos ate o teto. Devolve (texto, estourou_sozinho)."""

    grupos: list[tuple[str, bool]] = []
    buffer: list[str] = []
    tamanho = 0

    for paragrafo in paragrafos:
        if len(paragrafo) > teto:
            # Paragrafo maior que o teto sozinho: fecha o que estava aberto e
            # deixa este inteiro. Cortar aqui seria cortar no meio de uma ideia.
            if buffer:
                grupos.append(("\n\n".join(buffer), False))
                buffer, tamanho = [], 0
            grupos.append((paragrafo, True))
            continue

        if tamanho + len(paragrafo) > teto and buffer:
            grupos.append(("\n\n".join(buffer), False))
            buffer, tamanho = [], 0

        buffer.append(paragrafo)
        tamanho += len(paragrafo) + 2

    if buffer:
        grupos.append(("\n\n".join(buffer), False))
    return grupos


def chunk_markdown(content: str, *, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """Divide um markdown em chunks que preservam estrutura semantica."""

    chunks: list[Chunk] = []
    ordinal = 0

    for titulo_secao, corpo_secao in _split_headed_sections(content, "## ", LEAD_HEADING):
        if not corpo_secao.strip():
            continue

        if len(corpo_secao) <= max_chars:
            pedacos: list[tuple[str, str, bool]] = [(titulo_secao, corpo_secao, False)]
        else:
            pedacos = []
            # Secao grande: tenta subsecao antes de tentar paragrafo.
            subsecoes = _split_headed_sections(corpo_secao, "### ", titulo_secao)
            for titulo_sub, corpo_sub in subsecoes:
                heading = titulo_sub if titulo_sub != titulo_secao else titulo_secao
                if titulo_sub != titulo_secao:
                    heading = f"{titulo_secao} > {titulo_sub}"
                if len(corpo_sub) <= max_chars:
                    pedacos.append((heading, corpo_sub, False))
                    continue
                for texto, estourou in _agrupar(_split_paragraphs(corpo_sub), max_chars):
                    pedacos.append((heading, texto, estourou))

        for heading, texto, estourou in pedacos:
            texto = texto.strip()
            if not texto:
                continue
            # Sobra minuscula gruda no chunk anterior em vez de virar ruido.
            if chunks and len(texto) < MIN_CHUNK_CHARS and chunks[-1].heading == heading:
                anterior = chunks.pop()
                texto = f"{anterior.body}\n\n{texto}"
                ordinal = anterior.ordinal
            else:
                ordinal += 1

            chunks.append(
                Chunk(
                    ordinal=ordinal,
                    heading=heading,
                    body=texto,
                    token_count=estimate_tokens(texto),
                    checksum=checksum_of(texto),
                    oversized=estourou,
                )
            )

    # Renumera para garantir sequencia densa depois das fusoes.
    return [
        Chunk(
            ordinal=indice,
            heading=c.heading,
            body=c.body,
            token_count=c.token_count,
            checksum=c.checksum,
            oversized=c.oversized,
        )
        for indice, c in enumerate(chunks, start=1)
    ]
