"""
Step helpers — chama um Agent do registry dentro de um Workflow e produz
um AgentHandoff real (nao texto livre), gravando no ExecutionLog.

Isto e o unico lugar que sabe como transformar "chamar um Agent" em
"AgentHandoff estruturado". Os Workflows (orchestration/workflows/*) nunca
chamam agent.run() diretamente - sempre passam por aqui.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar, overload

from orchestration.execution_log import ExecutionLog
from orchestration.handoff import AgentHandoff, AgentStepDecision
from orchestration.registry import get_agent

DecisionT = TypeVar("DecisionT", bound=AgentStepDecision)

# Tools que contam como CONSULTAR uma fonte. `listar_fontes_*` fica de fora
# de proposito: listar o catalogo nao e ler documento, e essa distincao e
# justamente o que o Quality Control precisa conseguir verificar.
_CONSULT_TOOLS = {"ler_documento", "ler_documento_de_marca", "search_knowledge_base"}


def _extract_sources_opened(response: Any) -> list[str]:
    """Le o registro de execucao e devolve as fontes que o agente abriu de fato.

    Duas origens, ambas do runtime (nunca do texto do LLM - e por isso que
    isto serve como contraprova de uma citacao inventada):

    1. `ler_documento(fonte=...)` -> a chave pedida.
    2. Resultado de `search_knowledge_base` -> as chaves que a busca de fato
       devolveu. Verificado no runtime: a mensagem de role="tool" traz o JSON
       com os campos `fonte`. Ler a query nao bastaria - o que importa e qual
       documento voltou, nao o que o agente procurou.
    """

    opened: list[str] = []
    for message in getattr(response, "messages", None) or []:
        for call in getattr(message, "tool_calls", None) or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") or {}
            if function.get("name") not in _CONSULT_TOOLS:
                continue
            fonte = _arg(function.get("arguments") or "", "fonte")
            if fonte:
                opened.append(fonte.strip().upper())

        if getattr(message, "role", None) == "tool" and getattr(message, "tool_name", None) in _CONSULT_TOOLS:
            opened.extend(_sources_in_tool_result(message.content))

    # dedup preservando ordem
    return list(dict.fromkeys(opened))


def _sources_in_tool_result(content: Any) -> list[str]:
    """Extrai as chaves `fonte` do resultado de uma tool de consulta.

    Uma fonte marcada FONTE_NAO_DISPONIVEL e ignorada de proposito: a busca
    devolveu a lacuna, nao o documento - nada foi consultado ali.
    """

    try:
        payload = json.loads(content) if isinstance(content, str) else content
    except (json.JSONDecodeError, TypeError):
        return []

    entries = payload if isinstance(payload, list) else [payload]
    return [
        str(entry["fonte"]).strip().upper()
        for entry in entries
        if isinstance(entry, dict) and entry.get("fonte") and entry.get("status") != "FONTE_NAO_DISPONIVEL"
    ]


def _arg(raw: Any, key: str) -> str:
    """Extrai um argumento de tool call, que o Agno entrega como dict ou JSON."""

    if isinstance(raw, dict):
        return str(raw.get(key, ""))
    try:
        return str(json.loads(raw).get(key, ""))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return ""


# Overloads para o mypy inferir o tipo de retorno tanto com quanto sem
# `decision_schema` explicito (sem eles, o default do TypeVar nao e inferido
# e todo call site precisaria de anotacao manual).
@overload
def run_agent_step(
    *,
    agent_id: str,
    to_agent: str,
    workflow: str,
    task_id: str,
    objective: str,
    context: str,
    message: str,
    log: ExecutionLog,
    session_id: str | None = None,
    user_id: str | None = None,
) -> tuple[AgentHandoff, AgentStepDecision]: ...


@overload
def run_agent_step(
    *,
    agent_id: str,
    to_agent: str,
    workflow: str,
    task_id: str,
    objective: str,
    context: str,
    message: str,
    log: ExecutionLog,
    decision_schema: type[DecisionT],
    session_id: str | None = None,
    user_id: str | None = None,
) -> tuple[AgentHandoff, DecisionT]: ...


def run_agent_step(
    *,
    agent_id: str,
    to_agent: str,
    workflow: str,
    task_id: str,
    objective: str,
    context: str,
    message: str,
    log: ExecutionLog,
    decision_schema: type[AgentStepDecision] = AgentStepDecision,
    session_id: str | None = None,
    user_id: str | None = None,
) -> tuple[AgentHandoff, AgentStepDecision]:
    """Executa um agente com output_schema estruturado e registra o handoff.

    Retorna (handoff, decision) - `decision` e a instancia tipada completa
    (util quando decision_schema tem campos extras, como RoutingDecision.route_to
    ou WeeklyReportDecision.kpis, que o AgentHandoff generico nao carrega).
    """

    agent = get_agent(agent_id)
    # session_id/user_id so viajam quando o chamador os fornece (canal
    # WhatsApp). Execucao local/teste continua sem sessao, como antes.
    run_kwargs: dict[str, Any] = {}
    if session_id:
        run_kwargs["session_id"] = session_id
    if user_id:
        run_kwargs["user_id"] = user_id

    response = agent.run(message, output_schema=decision_schema, **run_kwargs)

    decision = response.content
    if not isinstance(decision, decision_schema):
        raise TypeError(
            f'agente "{agent_id}" nao retornou {decision_schema.__name__} valido '
            f"(recebido: {type(decision).__name__}). Isso indica falha do output_schema, "
            "nao deveria acontecer em uso normal."
        )

    handoff = AgentHandoff.from_step_decision(
        from_agent=agent_id,
        to_agent=to_agent,
        workflow=workflow,
        task_id=task_id,
        objective=objective,
        context=context,
        step_decision=decision,
        sources_opened=_extract_sources_opened(response),
    )
    log.record(handoff)
    return handoff, decision
