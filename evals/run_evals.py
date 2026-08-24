"""
Executa os eval cases contra os Agents reais e grava o resultado.

Uso:
    python evals/run_evals.py                 # todos
    python evals/run_evals.py cmo hook-finder # subconjunto

Saida: evals/results/baseline.json + resumo no stdout.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _name in list(logging.root.manager.loggerDict):
    logging.getLogger(_name).setLevel(logging.ERROR)

from evals.framework import EVALS_DIR, all_agents_with_cases, load_cases, run_case

RESULTS = EVALS_DIR / "results"


def run_dir() -> Path:
    """Diretorio dedicado por execucao.

    Cada rodada escreve num carimbo de tempo proprio, e nunca sobrescreve nem
    apaga rodada anterior. Na rodada 1 um `rm baseline-*.json` destruiu 71
    casos de baseline — com um diretorio por execucao, esse erro deixa de ser
    possivel: nada precisa ser apagado para uma nova rodada rodar.
    """

    carimbo = time.strftime("run-%Y%m%d-%H%M%S")
    # `exist_ok=False` de proposito: duas execucoes no mesmo segundo nao podem
    # compartilhar diretorio, ou uma sobrescreve os arquivos da outra — que e
    # a mesma classe de acidente que este diretorio existe para impedir.
    for sufixo in ("", *(f"-{i}" for i in range(1, 100))):
        d = RESULTS / f"{carimbo}{sufixo}"
        try:
            d.mkdir(parents=True, exist_ok=False)
            return d
        except FileExistsError:
            continue
    raise RuntimeError("nao foi possivel criar diretorio de execucao unico")


def main() -> None:
    agentes = sys.argv[1:] or all_agents_with_cases()
    destino = run_dir()

    todos: list[dict] = []
    for agent_id in agentes:
        casos = load_cases(agent_id)
        for caso in casos:
            try:
                r = run_case(caso)
                registro = {
                    "case_id": caso.id,
                    "agent_id": agent_id,
                    "scenario": caso.scenario,
                    "input": caso.input,
                    "blocked_by": caso.blocked_by,
                    "output": r.output,
                    "sources_opened": r.sources_opened,
                    "references": r.references,
                    "latency_s": r.latency_s,
                    "scores": r.scores,
                    "overall": r.overall,
                    "label": r.label,
                    "failures": r.failures,
                    "notes": r.notes,
                }
            except Exception as exc:  # noqa: BLE001 - um caso quebrado nao para a rodada
                registro = {
                    "case_id": caso.id, "agent_id": agent_id, "scenario": caso.scenario,
                    "input": caso.input, "blocked_by": caso.blocked_by, "output": "",
                    "sources_opened": [], "references": [], "latency_s": 0.0,
                    "scores": {}, "overall": 0, "label": "ERROR",
                    "failures": ["EXECUTION_ERROR"], "notes": [f"{type(exc).__name__}: {exc}"],
                }
            todos.append(registro)
            print(f"@@@{agent_id:28} {caso.id:8} {registro['label']:7} "
                  f"{registro['latency_s']:5.1f}s {','.join(registro['failures']) or '-'}", flush=True)

    # Um arquivo por lote dentro do diretorio da execucao: lotes paralelos
    # nao se sobrescrevem e rodadas antigas ficam intactas.
    lote = sys.argv[1] if len(sys.argv) > 1 else "all"
    saida = destino / f"{lote}.json"
    saida.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M"), "results": todos},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"@@@\n@@@gravado: {saida.relative_to(EVALS_DIR.parent)} ({len(todos)} casos)", flush=True)


if __name__ == "__main__":
    main()
