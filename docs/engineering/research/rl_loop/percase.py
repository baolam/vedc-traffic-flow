"""Per-case validation metrics for one loop iteration's policies (selected policy, else final checkpoint).
Usage: [SEED=29] PYTHONPATH=. python docs/engineering/research/rl_loop/percase.py <iter-id> [MAP ...]
The iteration's gates.env is applied before importing src (gates are read at import and act at inference too).
Writes artifacts/benchmarks/rl-loop/<iter>/percase.json: {map: {policy, cases: {case: metrics}}}."""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
KEYS = ("delay_per_scheduled_s", "p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s", "completed",
        "scheduled", "collisions", "teleports")
ALG = "phase_dqn_unified"
SEED = int(os.environ.get("SEED", 17))  # learner seed of the iteration

if __name__ == "__main__":
    it, maps = sys.argv[1], sys.argv[2:]
    root = REPO / "artifacts/benchmarks/rl-loop" / it
    for line in (root / "gates.env").read_text().split():
        k, v = line.split("=", 1)
        os.environ[k] = v
    import numpy as np
    import torch
    from contracts.benchmark import SEEDS, DQN_RECIPE, UNIFIED_DQN as U
    from src.benchmark.scheduling import run_tasks
    from src.benchmark.unified_campaign import load_suite
    from src.rl.unified_train import PHASE_FAMILY

    out_all = json.loads((root / "percase.json").read_text()) if (root / "percase.json").exists() else {}
    maps = maps or sorted(p.name for p in (root / "training").iterdir())
    protocol = dict(demand_s=DQN_RECIPE["demand_s"], drain_s=DQN_RECIPE["drain_s"], trace=False, benchmark_mode=True,
                    check_every=25)
    for m in maps:
        spec = load_suite(root / "prepared.json", root, [m])["maps"][0]
        d = root / "training" / m / ALG / str(SEED)
        r = json.loads((d / "result.json").read_text())
        if r.get("selected"):
            path, which = r["selected"]["path"], f"selected ep {r['selected']['episode']}"
        else:
            net = PHASE_FAMILY.build_net(U["algorithms"][ALG][0])
            net.load_state_dict(torch.load(d / "checkpoint.pt", map_location="cpu", weights_only=False)["net"])
            path, which = str(d / "final-policy.json"), "final checkpoint (no feasible checkpoint)"
            PHASE_FAMILY.export(spec, ALG, net, SEED, Path(path))
        ctl = dict(type=ALG, model_path=path, learner_seed=SEED, parameters={})
        tasks = [(dict(map=spec, scenario=c, seed=s, controller=ctl), protocol, str(root / "percase-cases" / m))
                 for c in spec["cases"] for s in SEEDS["validation"]]
        rows = [x for x in run_tasks(tasks, 4, continue_on_error=True) if x is not None]
        by = {}
        for x in rows:
            by.setdefault(x["scenario"], []).append(x)
        out_all[m] = dict(policy=which, cases={
            c: {k: round(float(np.mean([x.get(k) or 0 for x in v])), 2) for k in KEYS}
            | {"valid": all(x["valid"] for x in v), "runs": len(v)} for c, v in by.items()})
        (root / "percase.json").write_text(json.dumps(out_all, indent=1))
        print("done", m, which, flush=True)
