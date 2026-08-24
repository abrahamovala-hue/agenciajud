"""Os 3 primeiros Workflows Agno reais do Judith AI Business Team.

Cada modulo expoe uma funcao `run_<workflow>(...)` que constroi o
`agno.workflow.Workflow`, executa, e retorna (WorkflowRunOutput, ExecutionLog,
QualityControlResult). Nao ha estado global - cada chamada cria seu proprio
ExecutionLog e Workflow.
"""
