"""
Quality Control determinístico — SEM LLM.

Implementa em código o papel documentado em
docs/JUDITH-AI-TEAM-V2/agents/21-quality-control-agent.md: valida que o
PROCESSO foi seguido (nao a qualidade criativa - isso e o Brand Reviewer).

E so codigo Python puro sobre um ExecutionLog. Nao chama nenhum Agent, nao
faz nenhuma chamada de LLM - por design, conforme instruido: "Quality
Control NAO deve usar LLM nesta V1".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from orchestration.execution_log import ExecutionLog

QCStatus = Literal["PROCESSO_VALIDADO", "PROCESSO_INCOMPLETO"]

# Os agentes sao instruidos a escrever literalmente "nenhuma fonte consultada"
# quando nao abriram nada. Isso e honestidade, nao citacao - tratar como
# citacao inverteria o incentivo e puniria justamente quem foi honesto.
_HONESTY_MARKERS = ("nenhuma fonte consultada", "nenhuma fonte", "fonte nao disponivel", "fonte não disponível")


def _real_citations(references: list[str]) -> list[str]:
    """Filtra os marcadores de honestidade e devolve so citacoes de verdade."""

    return [r for r in references if not any(marker in r.strip().casefold() for marker in _HONESTY_MARKERS)]


@dataclass
class WorkflowSpec:
    """O que o Quality Control espera de um workflow especifico."""

    name: str
    required_agents_in_order: list[str]
    """Agentes obrigatorios cuja ORDEM RELATIVA importa (pipeline sequencial)."""

    required_agents_unordered: list[str] = field(default_factory=list)
    """Agentes obrigatorios cuja ordem NAO importa - tipicamente rodam dentro
    de um `Parallel`, onde a ordem de conclusao nao e deterministica. Exigir
    ordem entre eles produziria falso positivo de "order_violation"."""

    requires_brand_reviewer_approval: bool = False
    requires_human_approval: bool = False

    requires_references: bool = True
    """Se True, cobra evidencia (references) nos handoffs de
    `agents_requiring_evidence`."""

    agents_requiring_evidence: list[str] = field(default_factory=list)
    """Quais agentes DEVEM ter aberto documento. Vazio + requires_references=True
    significa "todos".

    Historico desta regra: ela nasceu frouxa porque nenhum agente tinha
    Knowledge — agentes criativos legitimamente nao tinham documento a citar.
    Depois que todos ganharam whitelist real (`agents/knowledge_policies.py`),
    a lista voltou a valer para quem decide COM BASE em documento vinculante
    (marca, pilar, preco, identidade visual). Continua existindo para as
    etapas que genuinamente nao consultam nada — exigir evidencia delas
    produziria citacao artificial, que e o problema que queremos evitar."""
    forbidden_direct_edges: list[tuple[str, str]] = field(default_factory=list)
    """Pares (from, to) que NUNCA podem ser um handoff direto - ex.: pular
    o Brand Reviewer e ir direto pra aprovacao humana."""


@dataclass
class QualityControlResult:
    status: QCStatus
    missing_agents: list[str]
    order_violations: list[str]
    missing_brand_reviewer_approval: bool
    brand_reviewer_rejected: bool
    handoffs_without_references: list[str]
    citations_without_source: list[str]
    """Agentes que citaram fonte sem ter aberto documento nenhum. Detectado
    comparando `references` (texto do LLM) com `sources_opened` (tool calls)."""
    brand_reviewer_needs_evidence: bool
    forbidden_edges_found: list[str]
    human_approval_pending: bool
    human_approval_missing: bool
    notes: list[str]

    @property
    def is_valid(self) -> bool:
        return self.status == "PROCESSO_VALIDADO"


def validate_workflow(log: ExecutionLog, spec: WorkflowSpec) -> QualityControlResult:
    """Checagem 100% determinística contra o ExecutionLog de uma execução."""

    notes: list[str] = []

    # 1. Agentes obrigatorios participaram (e, quando a ordem importa, na ordem certa)?
    missing_agents = [
        a for a in [*spec.required_agents_unordered, *spec.required_agents_in_order] if a not in log.agents_called
    ]

    order_violations: list[str] = []
    seen_positions = {agent: i for i, agent in enumerate(log.agents_called)}
    # So checa ordem entre os agentes de `required_agents_in_order` - agentes
    # em `required_agents_unordered` (Parallel) sao ignorados aqui de proposito.
    expected_in_log = [a for a in spec.required_agents_in_order if a in seen_positions]
    for earlier, later in zip(expected_in_log, expected_in_log[1:]):
        if seen_positions[earlier] > seen_positions[later]:
            order_violations.append(f"{earlier} deveria vir antes de {later}, mas veio depois")

    # 2. Brand Reviewer aprovou quando necessario?
    missing_brand_reviewer_approval = False
    brand_reviewer_rejected = False
    if spec.requires_brand_reviewer_approval:
        brand_reviewer_handoffs = [h for h in log.handoffs if h.from_agent == "brand-reviewer"]
        if not brand_reviewer_handoffs:
            missing_brand_reviewer_approval = True
            notes.append("Brand Reviewer nao participou, mas este workflow exige aprovacao dele.")
        else:
            # `approved` vem de ReviewDecision (bool explicito) — checado pelo
            # chamador via log.outputs["brand_reviewer_approved"], nao parseado
            # de texto livre aqui. Ver orchestration/workflows/create_reel.py.
            approved = log.outputs.get("brand_reviewer_approved")
            if approved is False:
                brand_reviewer_rejected = True
                notes.append("Brand Reviewer explicitamente REJEITOU o conteudo (approved=False).")
            elif approved is None:
                missing_brand_reviewer_approval = True
                notes.append("Brand Reviewer participou mas o veredito (approved) nao foi registrado no log.")

    # 3. Evidencia: o agente ABRIU documento, e o que ele diz bate com o que abriu?
    #
    # `references` e texto do LLM; `sources_opened` vem das tool calls do
    # runtime. Comparar os dois e o que permite pegar o caso "citei VOICE mas
    # so listei o catalogo" sem precisar de LLM para julgar.
    handoffs_without_references: list[str] = []
    citations_without_source: list[str] = []
    if spec.requires_references:
        for h in log.handoffs:
            applies = not spec.agents_requiring_evidence or h.from_agent in spec.agents_requiring_evidence
            if not applies:
                continue

            if not h.sources_opened:
                citadas = _real_citations(h.references)
                if citadas:
                    # Pior que nao consultar: alegar que consultou.
                    citations_without_source.append(f"{h.from_agent} citou {citadas[:2]} sem abrir nenhum documento")
                else:
                    # Honesto, mas ainda assim decidiu sem base documental -
                    # e a Regra 5 do protocolo ("Referencia Obrigatoria") vale
                    # para os agentes listados em agents_requiring_evidence.
                    handoffs_without_references.append(
                        f"{h.from_agent} -> {h.to_agent} (nao abriu documento nenhum)"
                    )

    # 3b. Brand Reviewer decidiu por regra de marca sem base documental?
    brand_reviewer_needs_evidence = bool(log.outputs.get("brand_reviewer_needs_evidence"))
    if brand_reviewer_needs_evidence:
        notes.append(
            "Brand Reviewer devolveu NEEDS_EVIDENCE: nao havia base documental suficiente "
            "para aprovar nem reprovar. Nao e rejeicao de conteudo."
        )

    # 4. Nenhuma etapa proibida foi pulada (handoff direto proibido)?
    forbidden_edges_found: list[str] = []
    actual_edges = {(h.from_agent, h.to_agent) for h in log.handoffs}
    for edge in spec.forbidden_direct_edges:
        if edge in actual_edges:
            forbidden_edges_found.append(f"{edge[0]} -> {edge[1]} (pulo de etapa proibido)")

    # 5. Aprovacao humana pendente quando requerida?
    human_approval_pending = spec.requires_human_approval and log.status == "pending_human_approval"
    human_approval_missing = (
        spec.requires_human_approval
        and log.status == "completed"
        and not human_approval_pending
        # Se o workflow se declarou "completed" sem nunca ter passado por
        # pending_human_approval, isso e uma violacao grave: alguem tentou
        # pular a aprovacao da Judith.
    )
    if human_approval_missing:
        notes.append(
            "CRITICO: workflow marcado como completed sem nunca ter passado por "
            "pending_human_approval. Aprovacao humana da Judith foi pulada."
        )

    is_incomplete = bool(
        missing_agents
        or order_violations
        or missing_brand_reviewer_approval
        or brand_reviewer_rejected
        or handoffs_without_references
        or citations_without_source
        or brand_reviewer_needs_evidence
        or forbidden_edges_found
        or human_approval_missing
    )

    return QualityControlResult(
        status="PROCESSO_INCOMPLETO" if is_incomplete else "PROCESSO_VALIDADO",
        missing_agents=missing_agents,
        order_violations=order_violations,
        missing_brand_reviewer_approval=missing_brand_reviewer_approval,
        brand_reviewer_rejected=brand_reviewer_rejected,
        handoffs_without_references=handoffs_without_references,
        citations_without_source=citations_without_source,
        brand_reviewer_needs_evidence=brand_reviewer_needs_evidence,
        forbidden_edges_found=forbidden_edges_found,
        human_approval_pending=human_approval_pending,
        human_approval_missing=human_approval_missing,
        notes=notes,
    )
