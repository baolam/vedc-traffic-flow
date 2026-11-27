"""Validation-seed benchmark of every deterministic controller in the repo (clean main-repo code), scored with the
campaign guardrail against tuned Fixed-Time. Writes per-map rows.json + summary.json under OUT."""
import json, os, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, os.environ.get("REPO", "."))
from contracts.benchmark import SEEDS, DQN_RECIPE
from src.benchmark.scheduling import run_tasks
from src.benchmark.unified_campaign import load_suite
from src.rl.selection import validation_score
ROOT = Path(os.environ.get("REPO", ".")) / "artifacts/benchmarks/unified-v1"
OUT = Path(os.environ.get("EXP_ROOT", "diag-exp")) / "baselines"
CONTROLLERS = ("actuated", "max_queue", "max_pressure", "edgeflow", "flow_theory", "fair_cycle", "fair_cycle_native")
KEYS = ("delay_per_scheduled_s", "p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s", "completed", "scheduled", "collisions", "teleports")

if __name__ == "__main__":
    protocol = dict(demand_s=DQN_RECIPE["demand_s"], drain_s=DQN_RECIPE["drain_s"], trace=False, benchmark_mode=True, check_every=25)
    for MAP in sys.argv[1:]:
        spec = load_suite(ROOT / "prepared.json", ROOT, [MAP])["maps"][0]
        out = OUT / MAP
        out.mkdir(parents=True, exist_ok=True)
        ref = json.load(open(ROOT / f"references/{MAP}-{DQN_RECIPE['demand_s']}-{DQN_RECIPE['drain_s']}.json"))
        rows = {"fixed_time": ref}
        for name in CONTROLLERS:
            ctl = dict(type=name, parameters={})
            tasks = [(dict(map=spec, scenario=c, seed=s, controller=ctl), protocol, str(out / name))
                     for c in spec["cases"] for s in SEEDS["validation"]]
            try:
                rows[name] = run_tasks(tasks, 4)
            except Exception as e:
                rows[name] = str(e)[-300:]
            print(MAP, name, "ok" if isinstance(rows[name], list) else rows[name], flush=True)
        json.dump(rows, open(out / "rows.json", "w"))
        summ = {}
        for name, rs in rows.items():
            if isinstance(rs, str):
                summ[name] = dict(error=rs)
                continue
            t = {}
            for r in rs:
                t.setdefault(r["scenario"], []).append(r)
            summ[name] = dict(guardrail=validation_score(rs, ref, spec["cases"], SEEDS["validation"]),
                              cases={c: {k: round(float(np.mean([x.get(k) or 0 for x in v])), 2) for k in KEYS}
                                     | {"valid": all(x["valid"] for x in v)} for c, v in t.items()})
        json.dump(summ, open(out / "summary.json", "w"), indent=1)
        print("done", MAP, flush=True)
