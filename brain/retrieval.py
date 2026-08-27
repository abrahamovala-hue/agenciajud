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

    def as_dict(self) -> dict[str, Any]:
        return {
            "fonte": self.external_key or self.document_id,
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
        if score > 0:
            pontuados.append((score, linha))

    pontuados.sort(key=lambda item: item[0], reverse=True)

    hits: list[SearchHit] = []
    for score, linha in pontuados[:limit]:
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
