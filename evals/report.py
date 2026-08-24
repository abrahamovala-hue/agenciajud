"""Consolida evals/results/*.json numa tabela por agente e num ranking de falhas."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.framework import CRITICAL_FAILURES as CRITICAL

RESULTS = Path(__file__).resolve().parent / "results"


def carregar(apenas_ultima: bool = True, runs: int = 1) -> list[dict]:
    """Consolida resultados.

    Cada rodada vive em `results/run-<timestamp>/` e nada e apagado — ver a
    nota em run_evals.run_dir sobre o acidente da rodada 1.

    `runs` diz quantos diretorios recentes juntar: uma rodada executada em
    lotes paralelos produz um diretorio por lote, e todos pertencem a mesma
    rodada. A dedup por (agent, case) garante que juntar demais nao duplica.
    """

    todos = sorted(p for p in RESULTS.glob("run-*") if p.is_dir())
    raizes = todos[-runs:] if (todos and apenas_ultima) else [RESULTS]
    dados: list[dict] = []
    for raiz in raizes:
        for f in sorted(raiz.rglob("*.json")):
            dados.extend(json.loads(f.read_text(encoding="utf-8")).get("results", []))

    # dedup por (agent, case) mantendo o ultimo
    vistos: dict[tuple[str, str], dict] = {}
    for r in dados:
        if "agent_id" not in r:
            continue
        vistos[(r["agent_id"], r["case_id"])] = r
    return list(vistos.values())


def main() -> None:
    rs = carregar(runs=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
    if not rs:
        print("sem resultados")
        return

    por_agente: dict[str, list[dict]] = {}
    for r in rs:
        por_agente.setdefault(r["agent_id"], []).append(r)

    print(f"{'AGENT':28} {'N':>2} {'PASS':>4} {'PART':>4} {'FAIL':>4}  CRITICAL / falhas")
    print("-" * 110)
    for aid in sorted(por_agente):
        casos = por_agente[aid]
        p = sum(1 for c in casos if c["label"] == "PASS")
        pa = sum(1 for c in casos if c["label"] == "PARTIAL")
        f = sum(1 for c in casos if c["label"] in ("FAIL", "ERROR"))
        falhas = Counter(x for c in casos for x in c["failures"])
        crit = {k: v for k, v in falhas.items() if k in CRITICAL}
        resumo = ", ".join(f"{k}×{v}" for k, v in sorted(falhas.items(), key=lambda kv: -kv[1]))
        marca = "  !! " + ", ".join(sorted(crit)) if crit else ""
        print(f"{aid:28} {len(casos):2} {p:4} {pa:4} {f:4} {marca}")
        if resumo:
            print(f"{'':28} {resumo}")

    print("\n=== RANKING DE FALHAS ===")
    total = Counter(x for c in rs for x in c["failures"])
    for nome, n in total.most_common():
        tag = "CRITICO" if nome in CRITICAL else "qualidade"
        agentes = sorted({c["agent_id"] for c in rs if nome in c["failures"]})
        print(f"  {n:3}× {nome:26} [{tag}] {len(agentes)} agentes: {', '.join(agentes[:6])}")

    print("\n=== CASOS CRITICOS (detalhe) ===")
    for c in rs:
        crit = [x for x in c["failures"] if x in CRITICAL]
        if crit:
            print(f"  {c['agent_id']}/{c['case_id']} {crit}")
            print(f"    input : {c['input'][:90]}")
            print(f"    notas : {c['notes']}")
            print(f"    saida : {c['output'][:160].replace(chr(10), ' ')}")

    n = len(rs)
    p = sum(1 for c in rs if c["label"] == "PASS")
    print(f"\nTOTAL: {n} casos | PASS {p} ({p*100//n}%) | "
          f"PARTIAL {sum(1 for c in rs if c['label']=='PARTIAL')} | "
          f"FAIL {sum(1 for c in rs if c['label'] in ('FAIL','ERROR'))}")
    lat = [c["latency_s"] for c in rs if c["latency_s"]]
    if lat:
        print(f"latencia: media {sum(lat)/len(lat):.1f}s | max {max(lat):.1f}s")


if __name__ == "__main__":
    main()
