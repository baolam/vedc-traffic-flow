"""Score one loop iteration against the best passing deterministic controller and the last kept iteration.
Usage: python score.py <iter-id> "<hypothesis>" [--seed 17] [--record]   (--record appends to ledger.jsonl)"""
import argparse, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LEDGER = HERE / "ledger.jsonl"
COMPARISON = REPO / "docs/engineering/reports/rl_environment_design_20261122/data/comparison.json"
DETERMINISTIC = ("fixed_time", "actuated", "max_queue", "max_pressure", "edgeflow", "flow_theory", "fair_cycle", "fair_cycle_native")
NOISE_S = 3.0  # single-seed noise floor measured in the 2026-11-22 report


def targets():
    data = json.loads(COMPARISON.read_text())
    return {m: min((r["score"], c) for c, r in rows.items() if c in DETERMINISTIC and r.get("feasible"))
            for m, rows in data.items()}


def map_result(root, m, seed):
    d = root / "training" / m / "phase_dqn_unified" / str(seed)
    if not (d / "result.json").exists():
        return dict(status="missing")
    r, h = json.loads((d / "result.json").read_text()), json.loads((d / "history.json").read_text())
    sel = r.get("selected")
    last = h[-1] if h else {}
    return dict(score=round(sel["score"], 1) if sel else None, episode=sel and sel["episode"],
                best_infeasible=None if sel else min((x["score"] for x in h), default=None),
                reasons=None if sel else last.get("reasons"), episodes=r["counters"]["episode"],
                wall_min=round(r["counters"]["wall_s"] / 60), stop=r["stop_reason"])


def verdict(new, base):
    """KEEP when a map gains >= NOISE_S (or becomes feasible) and no map loses feasibility."""
    lost = any(base.get(m, {}).get("score") is not None and new[m].get("score") is None for m in new)
    gained = any(n.get("score") is not None and (base.get(m, {}).get("score") is None
                                                 or base[m]["score"] - n["score"] >= NOISE_S) for m, n in new.items())
    return "KEEP" if gained and not lost else "DISCARD"


assert verdict({"a": {"score": 30.0}}, {"a": {"score": 34.0}}) == "KEEP"
assert verdict({"a": {"score": 33.0}}, {"a": {"score": 34.0}}) == "DISCARD"
assert verdict({"a": {"score": 20.0}, "b": {"score": None}}, {"a": {"score": 40.0}, "b": {"score": 9.0}}) == "DISCARD"
assert verdict({"a": {"score": 50.0}}, {"a": {"score": None}}) == "KEEP"

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("iteration"); p.add_argument("hypothesis"); p.add_argument("--seed", type=int, default=17)
    p.add_argument("--record", action="store_true")
    a = p.parse_args()
    root = REPO / "artifacts/benchmarks/rl-loop" / a.iteration
    maps = sorted(x.name for x in (root / "training").iterdir())
    new = {m: map_result(root, m, a.seed) for m in maps}
    kept = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()] if LEDGER.exists() else []
    kept = [k for k in kept if k["verdict"] in ("KEEP", "BASE") and k["seed"] == a.seed]
    base = {m: r for k in kept for m, r in k["maps"].items()}  # latest kept result per map
    tgt = targets()
    print(f"{'map':36} {'new':>7} {'base':>7} {'target':>18}  status")
    for m, n in new.items():
        s, b, (t, tc) = n.get("score"), base.get(m, {}).get("score"), tgt[m]
        win = "WIN" if s is not None and s < t else "feasible" if s is not None else f"infeasible ({len(n.get('reasons') or [])} guardrail fails)"
        print(f"{m:36} {s if s is not None else '-':>7} {b if b is not None else '-':>7} {t:>8} {tc:>9}  {win}")
    v = "BASE" if not kept else verdict(new, base)
    print("verdict:", v)
    if a.record:
        row = dict(iteration=a.iteration, hypothesis=a.hypothesis, seed=a.seed, verdict=v, maps=new,
                   gates=(root / "gates.env").read_text().split(), commit=(root / "commit").read_text().strip())
        with LEDGER.open("a") as f:
            f.write(json.dumps(row) + "\n")
