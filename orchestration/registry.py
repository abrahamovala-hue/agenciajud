"""
Agent Registry — resolve agent_id -> Agent.

Deliberadamente simples: um dict. Nao e um service locator (sem DI, sem
factories, sem lazy loading magico) - so precisamos localizar os 20 Agents
ja instanciados por id, de um lugar central, em vez de cada Workflow
importar cada agente manualmente.
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent

from agents.judith_team import (
    ai_performance_evals_agent,
    analytics_bi_agent,
    brand_architect,
    brand_reviewer,
    caption_writer,
    cmo,
    community_dm_agent,
    crm_lifecycle_agent,
    customer_insights_agent,
    customer_support_agent,
    hook_finder,
    knowledge_manager,
    market_trend_intelligence,
    marketing_director,
    offer_funnel_strategist,
    sales_conversion_agent,
    script_writer,
    social_media_manager,
    video_editor,
    visual_creative,
)
from agents.my_agent import my_agent

#: Os 20 agentes do time. `my_agent` fica FORA desta lista de proposito —
#: ver a nota de `_aplicar_politica_de_persistencia`.
_TEAM_AGENTS: list[Agent] = [
    cmo,
    brand_architect,
    marketing_director,
    social_media_manager,
    market_trend_intelligence,
    hook_finder,
    script_writer,
    caption_writer,
    visual_creative,
    video_editor,
    offer_funnel_strategist,
    sales_conversion_agent,
    crm_lifecycle_agent,
    community_dm_agent,
    customer_support_agent,
    analytics_bi_agent,
    customer_insights_agent,
    knowledge_manager,
    ai_performance_evals_agent,
    brand_reviewer,
]

_ALL_AGENTS: list[Agent] = [my_agent, *_TEAM_AGENTS]


# --- F4.1A: politica de persistencia de run ---------------------------------
#
# O QUE O AGNO GRAVA POR PADRAO, E POR QUE ISSO E UM PROBLEMA AQUI
#
# `agno_sessions.runs` guarda a run inteira em JSONB e reescreve o array todo a
# cada mensagem. Com os defaults do framework isso inclui as mensagens
# `role="tool"` — ou seja, o RESULTADO das buscas no Brain, com o corpo dos
# chunks. Para `customer-support-agent` e `knowledge-manager`, que podem
# conhecer material pago, isso significa CONTEUDO DE EBOOK PAGO gravado em
# texto puro, por run, sem prazo.
#
# Medido na F4.1: o resultado de uma tool responde por ~81% do peso de uma run
# (10.652 de 13.161 bytes).
#
# A F2.7 mantem o conteudo pago fora do Git; a F1 o mantem fora do
# `judith_execution_logs` por allowlist. O store de conversa do framework
# guardava assim mesmo, por default.
#
# POR QUE DESLIGAR NAO QUEBRA A PROVENANCE
#
# Auditado no Agno 2.6.4 (`agent/_run.py:cleanup_and_store`): o scrub roda
# sobre `copy.copy(run_response)` e REBINDA `messages`. O objeto vivo devolvido
# por `agent.run()` — que e o que `_extract_sources_opened` le — continua
# intacto. Isto e detalhe de implementacao, nao contrato publico, e por isso ha
# teste que pina esse comportamento e falha se um upgrade do Agno mudar.
#
# POR QUE `my_agent` FICA DE FORA
#
# Ele e o starter multimodal do template: tem `prepare_multimodal_input`, nao
# tem tools do Brain (logo nao alcanca conteudo pago) e nao esta no caminho da
# cliente — o webhook vai para o ANSWER_DM. Desligar midia nele mudaria em
# silencio o comportamento documentado do template sem resolver risco nenhum.
#
# O QUE ESTA POLITICA NAO E
#
# Nao e retencao. Ela reduz o que passa a ser gravado DAQUI PARA A FRENTE.
# Sessoes ja existentes continuam como estao — ver `LEAVE_UNTOUCHED_TEMPORARILY`
# em `RETENTION_TARGETS`.

#: Nao gravar resultado de tool na sessao. Continuidade nao depende disso:
#: `get_messages` reinjeta apenas user/assistant, e o system e remontado a cada
#: run a partir de `instructions`.
STORE_TOOL_MESSAGES = False

#: Nao gravar midia bruta. O canal transcreve audio ANTES do workflow
#: (`app/whatsapp/channel.py` -> `transcribe_audio`), entao o agente recebe
#: texto; e os post-hooks rodam antes do storage (`_run.py:1020` vs `:1095`),
#: entao nada que o processamento precise e removido cedo demais.
STORE_MEDIA = False


#: Marcador que substitui o resultado da tool. Curto e explicito: preserva o
#: fato de que houve resultado sem preservar o resultado.
RESULTADO_NAO_PERSISTIDO = "[nao persistido: politica de minimizacao F4.1A]"


def redigir_carga_de_tool(run_output: Any) -> None:
    """Post-hook: tira o corpo do resultado da tool do que sera gravado.

    POR QUE OS DOIS FLAGS NAO BASTAM
    --------------------------------

    `store_tool_messages=False` faz `scrub_tool_results_from_run_output`
    filtrar `run_output.messages`. Ele NAO toca em dois outros lugares onde o
    Agno guarda a mesma coisa:

        RunOutput.tools[].result   o payload inteiro da tool
        RunOutput.references       os trechos recuperados

    Medido num run real do `customer-support-agent`: depois do scrub, as
    mensagens estavam limpas e `tools[0].result` ainda carregava 6.757 bytes
    com o corpo dos chunks pagos. `references` idem.

    Sem isto, desligar os flags reduz o tamanho e NAO cumpre o objetivo, que e
    conteudo pago fora do store de conversa.

    O QUE ESTE HOOK NAO REMOVE
    --------------------------

    - `len(tools)`: `_step_usage` conta as chamadas para telemetria. A entrada
      continua existindo; so o `result` e substituido.
    - `tool_args`: e a query que o agente compos, nao o conteudo recuperado.
      Some com a politica de retencao, nao com esta.
    - a RESPOSTA do agente: ela e a conversa. Um agente de suporte pode
      legitimamente explicar um conceito tecnico que veio de material pago —
      o que ele pode dizer e decisao do Disclosure Gate, nao desta funcao.

    POR QUE POST-HOOK
    -----------------

    E o unico ponto que roda ANTES da gravacao (`_run.py:1020` vs `:1095`) e
    depois de o conteudo ja ter cumprido sua funcao no raciocinio. A
    provenance nao e afetada: `_extract_sources_opened` le
    `messages[role="tool"]`, que e outro lugar.
    """

    for chamada in getattr(run_output, "tools", None) or []:
        if isinstance(chamada, dict):
            if chamada.get("result"):
                chamada["result"] = RESULTADO_NAO_PERSISTIDO
        elif getattr(chamada, "result", None):
            chamada.result = RESULTADO_NAO_PERSISTIDO

    # Nada no projeto le `RunOutput.references`: o que alimenta o Evidence Gate
    # e `step_decision.references`, do output estruturado do agente.
    if getattr(run_output, "references", None):
        run_output.references = None


def _aplicar_politica_de_persistencia(agentes: list[Agent]) -> None:
    """Aplica a politica num lugar so, em vez de 20 arquivos divergentes."""

    for agente in agentes:
        agente.store_tool_messages = STORE_TOOL_MESSAGES
        agente.store_media = STORE_MEDIA

        # Os hooks sao normalizados uma vez, no primeiro run (`_hooks_normalised`).
        # Anexar aqui, no import, acontece antes disso.
        hooks = list(agente.post_hooks or [])
        if redigir_carga_de_tool not in hooks:
            hooks.append(redigir_carga_de_tool)
        agente.post_hooks = hooks


_aplicar_politica_de_persistencia(_TEAM_AGENTS)


#: ALVOS de retencao decididos pela Judith na F4.1. **Ainda nao ativados** —
#: registrados aqui para que a fase seguinte nao precise redescobri-los, e
#: porque um numero que mora so num relatorio nao sobrevive a proxima fase.
#:
#: O criterio e `updated_at`, NUNCA `created_at`: o que expira e conversa
#: parada, nao conversa antiga. A unidade de remocao e a SESSAO INTEIRA, nunca
#: run isolado — `get_messages` conta com a sequencia.
#:
#: 90 e 7 dias sao decisao de PRODUTO. Nao sao prazo exigido por lei; a
#: validacao juridica da retencao continua pendente.
RETENTION_TARGETS: dict[str, int] = {
    "customer_facing_days": 90,
    "internal_session_days": 7,
}

#: Estrategia para o que ja esta gravado. Nao executar purge retroativo nesta
#: fase: primeiro minimizar a persistencia nova e provar que nada quebrou.
HISTORICAL_DATA_STRATEGY = "LEAVE_UNTOUCHED_TEMPORARILY"

#: Apagamento a pedido da cliente. O caminho tecnico esta comprovado
#: (`get_sessions(user_id=...)` -> `delete_sessions(ids, user_id=...)`), mas
#: NAO ha endpoint e NAO ha execucao nesta fase.
#:
#: Decisao explicita pendente antes de implementar: `agno_traces`,
#: `agno_approvals` e `agno_learnings` carregam `session_id` e NAO tem foreign
#: key para `agno_sessions` — apagar a sessao deixa orfaos nas tres.
USER_REQUESTED_DELETION = "FUTURE_IMPLEMENTATION"


# Quality Control nao esta aqui de proposito: e validacao deterministica,
# nao um Agent do Agno (ver orchestration/quality_control.py e
# docs/JUDITH-AI-TEAM-V2/agents/21-quality-control-agent.md).

# `Agent.id` e Optional[str] na tipagem do Agno, mas todo agente deste
# projeto define um id explicitamente - o assert abaixo garante isso em
# tempo de import, em vez de falhar silenciosamente depois.
for _agent in _ALL_AGENTS:
    assert _agent.id, f"agente sem id definido: {_agent.name}"

AGENT_REGISTRY: dict[str, Agent] = {str(agent.id): agent for agent in _ALL_AGENTS}

assert len(AGENT_REGISTRY) == 21, f"esperava 21 ids unicos (jud + 20), achou {len(AGENT_REGISTRY)}"


class AgentNotFoundError(KeyError):
    """agent_id nao existe no registry."""


def get_agent(agent_id: str) -> Agent:
    """Resolve agent_id -> Agent. Lanca AgentNotFoundError com a lista de ids validos."""

    try:
        return AGENT_REGISTRY[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(AGENT_REGISTRY))
        raise AgentNotFoundError(f'agent_id "{agent_id}" nao existe no registry. IDs validos: {known}') from exc
