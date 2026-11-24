"""Markdown per-case tables for the loop report: learned (it05 seed 17, it06 seed 29) vs best passing deterministic
without and with the max-red envelope (it07 ablation). Usage: python report_tables.py > tables.md"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LOOP = REPO / "artifacts/benchmarks/rl-loop"
COMPARISON = REPO / "docs/engineering/reports/rl_environment_design_20261122/data/comparison.json"
DET = ("fixed_time", "actuated", "max_queue", "max_pressure", "edgeflow", "flow_theory", "fair_cycle", "fair_cycle_native")
NEW = ("jakarta_menteng_v1", "hanoi_dong_da_v1")  # re-downloaded 2026-11-24
TRIPLE = ("delay_per_scheduled_s", "p95_wait_s", "worst_approach_wait_s")


def summary_rows(path):
    """{controller: (score, feasible, fails, {case: [delay, p95, worst]})} from a baselines.py summary.json."""
    out = {}
    for c, v in json.loads(path.read_text()).items():
        g = v.get("guardrail")
        if g:
            out[c] = (g["score"], g["feasible"], len(g["reasons"]), {k: [x[t] for t in TRIPLE] for k, x in v["cases"].items()})
    return out


def best(rows):
    ok = [(v[0], c) for c, v in rows.items() if c in DET and v[1]]
    return min(ok) if ok else None


if __name__ == "__main__":
    comparison = json.loads(COMPARISON.read_text())
    learned = {s: json.loads((LOOP / it / "percase.json").read_text()) for s, it in (("17", "it05"), ("29", "it06"))}
    ledger = {json.loads(line)["iteration"]: json.loads(line) for line in (HERE / "ledger.jsonl").read_text().splitlines() if line.strip()}
    for m in learned["17"]:
        if m in NEW:
            plain = summary_rows(LOOP / "targets-osm-20261124/baselines" / m / "summary.json")
        else:
            plain = {c: (r["score"], r["feasible"], r["fails"], r["cases"]) for c, r in comparison[m].items() if "score" in r}
        boxed = summary_rows(LOOP / "it07-ablation/baselines" / m / "summary.json")
        cases = list(learned["17"][m]["cases"])
        print(f"\n**{m}**\n")
        print("| Controller | Score | Pass | " + " | ".join(cases) + " |")
        print("|---|---|---|" + "---|" * len(cases))
        for seed, it in (("17", "it05"), ("29", "it06")):
            r = ledger[it]["maps"][m]
            score = r["score"] if r.get("score") is not None else r.get("best_infeasible")
            cells = [" / ".join(f"{learned[seed][m]['cases'][c][t]:.1f}" for t in TRIPLE) for c in cases]
            print(f"| learned, seed {seed} ({learned[seed][m]['policy']}) | {score:.1f} | {'✓' if r.get('score') is not None else '✗'} | " + " | ".join(cells) + " |")
        for label, rows in (("best deterministic", plain), ("best deterministic + max-red", boxed)):
            b = best(rows)
            if b is None:
                print(f"| {label} | — | ✗ | " + " | ".join("—" for _ in cases) + " |")
                continue
            score, c = b
            cells = [" / ".join(f"{x:.1f}" for x in rows[c][3][k]) for k in cases]
            print(f"| {label}: {c} | {score:.1f} | ✓ | " + " | ".join(cells) + " |")
