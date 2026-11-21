"""Per-case validation metrics: campaign phase DQN vs per-node-reward phase DQN (seed 17; selected policy, else final checkpoint)."""
import json, os, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, os.environ["WORKTREE"])  # checkout with the experiment patch applied
from contracts.benchmark import SEEDS, DQN_RECIPE, UNIFIED_DQN as U
from src.rl.unified_train import PHASE_FAMILY
from src.benchmark.scheduling import run_tasks
from src.benchmark.unified_campaign import load_suite
CAMPAIGN = Path(os.environ.get("REPO", ".")) / "artifacts/benchmarks/unified-v1"
NEW = Path(os.environ.get("EXP_ROOT", "diag-exp")) / "dqnnode"
KEYS = ("delay_per_scheduled_s", "p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s", "completed", "scheduled", "collisions", "teleports")
ALG = "phase_dqn_unified"

def policy(spec, d, out):
    r = json.loads((d / "result.json").read_text()) if (d / "result.json").exists() else {}
    if r.get("selected"):
        return r["selected"]["path"], f"selected ep {r['selected']['episode']}"
    net = PHASE_FAMILY.build_net(U["algorithms"][ALG][0])
    net.load_state_dict(torch.load(d / "checkpoint.pt", map_location="cpu", weights_only=False)["net"])
    PHASE_FAMILY.export(spec, ALG, net, 17, out)
    return str(out), "final checkpoint"

if __name__ == "__main__":
    for MAP in sys.argv[1:]:
        spec = load_suite(CAMPAIGN / "prepared.json", CAMPAIGN, [MAP])["maps"][0]
        out = NEW / "percase" / MAP
        out.mkdir(parents=True, exist_ok=True)
        protocol = dict(demand_s=DQN_RECIPE["demand_s"], drain_s=DQN_RECIPE["drain_s"], trace=False, benchmark_mode=True, check_every=25)
        summ, which = {}, {}
        for name, root in (("campaign", CAMPAIGN), ("node_tail", NEW)):
            path, which[name] = policy(spec, root / "training" / MAP / ALG / "17", out / f"{name}.json")
            ctl = dict(type=ALG, model_path=path, learner_seed=17, parameters={})
            tasks = [(dict(map=spec, scenario=c, seed=s, controller=ctl), protocol, str(out / name / "cases"))
                     for c in spec["cases"] for s in SEEDS["validation"]]
            try:
                rows = run_tasks(tasks, 4)
            except Exception as e:
                summ[name] = str(e)[-300:]
                continue
            t = {}
            for r in rows:
                t.setdefault(r["scenario"], []).append(r)
            summ[name] = {c: {k: round(float(np.mean([x.get(k) or 0 for x in v])), 2) for k in KEYS} | {"valid": all(x["valid"] for x in v)} for c, v in t.items()}
        json.dump(dict(metrics=summ, policy=which), open(out / "summary.json", "w"), indent=1)
        print("done", MAP, flush=True)
