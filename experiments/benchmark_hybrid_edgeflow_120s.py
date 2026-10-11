"""
Benchmark execution script for EdgeFlow Hybrid CTM + Max-Pressure.
Runs SUMO 120s across 3 scenarios with 4 controllers:
  - fixed_time
  - max_pressure
  - flow_theory
  - edgeflow (Hybrid CTM + Max-Pressure)
"""
import os
import sys
import json
import time
from pathlib import Path

# Threading env vars to avoid OpenBLAS contention on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "services" / "experiment-runner"))
sys.path.insert(0, str(repo_root / "services" / "graph-control"))
sys.path.insert(0, str(repo_root / "contracts"))
sys.path.insert(0, str(repo_root))

from sumo_runner import run_sumo_experiment

TOPOLOGY = "four_intersection_v1"
SCENARIOS = ["balanced", "directional_surge", "downstream_congestion"]
CONTROLLERS = ["fixed_time", "max_pressure", "flow_theory", "edgeflow"]
SEED = 101
DURATION_S = 120
ARTIFACTS_DIR = str(repo_root / "artifacts" / "benchmark_120s")

def main():
    print("=" * 80)
    print("  EDGEFLOW HYBRID BENCHMARK (SUMO Micro-Simulation, 120s)")
    print(f"  Topology: {TOPOLOGY} | Seed: {SEED} | Duration: {DURATION_S}s")
    print(f"  Controllers: {CONTROLLERS}")
    print(f"  Scenarios: {SCENARIOS}")
    print("=" * 80)

    results = []
    total = len(SCENARIOS) * len(CONTROLLERS)
    step = 0

    for sc in SCENARIOS:
        print(f"\n>>> Running Scenario: {sc.upper()}")
        for ctrl in CONTROLLERS:
            step += 1
            print(f"[{step}/{total}] Simulating {sc} with {ctrl} (120s)...", end=" ", flush=True)
            t0 = time.time()
            try:
                res = run_sumo_experiment(
                    topology_id=TOPOLOGY,
                    scenario=sc,
                    seed=SEED,
                    controller_name=ctrl,
                    duration_s=DURATION_S,
                    artifacts_dir=ARTIFACTS_DIR,
                )
                elapsed = time.time() - t0
                valid = res.get("valid", False)
                mean_wait = res.get("mean_waiting_time_s", 0.0)
                mean_q = res.get("mean_queue_veh", 0.0)
                p95_wait = res.get("p95_waiting_time_s", 0.0)
                arrived = res.get("total_arrived", 0)
                print(f"DONE in {elapsed:.1f}s | Valid: {valid} | Wait: {mean_wait:.2f}s | Q: {mean_q:.2f} | Arrived: {arrived}")
                results.append(res)
            except Exception as e:
                print(f"FAILED ({e})")
                results.append({
                    "valid": False,
                    "error": str(e),
                    "scenario": sc,
                    "requested_controller": ctrl,
                    "seed": SEED,
                })

    # Save complete JSON
    out_json = Path(ARTIFACTS_DIR) / "benchmark_120s_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved raw results to {out_json}")

    # Generate Markdown Summary
    lines = [
        "# EdgeFlow Hybrid Benchmark Report (120s SUMO Simulation)",
        "",
        f"- **Simulation Engine**: Eclipse SUMO (TraCI)",
        f"- **Topology**: `{TOPOLOGY}` (4 Intersections)",
        f"- **Duration**: `{DURATION_S}s` | **Seed**: `{SEED}`",
        f"- **Controllers Tested**: `fixed_time`, `max_pressure`, `flow_theory`, `edgeflow` (Proposed Hybrid)",
        "",
        "## 1. Performance Matrix",
        "",
        "| Scenario | Controller | Mean Wait (s) | P95 Wait (s) | Mean Queue (veh) | Completed Trips | Mean Speed (m/s) | CO2 (g) |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for sc in SCENARIOS:
        sc_res = [r for r in results if r.get("scenario") == sc and r.get("valid")]
        for r in sc_res:
            ctrl = r.get("requested_controller")
            mean_wait = r.get("mean_waiting_time_s", 0.0)
            p95_wait = r.get("p95_waiting_time_s", 0.0)
            mean_q = r.get("mean_queue_veh", 0.0)
            arrived = r.get("total_arrived", 0)
            speed = r.get("mean_speed_mps", 0.0)
            co2 = round(r.get("total_co2_mg", 0.0) / 1000.0, 1)  # convert mg to g
            name = f"**{ctrl}**" if ctrl == "edgeflow" else f"`{ctrl}`"
            lines.append(f"| **{sc}** | {name} | {mean_wait:.2f}s | {p95_wait:.2f}s | {mean_q:.2f} | {arrived} | {speed:.2f} m/s | {co2}g |")

    lines.extend([
        "",
        "## 2. Improvements vs Fixed-Time Baseline",
        "",
        "| Scenario | Controller | Wait Reduction (%) | Queue Reduction (%) | Throughput Gain (%) |",
        "|:---|:---|:---:|:---:|:---:|",
    ])

    for sc in SCENARIOS:
        sc_res = {r.get("requested_controller"): r for r in results if r.get("scenario") == sc and r.get("valid")}
        base = sc_res.get("fixed_time")
        if base:
            base_w = base.get("mean_waiting_time_s", 1.0)
            base_q = base.get("mean_queue_veh", 1.0)
            base_trips = max(1, base.get("total_arrived", 1))
            for ctrl in CONTROLLERS:
                if ctrl == "fixed_time":
                    continue
                r = sc_res.get(ctrl)
                if r:
                    w = r.get("mean_waiting_time_s", 0.0)
                    q = r.get("mean_queue_veh", 0.0)
                    trips = r.get("total_arrived", 0)
                    w_red = ((base_w - w) / base_w) * 100.0
                    q_red = ((base_q - q) / base_q) * 100.0
                    t_gain = ((trips - base_trips) / base_trips) * 100.0
                    name = f"🔥 **{ctrl}**" if ctrl == "edgeflow" else f"`{ctrl}`"
                    lines.append(f"| **{sc}** | {name} | **{w_red:+.1f}%** | **{q_red:+.1f}%** | **{t_gain:+.1f}%** |")

    out_md = Path(ARTIFACTS_DIR) / "benchmark_120s_summary.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved markdown report to {out_md}\n")
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("\n".join(lines))

if __name__ == "__main__":
    main()
