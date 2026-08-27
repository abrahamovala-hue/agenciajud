"""
WEEKLY_BUSINESS_REVIEW — fan-out para 5 especialistas em paralelo, CMO
sintetiza num relatorio executivo estruturado, fica pronto para Judith.

Analytics & BI \\
Customer Insights \\
Sales & Conversion  >-- (paralelo) --> CMO --> relatorio --> Judith
CRM & Lifecycle    /
Market & Trend Int./

Kiwify/Instagram/CRM reais NAO estao conectados. Todo dado usado aqui vem
de orchestration/fixtures/weekly_business_review_fixtures.py, explicitamente
marcado como TEST DATA na propria mensagem enviada a cada agente - nunca
apresentado como dado real.
"""

from __future__ import annotations

from agno.workflow import Parallel, Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from orchestration.execution_log import ExecutionLog
from orchestration.execution_repository import persist_execution
from orchestration.handoff import AgentStepDecision, WeeklyReportDecision
from orchestration.quality_control import QualityControlResult, WorkflowSpec, validate_workflow
from orchestration.step_helpers import run_agent_step

WORKFLOW_NAME = "WEEKLY_BUSINESS_REVIEW"

CONTRIBUTOR_AGENTS = [
    "analytics-bi-agent",
    "customer-insights-agent",
    "sales-conversion-agent",
    "crm-lifecycle-agent",
    "market-trend-intelligence",
]

QC_SPEC = WorkflowSpec(
    name=WORKFLOW_NAME,
    # Os 5 contribuidores rodam em Parallel — a ordem de conclusao entre eles
    # nao e deterministica, entao vao em `unordered`. So o CMO tem posicao
    # fixa (sintetiza depois de todos).
    required_agents_unordered=CONTRIBUTOR_AGENTS,
    required_agents_in_order=["cmo"],
    requires_brand_reviewer_approval=False,
    requires_human_approval=False,  # e um relatorio informativo, nao uma publicacao - Judith le, nao "aprova/rejeita" com gate HITL
    requires_references=False,  # test data explicita costuma nao ter "referencia" no sentido de doc de marca
)


def _build_workflow(log: ExecutionLog, task_id: str, fixtures: dict[str, str]) -> Workflow:
    def make_contributor_step(agent_id: str):
        def executor(step_input: StepInput) -> StepOutput:
            test_data = fixtures.get(agent_id, "[TEST DATA] Nenhum dado disponivel.")
            message = (
                f"Analise os dados abaixo (marcados como TEST DATA - dados de teste, "
                f"nao integrações reais conectadas ainda) e produza seu relatório/insight "
                f"da semana dentro do seu domínio:\n\n{test_data}\n\n"
                f"Se não houver dado suficiente, diga isso explicitamente em vez de estimar."
            )
            _h, d = run_agent_step(
                agent_id=agent_id,
                to_agent="cmo",
                workflow=WORKFLOW_NAME,
                task_id=task_id,
                objective="Contribuir para o Weekly Business Review",
                context="Fan-out paralelo do WEEKLY_BUSINESS_REVIEW",
                message=message,
                log=log,
            )
            return StepOutput(content=d, step_name=agent_id)

        return executor

    contributor_steps = [Step(name=agent_id, executor=make_contributor_step(agent_id)) for agent_id in CONTRIBUTOR_AGENTS]

    def synthesize_step(step_input: StepInput) -> StepOutput:
        # As saidas de um Parallel vem agrupadas sob a chave com o NOME DO
        # BLOCO ("contributors"), com cada step individual dentro de
        # `.steps` - nao sob o nome de cada step no nivel de cima.
        contributions: dict[str, AgentStepDecision] = {}
        parallel_output = (step_input.previous_step_outputs or {}).get("contributors")
        for step_output in getattr(parallel_output, "steps", None) or []:
            if step_output.step_name in CONTRIBUTOR_AGENTS:
                contributions[step_output.step_name] = step_output.content

        summary_lines = []
        for agent_id, decision in contributions.items():
            summary_lines.append(f"### {agent_id}\n{decision.output}")
        combined = "\n\n".join(summary_lines) if summary_lines else "Nenhuma contribuicao recebida."

        message = f"""\
Você é o CMO. Sintetize as contribuições abaixo (de 5 especialistas, dados \
de teste/TEST DATA) num relatório executivo semanal estruturado.

{combined}

OBRIGATÓRIO: preencha as listas `kpis`, `insights`, `alerts`, \
`opportunities` e `recommended_plan` do output_schema — não deixe nenhuma \
delas vazia se houver qualquer informação nas contribuições acima que \
justifique um item. Exemplos do que vai em cada uma:
- kpis: métricas concretas relatadas (ex.: "Alcance 12.400, +23% vs semana anterior")
- insights: o que os números/conversas revelam (ex.: "Conteúdo educativo supera institucional")
- alerts: o que precisa de atenção agora (ex.: "2 leads sem follow-up há 1 semana")
- opportunities: o que dá pra explorar (ex.: "Dúvida recorrente sobre temperagem vira série educativa")
- recommended_plan: ações concretas para a próxima semana

Use SOMENTE o que os especialistas relataram. Se um especialista disse "sem \
dados suficientes" para a área dele, não invente um KPI para aquela área — \
mas registre isso como um `alert` (ex.: "Sem dados de vendas esta semana")."""

        _h, d = run_agent_step(
            agent_id="cmo",
            to_agent="judith",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Sintetizar relatorio executivo semanal",
            context="Sintese pos-fan-out do WEEKLY_BUSINESS_REVIEW",
            message=message,
            log=log,
            decision_schema=WeeklyReportDecision,
        )
        log.outputs["weekly_report"] = d
        return StepOutput(content=d, step_name="synthesize")

    return Workflow(
        name=WORKFLOW_NAME,
        steps=[
            Parallel(*contributor_steps, name="contributors"),
            Step(name="synthesize", executor=synthesize_step),
        ],
    )


def run_weekly_business_review(
    *, fixtures: dict[str, str], task_id: str | None = None
) -> tuple[ExecutionLog, QualityControlResult]:
    """Executa o WEEKLY_BUSINESS_REVIEW. `fixtures` deve vir de
    orchestration/fixtures/weekly_business_review_fixtures.py (ou um dict
    vazio/parcial, para testar o caso "nenhuma fonte disponivel")."""

    log = ExecutionLog(workflow=WORKFLOW_NAME, task_id=task_id) if task_id else ExecutionLog(workflow=WORKFLOW_NAME)
    log.inputs["fixtures_used"] = list(fixtures.keys())

    from agno.run.base import RunStatus

    try:
        workflow = _build_workflow(log, log.task_id, fixtures)
        run_output = workflow.run(input="Gerar Weekly Business Review")

        if run_output.status == RunStatus.completed:
            report = log.outputs.get("weekly_report")
            log.finish(status="completed", result=report.decision if report else None)
        else:
            log.finish(status="failed", result=f"status inesperado: {run_output.status}")
    except Exception as exc:
        log.finish(status="failed", error=f"{type(exc).__name__}: {exc}")
        persist_execution(log)
        raise

    resultado = validate_workflow(log, QC_SPEC)
    persist_execution(log)
    return log, resultado
