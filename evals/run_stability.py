"""
Teste de estabilidade: roda o MESMO caso N vezes.

Serve para separar defeito sistematico de variancia do modelo. Um caso de
seguranca que passa em 3 de 5 execucoes nao esta "quase certo" — esta
instavel, e instabilidade em decisao de seguranca e defeito por si so.

Uso:
    python evals/run_stability.py community-dm-agent cd-05 5
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _n in list(logging.root.manager.loggerDict):
    logging.getLogger(_n).setLevel(logging.ERROR)

from evals.framework import EVALS_DIR, load_cases, run_case


def main() -> None:
    agent_id, case_id, n = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5
    caso = next(c for c in load_cases(agent_id) if c.id == case_id)

    execucoes = []
    for i in range(1, n + 1):
        r = run_case(caso)
        execucoes.append({
            "run": i, "label": r.label, "scores": r.scores, "failures": r.failures,
            "sources_opened": r.sources_opened, "notes": r.notes,
            "output": r.output[:600], "latency_s": r.latency_s,
        })
        print(f"@@@run {i}/{n}: {r.label:7} falhas={r.failures or '-'} abriu={r.sources_opened}", flush=True)

    labels = [e["label"] for e in execucoes]
    estavel = len(set(labels)) == 1
    print(f"@@@\n@@@{agent_id}/{case_id}: {labels}", flush=True)
    print(f"@@@estavel={estavel} | PASS {labels.count('PASS')}/{n}", flush=True)

    destino = EVALS_DIR / "results" / f"stability-{agent_id}-{case_id}.json"
    destino.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%d %H:%M"), "agent_id": agent_id,
        "case_id": case_id, "runs": n, "labels": labels, "stable": estavel, "executions": execucoes,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"@@@gravado: {destino.name}", flush=True)


if __name__ == "__main__":
    main()
