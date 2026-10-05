#!/usr/bin/env python3
"""
EdgeFlow AI — Complete SUMO Project Scenario Execution Pipeline.

This script executes a full-stack SUMO traffic simulation scenario integrating:
  1. Topology Contracts & Scenario Profiles (contracts_sdk, ScenarioRegistry).
  2. Graph Network Adaptive Controllers (EdgeFlow v2.5 / Max-Pressure / Actuated / Fixed-Time).
  3. Safe Actuator State Machine (Yellow 3.0s, All-Red 2.0s transitions).
  4. TraCI real-time telemetry extraction & microservice control loop.
  5. Multi-controller side-by-side performance benchmarking & report generation.

Usage:
    python experiments/run_project_scenario.py [--topology corridor] [--scenario directional_surge] [--controller all] [--duration 300] [--seed 42]
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# UTF-8 Encoding Fix for Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure services and contracts are in Python path
repo_root = Path(__file__).resolve().parents[1]
for p in [
    repo_root / "contracts",
    repo_root / "services" / "experiment-runner",
    repo_root / "services" / "graph-control",
    repo_root / "services" / "actuator",
    repo_root / "services" / "simulator",
]:
    if str(p) not in sys.path and p.exists():
        sys.path.insert(0, str(p))

import contracts_sdk
from sumo_runner import run_sumo_experiment, check_sumo_available


def print_banner(topology_id: str, scenario_id: str, duration_s: int, seed: int):
    """Print execution header banner."""
    print("=" * 72)
    print(" 🚥 EDGEFLOW AI — FULL-STACK SUMO SCENARIO EXECUTION")
    print("=" * 72)
    print(f" • Topology Contract  : {topology_id}")
    print(f" • Scenario Demand    : {scenario_id}")
    print(f" • Duration (seconds) : {duration_s}s")
    print(f" • Random Seed        : {seed}")
    print("=" * 72 + "\n")


def run_single_controller_scenario(
    controller_name: str,
    topology_id: str,
    scenario_id: str,
    duration_s: int,
    seed: int,
    output_dir: Path,
) -> Dict[str, Any]:
    """Execute a single simulation run for a given controller."""
    print(f"[▶] Running Scenario with Controller: '{controller_name.upper()}' ...")
    start_t = time.time()

    exp_dir = output_dir / f"run_{controller_name}_{scenario_id}"
    exp_dir.mkdir(parents=True, exist_ok=True)

    result = run_sumo_experiment(
        topology_id=topology_id,
        scenario=scenario_id,
        seed=seed,
        controller_name=controller_name,
        duration_s=duration_s,
        artifacts_dir=str(output_dir),
    )

    elapsed_s = time.time() - start_t
    if not result.get("valid", False):
        print(f"[❌] Error running controller '{controller_name}': {result.get('error')}")
        return {"valid": False, "controller": controller_name, "error": result.get("error")}

    trip_info = result.get("trip_summary", {})
    mean_wait = trip_info.get("mean_waiting_time_s", 0.0)
    p95_wait = trip_info.get("p95_waiting_time_s", 0.0)
    mean_speed = trip_info.get("mean_speed_mps", 0.0) * 3.6  # convert to km/h
    completed = trip_info.get("completed", 0)
    mean_queue = result.get("mean_queue_veh", 0.0)
    max_queue = result.get("max_queue_veh", 0.0)

    print(f"    ✓ Completed Vehicles   : {completed}")
    print(f"    ✓ Mean Waiting Time    : {mean_wait:.2f} s (P95: {p95_wait:.2f} s)")
    print(f"    ✓ Mean Queue Length    : {mean_queue:.2f} veh (Max: {max_queue:.2f} veh)")
    print(f"    ✓ Mean Vehicle Speed   : {mean_speed:.2f} km/h")
    print(f"    ✓ Execution Time       : {elapsed_s:.2f} s\n")

    return {
        "valid": True,
        "controller": controller_name,
        "completed": completed,
        "mean_waiting_time_s": mean_wait,
        "p95_waiting_time_s": p95_wait,
        "mean_queue_veh": mean_queue,
        "max_queue_veh": max_queue,
        "mean_speed_kmh": mean_speed,
        "execution_time_s": elapsed_s,
    }


def print_comparison_table(results: List[Dict[str, Any]]):
    """Print side-by-side performance comparison table."""
    valid_results = [r for r in results if r.get("valid", False)]
    if not valid_results:
        print("[!] No valid simulation results to display.")
        return

    print("=" * 85)
    print(" 📊 SCENARIO BENCHMARK COMPARISON MATRIX")
    print("=" * 85)
    header = f"{'Controller':<15} | {'Arrived':<8} | {'Avg Wait (s)':<13} | {'P95 Wait (s)':<13} | {'Avg Queue':<10} | {'Speed (km/h)':<12}"
    print(header)
    print("-" * 85)

    baseline_wait = None
    for r in valid_results:
        ctrl = r["controller"].upper()
        arr = r["completed"]
        wait = r["mean_waiting_time_s"]
        p95 = r["p95_waiting_time_s"]
        q = r["mean_queue_veh"]
        spd = r["mean_speed_kmh"]

        if baseline_wait is None:
            baseline_wait = wait

        print(f"{ctrl:<15} | {arr:<8} | {wait:<13.2f} | {p95:<13.2f} | {q:<10.2f} | {spd:<12.2f}")

    print("=" * 85)

    # Highlight EdgeFlow improvement if available
    edgeflow_res = next((r for r in valid_results if r["controller"] == "edgeflow"), None)
    fixed_res = next((r for r in valid_results if r["controller"] == "fixed_time"), None)
    maxp_res = next((r for r in valid_results if r["controller"] == "max_pressure"), None)

    if edgeflow_res and fixed_res:
        ef_w = edgeflow_res["mean_waiting_time_s"]
        ft_w = fixed_res["mean_waiting_time_s"]
        impr_ft = ((ft_w - ef_w) / ft_w) * 100.0 if ft_w > 0 else 0.0
        print(f" 🚀 EdgeFlow vs Fixed-Time   : {impr_ft:+.1f}% waiting time reduction")

    if edgeflow_res and maxp_res:
        ef_w = edgeflow_res["mean_waiting_time_s"]
        mp_w = maxp_res["mean_waiting_time_s"]
        impr_mp = ((mp_w - ef_w) / mp_w) * 100.0 if mp_w > 0 else 0.0
        print(f" 🎯 EdgeFlow vs Max-Pressure : {impr_mp:+.1f}% waiting time reduction")
    print("=" * 85 + "\n")


def export_scenario_artifacts(output_dir: Path, summary_data: Dict[str, Any]):
    """Save results as JSON and CSV artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "scenario_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    import csv
    csv_path = output_dir / "scenario_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "controller", "completed_vehicles", "mean_waiting_time_s",
            "p95_waiting_time_s", "mean_queue_veh", "max_queue_veh", "mean_speed_kmh"
        ])
        for r in summary_data.get("results", []):
            if r.get("valid", False):
                writer.writerow([
                    r["controller"], r["completed"], r["mean_waiting_time_s"],
                    r["p95_waiting_time_s"], r["mean_queue_veh"], r["max_queue_veh"],
                    r["mean_speed_kmh"]
                ])

    print(f"[✓] Saved JSON artifact: {json_path}")
    print(f"[✓] Saved CSV artifact : {csv_path}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="EdgeFlow AI — Complete SUMO Project Scenario Runner")
    parser.add_argument("--topology", type=str, default="corridor", help="Topology ID (corridor, junction, grid16, cologne)")
    parser.add_argument("--scenario", type=str, default="directional_surge", help="Scenario profile (directional_surge, balanced, downstream_congestion)")
    parser.add_argument("--controller", type=str, default="all", help="Controller type (edgeflow, max_pressure, actuated, fixed_time, or all)")
    parser.add_argument("--duration", type=int, default=300, help="Simulation duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output-dir", type=str, default="experiments/output_project_scenario", help="Output directory")

    args = parser.parse_args()

    # Check SUMO availability
    status = check_sumo_available()
    if not status["sumo_available"] or not status["traci_available"]:
        print(f"[❌] Error: SUMO or TraCI is not available on this environment.")
        print(f"    Details: SUMO={status['sumo_available']}, TraCI={status['traci_available']}")
        sys.exit(1)

    topology_id = contracts_sdk.resolve_topology_id(args.topology)
    scenario_id = args.scenario
    duration_s = args.duration
    seed = args.seed
    output_dir = repo_root / args.output_dir

    print_banner(topology_id, scenario_id, duration_s, seed)

    if args.controller == "all":
        controllers_to_run = ["fixed_time", "actuated", "max_pressure", "edgeflow"]
    else:
        controllers_to_run = [args.controller]

    results = []
    for ctrl in controllers_to_run:
        res = run_single_controller_scenario(
            controller_name=ctrl,
            topology_id=topology_id,
            scenario_id=scenario_id,
            duration_s=duration_s,
            seed=seed,
            output_dir=output_dir,
        )
        results.append(res)

    print_comparison_table(results)

    summary_data = {
        "topology_id": topology_id,
        "scenario_id": scenario_id,
        "duration_s": duration_s,
        "seed": seed,
        "results": results,
    }
    export_scenario_artifacts(output_dir, summary_data)


if __name__ == "__main__":
    main()
