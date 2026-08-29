"""
Embeddings — o indice de recuperacao semantica. Nunca fonte de verdade.

    chunk (Postgres, governado)  --embed-->  vetor  --busca-->  chunk

O vetor nao guarda conteudo legivel, nao guarda provenance e nao decide nada.
Ele responde uma unica pergunta: "quais chunks se parecem com esta pergunta?".
Quem responde "este chunk pode ser lido por este agente?" continua sendo a
Access Policy, e quem responde "isto pode sair para a cliente?" continua sendo
o Disclosure Gate. Perder essa separacao seria trocar autorizacao por
similaridade — e similaridade nao e permissao.

A IDENTIDADE DE UM EMBEDDING E O CHECKSUM DO TEXTO, NAO O CHUNK
---------------------------------------------------------------

`write_chunks` e `rebuild_chunks` apagam e reinserem os chunks de uma versao,
com `chunk_id` novo a cada vez. Se o embedding fosse chaveado por `chunk_id`,
todo reprocessamento jogaria fora o indice inteiro e pagaria a API de novo
para produzir exatamente os mesmos vetores.

Chaveando por `(content_checksum, embedding_model)`:

    texto igual  + modelo igual  -> reaproveita, zero chamada de API
    texto mudou                  -> checksum novo -> embedding novo
    modelo mudou                 -> linha nova, a antiga continua auditavel

`chunks.checksum` ja e exatamente `sha256(body)` — o campo existe desde a F2 e
e gravado nos dois caminhos de escrita de chunk. Nao ha campo novo a inventar.

Efeito colateral desejado: dois documentos com o mesmo trecho compartilham um
vetor so.

O QUE NAO ENTRA NO GIT
----------------------

Nenhum vetor e serializado para o repositorio. O indice vive no Postgres, e
so. Um arquivo de vetores dos ebooks pagos no Git seria conteudo pago no Git
por outro nome — reconstruir texto a partir de embedding e imperfeito, mas a
regra da Judith nao admite a discussao.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from os import getenv
from typing import Any, Protocol

#: O modelo. Escolhido na F3 — ver o relatorio para a comparacao.
#:
#: Nao e configuravel por env de proposito: trocar o modelo invalida todos os
#: vetores gravados, e isso e uma migration, nao uma variavel de ambiente. A
#: troca acontece mudando esta constante, e o pipeline reindexa o que ficou
#: para tras sozinho, porque a chave de identidade inclui o nome do modelo.
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSION = 1536

#: Quantos textos por chamada. O limite da API e bem maior; 128 mantem cada
#: requisicao pequena o suficiente para um retry nao custar caro.
BATCH_SIZE = 128

#: Teto de caracteres por texto. `text-embedding-3-small` aceita 8191 tokens e
#: um chunk de receita cabe folgado. O corte existe para que um chunk anomalo
#: nao derrube o lote inteiro — e ele e contado no relatorio.
MAX_CHARS = 24_000


class Embedder(Protocol):
    """O contrato minimo. Duas implementacoes: OpenAI e deterministica."""

    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class OpenAIEmbedder:
    """`text-embedding-3-small` pela mesma `OPENAI_API_KEY` que ja existe.

    Nenhuma credencial nova: o provedor e o mesmo que ja recebe o corpo dos
    chunks pagos toda vez que o customer-support raciocina sobre eles. O
    embedding nao cria contraparte nova — ver o relatorio da F3.
    """

    model: str = DEFAULT_MODEL
    dimension: int = DEFAULT_DIMENSION

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        cliente = OpenAI()
        vetores: list[list[float]] = []
        for inicio in range(0, len(texts), BATCH_SIZE):
            lote = [t[:MAX_CHARS] or " " for t in texts[inicio : inicio + BATCH_SIZE]]
            resposta = cliente.embeddings.create(model=self.model, input=lote)
            vetores.extend(list(item.embedding) for item in sorted(resposta.data, key=lambda d: d.index))
        return vetores


@dataclass
class DeterministicEmbedder:
    """Embedder offline e reproduzivel. Testes, nunca producao.

    Projeta tokens em dimensoes por hash — o "hashing trick" classico. Nao tem
    semantica: "ganache" e "emulsao" ficam longe uma da outra. Isso e
    proposital e precisa ser dito em voz alta.

    O que ele PROVA e o encanamento: idempotencia, filtro, fusao, diversidade,
    provenance, rollback. O que ele NAO pode provar e que a busca semantica
    encontra sinonimo — essa afirmacao so vale medida com o modelo real, e por
    isso e medida no shadow de producao, nao num teste unitario.
    """

    model: str = "deterministic-hash-v1"
    dimension: int = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        from agents.knowledge_sources import _tokenize

        vetores: list[list[float]] = []
        for texto in texts:
            vetor = [0.0] * self.dimension
            for token in _tokenize(texto) or ["_vazio_"]:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                indice = struct.unpack_from(">I", digest)[0] % self.dimension
                sinal = 1.0 if digest[4] % 2 == 0 else -1.0
                vetor[indice] += sinal
            vetores.append(normalize(vetor))
        return vetores


def normalize(vetor: list[float]) -> list[float]:
    """Vetor unitario. Com norma 1, cosseno vira produto escalar."""

    norma = math.sqrt(sum(v * v for v in vetor))
    if norma == 0.0:
        return list(vetor)
    return [v / norma for v in vetor]


def cosine(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno. -1..1, maior e mais parecido.

    Implementado em Python porque e o mesmo calculo nos dois bancos: o
    Postgres tem o operador `<=>` e o SQLite dos testes nao tem. Um caminho de
    codigo so vale mais que a micro-otimizacao aqui — o conjunto candidato
    chega ja filtrado pela politica, e e pequeno.
    """

    # Comprimento, e nao valor-verdade: `not a` levanta ValueError quando `a` e
    # um `numpy.ndarray` com mais de um elemento — e e exatamente isso que o
    # pgvector devolve. O repositorio ja converte na fronteira; esta guarda
    # existe para que a funcao continue correta se alguem chamar direto.
    if len(a) == 0 or len(b) == 0 or len(a) != len(b):
        return 0.0
    produto = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    # `float()` explicito: se um vetor chegar com escalar de numpy — apesar da
    # conversao no repositorio — o resultado ainda sai como float de Python.
    # Defesa em profundidade contra um tipo que so aparece em producao.
    return float(produto / (na * nb))


def get_embedder() -> Embedder:
    """O embedder de producao, ou o deterministico quando declarado.

    `BRAIN_EMBEDDER=deterministic` existe para rodar a suite inteira sem rede e
    sem gastar. Nao ha fallback automatico: se a chave da OpenAI faltar em
    producao, o pipeline levanta em vez de gravar vetores sem semantica — um
    indice mudo que parece funcionar e pior que indice nenhum.
    """

    escolha = (getenv("BRAIN_EMBEDDER") or "").strip().lower()
    if escolha == "deterministic":
        return DeterministicEmbedder()
    return OpenAIEmbedder()


def embedding_identity(body: str) -> str:
    """Checksum do texto. O mesmo `sha256` que o chunk ja grava."""

    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class EmbeddingReport:
    """O que o pipeline fez. Contagem e id — nunca corpo, nunca vetor."""

    model: str
    dimension: int
    chunks_elegiveis: int = 0
    ja_indexados: int = 0
    novos: int = 0
    reaproveitados: int = 0
    truncados: int = 0
    erros: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        cobertos = self.ja_indexados + self.novos + self.reaproveitados
        return {
            "embedding_model": self.model,
            "embedding_dimension": self.dimension,
            "chunks_elegiveis": self.chunks_elegiveis,
            "ja_indexados": self.ja_indexados,
            "novos": self.novos,
            "reaproveitados": self.reaproveitados,
            "truncados": self.truncados,
            "erros": list(self.erros),
            "cobertura": round(cobertos / self.chunks_elegiveis, 4) if self.chunks_elegiveis else None,
        }


def run_embedding_pipeline(
    repository: Any,
    *,
    embedder: Embedder | None = None,
    dry_run: bool = False,
    batch_limit: int | None = None,
) -> EmbeddingReport:
    """Indexa o que falta. Idempotente por (checksum, modelo).

    ORDEM DAS DECISOES

        1. junta os chunks indexaveis (todo status, toda camada)
        2. descarta os que ja tem vetor para ESTE modelo
        3. deduplica por checksum — texto repetido embute uma vez
        4. chama o provedor em lote
        5. grava

    O passo 1 usa TODO status de proposito. Indexar so CONFIRMED faria a
    aprovacao de um documento disparar chamada de API no meio de um boot, e um
    documento recem-aprovado ficaria invisivel para a busca semantica ate
    alguem lembrar de rodar o pipeline. Indexar nao e publicar: o filtro de
    status continua acontecendo no retrieval, onde sempre esteve.

    DEPRECATED tambem e indexado, e tambem continua fora do retrieval de
    producao pelo mesmo filtro. O indice reflete o acervo; a politica decide o
    que sai dele.
    """

    motor = embedder or get_embedder()
    relatorio = EmbeddingReport(model=motor.model, dimension=motor.dimension)

    linhas = repository.chunks_for_embedding()
    relatorio.chunks_elegiveis = len(linhas)

    existentes = repository.embedded_checksums(embedding_model=motor.model)

    pendentes: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        checksum = str(linha["checksum"])
        if checksum in existentes:
            relatorio.ja_indexados += 1
            continue
        if checksum in pendentes:
            # Mesmo texto em outro chunk: um vetor serve aos dois.
            relatorio.reaproveitados += 1
            continue
        pendentes[checksum] = linha

    if batch_limit is not None:
        pendentes = dict(list(pendentes.items())[:batch_limit])

    if dry_run or not pendentes:
        return relatorio

    checksums = list(pendentes)
    textos: list[str] = []
    for checksum in checksums:
        corpo = str(pendentes[checksum]["body"])
        if len(corpo) > MAX_CHARS:
            relatorio.truncados += 1
        textos.append(corpo)

    try:
        vetores = motor.embed(textos)
    except Exception as erro:  # noqa: BLE001
        # Sem conteudo na mensagem: um erro de API nao pode virar o canal por
        # onde o corpo de um chunk pago aparece em log.
        relatorio.erros.append(f"{type(erro).__name__} ao indexar {len(textos)} textos")
        return relatorio

    if len(vetores) != len(checksums):
        relatorio.erros.append(f"provedor devolveu {len(vetores)} vetores para {len(checksums)} textos")
        return relatorio

    relatorio.novos = repository.store_embeddings(
        embedding_model=motor.model,
        dimension=motor.dimension,
        registros=[
            {
                "content_checksum": checksum,
                "chunk_id": pendentes[checksum]["chunk_id"],
                "version_id": pendentes[checksum]["version_id"],
                "document_id": pendentes[checksum]["document_id"],
                "embedding": normalize(vetor),
            }
            for checksum, vetor in zip(checksums, vetores, strict=True)
        ],
    )
    return relatorio
