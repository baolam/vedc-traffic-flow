"""
P0 TASK 10 — Small Validation Matrix (8 runs).

Scenario: balanced
Seeds: 101, 202
Controllers: fixed_time, max_queue, max_pressure, edgeflow

= 2 seeds × 4 controllers = 8 runs.

Purpose: validate the pipeline, NOT compare performance.
"""

import sys
import json
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
exp_runner_dir = repo_root / "services" / "experiment-runner"
sys.path.insert(0, str(exp_runner_dir))
for p in [repo_root / "contracts", repo_root / "services" / "graph-control", repo_root / "services" / "actuator"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from batch_runner import BatchRunner


def main():
    output_dir = str(repo_root / "artifacts" / "p0_validation")

    batch = BatchRunner(
        scenarios=["balanced"],
        controllers=["fixed_time", "max_queue", "max_pressure", "edgeflow"],
        seeds=[101, 202],
        topology="four_intersection_v1",
        duration_s=20,
        output_dir=output_dir,
        mode="deterministic_sim",
    )
    batch.run_all()

    # ---- Post-run validation ----
    print("\n" + "=" * 60)
    print("P0 VALIDATION MATRIX RESULTS")
    print("=" * 60)

    out_path = Path(output_dir)
    demand_hashes_by_seed = {}
    all_valid = True
    issues = []

    for seed in [101, 202]:
        for ctrl in ["fixed_time", "max_queue", "max_pressure", "edgeflow"]:
            exp_id = f"four_intersection_v1_balanced_{ctrl}_seed{seed}"
            exp_dir = out_path / exp_id

            # Check artifacts exist
            required = ["manifest.yaml", "environment.json", "demand.json",
                        "metrics.csv", "signal_events.jsonl", "faults.jsonl",
                        "summary.json", "validity.json"]
            missing = [f for f in required if not (exp_dir / f).exists()]
            if missing:
                issues.append(f"[{exp_id}] Missing artifacts: {missing}")
                all_valid = False
                continue

            # Check validity
            with open(exp_dir / "validity.json") as f:
                validity = json.load(f)
            if not validity.get("valid", False):
                issues.append(f"[{exp_id}] INVALID: {validity.get('faults', [])}")
                all_valid = False

            # Check demand hash consistency
            with open(exp_dir / "summary.json") as f:
                summary = json.load(f)

            dhash = summary.get("demand_hash")
            if seed not in demand_hashes_by_seed:
                demand_hashes_by_seed[seed] = dhash
            elif demand_hashes_by_seed[seed] != dhash:
                issues.append(
                    f"[{exp_id}] DEMAND HASH MISMATCH for seed {seed}: "
                    f"expected={demand_hashes_by_seed[seed]} got={dhash}"
                )
                all_valid = False

            # Check controller identity
            req_ctrl = summary.get("requested_controller")
            if req_ctrl != ctrl:
                issues.append(f"[{exp_id}] Controller mismatch: req={ctrl} got={req_ctrl}")
                all_valid = False

            # Check no synthetic
            if summary.get("is_synthetic", True):
                issues.append(f"[{exp_id}] Run is marked synthetic!")
                all_valid = False

            # Check metrics finite
            for metric in ["average_queue_veh", "average_waiting_time_s",
                           "throughput_veh_per_s", "mean_network_speed_mps"]:
                val = summary.get(metric, None)
                if val is None or not isinstance(val, (int, float)):
                    issues.append(f"[{exp_id}] Metric {metric} is not a number: {val}")
                    all_valid = False

            print(f"  [{exp_id}] valid={validity.get('valid')} | "
                  f"avg_q={summary.get('average_queue_veh')} | "
                  f"avg_wait={summary.get('average_waiting_time_s')}s | "
                  f"throughput={summary.get('throughput_veh_per_s')} | "
                  f"speed={summary.get('mean_network_speed_mps')} | "
                  f"demand_hash={dhash}")

    print()
    if issues:
        print("ISSUES FOUND:")
        for iss in issues:
            print(f"  ❌ {iss}")
    else:
        print("✅ No issues found.")

    print()
    print(f"Demand hashes by seed: {demand_hashes_by_seed}")
    print(f"\nVERDICT: {'PASS' if all_valid else 'FAIL'}")
    print(f"All artifacts in: {out_path.resolve()}")


if __name__ == "__main__":
    main()
