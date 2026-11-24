"""How often a residual policy overrides max_pressure: one in-process validation run per map and case.
Usage: PYTHONPATH=. python docs/engineering/research/rl_loop/deviation.py <iter-id> [seed=70001] [MAP ...]"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

if __name__ == "__main__":
    it, vseed = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 70001
    root = REPO / "artifacts/benchmarks/rl-loop" / it
    for line in (root / "gates.env").read_text().split():
        k, v = line.split("=", 1)
        os.environ[k] = v
    from contracts.benchmark import DQN_RECIPE
    from src.benchmark.cli import execute
    from src.benchmark.unified_campaign import load_suite
    from src.control import unified_dqn as ud

    stats, orig = {}, ud.residual_choice

    def counted(values, mask, mp_index):
        choice = orig(values, mask, mp_index)
        free = int(mask.sum()) > 1 and bool(mask[mp_index])  # decisions where the residual had a real choice
        greedy = int(ud.np.argmax(ud.np.where(mask, values, -ud.np.inf)))
        stats["free"] = stats.get("free", 0) + free
        stats["override"] = stats.get("override", 0) + (free and choice != mp_index)
        stats["greedy_differs"] = stats.get("greedy_differs", 0) + (free and greedy != mp_index)
        return choice

    ud.residual_choice = counted
    protocol = dict(demand_s=DQN_RECIPE["demand_s"], drain_s=DQN_RECIPE["drain_s"], trace=False, benchmark_mode=True,
                    check_every=25)
    out = {}
    only = sys.argv[3:]  # optional map filter
    for m in sorted(p.name for p in (root / "training").iterdir()):
        if only and m not in only:
            continue
        r = json.loads((root / "training" / m / "phase_dqn_unified/17/result.json").read_text())
        if not r.get("selected"):
            continue
        spec = load_suite(root / "prepared.json", root, [m])["maps"][0]
        ctl = dict(type="phase_dqn_unified", model_path=r["selected"]["path"], learner_seed=17, parameters={})
        for case in spec["cases"]:
            stats.clear()
            execute((dict(map=spec, scenario=case, seed=vseed, controller=ctl), protocol, str(root / "deviation-cases" / m)))
            f = max(stats.get("free", 0), 1)
            out.setdefault(m, {})[case] = dict(free=stats.get("free", 0), override=round(stats.get("override", 0) / f, 3),
                                               greedy_differs=round(stats.get("greedy_differs", 0) / f, 3))
            print(m, case, out[m][case], flush=True)
    (root / "deviation.json").write_text(json.dumps(out, indent=1))
