"""
EdgeFlow AI — Batch Benchmark Orchestrator (P0).

Runs a paired experiment matrix (Topology x Scenario x Controller x Seed)
with scientifically valid controls:

  1. Same demand for same (scenario, seed) regardless of controller.
  2. Demand hash verification before each run.
  3. Failed/invalid runs are recorded but excluded from aggregation.
  4. Synthetic/mock runs are blocked from research summaries.
  5. Complete per-run evidence packages.
"""

import json
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Union

from manifest import ExperimentManifest, ScenarioConfig, ControllerConfig
from runner import SingleExperimentRunner, DemandGenerator, compute_hash

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("batch-runner")

SCENARIOS = ["balanced", "directional_surge", "downstream_congestion"]
CONTROLLERS = ["fixed_time", "max_queue", "max_pressure", "flow_theory", "edgeflow"]
TOPOLOGIES = ["four_intersection_v1", "grid4x4", "cologne8", "hcm_corridor", "hcm_realworld_v1"]
SEEDS = [101, 202, 303, 404, 505]


class BatchRunner:
    """
    Standardized Batch Benchmark Orchestrator.
    Executes paired experiment matrix and produces statistical comparison.
    """

    def __init__(
        self,
        scenarios: List[str] = None,
        controllers: List[str] = None,
        seeds: List[int] = None,
        topology: Union[str, List[str]] = "four_intersection_v1",
        duration_s: int = 20,
        output_dir: str = "artifacts",
        mode: str = "deterministic_sim",
    ):
        self.scenarios = scenarios or SCENARIOS
        self.controllers = controllers or CONTROLLERS
        self.seeds = seeds or SEEDS

        if isinstance(topology, list):
            self.topologies = [t.strip().replace("-", "_") for t in topology]
        elif isinstance(topology, str):
            clean_top = topology.strip().replace("-", "_")
            if clean_top.lower() == "all":
                self.topologies = ["four_intersection_v1", "grid4x4", "cologne8", "hcm_corridor"]
            else:
                self.topologies = [clean_top]
        else:
            self.topologies = ["four_intersection_v1"]

        self.duration_s = duration_s
        self.output_dir = Path(output_dir)
        self.mode = mode
        self.results: List[Dict[str, Any]] = []
        self.failed_runs: List[Dict[str, Any]] = []

        # Demand hash registry: {(topology, scenario, seed): hash}
        self.demand_hashes: Dict[tuple, str] = {}

    def run_all(self):
        total_runs = (
            len(self.topologies)
            * len(self.scenarios)
            * len(self.controllers)
            * len(self.seeds)
        )
        logger.info(
            f"Starting Batch Benchmark Orchestrator:\n"
            f"  Topologies ({len(self.topologies)}): {self.topologies}\n"
            f"  Scenarios ({len(self.scenarios)}): {self.scenarios}\n"
            f"  Controllers ({len(self.controllers)}): {self.controllers}\n"
            f"  Seeds ({len(self.seeds)}): {self.seeds}\n"
            f"  Mode: {self.mode}\n"
            f"  -> Total Runs: {total_runs}"
        )

        current_run = 0
        for top_id in self.topologies:
            for scenario in self.scenarios:
                for seed in self.seeds:
                    # Pre-compute and verify demand hash for this (scenario, seed)
                    demand_key = (top_id, scenario, seed)
                    if demand_key not in self.demand_hashes:
                        try:
                            from contracts import contracts_sdk
                        except ImportError:
                            import contracts_sdk
                        topo = contracts_sdk.load_topology(top_id)
                        demand = DemandGenerator.generate(
                            scenario, seed, self.duration_s, topo
                        )
                        self.demand_hashes[demand_key] = demand["hash"]

                    for controller in self.controllers:
                        current_run += 1
                        exp_id = f"{top_id}_{scenario}_{controller}_seed{seed}"
                        logger.info(
                            f"[{current_run}/{total_runs}] Running: {exp_id}"
                        )

                        manifest = ExperimentManifest(
                            experiment_id=exp_id,
                            topology=top_id,
                            scenario=ScenarioConfig(
                                name=scenario,
                                duration_s=self.duration_s,
                                random_seed=seed,
                            ),
                            controller=ControllerConfig(
                                type=controller, decision_interval_s=1.0
                            ),
                        )

                        try:
                            runner = SingleExperimentRunner(
                                manifest=manifest,
                                artifacts_root=str(self.output_dir),
                                mode=self.mode,
                            )
                            valid = runner.run()

                            # TASK 7: Verify demand hash consistency
                            expected_hash = self.demand_hashes[demand_key]
                            actual_hash = runner.demand_hash
                            if actual_hash != expected_hash:
                                logger.error(
                                    f"DEMAND HASH MISMATCH for {exp_id}: "
                                    f"expected={expected_hash} actual={actual_hash}"
                                )
                                valid = False

                            # Load summary
                            summary_file = runner.artifacts_dir / "summary.json"
                            if summary_file.exists():
                                with open(summary_file, "r", encoding="utf-8") as f:
                                    summary_data = json.load(f)
                                    if valid and summary_data.get("valid_for_research", False):
                                        self.results.append(summary_data)
                                    else:
                                        self.failed_runs.append({
                                            "experiment_id": exp_id,
                                            "reason": "invalid_or_synthetic",
                                            "summary": summary_data,
                                        })
                            else:
                                self.failed_runs.append({
                                    "experiment_id": exp_id,
                                    "reason": "no_summary_file",
                                })

                        except Exception as e:
                            logger.error(f"Experiment {exp_id} FAILED: {e}")
                            self.failed_runs.append({
                                "experiment_id": exp_id,
                                "reason": str(e),
                            })

        logger.info(
            f"Batch complete: {len(self.results)} valid, "
            f"{len(self.failed_runs)} failed/invalid"
        )
        self.generate_comparison_reports()

    def generate_comparison_reports(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_json_file = self.output_dir / "benchmark_comparison_report.json"
        report_md_file = self.output_dir / "benchmark_summary.md"

        # Aggregate by topology/scenario/controller
        topology_aggregates: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for top_id in self.topologies:
            topology_aggregates[top_id] = {}
            for scenario in self.scenarios:
                topology_aggregates[top_id][scenario] = {}
                for ctrl in self.controllers:
                    runs = [
                        r
                        for r in self.results
                        if r.get("manifest", {}).get("topology") == top_id
                        and r.get("manifest", {}).get("scenario", {}).get("name") == scenario
                        and r.get("requested_controller") == ctrl
                    ]
                    if not runs:
                        continue

                    # Compute statistics
                    queues = [r.get("average_queue_veh", 0.0) for r in runs]
                    waitings = [r.get("average_waiting_time_s", 0.0) for r in runs]
                    max_queues = [r.get("maximum_queue_veh", 0.0) for r in runs]
                    p95_queues = [r.get("p95_queue_veh", 0.0) for r in runs]
                    throughputs = [r.get("throughput_veh_per_s", 0.0) for r in runs]
                    speeds = [r.get("mean_network_speed_mps", 0.0) for r in runs]

                    n = len(runs)
                    topology_aggregates[top_id][scenario][ctrl] = {
                        "valid_runs": n,
                        "average_waiting_time_s": round(sum(waitings) / n, 2),
                        "average_queue_veh": round(sum(queues) / n, 2),
                        "maximum_queue_veh": round(max(max_queues), 2),
                        "p95_queue_veh": round(sum(p95_queues) / n, 2),
                        "throughput_veh_per_s": round(sum(throughputs) / n, 4),
                        "mean_network_speed_mps": round(sum(speeds) / n, 2),
                        "demand_hashes": list(set(
                            r.get("demand_hash", "?") for r in runs
                        )),
                    }

        # Improvements vs Fixed-Time
        improvements: Dict[str, Any] = {}
        for top_id in self.topologies:
            improvements[top_id] = {}
            for scenario in self.scenarios:
                scen_data = topology_aggregates[top_id].get(scenario, {})
                ft = scen_data.get("fixed_time")
                improvements[top_id][scenario] = {}

                for ctrl in self.controllers:
                    if ctrl == "fixed_time":
                        continue
                    cand = scen_data.get(ctrl)
                    if ft and cand:
                        ft_wait = ft["average_waiting_time_s"]
                        cand_wait = cand["average_waiting_time_s"]
                        wait_red = ((ft_wait - cand_wait) / max(ft_wait, 0.01)) * 100

                        ft_q = ft["average_queue_veh"]
                        cand_q = cand["average_queue_veh"]
                        q_red = ((ft_q - cand_q) / max(ft_q, 0.01)) * 100

                        ft_th = ft["throughput_veh_per_s"]
                        cand_th = cand["throughput_veh_per_s"]
                        th_gain = ((cand_th - ft_th) / max(ft_th, 0.001)) * 100

                        improvements[top_id][scenario][ctrl] = {
                            "waiting_time_reduction_pct": round(wait_red, 2),
                            "queue_length_reduction_pct": round(q_red, 2),
                            "throughput_gain_pct": round(th_gain, 2),
                        }

        report_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_valid_runs": len(self.results),
            "total_failed_runs": len(self.failed_runs),
            "topologies": self.topologies,
            "scenarios": self.scenarios,
            "controllers": self.controllers,
            "seeds": self.seeds,
            "mode": self.mode,
            "topology_aggregates": topology_aggregates,
            "improvements": improvements,
            "failed_experiments": [
                {"id": f.get("experiment_id", "?"), "reason": f.get("reason", "?")}
                for f in self.failed_runs
            ],
        }

        with open(report_json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # Markdown report
        md = self._build_markdown_report(report_data, topology_aggregates, improvements)
        with open(report_md_file, "w", encoding="utf-8") as f:
            f.write(md)

        logger.info(
            f"Reports generated:\n  JSON: {report_json_file}\n  MD: {report_md_file}"
        )

    def _build_markdown_report(
        self, report_data, topology_aggregates, improvements
    ) -> str:
        lines = [
            "# EdgeFlow AI — Benchmark Comparison Report (P0 Validated)",
            "",
            f"**Generated**: {report_data['timestamp']}",
            f"**Valid Runs**: {report_data['total_valid_runs']} | "
            f"**Failed**: {report_data['total_failed_runs']}",
            f"**Seeds**: {self.seeds} | **Mode**: {self.mode}",
            "",
            "## KPI Comparison",
            "",
            "| Topology | Scenario | Controller | Runs | Avg Wait (s) | Avg Queue | P95 Queue | Throughput (veh/s) | Speed (m/s) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]

        for top_id in self.topologies:
            for scenario in self.scenarios:
                for ctrl in self.controllers:
                    d = topology_aggregates.get(top_id, {}).get(scenario, {}).get(ctrl)
                    if d:
                        lines.append(
                            f"| `{top_id}` | **{scenario}** | `{ctrl}` | "
                            f"{d['valid_runs']} | "
                            f"{d['average_waiting_time_s']}s | "
                            f"{d['average_queue_veh']} | "
                            f"{d['p95_queue_veh']} | "
                            f"{d['throughput_veh_per_s']} | "
                            f"{d['mean_network_speed_mps']} |"
                        )

        lines.extend([
            "",
            "## Performance vs Fixed-Time Baseline",
            "",
            "| Topology | Scenario | Controller | Wait Reduction (%) | Queue Reduction (%) | Throughput Gain (%) |",
            "|---|---|---|---|---|---|",
        ])

        for top_id in self.topologies:
            for scenario in self.scenarios:
                scen_imp = improvements.get(top_id, {}).get(scenario, {})
                for ctrl, imp in scen_imp.items():
                    lines.append(
                        f"| `{top_id}` | **{scenario}** | `{ctrl}` | "
                        f"**{imp['waiting_time_reduction_pct']}%** | "
                        f"**{imp['queue_length_reduction_pct']}%** | "
                        f"**{imp['throughput_gain_pct']:+.2f}%** |"
                    )

        if self.failed_runs:
            lines.extend([
                "",
                "## Failed / Invalid Runs",
                "",
                "| Experiment | Reason |",
                "|---|---|",
            ])
            for f in self.failed_runs:
                lines.append(
                    f"| `{f.get('experiment_id', '?')}` | {f.get('reason', '?')} |"
                )

        lines.append("")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="EdgeFlow AI Batch Benchmark Orchestrator"
    )
    parser.add_argument("--topology", type=str, default="four_intersection_v1")
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--output-dir", type=str, default="artifacts")
    parser.add_argument(
        "--mode", type=str, default="deterministic_sim",
        choices=["deterministic_sim", "mock_demo"],
    )
    parser.add_argument("--scenarios", type=str, nargs="*", default=None)
    parser.add_argument("--controllers", type=str, nargs="*", default=None)
    parser.add_argument("--seeds", type=int, nargs="*", default=None)

    args = parser.parse_args()
    batch = BatchRunner(
        scenarios=args.scenarios,
        controllers=args.controllers,
        seeds=args.seeds,
        topology=args.topology,
        duration_s=args.duration,
        output_dir=args.output_dir,
        mode=args.mode,
    )
    batch.run_all()


if __name__ == "__main__":
    main()
