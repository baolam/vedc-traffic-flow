import os
import json
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

from manifest import ExperimentManifest, ScenarioConfig, ControllerConfig
from runner import SingleExperimentRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("batch-runner")

SCENARIOS = ["balanced", "directional_surge", "downstream_congestion"]
CONTROLLERS = ["fixed_time", "max_pressure"]

class BatchRunner:
    def __init__(self, scenarios: List[str] = None, controllers: List[str] = None, seeds: List[int] = None, topology: str = "four_intersection_v1", duration_s: int = 10, output_dir: str = "artifacts"):
        self.scenarios = scenarios or SCENARIOS
        self.controllers = controllers or CONTROLLERS
        self.seeds = seeds or [42, 101, 202, 303, 404]
        self.topology = topology
        self.duration_s = duration_s
        self.output_dir = Path(output_dir)
        self.results: List[Dict[str, Any]] = []

    def run_all(self):
        total_runs = len(self.scenarios) * len(self.controllers) * len(self.seeds)
        logger.info(f"Starting Batch Experiment Runner ({self.topology}): {total_runs} total runs ({len(self.scenarios)} scenarios x {len(self.controllers)} controllers x {len(self.seeds)} seeds)")
        
        current_run = 0
        for scenario in self.scenarios:
            for controller in self.controllers:
                for seed in self.seeds:
                    current_run += 1
                    exp_id = f"{scenario}_{controller}_seed{seed}"
                    logger.info(f"[{current_run}/{total_runs}] Running experiment: {exp_id}")

                    manifest = ExperimentManifest(
                        experiment_id=exp_id,
                        topology=self.topology,
                        scenario=ScenarioConfig(name=scenario, duration_s=self.duration_s, random_seed=seed),
                        controller=ControllerConfig(type=controller, decision_interval_s=1.0)
                    )

                    runner = SingleExperimentRunner(manifest=manifest, artifacts_root=str(self.output_dir))
                    runner.run()

                    # Load summary
                    summary_file = runner.artifacts_dir / "summary.json"
                    if summary_file.exists():
                        with open(summary_file, "r", encoding="utf-8") as f:
                            summary_data = json.load(f)
                            self.results.append(summary_data)

        self.generate_comparison_reports()

    def generate_comparison_reports(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_json_file = self.output_dir / "benchmark_comparison_report.json"
        report_md_file = self.output_dir / "benchmark_summary.md"

        scenario_aggregates: Dict[str, Dict[str, Any]] = {}

        for scenario in self.scenarios:
            scenario_aggregates[scenario] = {}
            for ctrl in self.controllers:
                runs = [
                    r for r in self.results
                    if r.get("manifest", {}).get("scenario", {}).get("name") == scenario
                    and r.get("manifest", {}).get("controller", {}).get("type") == ctrl
                ]
                if not runs:
                    continue

                avg_waiting = sum(r.get("average_waiting_time_s", 0) for r in runs) / len(runs)
                avg_queue = sum(r.get("average_queue_veh", 0) for r in runs) / len(runs)
                max_queue = max(r.get("maximum_queue_veh", 0) for r in runs)
                avg_throughput = sum(r.get("throughput_veh_per_s", 0) for r in runs) / len(runs)

                scenario_aggregates[scenario][ctrl] = {
                    "total_runs": len(runs),
                    "average_waiting_time_s": round(avg_waiting, 2),
                    "average_queue_veh": round(avg_queue, 2),
                    "maximum_queue_veh": max_queue,
                    "throughput_veh_per_s": round(avg_throughput, 4)
                }

        # Calculate % Improvement (Max-Pressure vs Fixed-Time)
        improvements = {}
        for scenario in self.scenarios:
            ft = scenario_aggregates[scenario].get("fixed_time")
            mp = scenario_aggregates[scenario].get("max_pressure")
            if ft and mp:
                ft_wait = ft["average_waiting_time_s"]
                mp_wait = mp["average_waiting_time_s"]
                wait_reduction_pct = ((ft_wait - mp_wait) / max(ft_wait, 0.01)) * 100.0

                ft_q = ft["average_queue_veh"]
                mp_q = mp["average_queue_veh"]
                queue_reduction_pct = ((ft_q - mp_q) / max(ft_q, 0.01)) * 100.0

                ft_th = ft["throughput_veh_per_s"]
                mp_th = mp["throughput_veh_per_s"]
                throughput_gain_pct = ((mp_th - ft_th) / max(ft_th, 0.001)) * 100.0

                improvements[scenario] = {
                    "waiting_time_reduction_pct": round(wait_reduction_pct, 2),
                    "queue_length_reduction_pct": round(queue_reduction_pct, 2),
                    "throughput_gain_pct": round(throughput_gain_pct, 2)
                }

        report_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_completed_runs": len(self.results),
            "scenario_aggregates": scenario_aggregates,
            "improvements": improvements
        }

        with open(report_json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # Generate Markdown Summary Bảng So Sánh
        md_lines = [
            "# EdgeFlow AI - Benchmark Comparison Summary Report",
            "",
            f"**Generated at**: {report_data['timestamp']} | **Total Benchmark Runs**: {len(self.results)}",
            "",
            "## 📊 KPI Comparison Table (Fixed-Time Baseline vs Max-Pressure Adaptive Control)",
            "",
            "| Scenario | Controller | Avg Waiting Time (s) | Avg Queue (veh) | Max Queue (veh) | Throughput (veh/s) |",
            "|---|---|---|---|---|---|"
        ]

        for scenario in self.scenarios:
            for ctrl in self.controllers:
                data = scenario_aggregates[scenario].get(ctrl, {})
                if data:
                    md_lines.append(
                        f"| **{scenario}** | `{ctrl}` | {data.get('average_waiting_time_s')}s | {data.get('average_queue_veh')} veh | {data.get('maximum_queue_veh')} veh | {data.get('throughput_veh_per_s')} veh/s |"
                    )

        md_lines.extend([
            "",
            "## 🚀 EdgeFlow Max-Pressure Performance Gain Summary",
            "",
            "| Scenario | Waiting Time Reduction (%) | Queue Length Reduction (%) | Throughput Gain (%) |",
            "|---|---|---|---|"
        ])

        for scenario, imp in improvements.items():
            md_lines.append(
                f"| **{scenario}** | **-{imp['waiting_time_reduction_pct']}%** | **-{imp['queue_length_reduction_pct']}%** | **+{imp['throughput_gain_pct']}%** |"
            )

        md_lines.append("")
        with open(report_md_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        logger.info(f"Benchmark comparison reports generated:\n - JSON: {report_json_file}\n - Markdown: {report_md_file}")

def main():
    parser = argparse.ArgumentParser(description="EdgeFlow AI Batch Experiment Benchmark Orchestrator")
    parser.add_argument("--topology", type=str, default="four_intersection_v1", help="Topology contract ID")
    parser.add_argument("--duration", type=int, default=10, help="Run duration in seconds per experiment")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds (default: 5 seeds)")
    parser.add_argument("--output-dir", type=str, default="artifacts", help="Output directory")

    args = parser.parse_args()
    seed_list = [42 + i * 100 for i in range(args.seeds)]

    batch = BatchRunner(topology=args.topology, seeds=seed_list, duration_s=args.duration, output_dir=args.output_dir)
    batch.run_all()

if __name__ == "__main__":
    main()
