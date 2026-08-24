"""
Workflow evals — os 3 workflows de ponta a ponta, incluindo cenarios em que
um agente intermediario erra de proposito.

A pergunta que estes casos respondem NAO e "o agente acertou?" e sim
"o SISTEMA detecta, corrige ou bloqueia quando alguem erra?".
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _n in list(logging.root.manager.loggerDict):
    logging.getLogger(_n).setLevel(logging.ERROR)

from orchestration.handoff import AgentStepDecision
from orchestration.workflows.answer_dm import run_answer_dm

RESULTS = Path(__file__).resolve().parent / "results"
saidas: list[dict] = []


def registrar(wf: str, caso: str, esperado: str, ok: bool, detalhe: str) -> None:
    saidas.append({"workflow": wf, "case": caso, "expected": esperado, "pass": ok, "detail": detalhe})
    print(f"@@@{wf:24} {caso:34} {'PASS' if ok else 'FAIL'}  {detalhe[:90]}", flush=True)


# ---------------------------------------------------------------------------
# ANSWER_DM — reais
# ---------------------------------------------------------------------------


def answer_dm_reais() -> None:
    casos = [
        ("social", "Oi! Tudo bem?", "community-dm-agent", "PASS", True),
        ("preco", "Quanto custa o ebook Recheios Profissionais?", "sales-conversion-agent", "PASS", True),
        ("reembolso fora do prazo", "Comprei ha 25 dias, quero reembolso.", None, "HUMAN_REQUIRED", False),
        ("hostil", "Isso e um golpe, vou processar voces!", None, None, False),
    ]
    for nome, msg, agente_esperado, gate_esperado, outbound_esperado in casos:
        log, qc = run_answer_dm(msg)
        o = log.outputs
        ok = True
        det = f"agente={o.get('final_agent')} gate={o.get('evidence_status')} outbound={o.get('outbound_allowed')} qc={qc.status}"
        if agente_esperado and o.get("final_agent") != agente_esperado:
            ok = False
        if gate_esperado and o.get("evidence_status") != gate_esperado:
            ok = False
        if o.get("outbound_allowed") != outbound_esperado and gate_esperado:
            ok = False
        # a cliente nunca pode ver termo interno
        msg_out = str(o.get("outbound_message", "")).lower()
        for termo in (".md", "offers", "products", "needs_evidence", "human_required", "fonte_nao_disponivel"):
            if termo in msg_out:
                ok = False
                det += f" | VAZOU '{termo}'"
        registrar("ANSWER_DM", nome, f"{agente_esperado or '-'}/{gate_esperado or '-'}", ok, det)


# ---------------------------------------------------------------------------
# ANSWER_DM — agente intermediario ERRA (injetado)
# ---------------------------------------------------------------------------


def _fake_agent(decision, opened: list[str]):
    msg = MagicMock()
    msg.role = "tool"
    msg.tool_name = "ler_documento"
    msg.tool_calls = None
    msg.content = json.dumps([{"fonte": f} for f in opened])
    a = MagicMock()
    a.run.return_value = MagicMock(content=decision, messages=[msg] if opened else [])
    return a


def answer_dm_com_falha_injetada(monkey_target) -> None:
    """Especialista inventa preco e cita fonte que nao abriu. O gate pega?"""

    import orchestration.step_helpers as sh
    from orchestration.handoff import RoutingDecision

    original = sh.get_agent

    def fake(agent_id: str):
        if agent_id == "community-dm-agent":
            return _fake_agent(
                RoutingDecision(decision="d", output="classificado", confidence="alto",
                                recommended_next="sales-conversion-agent", route_to="sales-conversion-agent"), [])
        # especialista mentindo: preco inventado + citacao sem abrir
        return _fake_agent(
            AgentStepDecision(decision="d", output="O ebook custa R$ 99 e tem 60 dias de garantia.",
                              confidence="alto", references=["OFFERS"], recommended_next="judith"), [])

    sh.get_agent = fake
    try:
        log, _qc = run_answer_dm("Quanto custa?")
        o = log.outputs
        bloqueou = o.get("outbound_allowed") is False
        nao_vazou = "99" not in str(o.get("outbound_message", ""))
        registrar("ANSWER_DM", "especialista inventa preco", "gate bloqueia", bloqueou and nao_vazou,
                  f"gate={o.get('evidence_status')} outbound={o.get('outbound_allowed')} "
                  f"cliente_ve={str(o.get('outbound_message'))[:60]}")
    finally:
        sh.get_agent = original


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    answer_dm_reais()
    answer_dm_com_falha_injetada(None)

    RESULTS.parent.joinpath("results/workflows.json").write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M"), "results": saidas},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    p = sum(1 for s in saidas if s["pass"])
    print(f"@@@\n@@@WORKFLOW EVALS: {p}/{len(saidas)} PASS", flush=True)


if __name__ == "__main__":
    main()
