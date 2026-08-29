"""
Step helpers — chama um Agent do registry dentro de um Workflow e produz
um AgentHandoff real (nao texto livre), gravando no ExecutionLog.

Isto e o unico lugar que sabe como transformar "chamar um Agent" em
"AgentHandoff estruturado". Os Workflows (orchestration/workflows/*) nunca
chamam agent.run() diretamente - sempre passam por aqui.
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, TypeVar, overload

from orchestration.execution_log import ExecutionLog, StepUsage
from orchestration.handoff import AgentHandoff, AgentStepDecision
from orchestration.registry import get_agent

DecisionT = TypeVar("DecisionT", bound=AgentStepDecision)

# Tools que contam como CONSULTAR uma fonte. `listar_fontes_*` fica de fora
# de proposito: listar o catalogo nao e ler documento, e essa distincao e
# justamente o que o Quality Control precisa conseguir verificar.
def _brain_consultation_tools() -> frozenset[str]:
    """Nomes declarados por `brain/cutover.py` como tools de CONSULTA.

    Importado assim, e nao copiado, porque copiar foi o bug: o cutover
    renomeou a tool e esta lista ficou para tras, tornando invisivel toda
    consulta feita pelo nome novo. Import direto no topo criaria ciclo
    (`cutover` -> `knowledge_policies` -> ...), entao a leitura e tardia.
    """

    try:
        from brain.cutover import CONSULTATION_TOOL_NAMES

        return CONSULTATION_TOOL_NAMES
    except Exception:  # noqa: BLE001 - sem Brain, so o caminho legado existe
        return frozenset()


#: Tools cujo resultado conta como "fonte aberta" para o Evidence Gate.
#:
#: As tres primeiras sao o caminho lexical legado. As do Brain vem do contrato
#: declarado em `brain/cutover.py` — ha teste garantindo que os dois lados nao
#: divirjam de novo.
_CONSULT_TOOLS = {"ler_documento", "ler_documento_de_marca", "search_knowledge_base"} | set(
    _brain_consultation_tools()
)


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


#: Chaves onde uma tool pode aninhar a lista de trechos encontrados.
#:
#: `search_knowledge_base` devolve a lista crua; `buscar_conhecimento` embrulha
#: em `{"status": ..., "resultados": [...]}`. Procurar so no topo fazia as
#: fontes do Brain sumirem — e o Evidence Gate tratava a citacao legitima como
#: inventada.
#:
#: `documentos_disponiveis` NAO entra aqui de proposito: e o retorno de
#: `listar_fontes_disponiveis`, e listar nunca foi consultar.
_NESTED_RESULT_KEYS = ("resultados", "results")


def _sources_in_tool_result(content: Any) -> list[str]:
    """Extrai as chaves `fonte` do resultado de uma tool de consulta.

    Aceita as duas formas em uso — lista crua e envelope com `resultados` —
    e nunca desce ate o corpo do trecho: le so o campo de procedencia.

    Uma fonte marcada FONTE_NAO_DISPONIVEL e ignorada de proposito: a busca
    devolveu a lacuna, nao o documento - nada foi consultado ali.
    """

    try:
        payload = json.loads(content) if isinstance(content, str) else content
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(payload, dict):
        for chave in _NESTED_RESULT_KEYS:
            aninhado = payload.get(chave)
            if isinstance(aninhado, list):
                entries: list[Any] = aninhado
                break
        else:
            entries = [payload]
    elif isinstance(payload, list):
        entries = payload
    else:
        return []

    return [
        str(entry["fonte"]).strip().upper()
        for entry in entries
        if isinstance(entry, dict) and entry.get("fonte") and entry.get("status") != "FONTE_NAO_DISPONIVEL"
    ]


def _extract_consult_tools(response: Any) -> list[str]:
    """Quais tools de consulta o agente de fato chamou.

    Existe para observabilidade: sem isto, "o Brain foi consultado?" so era
    respondivel reconstruindo o comportamento por inferencia.
    """

    usadas: list[str] = []
    for message in getattr(response, "messages", None) or []:
        nome = getattr(message, "tool_name", None)
        if getattr(message, "role", None) == "tool" and nome in _CONSULT_TOOLS:
            usadas.append(str(nome))
    return list(dict.fromkeys(usadas))


def _texto(valor: Any) -> str | None:
    """So deixa passar string de verdade.

    Existe porque `response` vem de fora: provider novo, dublê de teste ou
    resposta parcial podem colocar qualquer coisa nesses campos, e um valor
    inesperado nao pode virar erro de validacao no meio de um atendimento.
    """

    return valor if isinstance(valor, str) else None


def _inteiro(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _step_usage(
    *,
    agent: Any,
    agent_id: str,
    to_agent: str,
    response: Any,
    duration_ms: int,
    error: str | None = None,
) -> StepUsage:
    """Le custo e latencia do `RunOutput` do Agno.

    REGRA DESTA FUNCAO: ela nunca levanta. Metrica e observabilidade — se a
    leitura falhar, o certo e perder a metrica, nunca a execucao que ja
    produziu resposta para a cliente. Por isso todo campo passa por coercao
    de tipo e o corpo inteiro tem rede de seguranca.
    """

    minimo = StepUsage(agent_id=agent_id, to_agent=to_agent, duration_ms=duration_ms, error=error)
    try:
        modelo = getattr(agent, "model", None)
        metrics = getattr(response, "metrics", None)

        def numero(nome: str) -> int | None:
            return _inteiro(getattr(metrics, nome, None))

        ferramentas = getattr(response, "tools", None)
        duracao_modelo = getattr(metrics, "duration", None)
        duracao = (
            int(duracao_modelo * 1000)
            if isinstance(duracao_modelo, (int, float)) and not isinstance(duracao_modelo, bool)
            else duration_ms
        )

        return StepUsage(
            agent_id=agent_id,
            to_agent=to_agent,
            model_id=_texto(getattr(response, "model", None)) or _texto(getattr(modelo, "id", None)),
            model_provider=(
                _texto(getattr(response, "model_provider", None)) or _texto(getattr(modelo, "provider", None))
            ),
            # Nao vem do RunOutput: e configuracao do Agent, e e justamente o
            # que precisamos saber para comparar tiers depois.
            reasoning_effort=_texto(getattr(modelo, "reasoning_effort", None)),
            input_tokens=numero("input_tokens"),
            output_tokens=numero("output_tokens"),
            reasoning_tokens=numero("reasoning_tokens"),
            cached_tokens=numero("cache_read_tokens"),
            total_tokens=numero("total_tokens"),
            tool_calls=len(ferramentas) if isinstance(ferramentas, (list, tuple)) else 0,
            duration_ms=duracao,
            error=error,
        )
    except Exception:  # noqa: BLE001
        return minimo


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

    inicio = perf_counter()
    try:
        response = agent.run(message, output_schema=decision_schema, **run_kwargs)
    except Exception as exc:
        # A chamada falhou: registra o custo/latencia do que houve e deixa o
        # erro subir. Quem decide o que fazer com a falha e o workflow — aqui
        # so garantimos que ela nao suma do rastro.
        log.record_usage(
            _step_usage(
                agent=agent,
                agent_id=agent_id,
                to_agent=to_agent,
                response=None,
                duration_ms=int((perf_counter() - inicio) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )
        )
        raise

    log.record_usage(
        _step_usage(
            agent=agent,
            agent_id=agent_id,
            to_agent=to_agent,
            response=response,
            duration_ms=int((perf_counter() - inicio) * 1000),
        )
    )

    # Observabilidade: QUAIS tools de consulta o agente chamou. So nomes.
    # Sem isto, "o Brain foi consultado?" so era respondivel por inferencia —
    # foi o que tornou o bug do Evidence Gate tao caro de encontrar.
    usadas = _extract_consult_tools(response)
    if usadas:
        anteriores = log.outputs.setdefault("brain_tools_called", [])
        anteriores.extend(t for t in usadas if t not in anteriores)

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
