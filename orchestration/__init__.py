"""
Orchestration layer — colaboração real entre os 20 Agents V2.

Implementa, em código, o que antes só existia como documentação em
docs/JUDITH-AI-TEAM-V2/ (AGENT_COLLABORATION_PROTOCOL_V2.md e
AGENT_HANDOFF_CONTRACT.md):

- handoff.py        -> modelo AgentHandoff (Pydantic, tipado)
- registry.py       -> AGENT_REGISTRY (agent_id -> Agent)
- execution_log.py  -> ExecutionLog (rastro completo de uma execucao)
- quality_control.py -> validacao deterministica (sem LLM)
- step_helpers.py   -> chama um Agent dentro de um Workflow e produz AgentHandoff
- workflows/        -> os 3 Workflows Agno reais (ANSWER_DM, CREATE_REEL,
                        WEEKLY_BUSINESS_REVIEW)
- fixtures/          -> dados de teste explicitamente marcados como TEST DATA
"""
