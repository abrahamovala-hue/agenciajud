"""
Cutover controlado — quais agentes leem do Brain em vez do lexical.

    legacy lexical (docs/, congelado)   <-- todo agente, por padrao
    Brain (Postgres, governado)         <-- somente quem esta declarado

O CONTROLE E UMA VARIAVEL DE AMBIENTE, E ISSO E DELIBERADO
-----------------------------------------------------------

`BRAIN_NATIVE_AGENTS=knowledge-manager,customer-support-agent`

Reverter e apagar um nome e redeployar — sem rebuild, sem migration, sem
tocar em conteudo. Um cutover que so pode ser revertido por commit e um
cutover que, na pratica, ninguem reverte as tres da manha.

Vazio (o padrao) = ninguem. Nao ha lista embutida no codigo: se a variavel
sumir, o sistema volta ao comportamento anterior inteiro.

O QUE MUDA PARA O AGENTE PROMOVIDO
----------------------------------

As duas tools continuam com o MESMO nome e a mesma forma de resposta —
`listar_fontes_disponiveis` e `ler_documento`. O que muda e de onde vem o
conteudo e o que vem junto: provenance completo, camada, status, versao,
quem aprovou, e a policy de divulgacao daquele trecho.

O que NAO muda: a whitelist. Um agente promovido ve no Brain exatamente os
documentos que a politica dele ja concedia, mais as concessoes nativas
explicitas de `BRAIN_NATIVE_GRANTS`. Cutover e troca de caminho, nao de
permissao.

PRODUCAO SO ENTREGA CONFIRMED
-----------------------------

Um agente promovido antes de haver documento aprovado enxergaria vazio. Por
isso o cutover vem DEPOIS das aprovacoes, e nesta ordem: quem revisa primeiro
(Knowledge Manager), quem atende depois (Customer Support), e so entao venda
e comunidade.
"""

from __future__ import annotations

import json
from os import getenv
from typing import Any

ENV_VAR = "BRAIN_NATIVE_AGENTS"

# --- CONTRATO COM O EVIDENCE RUNTIME ----------------------------------------
#
# Estes nomes nao sao decorativos: `orchestration/step_helpers.py` usa a lista
# de CONSULTA para saber quais tool calls contam como "abriu uma fonte". O que
# nao estiver la vira consulta invisivel — e o Evidence Gate acusa o agente de
# citar fonte que nao abriu, rejeitando uma resposta correta.
#
# Foi exatamente o que aconteceu: o cutover renomeou `ler_documento` para
# `buscar_conhecimento` e o extrator ficou para tras. A resposta de preco da
# Judith foi bloqueada por citacao "fabricada" que era legitima.
#
# Declarar aqui, na origem, permite que um teste de contrato falhe se alguem
# adicionar ou renomear uma tool sem avisar o outro lado.

#: Tools que DEVOLVEM conhecimento. Contam como fonte aberta.
CONSULTATION_TOOL_NAMES: frozenset[str] = frozenset({"buscar_conhecimento"})

#: Tools que so declaram o que existe. Listar NAO e consultar — a regra e
#: anterior ao cutover e continua valendo.
LISTING_TOOL_NAMES: frozenset[str] = frozenset({"listar_fontes_disponiveis"})

#: Tudo que `build_brain_tools_for` registra. O teste de contrato compara.
BRAIN_TOOL_NAMES: frozenset[str] = CONSULTATION_TOOL_NAMES | LISTING_TOOL_NAMES

#: A ordem recomendada. Nao e aplicada automaticamente — serve para o
#: relatorio e para o teste que garante que ninguem pulou etapa.
RECOMMENDED_ORDER: tuple[str, ...] = (
    "knowledge-manager",
    "customer-support-agent",
    "sales-conversion-agent",
    "community-dm-agent",
)


def brain_native_agents() -> frozenset[str]:
    """Quem le do Brain. Vazio = ninguem, e esse e o default."""

    declarado = (getenv(ENV_VAR) or "").strip()
    if not declarado:
        return frozenset()
    return frozenset(nome.strip() for nome in declarado.split(",") if nome.strip())


def is_brain_native(agent_id: str) -> bool:
    return agent_id in brain_native_agents()


def cutover_report() -> dict[str, Any]:
    """Estado do cutover, para o log de boot."""

    ativos = brain_native_agents()
    fora_de_ordem = [
        nome
        for indice, nome in enumerate(RECOMMENDED_ORDER)
        if nome not in ativos and any(posterior in ativos for posterior in RECOMMENDED_ORDER[indice + 1 :])
    ]
    return {
        "brain_native": sorted(ativos),
        "total": len(ativos),
        "origem": "env" if getenv(ENV_VAR) else "default",
        "pulados_na_ordem_recomendada": fora_de_ordem,
    }


def _payload(dados: dict[str, Any]) -> str:
    """Serializa o retorno de uma tool. JSON, sempre.

    POR QUE ISTO EXISTE
    -------------------

    O Agno guarda o retorno de uma tool em `Message.content` sem converter:
    `create_function_call_result(...)` faz `content=output`. Quando a funcao
    devolve um `dict`, o que chega ao historico e a REPRESENTACAO PYTHON dele
    — aspas simples, `None` no lugar de `null`:

        {'status': 'OK', 'resultados': [{'fonte': 'PRODUCTS', ...

    Isso nao e JSON. `_sources_in_tool_result` chama `json.loads` e recebe
    `JSONDecodeError`, entao devolve lista vazia. `sources_opened` fica vazio,
    o agente cita as fontes que leu (o modelo entende o repr sem problema), e o
    Evidence Gate conclui — corretamente, dado o que enxerga — que a citacao
    foi inventada. Resposta certa, rejeitada.

    As tools nativas do Agno sao tipadas `-> str` e serializam elas mesmas. E
    o contrato implicito, e estas passam a cumpri-lo.

    `ensure_ascii=False` para o modelo ler "preço" e nao "pre\\u00e7o".
    `default=str` para que um datetime em provenance nao derrube a tool.
    """

    return json.dumps(dados, ensure_ascii=False, default=str)


def build_brain_retriever_for(agent_id: str) -> Any:
    """`search_knowledge_base` do Agno, servido pelo Brain.

    Mesma assinatura que o Agno espera (`agno/agent/_default_tools.py`):
    `(query, num_documents=None, **kwargs) -> list[dict|str]`.

    Devolve lista vazia em falha em vez de levantar: o Agno chama isto dentro
    do loop de tool, e uma excecao ali vira erro na conversa da cliente.
    """

    def retriever(query: str, num_documents: int | None = None, **_kwargs: Any) -> list[Any]:
        from brain.bootstrap import get_knowledge_repository
        from brain.query_context import enrich
        from brain.retrieval import search

        consulta, _ = enrich(query)
        try:
            resultado = search(
                agent_id=agent_id,
                query=consulta,
                repository=get_knowledge_repository(),
                limit=num_documents or 4,
            )
        except Exception:  # noqa: BLE001
            return []
        return list(resultado.as_documents())

    return retriever


def build_brain_tools_for(agent_id: str) -> list[Any]:
    """As mesmas duas tools, servidas pelo Brain.

    Assinatura e nomes identicos aos do caminho lexical de proposito: trocar
    o caminho nao pode exigir reescrever a instrucao do agente.
    """

    from agno.tools import tool

    from agents.knowledge_policies import get_policy
    from brain.access_policy import resolve_access

    policy = get_policy(agent_id)
    acesso = resolve_access(agent_id)
    chaves = ", ".join(sorted(acesso.external_keys or ()))

    def _repositorio() -> Any:
        from brain.bootstrap import get_knowledge_repository

        return get_knowledge_repository()

    def listar_fontes_disponiveis() -> str:
        from brain.retrieval import search

        try:
            repositorio = _repositorio()
            linhas = repositorio.chunks_for_search(statuses=acesso.statuses, layers=acesso.layers)
        except Exception as erro:  # noqa: BLE001
            return _payload(
                {"status": "BRAIN_INDISPONIVEL", "detalhe": f"{type(erro).__name__}", "documentos_disponiveis": []}
            )

        vistos: dict[str, dict[str, Any]] = {}
        for linha in linhas:
            chave = str(linha.get("external_key") or linha.get("document_id"))
            if not acesso.allows_document(
                external_key=linha.get("external_key"),
                layer=str(linha.get("layer")),
                status=str(linha.get("status")),
            ):
                continue
            vistos.setdefault(
                chave,
                {
                    "fonte": chave,
                    "titulo": linha.get("title"),
                    "camada": linha.get("layer"),
                    "status": linha.get("status"),
                    "autoridade": linha.get("source_authority"),
                    "aprovado_por": linha.get("approved_by"),
                },
            )
        del search  # a listagem nao busca; so declara o que existe
        return _payload(
            {
                "documentos_disponiveis": sorted(vistos.values(), key=lambda d: str(d["fonte"])),
                # `ask_agent` e o campo real de MissingSource. A versao anterior
                # usava `.owner`, que nao existe: a tool levantava AttributeError
                # e o agente recebia a mensagem de erro no lugar da lista.
                "fontes_ausentes": [
                    {"fonte": m.key, "responsavel": m.ask_agent, "motivo": m.reason}
                    for m in policy.missing_sources
                ],
            }
        )

    def buscar_conhecimento(pergunta: str) -> str:
        from brain.query_context import enrich
        from brain.retrieval import search

        # J2: "entao so os ingredientes" nao tem termo proprio para casar com
        # documento nenhum. Costura o turno anterior da cliente antes de
        # buscar — so quando a pergunta e eliptica.
        consulta, contextualizada = enrich(pergunta)

        try:
            resultado = search(agent_id=agent_id, query=consulta, repository=_repositorio(), limit=4)
        except Exception as erro:  # noqa: BLE001
            return _payload({"status": "BRAIN_INDISPONIVEL", "detalhe": f"{type(erro).__name__}", "resultados": []})

        if not resultado.hits:
            return _payload(
                {
                    "status": "NENHUM_RESULTADO",
                    "resultados": [],
                    "contexto_adicionado": contextualizada,
                    "bloqueados_pela_politica": resultado.filtered_out,
                }
            )
        return _payload(
            {
                "status": "OK",
                "contexto_adicionado": contextualizada,
                "resultados": resultado.as_documents(),
            }
        )

    listar_fontes_disponiveis.__doc__ = (
        "Lista as fontes que voce pode consultar, com camada, status e quem aprovou, "
        "e as que NAO existem — com o responsavel por cada lacuna.\n\n"
        "Listar NAO e consultar: para citar evidencia, busque."
    )
    buscar_conhecimento.__doc__ = (
        "Busca no conhecimento governado e devolve trechos com procedencia completa "
        "(fonte, camada, versao, quem aprovou) e a politica do que pode ser dito.\n\n"
        f"Fontes que voce alcanca: {chaves}."
    )

    return [
        tool(name="listar_fontes_disponiveis")(listar_fontes_disponiveis),
        tool(name="buscar_conhecimento")(buscar_conhecimento),
    ]
