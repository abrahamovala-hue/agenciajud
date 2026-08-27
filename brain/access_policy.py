"""
Knowledge Access Policy — determinística e fail-closed.

    Agent  ->  Brain Retrieval API  ->  ESTA POLITICA  ->  Repository  ->  Postgres

Nenhum agente fala com o banco. Nenhum agente escolhe o proprio acesso.

AS QUATRO REGRAS
----------------

1. **Agente desconhecido -> DENIED.** Nao existe default permissivo. Um
   agente novo que ninguem cadastrou nao le nada — e o erro diz isso.

2. **Camada nao permitida explicitamente -> DENIED.** Permissao e lista, nao
   ausencia de proibicao.

3. **Producao entrega somente CONFIRMED.** DRAFT e TO_VALIDATE existem para
   revisao humana; DEPRECATED nao entra em retrieval normal. So o Knowledge
   Manager e o console de revisao enxergam os outros status.

4. **Nenhum agente escreve Knowledge.** `can_write_knowledge` e False para
   todo mundo, sem excecao configuravel. Escrita futura entra pelo Ingestion
   Pipeline, que e outro caminho e outra autorizacao.

DE ONDE VEM A PERMISSAO
-----------------------

Da whitelist que ja existe: `agents/knowledge_policies.py`. Um agente enxerga
no Brain exatamente os documentos que ja enxerga hoje pelo caminho lexical —
nem um a mais. A F2 nao concede acesso novo a ninguem; se concedesse, seria
uma mudanca de seguranca escondida dentro de uma mudanca de arquitetura.

As camadas permitidas sao DERIVADAS dessa whitelist, nao declaradas a mao:
se o agente pode ler um documento L3, ele tem L3. Assim as duas listas nao
podem divergir.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from brain.models import PRODUCTION_STATUSES, REVIEW_STATUSES, DocStatus, Layer
from brain.taxonomy import layer_for

PiiScope = Literal["none", "pseudonymous", "full"]

#: Agentes que falam com a cliente. So eles podem revelar qualquer coisa, e
#: mesmo assim dentro do teto de `decide_disclosure`.
CUSTOMER_FACING_AGENTS: frozenset[str] = frozenset(
    {
        "community-dm-agent",
        "customer-support-agent",
        "sales-conversion-agent",
        "crm-lifecycle-agent",
    }
)

#: Quem pode CONSULTAR material pago (ENTITLEMENT_REQUIRED) para responder
#: corretamente. Consultar nao e entregar — ver brain/models.py.
#:
#: F2.7: `sales-conversion-agent` SAIU desta lista. Vender nao exige conhecer
#: a formula: o outline seguro (PRODUCT_OUTLINE_*, L3 PUBLIC) responde tudo
#: que uma conversa de venda precisa — o que o ebook cobre, quantas receitas,
#: quais categorias, quais bonus. Manter o acesso ao corpo integral so
#: aumentaria a superficie por onde conteudo pago pode sair, sem responder
#: nenhuma pergunta a mais. Least privilege de verdade custa uma linha.
CAN_KNOW_PAID_AGENTS: frozenset[str] = frozenset(
    {
        "customer-support-agent",
        "knowledge-manager",
    }
)

#: Documentos nativos do Brain — nao existem em `docs/`, entao a whitelist
#: herdada de `agents/knowledge_policies.py` nao fala deles.
#:
#: Esta e uma concessao EXPLICITA e por agente. Nao ha default: agente que nao
#: aparece aqui nao ve nenhum documento novo da F2.7, exatamente como antes.
#: Fail-closed continua valendo — a tabela concede, nunca abre.
BRAIN_NATIVE_GRANTS: dict[str, frozenset[str]] = {
    # Revisao humana e curadoria: ve tudo, inclusive o corpo integral.
    "knowledge-manager": frozenset(
        {
            "EBOOK_RECHEIOS",
            "EBOOK_CASQUINHAS",
            "EBOOK_LASCAS",
            "PRODUCT_OUTLINE_RECHEIOS",
            "PRODUCT_OUTLINE_CASQUINHAS",
            "PRODUCT_OUTLINE_LASCAS",
            "SITE_SNAPSHOT",
        }
    ),
    # Suporte: precisa do conteudo tecnico para diagnosticar de verdade
    # ("sua ganache separou por falha de emulsificacao"). O que ele pode
    # ENTREGAR e outra decisao, e mora no Disclosure Gate.
    "customer-support-agent": frozenset(
        {
            "EBOOK_RECHEIOS",
            "EBOOK_CASQUINHAS",
            "EBOOK_LASCAS",
            "PRODUCT_OUTLINE_RECHEIOS",
            "PRODUCT_OUTLINE_CASQUINHAS",
            "PRODUCT_OUTLINE_LASCAS",
            "SITE_SNAPSHOT",
        }
    ),
    # Venda, DM e funil: outline seguro e condicao comercial. Sem corpo pago.
    "sales-conversion-agent": frozenset(
        {"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS", "SITE_SNAPSHOT"}
    ),
    "community-dm-agent": frozenset(
        {"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}
    ),
    "offer-funnel-strategist": frozenset(
        {"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS", "SITE_SNAPSHOT"}
    ),
    "crm-lifecycle-agent": frozenset(
        {"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}
    ),
    # Conteudo: temas e resumos seguros. Nunca o corpo — transformar conteudo
    # pago em post publico e o vazamento mais facil de cometer sem perceber.
    "caption-writer": frozenset({"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}),
    "script-writer": frozenset({"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}),
    "hook-finder": frozenset({"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}),
    "social-media-manager": frozenset(
        {"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}
    ),
    "brand-architect": frozenset(
        {"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}
    ),
    "cmo": frozenset({"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}),
    "marketing-director": frozenset(
        {"PRODUCT_OUTLINE_RECHEIOS", "PRODUCT_OUTLINE_CASQUINHAS", "PRODUCT_OUTLINE_LASCAS"}
    ),
}

#: Camadas que os documentos nativos ocupam. Concedidas junto com as chaves —
#: sem isto o filtro de camada barraria o documento antes da whitelist.
_NATIVE_LAYERS: dict[str, str] = {
    "EBOOK_RECHEIOS": "L1",
    "EBOOK_CASQUINHAS": "L1",
    "EBOOK_LASCAS": "L1",
    "PRODUCT_OUTLINE_RECHEIOS": "L3",
    "PRODUCT_OUTLINE_CASQUINHAS": "L3",
    "PRODUCT_OUTLINE_LASCAS": "L3",
    "SITE_SNAPSHOT": "L3",
}


def native_grants(agent_id: str) -> frozenset[str]:
    """Documentos nativos do Brain concedidos a este agente. Vazio por default."""

    return BRAIN_NATIVE_GRANTS.get(agent_id, frozenset())

#: Principals que revisam conteudo nao aprovado. Nao sao agentes de negocio:
#: o console e uma interface humana.
REVIEW_PRINCIPALS: frozenset[str] = frozenset({"knowledge-manager", "judith-review-console"})

#: Quem pode propor melhoria para revisao humana (nunca aplicar).
CAN_PROPOSE_LEARNING: frozenset[str] = frozenset({"knowledge-manager", "ai-performance-evals-agent"})


class AccessDenied(Exception):
    """Acesso negado. A mensagem diz o motivo — silencio esconde bug."""


@dataclass(frozen=True)
class KnowledgeAccess:
    """O que um agente pode ver. Imutavel e inteiramente derivado."""

    agent_id: str
    layers: frozenset[Layer]
    topics: frozenset[str]
    """Vazio = sem restricao de topic dentro das camadas permitidas."""

    statuses: frozenset[DocStatus]
    external_keys: frozenset[str] | None
    """Whitelist de documentos, herdada de agents/knowledge_policies.py.

    `None` significa SEM restricao por documento — reservado ao console de
    revisao humana. Frozenset vazio significa "nenhum documento", que e o
    oposto; a distincao importa e por isso nao e um set vazio."""

    pii_scope: PiiScope
    can_write_memory: bool
    can_propose_learning: bool
    is_customer_facing: bool
    can_know_paid: bool

    #: Sempre False. Existe como campo para que a regra fique visivel no
    #: objeto, e nao apenas escondida na ausencia de um metodo.
    can_write_knowledge: bool = False

    def allows_layer(self, layer: str) -> bool:
        return layer in self.layers

    def allows_status(self, status: str) -> bool:
        return status in self.statuses

    def allows_topic(self, topics: list[str] | tuple[str, ...] | None) -> bool:
        if not self.topics:
            return True
        return bool(set(topics or ()) & self.topics)

    def allows_document(self, *, external_key: str | None, layer: str, status: str) -> bool:
        if not self.allows_layer(layer) or not self.allows_status(status):
            return False
        if self.external_keys is None:
            return True
        # Documento sem chave externa e conteudo novo (upload, futuro): a
        # whitelist herdada nao fala dele, entao vale a camada.
        if external_key is None:
            return True
        return external_key in self.external_keys


def _derive(agent_id: str) -> KnowledgeAccess:
    from agents.knowledge_policies import KNOWLEDGE_POLICIES

    politica = KNOWLEDGE_POLICIES.get(agent_id)
    if politica is None:
        raise AccessDenied(
            f'agente "{agent_id}" nao tem politica de Knowledge. '
            f"Acesso negado (fail-closed). Agentes conhecidos: {', '.join(sorted(KNOWLEDGE_POLICIES))}."
        )

    concedidos = native_grants(agent_id)
    chaves = frozenset(doc.key for doc in politica.documents) | concedidos
    camadas = frozenset(
        layer_for(key=doc.key, relative_path=doc.relative_path) for doc in politica.documents
    ) | frozenset(_NATIVE_LAYERS[chave] for chave in concedidos if chave in _NATIVE_LAYERS)

    revisor = agent_id in REVIEW_PRINCIPALS
    return KnowledgeAccess(
        agent_id=agent_id,
        layers=camadas,
        topics=frozenset(),
        statuses=REVIEW_STATUSES if revisor else PRODUCTION_STATUSES,
        external_keys=chaves,
        # Knowledge nao carrega dado de cliente na F2. O campo existe porque
        # a mesma politica vai reger Memory na F5, e mudar a forma do objeto
        # depois seria pior do que declarar o eixo agora.
        pii_scope="none",
        can_write_memory=False,
        can_propose_learning=agent_id in CAN_PROPOSE_LEARNING,
        is_customer_facing=agent_id in CUSTOMER_FACING_AGENTS,
        can_know_paid=agent_id in CAN_KNOW_PAID_AGENTS,
    )


@lru_cache(maxsize=64)
def _cached(agent_id: str) -> KnowledgeAccess:
    return _derive(agent_id)


def resolve_access(agent_id: str) -> KnowledgeAccess:
    """Politica do agente. Levanta `AccessDenied` se ele nao for conhecido."""

    normalizado = (agent_id or "").strip()
    if not normalizado:
        raise AccessDenied("agent_id vazio. Acesso negado (fail-closed).")

    if normalizado == "judith-review-console":
        # Console de revisao humana: enxerga todo status e toda camada, mas
        # continua sem poder escrever. Nao e um agente — nao roda LLM.
        return KnowledgeAccess(
            agent_id=normalizado,
            layers=frozenset({"L1", "L2", "L3"}),
            topics=frozenset(),
            statuses=REVIEW_STATUSES,
            external_keys=None,  # sem whitelist: revisao ve tudo
            pii_scope="none",
            can_write_memory=False,
            can_propose_learning=True,
            is_customer_facing=False,
            can_know_paid=True,
        )

    return _cached(normalizado)


def clear_cache() -> None:
    """Usado pelos testes que mexem no catalogo."""

    _cached.cache_clear()
