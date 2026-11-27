"""Test-seed benchmark (80001-80020: the contract's 10 test seeds plus 10 more) of one controller group on the given maps, full campaign protocol
(trace=True, full checks). Writes OUT/<group>/<map>/rows.json = {controller: [metrics rows] | "error"}.
Usage: PYTHONPATH=. python bench.py det [MAP ...]            (gates from the caller's env, e.g. EDGEFLOW_MAX_RED=40)
       PYTHONPATH=. python bench.py <iter>:<seed> [MAP ...]  (learned phase DQN; the iteration's gates.env is applied
                                                            before importing src, since gates are read at import)"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
LOOP = REPO / "artifacts/benchmarks/rl-loop"
OUT = Path(os.environ.get("BENCH_OUT", REPO / "artifacts/benchmarks/test-benchmark-20261126"))
GROUP = os.environ.get("BENCH_GROUP")  # output folder name; defaults to the first argument
DET = ("fixed_time", "actuated", "max_queue", "max_pressure", "edgeflow", "flow_theory", "fair_cycle", "fair_cycle_native")
ALG = "phase_dqn_unified"
# The contract test split (80001-80010) extended to 80001-80020 for this benchmark only (user, 2026-11-26).
TEST_SEEDS = list(range(80001, 80021))
WORKERS = int(os.environ.get("BENCH_WORKERS", 4))

if __name__ == "__main__":
    which, maps = sys.argv[1], sys.argv[2:]
    learned = ":" in which
    if learned:
        it, seed = which.split(":")
        seed = int(seed)
        for line in (LOOP / it / "gates.env").read_text().split():
            k, v = line.split("=", 1)
            os.environ[k] = v
    from src.benchmark.scheduling import run_tasks
    from src.benchmark.unified_campaign import PROTOCOL, load_suite

    base = REPO / "artifacts/benchmarks/unified-v1"
    suite = load_suite(base / "prepared.json", base, maps or None)
    for spec in suite["maps"]:
        m = spec["id"]
        out = OUT / (GROUP or which.replace(":", "-")) / m
        out.mkdir(parents=True, exist_ok=True)
        if learned:
            d = LOOP / it / "training" / m / ALG / str(seed)
            r = json.loads((d / "result.json").read_text())
            if r.get("selected"):
                path, policy = r["selected"]["path"], f"selected ep {r['selected']['episode']}"
            else:  # no checkpoint passed validation: evaluate the final checkpoint, as percase.py does
                path, policy = d / "final-policy.json", "final checkpoint (no feasible checkpoint)"
                if not path.exists():
                    import torch
                    from contracts.benchmark import UNIFIED_DQN as U
                    from src.rl.unified_train import PHASE_FAMILY
                    net = PHASE_FAMILY.build_net(U["algorithms"][ALG][0])
                    net.load_state_dict(torch.load(d / "checkpoint.pt", map_location="cpu", weights_only=False)["net"])
                    PHASE_FAMILY.export(spec, ALG, net, seed, path)
            controllers = {ALG: dict(type=ALG, model_path=str(path), learner_seed=seed, parameters={})}
            (out / "policy.json").write_text(json.dumps(dict(path=str(path), policy=policy)))
        else:
            controllers = {c: spec.get("controller_overrides", {}).get(c, dict(type=c, parameters={})) for c in DET}
        rows = {}
        for name, ctl in controllers.items():
            tasks = [(dict(map=spec, scenario=c, seed=s, controller=ctl), PROTOCOL, str(out / "cases" / name))
                     for c in spec["cases"] for s in TEST_SEEDS]
            try:
                rows[name] = run_tasks(tasks, WORKERS, continue_on_error=True)  # a failed case stays visible as null
            except Exception as e:  # e.g. legacy fair_cycle is two-phase only
                rows[name] = str(e)[-400:]
            print(m, name, "error" if isinstance(rows[name], str) else f'{sum(x is not None for x in rows[name])}/{len(tasks)}', flush=True)
            (out / "rows.json").write_text(json.dumps(rows))
        print("done", m, flush=True)
