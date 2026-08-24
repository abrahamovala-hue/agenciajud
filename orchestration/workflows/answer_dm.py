"""
ANSWER_DM — mensagem recebida -> classificacao -> especialista correto.

mensagem
  -> Community & DM Agent (classifica)
  -> Router:
       - community-dm-agent      (conversa social - responde direto)
       - customer-support-agent  (FAQ / problema de produto)
       - sales-conversion-agent  (intencao de compra)
       - crm-lifecycle-agent     (lead que merece acompanhamento)
       - human-escalation        (sensivel / fora de politica - sem LLM)
  -> Evidence Gate na RESPOSTA FINAL (orchestration/evidence_gate.py)

So chama os agentes necessarios para a mensagem em questao - nunca os 20.

Evidence Gate: nenhuma afirmacao factual sobre o negocio (preco, oferta,
politica, conteudo de produto, prazo, acesso) sai sem fonte realmente aberta.
Conversa social passa sem consulta nenhuma - o gate age sobre a resposta
final, nao sobre cada etapa interna.

Nenhuma integracao real com Instagram existe ainda. A "mensagem recebida" e
sempre texto passado diretamente pela chamada (fixture ou input real do
chamador) - nunca fingimos ter lido algo do Instagram de verdade.
"""

from __future__ import annotations

from typing import cast

from agno.run.base import RunStatus
from agno.workflow import Router, Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from orchestration.evidence_gate import (
    EvidenceGateResult,
    customer_facing_message,
    evaluate_final_response,
    leaks_internal_terms,
    strip_internal_references,
)
from orchestration.execution_log import ExecutionLog
from orchestration.handoff import AgentHandoff, AgentStepDecision, RoutingDecision
from orchestration.quality_control import QualityControlResult, WorkflowSpec, validate_workflow
from orchestration.step_helpers import run_agent_step

WORKFLOW_NAME = "ANSWER_DM"

# So o especialista que RESPONDE a cliente recebe esta instrucao. O
# classificador nao: decidir "isto e intencao de compra" nao exige abrir
# OFFERS, e obrigar isso encareceria toda mensagem sem ganho nenhum.
CONSULTAR_ANTES_DE_AFIRMAR = (
    "\n\n---\n"
    "Regra do canal: qualquer afirmacao sobre preco, oferta, desconto, "
    "conteudo do produto, acesso, entrega, prazo, garantia ou reembolso "
    "precisa vir de documento que voce ABRIU agora (OFFERS/PRODUCTS para dado "
    "comercial). Cite em `references` so o que abriu. Se nao encontrar a "
    "informacao, diga que vai confirmar — nunca preencha com um valor "
    "plausivel. Saudacao, agradecimento e pergunta de clarificacao nao "
    "precisam de consulta.\n"
    "A cliente NAO pode ver nome de documento interno. Escreva 'OFFERS', "
    "'PRODUCTS.md', 'segundo o documento X' apenas no campo `references` — "
    "nunca no texto da resposta. Para a cliente, fale como a marca fala."
)

QC_SPEC = WorkflowSpec(
    name=WORKFLOW_NAME,
    # community-dm-agent sempre participa (classifica). O especialista de
    # destino varia por mensagem, entao nao entra na lista de obrigatorios
    # fixos — o QC dessa etapa valida via `log.outputs["route_to"]` em vez
    # de uma lista de agentes fixa (ver nota em validate_answer_dm abaixo).
    required_agents_in_order=["community-dm-agent"],
    requires_brand_reviewer_approval=False,
    requires_human_approval=False,
    requires_references=False,  # respostas de suporte/venda podem legitimamente nao citar doc
)


def _finalize(
    log: ExecutionLog,
    *,
    agent_id: str,
    handoff: AgentHandoff,
    decision: AgentStepDecision,
    escalated: bool = False,
) -> EvidenceGateResult:
    """Aplica o Evidence Gate a resposta final e grava o rastro no log.

    A resposta so vai para a cliente se `outbound_allowed`. Quando nao vai, o
    que sai e uma frase natural — o motivo tecnico fica so no log.
    """

    gate = evaluate_final_response(
        agent_id=agent_id,
        response=decision.output,
        references=handoff.references,
        sources_opened=handoff.sources_opened,
        escalated=escalated,
    )

    # A cliente nunca ve nome de documento interno. A evidencia continua
    # inteira em `references`/`sources_opened` — o corte e so na prosa.
    outbound = customer_facing_message(gate) or strip_internal_references(decision.output)

    log.outputs.update(
        {
            "route_to": agent_id if not escalated else "human-escalation",
            "final_agent": agent_id,
            "final_response": decision.output,
            "factual_claims_detected": gate.factual_claims_detected,
            "evidence_required": gate.evidence_required,
            "sources_opened": gate.sources_opened,
            "references": gate.references,
            "evidence_status": gate.status,
            "outbound_allowed": gate.outbound_allowed,
            "outbound_message": outbound,
            "outbound_sanitized": outbound != decision.output,
            "internal_terms_leaked": leaks_internal_terms(outbound),
            "evidence_reason": gate.reason,
        }
    )

    if not gate.outbound_allowed and not escalated:
        log.escalate(raised_by=agent_id, reason=f"Evidence gate: {gate.status} — {gate.reason}", at_step="final_response")

    return gate


def _build_workflow(
    log: ExecutionLog,
    task_id: str,
    message: str,
    session_id: str | None = None,
    user_id: str | None = None,
) -> Workflow:
    # Duas sessoes, de proposito.
    #
    # `sessao` e a CONVERSA: o que a cliente disse e o que respondemos. So os
    # agentes que falam com ela usam esta.
    #
    # `sessao_interna` e a maquinaria: prompts de classificacao, que sao
    # instrucao nossa e nao fala da cliente. Medido em execucao real: com as
    # duas no mesmo session_id, os prompts de classificacao afogam o historico
    # e o agente perde o fio da conversa ("nao lembro seu nome" no turno
    # seguinte a ela ter dito o nome).
    sessao = {"session_id": session_id, "user_id": user_id}
    sessao_interna = {
        "session_id": f"{session_id}:interno" if session_id else None,
        "user_id": user_id,
    }

    def classify(step_input: StepInput) -> StepOutput:
        prompt = f"""\
Classifique esta mensagem de cliente recebida via Instagram (DM ou \
comentário) e decida para qual especialista ela deve ser roteada.

Mensagem recebida: "{message}"

Escolha route_to entre exatamente estas opções:
- "community-dm-agent": conversa social sem pergunta de negócio — saudação \
("oi", "bom dia"), agradecimento, elogio, emoji, comentário solto, ou \
pergunta que só pede clarificação. Se a mensagem não faz nenhuma pergunta \
sobre produto, preço, compra ou problema, é AQUI.
- "customer-support-agent": problema com uma compra JÁ FEITA (acesso, \
entrega, conteúdo do produto que já tem) OU dúvida factual genérica sobre \
como o processo funciona (ex.: "precisa de experiência?", "funciona no \
celular?") — NUNCA use esta opção se a pessoa está decidindo COMPRAR algo.
- "sales-conversion-agent": a pessoa ainda NÃO comprou e está decidindo o \
quê comprar, comparando produtos, perguntando preço, ou pedindo recomendação \
de qual produto é melhor pra ela — QUALQUER pergunta do tipo "qual é melhor \
pra mim?", "quanto custa?", "vale a pena?" vai AQUI, mesmo que pareça uma \
dúvida simples.
- "crm-lifecycle-agent": lead que já demonstrou interesse forte e merece \
acompanhamento contínuo (não é uma pergunta imediata a responder agora)
- "human-escalation": reclamação séria, tom hostil, ameaça, ou qualquer \
coisa fora de política

Preencha o restante do output_schema normalmente."""
        # to_agent="pending-route": ainda nao sabemos o destino final aqui
        # (e a proxima decisao, do proprio Router). Corrigido para o valor
        # real por _patch_classify_to_agent assim que a rota e escolhida.
        _handoff, decision = run_agent_step(
            agent_id="community-dm-agent",
            to_agent="pending-route",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Classificar mensagem recebida e rotear para o especialista certo",
            context=f"Mensagem recebida via Instagram: {message!r}",
            message=prompt,
            log=log,
            **sessao_interna,
            decision_schema=RoutingDecision,
        )
        return StepOutput(content=decision, step_name="classify")

    def route_to_community(step_input: StepInput) -> StepOutput:
        """Conversa social: o proprio Community responde, sem consulta.

        Existe porque forcar uma saudacao a passar por vendas/CRM produzia
        analise interna de lead no lugar de um "oi" — observado em execucao
        real antes desta rota existir.
        """

        handoff, decision = run_agent_step(
            agent_id="community-dm-agent",
            to_agent="judith",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Responder conversa social",
            context=f"Mensagem social, sem pergunta de negocio: {message!r}",
            message=(
                f"Responda esta mensagem de forma breve, calorosa e natural, no tom da marca: {message!r}\n"
                "E so conversa — nao afirme nada sobre preco, produto, oferta, prazo ou politica, "
                "e nao precisa consultar documento. Se a pessoa quiser algo concreto, convide-a a perguntar."
            ),
            log=log,
            **sessao,
        )
        _patch_classify_to_agent(log, "community-dm-agent")
        _finalize(log, agent_id="community-dm-agent", handoff=handoff, decision=decision)
        return StepOutput(content=handoff, step_name="route_to_community")

    def route_to_support(step_input: StepInput) -> StepOutput:
        handoff, decision = run_agent_step(
            agent_id="customer-support-agent",
            to_agent="judith",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Resolver FAQ ou problema pos-venda",
            context=f"Community & DM classificou como suporte. Mensagem original: {message!r}",
            message=message + CONSULTAR_ANTES_DE_AFIRMAR,
            log=log,
            **sessao,
        )
        _patch_classify_to_agent(log, "customer-support-agent")
        _finalize(log, agent_id="customer-support-agent", handoff=handoff, decision=decision)
        return StepOutput(content=handoff, step_name="route_to_support")

    def route_to_sales(step_input: StepInput) -> StepOutput:
        handoff, decision = run_agent_step(
            agent_id="sales-conversion-agent",
            to_agent="crm-lifecycle-agent",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Responder intencao de compra",
            context=f"Community & DM classificou como intencao de compra. Mensagem original: {message!r}",
            message=message + CONSULTAR_ANTES_DE_AFIRMAR,
            log=log,
            **sessao,
        )
        _patch_classify_to_agent(log, "sales-conversion-agent")
        _finalize(log, agent_id="sales-conversion-agent", handoff=handoff, decision=decision)
        return StepOutput(content=handoff, step_name="route_to_sales")

    def route_to_crm(step_input: StepInput) -> StepOutput:
        handoff, decision = run_agent_step(
            agent_id="crm-lifecycle-agent",
            to_agent="sales-conversion-agent",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Registrar lead e recomendar follow-up",
            context=f"Community & DM classificou como lead a acompanhar. Mensagem original: {message!r}",
            message=message + CONSULTAR_ANTES_DE_AFIRMAR,
            log=log,
            **sessao,
        )
        _patch_classify_to_agent(log, "crm-lifecycle-agent")
        _finalize(log, agent_id="crm-lifecycle-agent", handoff=handoff, decision=decision)
        return StepOutput(content=handoff, step_name="route_to_crm")

    def route_to_human(step_input: StepInput) -> StepOutput:
        routing = cast(RoutingDecision, step_input.previous_step_content)
        handoff = AgentHandoff(
            from_agent="community-dm-agent",
            to_agent="judith",
            workflow=WORKFLOW_NAME,
            task_id=task_id,
            objective="Escalar mensagem sensivel para revisao humana",
            context=f"Mensagem original: {message!r}",
            decision="Escalado para Judith — mensagem sensivel ou fora de politica.",
            output=routing.output,
            confidence=routing.confidence,
            risks=routing.risks or ["Mensagem classificada como sensivel/fora de politica"],
            references=routing.references,
            recommended_next="Judith revisa e decide a resposta manualmente.",
        )
        log.record(handoff)
        _patch_classify_to_agent(log, "judith")
        log.escalate(raised_by="community-dm-agent", reason="Mensagem sensivel ou fora de politica", at_step="route")
        _finalize(log, agent_id="community-dm-agent", handoff=handoff, decision=routing, escalated=True)
        return StepOutput(content=handoff, step_name="route_to_human")

    community_step = Step(name="route_to_community", executor=route_to_community)
    support_step = Step(name="route_to_support", executor=route_to_support)
    sales_step = Step(name="route_to_sales", executor=route_to_sales)
    crm_step = Step(name="route_to_crm", executor=route_to_crm)
    human_step = Step(name="route_to_human", executor=route_to_human)

    route_map = {
        "community-dm-agent": community_step,
        "customer-support-agent": support_step,
        "sales-conversion-agent": sales_step,
        "crm-lifecycle-agent": crm_step,
        "human-escalation": human_step,
    }

    def selector(step_input: StepInput):
        # O step 'classify' sempre coloca um RoutingDecision aqui.
        routing = cast(RoutingDecision, step_input.previous_step_content)
        return route_map[routing.route_to]

    router = Router(
        name="route",
        selector=selector,
        choices=[community_step, support_step, sales_step, crm_step, human_step],
    )

    return Workflow(
        name=WORKFLOW_NAME,
        steps=[Step(name="classify", executor=classify), router],
    )


def _patch_classify_to_agent(log: ExecutionLog, to_agent: str) -> None:
    """O handoff de classificacao e criado antes de sabermos a rota final;
    corrige `to_agent` para o destino real assim que decidido."""

    for h in log.handoffs:
        if h.from_agent == "community-dm-agent" and h.to_agent == "pending-route":
            h.to_agent = to_agent


def run_answer_dm(
    message: str,
    *,
    task_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> tuple[ExecutionLog, QualityControlResult]:
    """Executa o workflow ANSWER_DM de ponta a ponta para uma mensagem.

    `session_id`/`user_id` mantem a conversa separada por pessoa quando a
    chamada vem de um canal real (WhatsApp). Sem eles o comportamento e o
    de antes: execucao isolada, sem historico.
    """

    log = ExecutionLog(workflow=WORKFLOW_NAME, task_id=task_id) if task_id else ExecutionLog(workflow=WORKFLOW_NAME)
    log.inputs["message"] = message

    workflow = _build_workflow(log, log.task_id, message, session_id=session_id, user_id=user_id)
    run_output = workflow.run(input=message)

    evidence_status = log.outputs.get("evidence_status")

    if log.outputs.get("route_to") == "human-escalation" or evidence_status == "HUMAN_REQUIRED":
        log.finish(status="pending_human_approval", result=log.outputs.get("outbound_message"))
    elif evidence_status in {"NEEDS_EVIDENCE", "REJECTED"}:
        # A resposta do agente nao sai. O que sai e a frase natural de espera.
        log.finish(status="rejected", result=log.outputs.get("outbound_message"))
    elif run_output.status == RunStatus.completed:
        log.finish(status="completed", result=log.outputs.get("outbound_message"))
    else:
        log.finish(status="failed", result=f"status inesperado: {run_output.status}")

    result = validate_workflow(log, QC_SPEC)
    return log, result
