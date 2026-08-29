"""
Brain Retrieval API — a porta unica dos agentes para o Knowledge.

    Agent  ->  brain.search()  ->  Access Policy  ->  Repository  ->  Postgres

Nenhum agente monta SQL. Nenhum agente escolhe status. Nenhum agente decide o
que pode revelar.

ORDEM DAS DECISOES (importa)
----------------------------

    1. resolve_access(agent_id)        -> agente desconhecido morre aqui
    2. filtra por camada permitida
    3. filtra por status (producao = CONFIRMED)
    4. filtra por whitelist de documento e por topic
    5. pontua lexicalmente
    6. decide disclosure por resultado
    7. monta provenance

O passo 6 nao pode vir antes do 5: a policy e resolvida por resultado, com o
`content_access` daquele documento — nao uma vez para a busca inteira.

RELACAO COM O CAMINHO DE PRODUCAO ATUAL
---------------------------------------

O retriever lexical de `agents/knowledge_sources.py` continua sendo producao,
intocado. Este modulo roda EM PARALELO e nao esta plugado em nenhum agente.
`compare_with_lexical()` existe para medir a diferenca entre os dois antes de
qualquer cutover — que nao acontece na F2.

Enquanto nenhum documento estiver CONFIRMED, `search()` em modo producao
devolve vazio. Isso e o comportamento correto, nao um bug: nada foi aprovado
pela Judith ainda.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

# Reusa o tokenizador que ja governa o retrieval de producao. Duas
# tokenizacoes diferentes tornariam a comparacao entre os dois caminhos
# inutil — as diferencas viriam do tokenizador, nao da arquitetura.
from agents.knowledge_sources import _normalize, _tokenize
from brain.access_policy import AccessDenied, KnowledgeAccess, resolve_access
from brain.fusion import reciprocal_rank_fusion
from brain.models import DisclosurePolicy, decide_disclosure
from brain.security import as_data_envelope

DEFAULT_LIMIT = 4

#: Quantos candidatos pontuar antes de diversificar. Precisa ser maior que o
#: top-k final, senao nao ha o que diversificar.
CANDIDATE_POOL_FACTOR = 5

# --- J1: a canonicalizacao precisa influenciar o retrieval ------------------
#
# O scorer lexical conta repeticao de palavra. Ele nao sabe QUE TIPO de
# pergunta esta respondendo, e por isso nao sabe qual fonte e canonica para
# ela. Medido na auditoria:
#
#     "quanto custa Casquinhas e Recheios?"
#       PRODUCTS  score 12   (repete o nome dos produtos)
#       OFFERS    score  4   posicao 15 de 27  <- a fonte do preco, fora do top-k
#
# "quanto" e "custa" pontuam ZERO: nao aparecem em documento nenhum. E a F2.7
# piorou isso — ao tirar o preco de PRODUCTS, transformou o vencedor da corrida
# lexical num documento que estruturalmente nao responde a pergunta.
#
# A correcao usa o que ja existe: `topics`. OFFERS ja carrega `preco`, os
# ebooks ja carregam `tecnica`. Falta so ligar a intencao da pergunta ao topic
# da fonte.

#: Quanto vale um topic que casa com a intencao.
#:
#: 5 e calibrado contra a escala que ja existe: termo no cabecalho vale +4,
#: termo na chave vale +3. Se a pergunta e sobre preco e o documento E o
#: documento de preco, esse sinal vale pelo menos tanto quanto a palavra
#: aparecer num cabecalho. Mais que isso faria OFFERS ganhar de fontes que
#: mencionam o termo de verdade.
TOPIC_BOOST = 5

#: intencao -> topics canonicos. Deterministico, sem LLM.
#:
#: Deliberadamente pequeno. Nao e um classificador de intencao: e um mapa de
#: sinonimos comerciais para os topics que a taxonomia ja atribui.
#:
#: A ORDEM E SIGNIFICATIVA — vence a primeira regra que casar, e nao a uniao.
#:
#: Motivo, medido: "quanto custa Casquinhas e Recheios?" disparava a intencao
#: de PRECO **e** a TECNICA ao mesmo tempo, porque "casquinha" e "recheio" sao
#: nome de produto e palavra tecnica ao mesmo tempo. A uniao dos topics
#: impulsionava as fichas de produto (`ebook`) junto com OFFERS, e as fichas
#: afogavam OFFERS por serem varias.
#:
#: Preco e garantia vem primeiro porque sao os sinais MAIS ESPECIFICOS: quem
#: escreve "quanto custa" esta perguntando preco, mesmo citando o nome de um
#: produto que tambem e uma tecnica.
_INTENT_TOPICS: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (
        (
            "quanto custa",
            "quanto e",
            "quanto sai",
            "quanto fica",
            "qual valor",
            "qual o valor",
            "preco",
            "valor do",
            "caro",
            "barato",
            "promocao",
            "desconto",
            "quanto voce cobra",
            "quanto custam",
        ),
        # `comercial` fica DE FORA de proposito. PRODUCTS tambem o carrega, e
        # incluir esse topic dava o mesmo boost ao documento que ja vencia a
        # corrida lexical — amplificava o problema em vez de corrigi-lo.
        # `preco` e exclusivo de OFFERS; `oferta` alcanca OFFERS e o site.
        frozenset({"preco", "oferta"}),
    ),
    (
        ("garantia", "reembolso", "devolucao", "devolver", "cancelar", "arrependimento", "estorno"),
        frozenset({"politica", "oferta"}),
    ),
    (
        (
            "receita",
            "ganache",
            "temperagem",
            "temperar",
            "casquinha",
            "cristaliza",
            "emulsific",
            "gianduia",
            "brigadeiro",
            "recheio",
            "bombom",
            "ingrediente",
            "gramagem",
            "derreter",
            "molde",
            "separou",
            "brilho",
        ),
        frozenset({"tecnica", "chocolate", "ebook"}),
    ),
    (
        ("qual ebook", "quais ebooks", "diferenca entre", "o que ensina", "quantas receitas", "qual deles"),
        frozenset({"produto", "ebook"}),
    ),
)


def detect_intent_topics(query: str) -> frozenset[str]:
    """Topics canonicos para a intencao da pergunta. Vazio = sem boost.

    Primeira regra que casa vence — ver a nota de ordem em `_INTENT_TOPICS`.
    Sem intencao detectada o comportamento e exatamente o de antes: score
    puramente lexical. O boost adiciona, nunca substitui.
    """

    baixo = _normalize(query or "")
    for marcas, topics in _INTENT_TOPICS:
        if any(marca in baixo for marca in marcas):
            return topics
    return frozenset()


#: Teto de chunks do MESMO documento no resultado final.
#:
#: A F2.5 media isso: um documento longo ocupava o top-k inteiro e expulsava a
#: outra fonte relevante. Com os ebooks o risco piora — um ebook tem 25-31
#: chunks e uma busca por "temperagem" casa com quase todos, empurrando
#: PRODUCTS e OFFERS para fora.
#:
#: 2 e o menor numero que ainda deixa um documento contribuir com contexto
#: (secao + secao vizinha) sem monopolizar.
MAX_PER_DOCUMENT = 2


@dataclass(frozen=True)
class Provenance:
    """A resposta para "de onde veio isto?", inteira, junto do resultado.

    Sobrevive ate o consumidor de proposito: quando o RAG entrar na F3, o
    provenance nao pode ser reconstruido depois — ele viaja com o trecho.
    """

    source_id: str
    source_kind: str
    origin: str
    owner: str
    source_ref: str | None
    document_id: str
    external_key: str | None
    title: str
    layer: str
    status: str
    version: int
    approved_by: str | None
    approved_at: str | None
    topics: list[str]
    confidence: str | None
    valid_to: str | None
    deprecated_by: str | None
    heading: str | None
    ordinal: int
    # --- F2.7 -----------------------------------------------------------
    source_authority: str | None = None
    provided_by: str | None = None
    content_kind: str | None = None
    page: int | None = None
    recipe_id: str | None = None
    heading_path: str | None = None
    entitlement_scope: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "fonte": self.external_key or self.document_id,
            "autoridade": self.source_authority,
            "fornecido_por": self.provided_by,
            "tipo_de_conteudo": self.content_kind,
            "pagina": self.page,
            "receita": self.recipe_id,
            "caminho": self.heading_path,
            "escopo_de_compra": self.entitlement_scope,
            "documento": self.title,
            "camada": self.layer,
            "status": self.status,
            "versao": self.version,
            "aprovado_por": self.approved_by,
            "aprovado_em": self.approved_at,
            "origem": self.origin,
            "tipo_de_fonte": self.source_kind,
            "responsavel": self.owner,
            "referencia": self.source_ref,
            "topics": self.topics,
            "confianca": self.confidence,
            "vigente_ate": self.valid_to,
            "substituido_por": self.deprecated_by,
            "secao": self.heading,
            "ordinal": self.ordinal,
        }


@dataclass(frozen=True)
class SearchHit:
    score: int
    provenance: Provenance
    disclosure: DisclosurePolicy
    #: Corpo que o agente pode ver. Vazio quando `disclosure.withheld`.
    body: str
    #: Sinais do scanner de injecao, se houver. O corpo continua original.
    flags: list[dict[str, Any]] = field(default_factory=list)
    #: F3: por que este trecho ficou onde ficou. `None` no modo lexical puro.
    #: Nao vai para o payload do agente — e diagnostico, nao conhecimento.
    ranking: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **self.provenance.as_dict(),
            "conteudo": self.body,
            "divulgacao": self.disclosure.as_dict(),
        }
        if self.flags:
            payload["conteudo_suspeito"] = self.flags
        return payload


@dataclass(frozen=True)
class SearchResult:
    agent_id: str
    query: str
    hits: list[SearchHit]
    #: Documentos que casaram com a busca mas foram retirados pela politica.
    #: Contagem, nunca conteudo — saber que existe algo bloqueado nao pode
    #: virar um canal lateral para o conteudo.
    filtered_out: dict[str, int]

    # --- F3: observabilidade do retrieval ---------------------------------
    #: LEXICAL | HYBRID | HYBRID_SHADOW. O que de fato ACONTECEU nesta busca,
    #: que nem sempre e o que `RAG_MODE` pediu: sem indice, ou com o provedor
    #: de embedding fora do ar, o hibrido degrada para lexical e diz isso.
    retrieval_mode: str = "LEXICAL"
    #: O modo pedido. A diferenca entre os dois campos e o diagnostico.
    rag_mode: str = "current"
    lexical_candidates: int = 0
    vector_candidates: int = 0
    final_candidates: int = 0
    eligible_chunks: int = 0
    embedding_model: str | None = None
    #: Por que a perna vetorial nao rodou, quando nao rodou.
    vector_skip_reason: str | None = None
    #: Modo shadow: o top-k que o hibrido TERIA devolvido. Nao afeta `hits`.
    shadow_keys: list[str] = field(default_factory=list)
    latency_ms: int | None = None

    def as_documents(self) -> list[dict[str, Any]]:
        return [hit.as_dict() for hit in self.hits]

    def observability(self) -> dict[str, Any]:
        """O que vai para log. IDs e contagem — nunca corpo, nunca vetor."""

        return {
            "retrieval_mode": self.retrieval_mode,
            "rag_mode": self.rag_mode,
            "lexical_candidates": self.lexical_candidates,
            "vector_candidates": self.vector_candidates,
            "final_candidates": self.final_candidates,
            "eligible_chunks": self.eligible_chunks,
            "embedding_model": self.embedding_model,
            "vector_skip_reason": self.vector_skip_reason,
            "sources": [h.provenance.external_key or h.provenance.document_id for h in self.hits],
            "documentos_distintos": len({h.provenance.document_id for h in self.hits}),
            "shadow_sources": list(self.shadow_keys),
            "latency_ms": self.latency_ms,
            "ranking": [h.ranking for h in self.hits if h.ranking],
        }


def _texto_para_score(hit: dict[str, Any]) -> str:
    return _normalize(f"{hit.get('heading') or ''}\n{hit.get('title') or ''}\n{hit.get('body') or ''}")


def _pontuar(termos: list[str], linha: dict[str, Any]) -> int:
    """Mesma heuristica do retrieval lexical de producao."""

    corpo = _texto_para_score(linha)
    tokens_titulo = set(_tokenize(str(linha.get("heading") or "")))
    tokens_chave = set(_tokenize(f"{linha.get('external_key') or ''} {linha.get('title') or ''}"))

    score = 0
    for termo in termos:
        ocorrencias = corpo.count(termo)
        if ocorrencias:
            score += min(ocorrencias, 5)
        if termo in tokens_titulo:
            score += 4
        if termo in tokens_chave:
            score += 3
    return score


def _iso(valor: Any) -> str | None:
    return valor.isoformat() if hasattr(valor, "isoformat") else (str(valor) if valor else None)


def _diversify(pontuados: list[tuple[int, dict[str, Any]]], *, limit: int) -> list[tuple[int, dict[str, Any]]]:
    """Escolhe o top-k espalhando por documento e por receita.

    Duas passadas, e a segunda importa tanto quanto a primeira:

    1. respeitando `MAX_PER_DOCUMENT` e no maximo um chunk por `recipe_id`;
    2. se sobraram vagas, preenche ignorando os tetos.

    A segunda passada existe para que a diversificacao NUNCA devolva menos
    resultados do que a ordenacao por score devolveria. O teto redistribui
    posicoes; nao descarta recall. Sem ela, uma busca cuja unica fonte
    relevante e um documento so voltaria com 2 resultados em vez de 4 —
    trocando um problema real por outro.

    O score original e preservado e continua ordenando: isto reordena
    posicoes, nao inventa relevancia.
    """

    escolhidos: list[tuple[int, dict[str, Any]]] = []
    por_documento: dict[str, int] = {}
    receitas_vistas: set[str] = set()
    usados: set[int] = set()

    for indice, (score, linha) in enumerate(pontuados):
        if len(escolhidos) >= limit:
            break
        documento = str(linha.get("document_id"))
        receita = linha.get("recipe_id")
        if por_documento.get(documento, 0) >= MAX_PER_DOCUMENT:
            continue
        if receita and receita in receitas_vistas:
            continue
        escolhidos.append((score, linha))
        usados.add(indice)
        por_documento[documento] = por_documento.get(documento, 0) + 1
        if receita:
            receitas_vistas.add(str(receita))

    if len(escolhidos) < limit:
        for indice, (score, linha) in enumerate(pontuados):
            if len(escolhidos) >= limit:
                break
            if indice not in usados:
                escolhidos.append((score, linha))

    return escolhidos


#: Cache de vetor de consulta, no processo. Pergunta repetida nao repaga.
#:
#: "quanto custa?" e "tem desconto?" chegam o dia inteiro. O cache e pequeno e
#: local ao processo de proposito: nao ha invalidacao a fazer (o vetor de uma
#: string com um modelo fixo nunca muda) e nao vale um Redis para isto.
_CACHE_DE_CONSULTA: OrderedDict[tuple[str, str], list[float]] = OrderedDict()
_CACHE_MAXIMO = 256


def _vetor_da_consulta(query: str, embedder: Any) -> list[float]:
    chave = (str(embedder.model), query)
    if chave in _CACHE_DE_CONSULTA:
        _CACHE_DE_CONSULTA.move_to_end(chave)
        return _CACHE_DE_CONSULTA[chave]

    vetor = embedder.embed([query])[0]
    _CACHE_DE_CONSULTA[chave] = vetor
    if len(_CACHE_DE_CONSULTA) > _CACHE_MAXIMO:
        _CACHE_DE_CONSULTA.popitem(last=False)
    return vetor


def clear_query_cache() -> None:
    """Usado pelos testes que trocam de embedder no meio do caminho."""

    _CACHE_DE_CONSULTA.clear()


def _elegiveis(
    politica: KnowledgeAccess, candidatos: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """O filtro de politica. UMA passada, para as duas pernas.

    Isto e o coracao da seguranca da F3, e por isso e uma funcao so: as duas
    pernas recebem EXATAMENTE o mesmo conjunto. Nao existe caminho por onde a
    busca vetorial alcance um chunk que a lexical nao alcanca — nao porque ha
    uma checagem extra depois, mas porque o conjunto e o mesmo objeto.

    Similaridade nunca vira permissao: um chunk pago fora da whitelist do
    agente nem entra na lista sobre a qual o cosseno e calculado.
    """

    bloqueados: dict[str, int] = {}
    passaram: list[dict[str, Any]] = []
    for linha in candidatos:
        if not politica.allows_document(
            external_key=linha.get("external_key"),
            layer=str(linha.get("layer")),
            status=str(linha.get("status")),
        ):
            bloqueados["fora_da_whitelist"] = bloqueados.get("fora_da_whitelist", 0) + 1
            continue
        if not politica.allows_topic(linha.get("topics")):
            bloqueados["topic_nao_permitido"] = bloqueados.get("topic_nao_permitido", 0) + 1
            continue
        passaram.append(linha)
    return passaram, bloqueados


def _perna_lexical(
    termos: list[str], intent_topics: frozenset[str], elegiveis: list[dict[str, Any]]
) -> list[tuple[int, dict[str, Any]]]:
    """A busca de sempre: contagem de termo + boost de intencao (J1).

    Continua indispensavel e continua primeiro. Nome de produto, preco, codigo
    de checkout, titulo e termo tecnico exato sao casamento de string — nenhum
    embedding acerta "Casquinhas Profissionais" melhor do que procurar
    "casquinhas profissionais".
    """

    pontuados: list[tuple[int, dict[str, Any]]] = []
    for linha in elegiveis:
        score = _pontuar(termos, linha)
        # J1: o boost soma ao score lexical e SO depois dos filtros de acesso,
        # status, whitelist e topic. Documento proibido nem chegou ate aqui —
        # o boost reordena o que ja passou, nunca abre porta.
        if intent_topics and set(linha.get("topics") or ()) & intent_topics:
            score += TOPIC_BOOST
        if score > 0:
            pontuados.append((score, linha))
    pontuados.sort(key=lambda item: item[0], reverse=True)
    return pontuados


def _perna_vetorial(
    query: str,
    elegiveis: list[dict[str, Any]],
    *,
    repository: Any,
    embedder: Any,
) -> tuple[list[tuple[float, dict[str, Any]]], str | None]:
    """Busca semantica sobre o MESMO conjunto elegivel.

    Devolve `(ordenados, motivo_da_ausencia)`. Motivo preenchido significa que
    a perna nao rodou — e isso e degradacao, nao erro: a resposta continua
    saindo pelo lexical. Falha de indice nao pode virar falha de atendimento.

    Chunk sem vetor simplesmente nao participa desta perna. Cobertura parcial
    do indice degrada a busca semantica proporcionalmente, sem quebrar nada.
    """

    from brain.embeddings import cosine

    checksums = {str(linha["checksum"]) for linha in elegiveis if linha.get("checksum")}
    if not checksums:
        return [], "chunks sem checksum"

    try:
        vetores = repository.embeddings_for_checksums(checksums, embedding_model=embedder.model)
    except Exception as erro:  # noqa: BLE001
        return [], f"indice indisponivel ({type(erro).__name__})"
    if not vetores:
        return [], "nenhum chunk elegivel esta indexado"

    try:
        consulta = _vetor_da_consulta(query, embedder)
    except Exception as erro:  # noqa: BLE001
        return [], f"provedor de embedding indisponivel ({type(erro).__name__})"

    pontuados = [
        (cosine(consulta, vetores[str(linha["checksum"])]), linha)
        for linha in elegiveis
        if str(linha.get("checksum") or "") in vetores
    ]
    # Cosseno negativo e o oposto do que se procura; deixar entrar so poluiria
    # o pool com aquilo que a pergunta menos parece.
    pontuados = [(score, linha) for score, linha in pontuados if score > 0]
    pontuados.sort(key=lambda item: item[0], reverse=True)
    return pontuados, None


def search(
    *,
    agent_id: str,
    query: str,
    repository: Any,
    limit: int = DEFAULT_LIMIT,
    include_body: bool = True,
    access: KnowledgeAccess | None = None,
    mode: str | None = None,
    embedder: Any | None = None,
) -> SearchResult:
    """Busca no Brain respeitando a politica de acesso.

    Levanta `AccessDenied` para agente desconhecido — fail-closed, e o erro e
    explicito em vez de uma lista vazia que parece "nao achei nada".

    A PORTA CONTINUA SENDO UMA SO
    -----------------------------

    O hibrido acontece DENTRO desta funcao. Nao ha tool nova, nao ha segundo
    caminho ate o Postgres, nao ha rota alternativa que devolva trecho sem
    passar por aqui. Isso e resposta direta ao MOBILE_FAIL_02: naquele caso a
    provenance sumiu porque um segundo caminho serializava diferente do
    primeiro. Uma porta so nao tem como divergir de si mesma.

    Todo resultado sai por `SearchHit.provenance` e vira `fonte` no payload —
    o mesmo campo que `_sources_in_tool_result` le para montar
    `sources_opened`. Um chunk trazido pelo vetor e indistinguivel, para o
    Evidence Gate, de um trazido pelo lexical: os dois carregam a mesma
    procedencia completa.
    """

    from time import perf_counter

    from brain.rag_mode import rag_mode, uses_vector, vector_decides

    comeco = perf_counter()
    modo = mode or rag_mode()
    politica = access or resolve_access(agent_id)
    termos = _tokenize(query)
    intent_topics = detect_intent_topics(query)

    candidatos = repository.chunks_for_search(statuses=politica.statuses, layers=politica.layers)
    elegiveis, bloqueados = _elegiveis(politica, candidatos)

    lexical = _perna_lexical(termos, intent_topics, elegiveis)
    teto = limit * CANDIDATE_POOL_FACTOR

    vetorial: list[tuple[float, dict[str, Any]]] = []
    motivo_sem_vetor: str | None = None
    motor: Any = None
    if uses_vector(modo):  # type: ignore[arg-type]
        from brain.embeddings import get_embedder

        motor = embedder or get_embedder()
        vetorial, motivo_sem_vetor = _perna_vetorial(query, elegiveis, repository=repository, embedder=motor)
    else:
        motivo_sem_vetor = "rag_mode=current"

    por_chunk = {str(linha["chunk_id"]): linha for _, linha in lexical}
    por_chunk.update({str(linha["chunk_id"]): linha for _, linha in vetorial})
    score_lexical = {str(linha["chunk_id"]): valor for valor, linha in lexical}
    score_vetorial = {str(linha["chunk_id"]): valor for valor, linha in vetorial}

    fundidos = reciprocal_rank_fusion(
        {
            "lexical": [str(linha["chunk_id"]) for _, linha in lexical[:teto]],
            "vetorial": [str(linha["chunk_id"]) for _, linha in vetorial[:teto]],
        }
    )
    ordem_hibrida = [(item, por_chunk[item.key]) for item in fundidos if item.key in por_chunk]
    explicacao = {item.key: item for item, _ in ordem_hibrida}

    # QUEM DECIDE O RESULTADO
    #
    # `hybrid`        -> a ordem fundida.
    # `hybrid_shadow` -> a ordem lexical, byte a byte igual a `current`. O
    #                    hibrido e calculado e registrado, e so.
    # `current`       -> a ordem lexical, sem sequer consultar o indice.
    if vector_decides(modo):  # type: ignore[arg-type]
        ordenados: list[tuple[Any, dict[str, Any]]] = [(item.score, linha) for item, linha in ordem_hibrida]
        retrieval_mode = "HYBRID"
    else:
        ordenados = list(lexical)
        retrieval_mode = "HYBRID_SHADOW" if uses_vector(modo) else "LEXICAL"  # type: ignore[arg-type]

    if motivo_sem_vetor and retrieval_mode != "LEXICAL":
        # Pediu hibrido e nao teve vetor: degradou. O relatorio precisa dizer,
        # senao um indice vazio parece um hibrido que simplesmente nao ajudou.
        retrieval_mode = "LEXICAL_DEGRADADO"

    selecionados = _diversify(ordenados[:teto], limit=limit)

    hits: list[SearchHit] = []
    for _, linha in selecionados:
        disclosure = decide_disclosure(
            content_access=linha["content_access"],
            agent_is_customer_facing=politica.is_customer_facing,
            agent_can_know_paid=politica.can_know_paid,
        )
        if disclosure.withheld:
            bloqueados["conteudo_pago_sem_permissao"] = bloqueados.get("conteudo_pago_sem_permissao", 0) + 1
            continue

        corpo = ""
        if include_body:
            # F2.5: o corpo NAO e mais truncado. Truncar mutilava o contexto
            # de quem precisa raciocinar sobre o conteudo e nao impedia
            # parafrase do que sobrava. A protecao real e o acesso (conteudo
            # que o agente nao pode conhecer nem chega aqui); o que pode SAIR
            # viaja como policy explicita ao lado. Ver brain/models.py.
            corpo = as_data_envelope(
                str(linha["body"]),
                fonte=str(linha.get("external_key") or linha["document_id"]),
                secao=str(linha.get("heading") or ""),
            )

        chave_chunk = str(linha["chunk_id"])
        fundido = explicacao.get(chave_chunk)
        ranking = None
        if fundido is not None:
            ranking = {
                **fundido.as_dict(),
                "fonte": linha.get("external_key") or linha.get("document_id"),
                "score_lexical": score_lexical.get(chave_chunk),
                "score_vetorial": (round(score_vetorial[chave_chunk], 6) if chave_chunk in score_vetorial else None),
            }

        hits.append(
            SearchHit(
                score=int(score_lexical.get(chave_chunk, 0)),
                provenance=Provenance(
                    source_id=str(linha["source_id"]),
                    source_kind=str(linha["source_kind"]),
                    origin=str(linha["origin"]),
                    owner=str(linha["owner"]),
                    source_ref=linha.get("source_ref"),
                    document_id=str(linha["document_id"]),
                    external_key=linha.get("external_key"),
                    title=str(linha["title"]),
                    layer=str(linha["layer"]),
                    status=str(linha["status"]),
                    version=int(linha["version"]),
                    approved_by=linha.get("approved_by"),
                    approved_at=_iso(linha.get("approved_at")),
                    topics=list(linha.get("topics") or []),
                    confidence=linha.get("confidence"),
                    valid_to=_iso(linha.get("valid_to")),
                    deprecated_by=linha.get("deprecated_by"),
                    heading=linha.get("heading"),
                    ordinal=int(linha["ordinal"]),
                    source_authority=linha.get("source_authority"),
                    provided_by=linha.get("provided_by"),
                    content_kind=linha.get("content_kind"),
                    page=linha.get("page"),
                    recipe_id=linha.get("recipe_id"),
                    heading_path=linha.get("heading_path"),
                    entitlement_scope=linha.get("entitlement_scope"),
                ),
                disclosure=disclosure,
                body=corpo,
                flags=list(linha.get("flags") or []),
                ranking=ranking,
            )
        )

    sombra: list[str] = []
    if uses_vector(modo) and not vector_decides(modo):  # type: ignore[arg-type]
        # O que o hibrido TERIA devolvido, ja diversificado, para a comparacao
        # ser justa. Nao toca em `hits`.
        sombra = [
            str(linha.get("external_key") or linha["document_id"])
            for _, linha in _diversify([(item.score, linha) for item, linha in ordem_hibrida][:teto], limit=limit)
        ]

    resultado = SearchResult(
        agent_id=agent_id,
        query=query,
        hits=hits,
        filtered_out=bloqueados,
        retrieval_mode=retrieval_mode,
        rag_mode=str(modo),
        lexical_candidates=len(lexical),
        vector_candidates=len(vetorial),
        final_candidates=len(hits),
        eligible_chunks=len(elegiveis),
        embedding_model=str(motor.model) if motor is not None else None,
        vector_skip_reason=motivo_sem_vetor,
        shadow_keys=sombra,
        latency_ms=int((perf_counter() - comeco) * 1000),
    )

    # Diagnostico, nunca evidencia. Ver brain/retrieval_trace.py para por que
    # isto nao e um segundo caminho de provenance.
    from brain.retrieval_trace import record

    record(resultado.observability())
    return resultado


def compare_with_lexical(*, agent_id: str, query: str, repository: Any, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Roda os dois caminhos e devolve a diferenca. Nao muda producao.

    Existe para responder, com numero, se o store novo pode substituir o
    lexical — em vez de trocar e torcer.
    """

    from agents.knowledge_policies import get_policy
    from agents.knowledge_sources import search_documents

    politica_antiga = get_policy(agent_id)
    antigos = search_documents(
        query,
        sources=politica_antiga.documents,
        missing=politica_antiga.missing_sources,
        num_documents=limit,
    )
    chaves_antigas = [str(doc.get("fonte")) for doc in antigos if doc.get("fonte")]

    try:
        novo = search(agent_id=agent_id, query=query, repository=repository, limit=limit, include_body=False)
        chaves_novas = [hit.provenance.external_key or hit.provenance.document_id for hit in novo.hits]
        negado = None
        bloqueados = novo.filtered_out
    except AccessDenied as exc:
        chaves_novas, negado, bloqueados = [], str(exc), {}

    return {
        "agent_id": agent_id,
        "query": query,
        "lexical": chaves_antigas,
        "brain": chaves_novas,
        "somente_no_lexical": [k for k in chaves_antigas if k not in chaves_novas],
        "somente_no_brain": [k for k in chaves_novas if k not in chaves_antigas],
        "iguais": [k for k in chaves_antigas if k in chaves_novas],
        "bloqueados_pela_politica": bloqueados,
        "acesso_negado": negado,
    }
