"""
Testes do hardening de evidencia (deterministicos, sem LLM).

O que esta rodada garantiu:
- `sources_opened` vem das tool calls do runtime, nao do texto do LLM;
- listar o catalogo NAO conta como consultar;
- o Quality Control rejeita citacao sem consulta real;
- NEEDS_EVIDENCE existe como estado proprio, distinto de reprovacao;
- o CMO nao consegue mais recuperar a secao de tracking do BRAND.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from agents.knowledge_policies import KNOWLEDGE_POLICIES, get_policy
from agents.knowledge_sources import CMO_DOCUMENTS, read_document, search_documents
from orchestration.execution_log import ExecutionLog
from orchestration.handoff import AgentHandoff, ReviewDecision
from orchestration.quality_control import WorkflowSpec, validate_workflow
from orchestration.step_helpers import _extract_sources_opened
from orchestration.workflows.create_reel import AGENTS_REQUIRING_EVIDENCE, PIPELINE_AGENTS


def _response_with_tools(calls: list[tuple[str, dict]]):
    message = MagicMock()
    message.role = "assistant"
    message.tool_name = None
    message.tool_calls = [{"function": {"name": name, "arguments": json.dumps(args)}} for name, args in calls]
    return MagicMock(messages=[message])


def _response_with_tool_result(tool_name: str, payload: list[dict]):
    """Simula a mensagem role='tool' que o Agno grava com o retorno da tool."""

    result = MagicMock()
    result.role = "tool"
    result.tool_name = tool_name
    result.tool_calls = None
    result.content = json.dumps(payload)
    return MagicMock(messages=[result])


def _handoff(agent: str, *, references: list[str], sources_opened: list[str], risks: list[str] | None = None):
    return AgentHandoff(
        from_agent=agent,
        to_agent="next",
        workflow="TEST",
        task_id="t",
        objective="obj",
        context="ctx",
        decision="d",
        output="o",
        confidence="alto",
        references=references,
        risks=risks or [],
        sources_opened=sources_opened,
        recommended_next="next",
    )


# --- Instrumentacao: o que o agente REALMENTE abriu -------------------------


def test_ler_documento_conta_como_consulta() -> None:
    response = _response_with_tools([("ler_documento", {"fonte": "voice"})])
    assert _extract_sources_opened(response) == ["VOICE"]


def test_search_knowledge_base_registra_a_fonte_que_voltou() -> None:
    """Vale o documento que a busca DEVOLVEU, nao a query que o agente
    escreveu — verificado no runtime: a mensagem role='tool' traz os `fonte`."""

    response = _response_with_tool_result(
        "search_knowledge_base",
        [{"fonte": "OFFERS", "conteudo": "..."}, {"fonte": "PRODUCTS", "conteudo": "..."}],
    )
    assert _extract_sources_opened(response) == ["OFFERS", "PRODUCTS"]


def test_busca_que_so_devolve_lacuna_nao_conta_como_consulta() -> None:
    """FONTE_NAO_DISPONIVEL e a ausencia da fonte, nao a fonte."""

    response = _response_with_tool_result(
        "search_knowledge_base",
        [{"fonte": "VENDAS_KIWIFY", "status": "FONTE_NAO_DISPONIVEL", "peca_para": "analytics-bi-agent"}],
    )
    assert _extract_sources_opened(response) == []


def test_listar_fontes_nao_conta_como_consulta() -> None:
    """A distincao central: listar o catalogo nao e abrir documento."""

    response = _response_with_tools([("listar_fontes_disponiveis", {})])
    assert _extract_sources_opened(response) == []


def test_consulta_repetida_nao_duplica() -> None:
    response = _response_with_tools(
        [("ler_documento", {"fonte": "VOICE"}), ("ler_documento", {"fonte": "VOICE"})]
    )
    assert _extract_sources_opened(response) == ["VOICE"]


def test_sem_tool_call_nenhuma_o_agente_nao_consultou() -> None:
    assert _extract_sources_opened(MagicMock(messages=[])) == []


# --- Quality Control: evidencia valida vs invalida --------------------------


def _spec(agents: list[str]) -> WorkflowSpec:
    return WorkflowSpec(
        name="TEST",
        required_agents_in_order=agents,
        requires_references=True,
        agents_requiring_evidence=agents,
    )


def _log_with(handoffs: list[AgentHandoff]) -> ExecutionLog:
    log = ExecutionLog(workflow="TEST")
    for handoff in handoffs:
        log.record(handoff)
    log.finish(status="completed", result="ok")
    return log


def test_qc_aceita_evidencia_valida() -> None:
    log = _log_with([_handoff("brand-reviewer", references=["VOICE"], sources_opened=["VOICE"])])
    result = validate_workflow(log, _spec(["brand-reviewer"]))

    assert result.citations_without_source == []
    assert result.handoffs_without_references == []
    assert result.status == "PROCESSO_VALIDADO"


def test_qc_rejeita_citacao_sem_consulta_real() -> None:
    """O defeito observado no Brand Reviewer: citar fonte que nao abriu."""

    log = _log_with([_handoff("brand-reviewer", references=["VOICE", "BUSINESS_RULES"], sources_opened=[])])
    result = validate_workflow(log, _spec(["brand-reviewer"]))

    assert result.citations_without_source
    assert "brand-reviewer" in result.citations_without_source[0]
    assert result.status == "PROCESSO_INCOMPLETO"


def test_qc_rejeita_quem_deveria_consultar_e_nao_consultou() -> None:
    log = _log_with([_handoff("caption-writer", references=[], sources_opened=[])])
    result = validate_workflow(log, _spec(["caption-writer"]))

    assert result.handoffs_without_references
    assert result.status == "PROCESSO_INCOMPLETO"


def test_qc_rejeita_mesmo_com_risco_declarado_se_nao_abriu_documento() -> None:
    """Antes, declarar um risco bastava. Agora nao substitui consultar."""

    log = _log_with([_handoff("brand-architect", references=[], sources_opened=[], risks=["nao tenho certeza"])])
    result = validate_workflow(log, _spec(["brand-architect"]))

    assert result.handoffs_without_references
    assert result.status == "PROCESSO_INCOMPLETO"


def test_qc_nao_exige_evidencia_de_quem_nao_esta_na_lista() -> None:
    """Nao inventar exigencia para etapa que genuinamente nao consulta nada."""

    spec = WorkflowSpec(
        name="TEST",
        required_agents_in_order=["community-dm-agent", "brand-reviewer"],
        requires_references=True,
        agents_requiring_evidence=["brand-reviewer"],
    )
    log = _log_with(
        [
            _handoff("community-dm-agent", references=[], sources_opened=[]),
            _handoff("brand-reviewer", references=["VOICE"], sources_opened=["VOICE"]),
        ]
    )
    result = validate_workflow(log, spec)

    assert result.status == "PROCESSO_VALIDADO"


# --- NEEDS_EVIDENCE --------------------------------------------------------


def test_needs_evidence_e_estado_proprio_no_contrato() -> None:
    decision = ReviewDecision(
        decision="sem base para decidir",
        output="",
        confidence="baixo",
        references=[],
        recommended_next="judith",
        approved=False,
        needs_evidence=True,
    )

    assert decision.needs_evidence is True
    # Default preservado para quem nao usa o campo (ex.: gate do CMO).
    assert ReviewDecision(
        decision="ok", output="", confidence="alto", recommended_next="x", approved=True
    ).needs_evidence is False


def test_qc_marca_needs_evidence_e_nao_chama_de_rejeicao() -> None:
    log = ExecutionLog(workflow="TEST")
    log.record(_handoff("brand-reviewer", references=["VOICE"], sources_opened=["VOICE"]))
    log.outputs["brand_reviewer_approved"] = False
    log.outputs["brand_reviewer_needs_evidence"] = True
    log.finish(status="rejected", result="sem base")

    result = validate_workflow(
        log,
        WorkflowSpec(
            name="TEST",
            required_agents_in_order=["brand-reviewer"],
            requires_brand_reviewer_approval=True,
            agents_requiring_evidence=["brand-reviewer"],
        ),
    )

    assert result.brand_reviewer_needs_evidence is True
    assert result.status == "PROCESSO_INCOMPLETO"
    assert any("NEEDS_EVIDENCE" in nota for nota in result.notes)


# --- CREATE_REEL: exigencia reativada --------------------------------------


def test_create_reel_exige_evidencia_de_todo_o_pipeline() -> None:
    assert AGENTS_REQUIRING_EVIDENCE == ["cmo", *PIPELINE_AGENTS]
    assert len(AGENTS_REQUIRING_EVIDENCE) == 9


def test_todo_agente_exigido_tem_whitelist_para_consultar() -> None:
    """Nao exigir evidencia de quem nao tem fonte para abrir."""

    for agent_id in AGENTS_REQUIRING_EVIDENCE:
        assert get_policy(agent_id).documents


# --- CMO: bloco de tracking -------------------------------------------------


def test_cmo_nao_recupera_secao_de_tracking_por_leitura() -> None:
    conteudo = read_document("BRAND", CMO_DOCUMENTS)["conteudo"]

    assert "Tracking e Analytics" not in conteudo
    assert "Facebook Pixel" not in conteudo
    assert "Posicionamento" in conteudo, "o corte nao pode levar embora o conteudo util"


def test_cmo_nao_recupera_secao_de_tracking_por_busca() -> None:
    """Busca dirigida ao bloco excluido nao pode devolve-lo por outro caminho."""

    for pergunta in ("facebook pixel hotjar clarity", "google search console verificado", "tracking e analytics"):
        for doc in search_documents(pergunta, CMO_DOCUMENTS):
            assert doc.get("secao") != "Tracking e Analytics"
            assert "Facebook Pixel" not in str(doc.get("conteudo", ""))


def test_nenhum_agente_alcanca_o_bloco_de_tracking() -> None:
    """O bloco esta duplicado em BRAND.md e WEBSITE_AUDIT.md — cobrir um so
    deixava o outro aberto. Este teste varre os 20 agentes por qualquer rota."""

    perguntas = ("facebook pixel", "hotjar clarity", "tracking e analytics", "search console")

    for agent_id in sorted(KNOWLEDGE_POLICIES):
        policy = get_policy(agent_id)

        for source in policy.documents:
            if "Tracking e Analytics" not in source.path.read_text(encoding="utf-8"):
                continue
            conteudo = read_document(source.key, policy.documents)["conteudo"]
            assert "Facebook Pixel" not in conteudo, f"{agent_id} le tracking via {source.key}"

        for pergunta in perguntas:
            for doc in search_documents(pergunta, policy.documents, policy.missing_sources):
                assert doc.get("secao") != "Tracking e Analytics", f"{agent_id} alcanca tracking por busca"
