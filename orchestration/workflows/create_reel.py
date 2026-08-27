"""
CREATE_REEL — brief -> pipeline de criacao -> Quality Control -> HUMAN
APPROVAL REQUIRED.

CMO (gate, pode rejeitar brief incompleto)
  -> Brand Architect -> Market & Trend Intelligence -> Hook Finder
  -> Script Writer -> Caption Writer -> Visual Creative -> Video Editor
  -> Brand Reviewer (pode rejeitar)
  -> Quality Control determinístico (pode interromper - StepOutput(stop=True))
  -> HUMAN APPROVAL REQUIRED (Step com human_review nativo do Agno - o
     workflow literalmente PAUSA aqui, nao ha como completar sem revisao)

IMPORTANTE:
- Nenhum conteudo e publicado. A etapa final so PREPARA a revisao de Judith
  - nunca marca nada como "publicado".
- O Video Editor produz sua decisao/briefing (texto estruturado). NAO
  chamamos o motor Remotion real (services/video-editor/) - essa integracao
  nao existe ainda e nao foi forcada aqui.
"""

from __future__ import annotations

from agno.run.base import RunStatus
from agno.workflow import Step, Workflow
from agno.workflow.types import HumanReview, StepInput, StepOutput

from orchestration.execution_log import ExecutionLog
from orchestration.execution_repository import persist_execution
from typing import cast

from orchestration.handoff import AgentStepDecision, ReviewDecision
from orchestration.quality_control import QualityControlResult, WorkflowSpec, validate_workflow
from orchestration.step_helpers import run_agent_step

WORKFLOW_NAME = "CREATE_REEL"

PIPELINE_AGENTS = [
    "brand-architect",
    "market-trend-intelligence",
    "hook-finder",
    "script-writer",
    "caption-writer",
    "visual-creative",
    "video-editor",
    "brand-reviewer",
]

# Usado pelo Quality Control DENTRO do workflow (roda ANTES da etapa de
# aprovacao humana - nesse ponto ainda nao faz sentido cobrar
# requires_human_approval, porque essa e literalmente a proxima etapa).
# Todos os 9 tem whitelist de Knowledge com documento vinculante (marca,
# pilar, preco, identidade visual), entao todos devem abrir fonte antes de
# decidir. Isso so passou a ser exigivel depois de
# `agents/knowledge_policies.py` - antes nao havia o que consultar.
AGENTS_REQUIRING_EVIDENCE = ["cmo", *PIPELINE_AGENTS]

# O Quality Control cobra consulta real de todas as etapas acima, entao o
# prompt precisa pedir isso explicitamente. Sem esta linha os agentes
# criativos produzem direto do contexto do handoff anterior e o QC barra o
# workflow - foi exatamente o que aconteceu com hook-finder e caption-writer
# na primeira execucao apos a exigencia ser reativada.
CONSULTAR = (
    "\n\nAntes de produzir, abra as fontes da sua whitelist que sustentam esta "
    "etapa (no minimo tom e pilar; some OFFERS/PRODUCTS se citar preco, link ou "
    "produto). Cite em `references` apenas o que abriu, com a confiabilidade de "
    "cada uma. Se nao abrir nada, escreva 'nenhuma fonte consultada'."
)

QC_SPEC_PRE_APPROVAL = WorkflowSpec(
    name=WORKFLOW_NAME,
    required_agents_in_order=["cmo", *PIPELINE_AGENTS],
    requires_brand_reviewer_approval=True,
    requires_human_approval=False,
    requires_references=True,
    agents_requiring_evidence=AGENTS_REQUIRING_EVIDENCE,
    forbidden_direct_edges=[("script-writer", "judith"), ("hook-finder", "judith")],
)

# Usado por run_create_reel no final, sobre o log JA completo (inclui a
# checagem de que a aprovacao humana foi corretamente requerida/atingida).
QC_SPEC_FULL = WorkflowSpec(
    name=WORKFLOW_NAME,
    required_agents_in_order=["cmo", *PIPELINE_AGENTS],
    requires_brand_reviewer_approval=True,
    requires_human_approval=True,
    requires_references=True,
    agents_requiring_evidence=AGENTS_REQUIRING_EVIDENCE,
    forbidden_direct_edges=[("script-writer", "judith"), ("hook-finder", "judith")],
)


def _cmo_gate(log: ExecutionLog, task_id: str, tema: str, objetivo: str) -> ReviewDecision:
    """Etapa 1, fora do Workflow Agno: pode encerrar tudo cedo se o brief
    estiver incompleto (nao ha por que montar o pipeline inteiro so pra
    descobrir isso depois)."""

    message = f"""\
Tema: {tema}
Objetivo: {objetivo}

Aprova este objetivo para o workflow CREATE_REEL? Preencha approved=true \
APENAS se tema e objetivo forem específicos o suficiente para o time \
trabalhar (produto/oferta claro, direção clara). Se faltar informação \
essencial (ex.: objetivo vago tipo "vender mais", sem produto/ângulo \
definido), approved=false e explique exatamente o que falta em `risks`."""

    _handoff, decision = run_agent_step(
        agent_id="cmo",
        to_agent="brand-architect",
        workflow=WORKFLOW_NAME,
        task_id=task_id,
        objective="Aprovar objetivo do reel antes de iniciar producao",
        context=f"Tema: {tema} | Objetivo: {objetivo}",
        message=message,
        log=log,
        decision_schema=ReviewDecision,
    )
    log.outputs["cmo_approved"] = decision.approved
    return decision


def _build_pipeline(log: ExecutionLog, task_id: str, tema: str, objetivo: str) -> Workflow:
    def brand_architect_step(step_input: StepInput) -> StepOutput:
        _h, d = run_agent_step(
            agent_id="brand-architect",
            to_agent="market-trend-intelligence",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Definir estrategia de brand para o reel",
            context=f"Tema: {tema} | Objetivo: {objetivo}",
            message=f"Defina a estrategia (angulo, tom, pilar, mensagem central) para um reel sobre: {tema}. Objetivo: {objetivo}." + CONSULTAR,
            log=log,
        )
        return StepOutput(content=d, step_name="brand_architect")

    def trend_step(step_input: StepInput) -> StepOutput:
        strategy = cast(AgentStepDecision, step_input.previous_step_content)
        _h, d = run_agent_step(
            agent_id="market-trend-intelligence",
            to_agent="hook-finder",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Contextualizar com tendencias reais",
            context=f"Estrategia definida: {strategy.decision}",
            message=f"Pesquise contexto/tendencias relevantes para um reel sobre: {tema}. Estrategia: {strategy.output}" + CONSULTAR,
            log=log,
        )
        return StepOutput(content=d, step_name="trend")

    def hook_step(step_input: StepInput) -> StepOutput:
        trend = cast(AgentStepDecision, step_input.previous_step_content)
        _h, d = run_agent_step(
            agent_id="hook-finder",
            to_agent="script-writer",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Gerar hooks para o reel",
            context=f"Contexto de tendencia: {trend.decision}",
            message=f"Gere 3 hooks para um reel sobre: {tema}. Contexto: {trend.output}" + CONSULTAR,
            log=log,
        )
        return StepOutput(content=d, step_name="hook")

    def script_step(step_input: StepInput) -> StepOutput:
        hooks = cast(AgentStepDecision, step_input.previous_step_content)
        _h, d = run_agent_step(
            agent_id="script-writer",
            to_agent="caption-writer",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Escrever roteiro a partir do hook vencedor",
            context=f"Hooks gerados: {hooks.decision}",
            message=f"Escreva um roteiro de 30-45s para: {tema}. Objetivo: {objetivo}. Hooks disponiveis: {hooks.output}" + CONSULTAR,
            log=log,
        )
        return StepOutput(content=d, step_name="script")

    def caption_step(step_input: StepInput) -> StepOutput:
        script = cast(AgentStepDecision, step_input.previous_step_content)
        _h, d = run_agent_step(
            agent_id="caption-writer",
            to_agent="visual-creative",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Escrever legenda a partir do roteiro",
            context=f"Roteiro: {script.decision}",
            message=f"Escreva a legenda para este reel. Roteiro: {script.output}" + CONSULTAR,
            log=log,
        )
        return StepOutput(content=d, step_name="caption")

    def visual_step(step_input: StepInput) -> StepOutput:
        caption = cast(AgentStepDecision, step_input.previous_step_content)
        _h, d = run_agent_step(
            agent_id="visual-creative",
            to_agent="video-editor",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Criar briefing visual",
            context=f"Legenda: {caption.decision}",
            message=f"Crie o briefing visual para o reel sobre: {tema}." + CONSULTAR,
            log=log,
        )
        return StepOutput(content=d, step_name="visual")

    def video_editor_step(step_input: StepInput) -> StepOutput:
        visual = cast(AgentStepDecision, step_input.previous_step_content)
        _h, d = run_agent_step(
            agent_id="video-editor",
            to_agent="brand-reviewer",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Especificar edicao do video",
            context=f"Brief visual: {visual.decision}",
            message=f"Especifique a edicao (cortes, ritmo, legendas, musica) para o reel sobre: {tema}. Brief visual: {visual.output}" + CONSULTAR,
            log=log,
        )
        return StepOutput(content=d, step_name="video_editor")

    def brand_reviewer_step(step_input: StepInput) -> StepOutput:
        video = cast(AgentStepDecision, step_input.previous_step_content)
        _h, d = run_agent_step(
            agent_id="brand-reviewer",
            to_agent="quality-control",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Validar conteudo final antes de Quality Control",
            context=f"Edicao especificada: {video.decision}",
            message=(
                f"Revise este reel completo sobre '{tema}'. Objetivo: {objetivo}.\n"
                f"Conteudo entregue pelas etapas anteriores:\n{video.output}\n\n"
                "ANTES de decidir, abra as fontes da sua whitelist que sustentam a "
                "decisao (VOICE, CONTENT_PILLARS, VISUAL_IDENTITY, BUSINESS_RULES, e "
                "OFFERS/PRODUCTS se houver preco ou link). Cite em `references` apenas "
                "o que abriu.\n"
                "Aprova (approved=true) ou reprova (approved=false, com motivo "
                "especifico e a fonte que sustenta o motivo)? Se nao houver base "
                "documental suficiente para decidir, use needs_evidence=true com "
                "approved=false e diga em `risks` qual evidencia falta."
            ),
            log=log,
            decision_schema=ReviewDecision,
        )
        log.outputs["brand_reviewer_approved"] = d.approved
        log.outputs["brand_reviewer_needs_evidence"] = d.needs_evidence
        return StepOutput(content=d, step_name="brand_reviewer")

    def quality_control_step(step_input: StepInput) -> StepOutput:
        qc_result = validate_workflow(log, QC_SPEC_PRE_APPROVAL)
        log.outputs["qc_pre_approval"] = qc_result
        if not qc_result.is_valid:
            return StepOutput(content=qc_result, step_name="quality_control", stop=True, success=False)
        return StepOutput(content=qc_result, step_name="quality_control")

    def human_approval_step(step_input: StepInput) -> StepOutput:
        return StepOutput(
            content="Reel pronto para aprovacao final da Judith. Nenhum conteudo foi publicado.",
            step_name="human_approval",
        )

    return Workflow(
        name=WORKFLOW_NAME,
        steps=[
            Step(name="brand_architect", executor=brand_architect_step),
            Step(name="trend", executor=trend_step),
            Step(name="hook", executor=hook_step),
            Step(name="script", executor=script_step),
            Step(name="caption", executor=caption_step),
            Step(name="visual", executor=visual_step),
            Step(name="video_editor", executor=video_editor_step),
            Step(name="brand_reviewer", executor=brand_reviewer_step),
            Step(name="quality_control", executor=quality_control_step),
            Step(
                name="human_approval",
                executor=human_approval_step,
                human_review=HumanReview(
                    requires_output_review=True,
                    output_review_message="Judith, aprova este reel para publicacao?",
                ),
            ),
        ],
    )


def run_create_reel(
    tema: str, objetivo: str, *, task_id: str | None = None
) -> tuple[ExecutionLog, QualityControlResult]:
    """Executa o workflow CREATE_REEL de ponta a ponta.

    Retorna (log, quality_control_result). Se o CMO rejeitar o brief, o
    pipeline nem chega a ser montado - log.status="rejected" direto.
    """

    log = ExecutionLog(workflow=WORKFLOW_NAME, task_id=task_id) if task_id else ExecutionLog(workflow=WORKFLOW_NAME)
    log.inputs["tema"] = tema
    log.inputs["objetivo"] = objetivo

    try:
        cmo_decision = _cmo_gate(log, log.task_id, tema, objetivo)
        if not cmo_decision.approved:
            log.finish(status="rejected", result=f"CMO rejeitou o objetivo: {cmo_decision.decision}")
            resultado = validate_workflow(log, QC_SPEC_FULL)
            persist_execution(log)
            return log, resultado

        workflow = _build_pipeline(log, log.task_id, tema, objetivo)
        run_output = workflow.run(input=f"Tema: {tema}\nObjetivo: {objetivo}")

        qc_pre_approval = log.outputs.get("qc_pre_approval")
        if qc_pre_approval is not None and not qc_pre_approval.is_valid:
            log.finish(status="rejected", result="Quality Control interrompeu: processo incompleto.")
        elif run_output.is_paused:
            log.finish(status="pending_human_approval", result="Aguardando aprovacao final da Judith.")
        elif run_output.status == RunStatus.completed:
            # Nao deveria acontecer sem passar por pending_human_approval - se
            # acontecer, e um bug (a etapa human_approval nao pausou como
            # deveria) e o proprio Quality Control (QC_SPEC_FULL,
            # requires_human_approval=True) vai acusar isso.
            log.finish(status="completed", result="Workflow reportou completed sem pausa de aprovacao humana.")
        else:
            log.finish(status="failed", result=f"status inesperado: {run_output.status}")
    except Exception as exc:
        # Execucao que morre no meio continua auditavel.
        log.finish(status="failed", error=f"{type(exc).__name__}: {exc}")
        persist_execution(log)
        raise

    resultado = validate_workflow(log, QC_SPEC_FULL)
    persist_execution(log)
    return log, resultado
