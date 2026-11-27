"""One table per map: deterministic controllers + learned variants, guardrail vs tuned Fixed-Time, per-case means."""
import json, os, glob, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, os.environ.get("REPO", "."))
from contracts.benchmark import SEEDS
from src.rl.selection import validation_score
D = Path(os.environ.get("EXP_ROOT", "diag-exp"))
MAPS = ["hcm_neighborhood_v3_benchmark_v1", "jakarta_menteng_v1", "hanoi_dong_da_v1", "cologne8_benchmark_v1", "grid4x4_benchmark_v1", "four_intersection_rl_v1"]
LEARNED = {"DQN campaign": "dqnnode/percase/{m}/campaign", "DQN node+tail": "dqnnode/percase/{m}/node_tail",
           "DQN node+tail+obs2": "dqnobs/percase/{m}/node_tail_obs2",
           "graph MAPPO cyc": "cycleact/percase/{m}/graph_mappo_unified", "local MAPPO cyc": "cycleact/percase/{m}/local_mappo_unified",
           "graph MAPPO cyc+obs2": "obsfeat/percase/{m}/graph_mappo_unified", "local MAPPO cyc+obs2": "obsfeat/percase/{m}/local_mappo_unified"}
def cases_rows(p):
    return [json.load(open(f))["metrics"] for f in glob.glob(str(D / p / "cases/*/complete.json"))]
out = {}
for m in MAPS:
    base = json.load(open(D / "baselines" / m / "rows.json"))
    ref = base["fixed_time"]
    cases = list(dict.fromkeys(r["scenario"] for r in ref))
    sets = {k: v for k, v in base.items()} | {k: cases_rows(p.format(m=m)) for k, p in LEARNED.items()}
    out[m] = {}
    for name, rows in sets.items():
        if isinstance(rows, str) or not rows:
            out[m][name] = dict(error="n/a" if isinstance(rows, str) else "missing"); continue
        g = validation_score(rows, ref, cases, SEEDS["validation"])
        per = {c: [round(float(np.mean([r[k] for r in rows if r["scenario"] == c])), 1) for k in ("delay_per_scheduled_s", "p95_wait_s", "worst_approach_wait_s")] for c in cases}
        out[m][name] = dict(score=round(g["score"], 1), feasible=g["feasible"], fails=len(g["reasons"]), cases=per)
json.dump(out, open(D / "comparison.json", "w"), indent=1)
for m, t in out.items():
    print("=====", m)
    for n, v in sorted(t.items(), key=lambda kv: kv[1].get("score", 1e9)):
        if "error" in v: print(f"  {n:22s} {v['error']}"); continue
        print(f"  {n:22s} {v['score']:7.1f} {'OK ' if v['feasible'] else 'x%-2d' % v['fails']} " + " | ".join(f"{c[:10]} {'/'.join(map(str, x))}" for c, x in v["cases"].items()))
