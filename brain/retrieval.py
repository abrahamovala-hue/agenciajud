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

from dataclasses import dataclass, field
from typing import Any

# Reusa o tokenizador que ja governa o retrieval de producao. Duas
# tokenizacoes diferentes tornariam a comparacao entre os dois caminhos
# inutil — as diferencas viriam do tokenizador, nao da arquitetura.
from agents.knowledge_sources import _normalize, _tokenize
from brain.access_policy import AccessDenied, KnowledgeAccess, resolve_access
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

    def as_documents(self) -> list[dict[str, Any]]:
        return [hit.as_dict() for hit in self.hits]


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


def search(
    *,
    agent_id: str,
    query: str,
    repository: Any,
    limit: int = DEFAULT_LIMIT,
    include_body: bool = True,
    access: KnowledgeAccess | None = None,
) -> SearchResult:
    """Busca no Brain respeitando a politica de acesso.

    Levanta `AccessDenied` para agente desconhecido — fail-closed, e o erro
    e explicito em vez de uma lista vazia que parece "nao achei nada".
    """

    politica = access or resolve_access(agent_id)
    termos = _tokenize(query)
    intent_topics = detect_intent_topics(query)
    bloqueados: dict[str, int] = {}

    candidatos = repository.chunks_for_search(statuses=politica.statuses, layers=politica.layers)

    pontuados: list[tuple[int, dict[str, Any]]] = []
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

        score = _pontuar(termos, linha)
        # J1: o boost soma ao score lexical, e SO depois dos filtros de
        # acesso, status, whitelist e topic. Um documento proibido nao chega
        # aqui — o boost nunca abre porta, so reordena o que ja passou.
        if intent_topics and score >= 0 and set(linha.get("topics") or ()) & intent_topics:
            score += TOPIC_BOOST
        if score > 0:
            pontuados.append((score, linha))

    pontuados.sort(key=lambda item: item[0], reverse=True)
    selecionados = _diversify(pontuados[: limit * CANDIDATE_POOL_FACTOR], limit=limit)

    hits: list[SearchHit] = []
    for score, linha in selecionados:
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

        hits.append(
            SearchHit(
                score=score,
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
            )
        )

    return SearchResult(agent_id=agent_id, query=query, hits=hits, filtered_out=bloqueados)


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
