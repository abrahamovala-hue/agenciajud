"""Testes da camada de orquestração (AgentHandoff, Registry, Quality Control,
e os 3 Workflows: ANSWER_DM, CREATE_REEL, WEEKLY_BUSINESS_REVIEW).

Estratégia: `Agent.run()` real faz chamada de LLM (lento, custa dinheiro,
não-determinístico para asserções exatas). Os testes automatizados aqui
mockam `orchestration.step_helpers.get_agent` para retornar decisões
controladas, testando a CORREÇÃO DA ORQUESTRAÇÃO (roteamento, gates,
Quality Control, aprovação humana) — não o julgamento do LLM em si.

Os cenários reais (chamando o LLM de verdade) foram exercitados
manualmente durante o desenvolvimento; resultado documentado no relatório
de entrega, não neste arquivo (custaria API a cada `pytest`).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from orchestration.execution_log import ExecutionLog
from orchestration.handoff import AgentHandoff, AgentStepDecision, ReviewDecision, RoutingDecision
from orchestration.quality_control import WorkflowSpec, validate_workflow
from orchestration.registry import AGENT_REGISTRY, AgentNotFoundError, get_agent

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_has_20_team_agents_plus_jud() -> None:
    assert len(AGENT_REGISTRY) == 21


def test_registry_resolves_known_agent() -> None:
    agent = get_agent("cmo")
    assert agent.id == "cmo"


def test_registry_raises_clear_error_for_unknown_agent_id() -> None:
    with pytest.raises(AgentNotFoundError) as exc_info:
        get_agent("does-not-exist")
    assert "does-not-exist" in str(exc_info.value)
    assert "cmo" in str(exc_info.value)  # lista os ids validos


def test_quality_control_agent_is_not_in_registry() -> None:
    # Decisao de design: Quality Control e logica deterministica, nao Agent.
    assert "quality-control-agent" not in AGENT_REGISTRY


# ---------------------------------------------------------------------------
# AgentHandoff
# ---------------------------------------------------------------------------


def test_agent_handoff_from_step_decision_combines_envelope_and_decision() -> None:
    decision = AgentStepDecision(
        decision="Aprovado",
        output="Conteudo produzido",
        confidence="alto",
        risks=[],
        references=["VOICE.md"],
        recommended_next="script-writer",
    )
    handoff = AgentHandoff.from_step_decision(
        from_agent="hook-finder",
        to_agent="script-writer",
        workflow="CREATE_REEL",
        task_id="t1",
        objective="Gerar hooks",
        context="ctx",
        step_decision=decision,
    )
    assert handoff.from_agent == "hook-finder"
    assert handoff.to_agent == "script-writer"
    assert handoff.output == "Conteudo produzido"
    assert handoff.references == ["VOICE.md"]
    assert handoff.evidence == ["VOICE.md"]  # evidence espelha references


def test_agent_handoff_rejects_invalid_confidence() -> None:
    with pytest.raises(Exception):
        AgentStepDecision(
            decision="d",
            output="o",
            confidence="super-certeza",  # nao e alto/medio/baixo
            recommended_next="x",
        )


def test_routing_decision_rejects_invalid_route() -> None:
    with pytest.raises(Exception):
        RoutingDecision(
            decision="d",
            output="o",
            confidence="alto",
            recommended_next="x",
            route_to="instagram-api",  # nao e uma das 4 opcoes validas
        )


# ---------------------------------------------------------------------------
# Quality Control (deterministico)
# ---------------------------------------------------------------------------


def _handoff(
    from_agent: str,
    to_agent: str,
    *,
    references: list[str] | None = None,
    risks: list[str] | None = None,
    sources_opened: list[str] | None = None,
) -> AgentHandoff:
    # Por padrao o agente ABRIU o que citou. Passe `sources_opened=[]`
    # explicitamente para simular uma citacao sem consulta real.
    if sources_opened is None:
        sources_opened = list(references or [])
    return AgentHandoff(
        sources_opened=sources_opened,
        from_agent=from_agent,
        to_agent=to_agent,
        workflow="TEST",
        task_id="t",
        objective="obj",
        context="ctx",
        decision="d",
        output="o",
        confidence="alto",
        references=references or [],
        risks=risks or [],
        recommended_next=to_agent,
    )


def test_quality_control_validates_complete_workflow() -> None:
    spec = WorkflowSpec(
        name="TEST",
        required_agents_in_order=["cmo", "brand-architect", "brand-reviewer"],
        requires_brand_reviewer_approval=True,
        requires_human_approval=True,
    )
    log = ExecutionLog(workflow="TEST", task_id="t1")
    log.record(_handoff("cmo", "brand-architect", references=["PRD.md"]))
    log.record(_handoff("brand-architect", "brand-reviewer", references=["VOICE.md"]))
    log.record(_handoff("brand-reviewer", "judith", references=["VOICE.md"]))
    log.outputs["brand_reviewer_approved"] = True
    log.finish(status="pending_human_approval")

    result = validate_workflow(log, spec)
    assert result.status == "PROCESSO_VALIDADO"


def test_quality_control_detects_missing_required_agent() -> None:
    spec = WorkflowSpec(name="TEST", required_agents_in_order=["cmo", "brand-architect", "brand-reviewer"])
    log = ExecutionLog(workflow="TEST", task_id="t2")
    log.record(_handoff("cmo", "brand-architect"))
    log.finish(status="completed")

    result = validate_workflow(log, spec)
    assert result.status == "PROCESSO_INCOMPLETO"
    assert "brand-architect" in result.missing_agents
    assert "brand-reviewer" in result.missing_agents


def test_quality_control_rejects_workflow_that_skipped_human_approval() -> None:
    spec = WorkflowSpec(
        name="TEST",
        required_agents_in_order=["cmo", "brand-reviewer"],
        requires_brand_reviewer_approval=True,
        requires_human_approval=True,
    )
    log = ExecutionLog(workflow="TEST", task_id="t3")
    log.record(_handoff("cmo", "brand-reviewer", references=["PRD.md"]))
    log.record(_handoff("brand-reviewer", "judith", references=["VOICE.md"]))
    log.outputs["brand_reviewer_approved"] = True
    log.finish(status="completed")  # <- pulou pending_human_approval de proposito

    result = validate_workflow(log, spec)
    assert result.status == "PROCESSO_INCOMPLETO"
    assert result.human_approval_missing is True
    assert any("CRITICO" in note for note in result.notes)


def test_quality_control_detects_brand_reviewer_rejection() -> None:
    spec = WorkflowSpec(name="TEST", required_agents_in_order=["brand-reviewer"], requires_brand_reviewer_approval=True)
    log = ExecutionLog(workflow="TEST", task_id="t4")
    log.record(_handoff("brand-reviewer", "script-writer", references=["VOICE.md"]))
    log.outputs["brand_reviewer_approved"] = False
    log.finish(status="rejected")

    result = validate_workflow(log, spec)
    assert result.status == "PROCESSO_INCOMPLETO"
    assert result.brand_reviewer_rejected is True


def test_quality_control_detects_forbidden_skip() -> None:
    spec = WorkflowSpec(
        name="TEST",
        required_agents_in_order=["script-writer"],
        forbidden_direct_edges=[("script-writer", "judith")],
    )
    log = ExecutionLog(workflow="TEST", task_id="t5")
    log.record(_handoff("script-writer", "judith"))  # pulou Brand Reviewer direto pra Judith
    log.finish(status="completed")

    result = validate_workflow(log, spec)
    assert result.status == "PROCESSO_INCOMPLETO"
    assert any("script-writer -> judith" in e for e in result.forbidden_edges_found)


def test_quality_control_only_requires_evidence_from_designated_agents() -> None:
    """Agentes criativos nao precisam citar documento (produzem, nao
    consultam); agentes de decisao/validacao precisam."""

    spec = WorkflowSpec(
        name="TEST",
        required_agents_in_order=["cmo", "hook-finder"],
        requires_references=True,
        agents_requiring_evidence=["cmo"],
    )
    log = ExecutionLog(workflow="TEST", task_id="t-ev")
    log.record(_handoff("cmo", "hook-finder", references=["PRD.md"]))
    log.record(_handoff("hook-finder", "script-writer", references=[]))  # criativo, sem doc
    log.finish(status="completed")

    result = validate_workflow(log, spec)
    assert result.handoffs_without_references == []
    assert result.status == "PROCESSO_VALIDADO"


def test_quality_control_still_flags_decision_agent_without_evidence() -> None:
    spec = WorkflowSpec(
        name="TEST",
        required_agents_in_order=["cmo"],
        requires_references=True,
        agents_requiring_evidence=["cmo"],
    )
    log = ExecutionLog(workflow="TEST", task_id="t-ev2")
    log.record(_handoff("cmo", "brand-architect", references=[], risks=[]))  # decisao sem base
    log.finish(status="completed")

    result = validate_workflow(log, spec)
    assert result.status == "PROCESSO_INCOMPLETO"
    assert len(result.handoffs_without_references) == 1


def test_quality_control_flags_handoff_without_evidence_or_risk() -> None:
    spec = WorkflowSpec(name="TEST", required_agents_in_order=["cmo"], requires_references=True)
    log = ExecutionLog(workflow="TEST", task_id="t6")
    log.record(_handoff("cmo", "brand-architect", references=[], risks=[]))
    log.finish(status="completed")

    result = validate_workflow(log, spec)
    assert result.status == "PROCESSO_INCOMPLETO"
    assert len(result.handoffs_without_references) == 1


# ---------------------------------------------------------------------------
# Workflows — mockando get_agent para nao gastar chamada de LLM real
# ---------------------------------------------------------------------------


def _mock_agent_returning(decision, *, opened: list[str] | None = None):
    """Agente fake que devolve `decision`.

    `opened` simula as tool calls de consulta que o runtime registraria. O
    default abre um documento porque, depois de `agents/knowledge_policies.py`,
    o Quality Control exige consulta real dos agentes do CREATE_REEL. Passe
    `opened=[]` para simular um agente que citou fonte sem abrir nada.
    """

    if opened is None:
        opened = ["VOICE"]

    message = MagicMock()
    message.tool_calls = [
        {"function": {"name": "ler_documento", "arguments": json.dumps({"fonte": fonte})}} for fonte in opened
    ]

    fake_agent = MagicMock()
    fake_agent.run.return_value = MagicMock(content=decision, messages=[message])
    return fake_agent


class TestAnswerDmRouting:
    """ANSWER_DM: 3 cenarios pedidos (FAQ, intencao de compra, caso sensivel)
    + agent_id inexistente."""

    def _run_with_routing(self, route_to: str, monkeypatch):
        from orchestration.workflows import answer_dm as module

        classify_decision = RoutingDecision(
            decision="classificado",
            output="resposta simulada",
            confidence="alto",
            references=[],
            recommended_next=route_to,
            route_to=route_to,
        )
        specialist_decision = AgentStepDecision(
            decision="resolvido",
            output="resposta do especialista",
            confidence="alto",
            references=[],
            recommended_next="judith",
        )

        call_count = {"n": 0}

        def fake_get_agent(agent_id: str):
            call_count["n"] += 1
            if agent_id == "community-dm-agent":
                return _mock_agent_returning(classify_decision)
            return _mock_agent_returning(specialist_decision)

        monkeypatch.setattr(module, "run_agent_step", module.run_agent_step)  # no-op, mantem import
        monkeypatch.setattr("orchestration.step_helpers.get_agent", fake_get_agent)
        return module.run_answer_dm("mensagem de teste")

    def test_faq_or_product_problem_routes_to_support(self, monkeypatch) -> None:
        log, qc = self._run_with_routing("customer-support-agent", monkeypatch)
        assert log.outputs["route_to"] == "customer-support-agent"
        assert log.status == "completed"
        assert qc.status == "PROCESSO_VALIDADO"

    def test_purchase_intent_routes_to_sales(self, monkeypatch) -> None:
        log, qc = self._run_with_routing("sales-conversion-agent", monkeypatch)
        assert log.outputs["route_to"] == "sales-conversion-agent"
        assert log.status == "completed"

    def test_sensitive_message_escalates_to_human(self, monkeypatch) -> None:
        log, qc = self._run_with_routing("human-escalation", monkeypatch)
        assert log.outputs["route_to"] == "human-escalation"
        assert log.status == "pending_human_approval"
        assert len(log.escalations) == 1
        assert qc.status == "PROCESSO_VALIDADO"


class TestCreateReelGates:
    """CREATE_REEL: brief incompleto (CMO rejeita), e a garantia de que nao
    ha caminho para 'completed' sem aprovacao humana."""

    def test_incomplete_brief_is_rejected_by_cmo_gate(self, monkeypatch) -> None:
        from orchestration.workflows import create_reel as module

        rejection = ReviewDecision(
            decision="Objetivo vago demais",
            output="Preciso de produto, publico e KPI numerico",
            confidence="alto",
            risks=["Sem KPI mensuravel"],
            references=["PRD.md"],
            recommended_next="Judith redefine o brief",
            approved=False,
        )
        monkeypatch.setattr("orchestration.step_helpers.get_agent", lambda _id: _mock_agent_returning(rejection))

        log, qc = module.run_create_reel("chocolate", "vender mais")

        assert log.status == "rejected"
        # Nenhum agente de producao foi chamado — o gate poupou o pipeline inteiro.
        assert log.agents_called == ["cmo"]
        assert qc.status == "PROCESSO_INCOMPLETO"

    def test_quality_control_blocks_pipeline_when_brand_reviewer_rejects(self, monkeypatch) -> None:
        from orchestration.workflows import create_reel as module

        approval = ReviewDecision(
            decision="Aprovado",
            output="ok",
            confidence="alto",
            references=["PRD.md"],
            recommended_next="next",
            approved=True,
        )
        rejection = ReviewDecision(
            decision="Reprovado: claim de saude nao comprovado",
            output="corrigir",
            confidence="alto",
            risks=["Claim de saude"],
            references=["BUSINESS_RULES.md"],
            recommended_next="script-writer",
            approved=False,
        )
        generic = AgentStepDecision(
            decision="feito",
            output="conteudo",
            confidence="alto",
            references=["VOICE.md"],
            recommended_next="next",
        )

        def fake_get_agent(agent_id: str):
            if agent_id == "cmo":
                return _mock_agent_returning(approval)
            if agent_id == "brand-reviewer":
                return _mock_agent_returning(rejection)
            return _mock_agent_returning(generic)

        monkeypatch.setattr("orchestration.step_helpers.get_agent", fake_get_agent)

        log, qc = module.run_create_reel("Chocolate Ruby", "Vender 30 unidades ate 30/08/2026")

        # Brand Reviewer reprovou -> Quality Control interrompe -> nunca chega
        # na etapa de aprovacao humana.
        assert log.status == "rejected"
        assert log.outputs["brand_reviewer_approved"] is False
        assert qc.brand_reviewer_rejected is True
        assert qc.status == "PROCESSO_INCOMPLETO"

    def test_happy_path_pauses_for_human_approval_and_never_publishes(self, monkeypatch) -> None:
        from orchestration.workflows import create_reel as module

        approval = ReviewDecision(
            decision="Aprovado",
            output="ok",
            confidence="alto",
            references=["PRD.md"],
            recommended_next="next",
            approved=True,
        )
        generic = AgentStepDecision(
            decision="feito",
            output="conteudo",
            confidence="alto",
            references=["VOICE.md"],
            recommended_next="next",
        )

        def fake_get_agent(agent_id: str):
            if agent_id in {"cmo", "brand-reviewer"}:
                return _mock_agent_returning(approval)
            return _mock_agent_returning(generic)

        monkeypatch.setattr("orchestration.step_helpers.get_agent", fake_get_agent)

        log, qc = module.run_create_reel("Chocolate Ruby", "Vender 30 unidades ate 30/08/2026")

        # A garantia central: NUNCA "completed" sem passar por humano.
        assert log.status == "pending_human_approval"
        assert qc.human_approval_pending is True
        assert qc.human_approval_missing is False
        assert qc.status == "PROCESSO_VALIDADO"
        # Todos os 9 agentes do pipeline participaram.
        assert len(log.agents_called) == 9
        assert len(log.handoffs) == 9


class TestExecutionLog:
    """O log de execucao precisa carregar o que o AI Performance & Evals
    Agent vai consumir depois (ver LEARNING_EVALS_MODEL.md)."""

    def test_log_records_handoffs_agents_and_evidence(self) -> None:
        log = ExecutionLog(workflow="TEST")
        log.record(_handoff("cmo", "brand-architect", references=["PRD.md"]))
        log.record(_handoff("brand-architect", "hook-finder", references=["VOICE.md", "PRD.md"]))

        assert log.agents_called == ["cmo", "brand-architect"]
        assert len(log.handoffs) == 2
        assert set(log.evidence) == {"PRD.md", "VOICE.md"}  # deduplica

    def test_log_is_serializable_for_future_persistence(self) -> None:
        log = ExecutionLog(workflow="TEST")
        log.record(_handoff("cmo", "brand-architect", references=["PRD.md"]))
        log.escalate(raised_by="cmo", reason="risco financeiro", at_step="gate")
        log.finish(status="pending_human_approval", result="aguardando Judith")

        dumped = log.model_dump()
        assert dumped["workflow"] == "TEST"
        assert dumped["status"] == "pending_human_approval"
        assert len(dumped["handoffs"]) == 1
        assert len(dumped["escalations"]) == 1
        assert log.model_dump_json()  # nao levanta


class TestLearningLoop:
    """O ciclo de aprendizado existe como estrutura, mas NUNCA aplica nada
    automaticamente (BUSINESS_RULES.md regra 19)."""

    def test_improvement_proposal_can_never_be_auto_approved_or_applied(self) -> None:
        from orchestration.learning_loop import ImprovementProposal

        proposal = ImprovementProposal(
            target_agent_id="hook-finder",
            kind="instructions",
            evidence=["task-1", "task-2", "task-3"],
            occurrences=3,
            current_behavior="Gera hooks com tom agressivo demais",
            proposed_change="Reforcar a regra de tom premium",
            expected_impact="Menos rejeicao do Brand Reviewer",
            regression_risk="Baixo",
        )
        assert proposal.requires_human_approval is True
        assert proposal.applied is False

        # Os campos sao Literal - tentar "aprovar sozinho" e um erro de tipo.
        with pytest.raises(Exception):
            ImprovementProposal(
                target_agent_id="hook-finder",
                kind="instructions",
                evidence=["t1"],
                occurrences=1,
                current_behavior="x",
                proposed_change="y",
                expected_impact="z",
                regression_risk="w",
                applied=True,  # proibido
            )

    def test_learning_loop_module_exposes_no_mutation_function(self) -> None:
        import orchestration.learning_loop as module

        forbidden = [n for n in dir(module) if any(k in n.lower() for k in ("apply", "promote", "update_agent", "edit"))]
        assert forbidden == [], f"learning_loop nao deve expor funcao de mutacao: {forbidden}"

    def test_collect_for_evaluation_aggregates_logs(self) -> None:
        from orchestration.learning_loop import attach_human_feedback, collect_for_evaluation

        log = ExecutionLog(workflow="CREATE_REEL", task_id="t1")
        log.record(_handoff("hook-finder", "script-writer", references=[], risks=["risco X"]))
        log.escalate(raised_by="cmo", reason="risco financeiro", at_step="gate")
        attach_human_feedback(log, "Judith: hook ficou agressivo demais")
        log.finish(status="rejected")

        summary = collect_for_evaluation([log])
        assert summary["total_executions"] == 1
        assert summary["per_agent"]["hook-finder"]["calls"] == 1
        assert summary["per_agent"]["hook-finder"]["no_evidence"] == 1
        assert summary["per_agent"]["hook-finder"]["risks_raised"] == 1
        assert len(summary["escalations"]) == 1
        assert len(summary["human_feedback"]) == 1


# ---------------------------------------------------------------------------
# Regressão — os 20 agentes continuam intactos
# ---------------------------------------------------------------------------


def test_all_20_team_agents_still_importable() -> None:
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

    agents = [
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
    ]
    assert len(agents) == 20
    assert len({a.id for a in agents}) == 20
