"""
EdgeFlow AI — Scientifically Rigorous Parallel Batch Benchmark Orchestrator.

Executes paired experiment matrix (Topology x Scenario x Controller x Seed)
across multiple concurrent worker processes to significantly accelerate benchmarking,
while strictly maintaining all scientific controls and invariants:
  1. Identical frozen demand pre-generated deterministically per (topology, scenario, seed).
  2. SHA-256 demand integrity verification before and after every run.
  3. Isolated execution per run to avoid filesystem or TraCI socket conflicts.
  4. Real-time incremental progress tracking and benchmark_runs.csv recording.
  5. Paired matrix comparisons over common seeds where all controllers completed validly.
"""

import os
import sys
import csv
import json
import time
import argparse
import logging
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

curr_dir = Path(__file__).resolve().parent
repo_root = next(p for p in [curr_dir, *curr_dir.parents] if (p / "src" / "control").is_dir())
for p in [repo_root / "contracts", repo_root, curr_dir]:
    if str(p) not in sys.path and p.exists():
        sys.path.insert(0, str(p))

from batch_runner import (
    BatchRunner,
    CANONICAL_SCENARIOS,
    REPORT_CONTROLLERS,
    ALL_CONTROLLERS,
    CANONICAL_TOPOLOGIES,
    CANONICAL_SEEDS,
    get_git_commit,
)
from manifest import ExperimentManifest, ScenarioConfig, ControllerConfig
from runner import SingleExperimentRunner, DemandGenerator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("batch-runner-parallel")


def _run_single_experiment_worker(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Top-level worker function executing a single experiment run in a subprocess.
    Ensures safe serialization and execution across all platforms (Windows/Linux/macOS).
    """
    root = Path(task["repo_root_str"])
    for p in [root / "contracts", root, root / "services" / "experiment-runner"]:
        if str(p) not in sys.path and p.exists():
            sys.path.insert(0, str(p))

    exp_id = task["exp_id"]
    top_id = task["top_id"]
    scenario = task["scenario"]
    controller = task["controller"]
    seed = task["seed"]
    duration_s = task["duration_s"]
    warmup_s = task["warmup_s"]
    drain_s = task["drain_s"]
    artifacts_root = task["artifacts_root"]
    mode = task["mode"]
    expected_demand_hash = task["expected_demand_hash"]
    frozen_demand_dir = task.get("frozen_demand_dir")

    t0 = time.time()
    manifest = ExperimentManifest(
        experiment_id=exp_id,
        topology=top_id,
        scenario=ScenarioConfig(
            name=scenario,
            duration_s=duration_s,
            random_seed=seed,
            warmup_s=warmup_s,
            drain_s=drain_s,
        ),
        controller=ControllerConfig(
            type=controller, decision_interval_s=1.0
        ),
    )

    run_success = False
    summary_data: Optional[Dict[str, Any]] = None
    fail_reason = ""
    valid = False

    try:
        # Subtle startup jitter in sumo_live mode to prevent concurrent TraCI socket collisions
        if mode == "sumo_live":
            import random
            time.sleep(random.uniform(0.05, 0.35))

        runner = SingleExperimentRunner(
            manifest=manifest,
            artifacts_root=artifacts_root,
            mode=mode,
        )
        if frozen_demand_dir:
            runner.frozen_demand_dir = Path(frozen_demand_dir)

        valid = runner.run()
        actual_hash = runner.demand_hash

        if actual_hash != expected_demand_hash:
            logger.error(
                f"DEMAND INTEGRITY FAULT for {exp_id}: "
                f"expected={expected_demand_hash} actual={actual_hash}"
            )
            valid = False
            fail_reason = "demand_hash_mismatch"

        summary_file = runner.artifacts_dir / "summary.json"
        if summary_file.exists():
            with open(summary_file, "r", encoding="utf-8") as f:
                summary_data = json.load(f)

            is_research_valid = valid and summary_data.get("valid_for_research", False)
            if is_research_valid:
                run_success = True
            else:
                fail_reason = fail_reason or "invalid_for_research"
        else:
            fail_reason = fail_reason or "missing_summary_file"

    except Exception as e:
        logger.error(f"Experiment {exp_id} crashed in worker: {e}", exc_info=True)
        fail_reason = str(e)
        valid = False
        run_success = False

    elapsed_s = round(time.time() - t0, 2)
    return {
        "exp_id": exp_id,
        "top_id": top_id,
        "scenario": scenario,
        "controller": controller,
        "seed": seed,
        "run_success": run_success,
        "valid": valid,
        "fail_reason": fail_reason,
        "summary_data": summary_data,
        "elapsed_s": elapsed_s,
    }


class ParallelBatchRunner(BatchRunner):
    """
    Parallel Batch Benchmark Orchestrator for EdgeFlow AI.
    Executes benchmark matrix concurrently while preserving strict scientific invariants.
    """

    def __init__(
        self,
        scenarios: Optional[List[str]] = None,
        controllers: Optional[List[str]] = None,
        seeds: Optional[List[int]] = None,
        topology: Union[str, List[str]] = "four_intersection_v1",
        topologies: Optional[List[str]] = None,
        duration_s: int = 1800,
        warmup_s: int = 300,
        drain_s: int = 600,
        output_dir: Optional[str] = None,
        mode: str = "sumo_live",
        gui: bool = False,
        workers: Optional[int] = None,
    ):
        super().__init__(
            scenarios=scenarios,
            controllers=controllers,
            seeds=seeds,
            topology=topology,
            topologies=topologies,
            duration_s=duration_s,
            warmup_s=warmup_s,
            drain_s=drain_s,
            output_dir=output_dir,
            mode=mode,
            gui=gui,
        )
        if workers is not None and workers > 0:
            self.workers = int(workers)
        else:
            cpu_cnt = os.cpu_count() or 4
            if self.mode == "sumo_live":
                # SUMO processes are heavy binaries requiring socket connections and memory.
                # Default to half of available cores (bounded 1..4) to prevent socket/RAM exhaustion.
                self.workers = max(1, min(cpu_cnt // 2 or 1, 4))
            else:
                self.workers = max(1, min(cpu_cnt, 16))

    def _write_campaign_manifest(self):
        super()._write_campaign_manifest()
        manifest_file = self.output_dir / "campaign_manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["workers"] = self.workers
                data["parallel_execution"] = True
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to enrich campaign manifest with worker count: {e}")

    def _prepare_frozen_demands(self):
        """
        Phase 1: Deterministically generate and verify frozen demands for all
        (topology, scenario, seed) combinations sequentially before launching workers.
        This prevents race conditions on disk and guarantees SHA-256 reproducibility.
        """
        logger.info("Phase 1: Pre-generating and freezing deterministic demands...")
        t0 = time.time()
        for top_id in self.topologies:
            for scenario in self.scenarios:
                for seed in self.seeds:
                    demand_key = (top_id, scenario, seed)
                    frozen_demand_dir = (
                        self.output_dir / "frozen_inputs" / top_id / scenario / f"seed_{seed}"
                    )

                    if self.mode == "sumo_live":
                        from src.simulation.sumo_demand_generator import SumoDemandGenerator
                        if demand_key not in self.demand_hashes:
                            frozen_demand_dir.mkdir(parents=True, exist_ok=True)
                            demand_meta = SumoDemandGenerator.generate_frozen_demand(
                                topology_id=top_id,
                                scenario=scenario,
                                seed=seed,
                                output_dir=frozen_demand_dir,
                                warmup_s=self.warmup_s,
                                duration_s=self.duration_s,
                                drain_s=self.drain_s,
                            )
                            self.demand_hashes[demand_key] = demand_meta["demand_rou_sha256"]
                    else:
                        if demand_key not in self.demand_hashes:
                            try:
                                import contracts_sdk
                            except ImportError:
                                from contracts import contracts_sdk
                            topo = contracts_sdk.load_topology(top_id)
                            demand = DemandGenerator.generate(
                                scenario, seed, self.duration_s, topo
                            )
                            self.demand_hashes[demand_key] = demand["hash"]

        logger.info(
            f"Phase 1 complete in {time.time() - t0:.2f}s: "
            f"{len(self.demand_hashes)} unique demand sets verified."
        )

    def _build_task_list(self) -> List[Dict[str, Any]]:
        """Construct task specifications for all matrix cells."""
        tasks: List[Dict[str, Any]] = []
        for top_id in self.topologies:
            for scenario in self.scenarios:
                for seed in self.seeds:
                    demand_key = (top_id, scenario, seed)
                    expected_demand_hash = self.demand_hashes[demand_key]
                    frozen_demand_dir = (
                        self.output_dir / "frozen_inputs" / top_id / scenario / f"seed_{seed}"
                    )

                    for controller in self.controllers:
                        exp_id = f"{top_id}_{scenario}_{controller}_seed{seed}"
                        tasks.append({
                            "exp_id": exp_id,
                            "top_id": top_id,
                            "scenario": scenario,
                            "controller": controller,
                            "seed": seed,
                            "duration_s": self.duration_s,
                            "warmup_s": self.warmup_s,
                            "drain_s": self.drain_s,
                            "artifacts_root": str(self.output_dir),
                            "mode": self.mode,
                            "expected_demand_hash": expected_demand_hash,
                            "frozen_demand_dir": str(frozen_demand_dir) if self.mode == "sumo_live" else None,
                            "gui": self.gui,
                            "repo_root_str": str(repo_root),
                        })
        return tasks

    def _record_run_result(
        self,
        res: Dict[str, Any],
        completed_count: int,
        total_runs: int,
        runs_csv_path: Path,
    ):
        """Thread-safe state update and logging upon completion of a worker task."""
        exp_id = res["exp_id"]
        top_id = res["top_id"]
        scenario = res["scenario"]
        controller = res["controller"]
        seed = res["seed"]
        run_success = res["run_success"]
        summary_data = res["summary_data"]
        fail_reason = res["fail_reason"]
        elapsed_s = res.get("elapsed_s", 0.0)

        status_str = "PASS" if run_success else f"FAIL ({fail_reason})"
        logger.info(
            f"[{completed_count}/{total_runs}] ({elapsed_s}s) "
            f"Finished: {exp_id} -> {status_str}"
        )

        if run_success and summary_data is not None:
            self.results.append(summary_data)
        else:
            self.failed_runs.append({
                "experiment_id": exp_id,
                "reason": fail_reason,
                "summary": summary_data,
            })

        row = self._format_run_csv_row(
            exp_id, top_id, scenario, controller, seed, run_success, summary_data, fail_reason
        )
        self.all_run_rows.append(row)
        self._write_incremental_runs_csv(runs_csv_path)

    def run_all(self):
        total_runs = (
            len(self.topologies)
            * len(self.scenarios)
            * len(self.controllers)
            * len(self.seeds)
        )
        logger.info(
            f"Starting Parallel Batch Benchmark Orchestrator:\n"
            f"  Topologies ({len(self.topologies)}): {self.topologies}\n"
            f"  Scenarios ({len(self.scenarios)}): {self.scenarios}\n"
            f"  Controllers ({len(self.controllers)}): {self.controllers}\n"
            f"  Seeds ({len(self.seeds)}): {self.seeds}\n"
            f"  Mode: {self.mode}\n"
            f"  Horizon: warmup={self.warmup_s}s, duration={self.duration_s}s, drain={self.drain_s}s\n"
            f"  Workers: {self.workers}\n"
            f"  Output Directory: {self.output_dir}\n"
            f"  -> Total Runs: {total_runs}"
        )

        # Pre-export campaign manifest
        self._write_campaign_manifest()

        # Phase 1: Setup deterministic demands
        self._prepare_frozen_demands()

        # Phase 2: Build tasks
        tasks = self._build_task_list()
        runs_csv_path = self.output_dir / "benchmark_runs.csv"
        completed_count = 0
        t_start = time.time()

        # Phase 3: Parallel Execution
        logger.info(
            f"Phase 2: Executing {len(tasks)} runs concurrently using {self.workers} worker processes..."
        )

        if self.workers == 1:
            for task in tasks:
                res = _run_single_experiment_worker(task)
                completed_count += 1
                self._record_run_result(res, completed_count, total_runs, runs_csv_path)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.workers) as executor:
                futures = {
                    executor.submit(_run_single_experiment_worker, task): task
                    for task in tasks
                }
                try:
                    for future in concurrent.futures.as_completed(futures):
                        task = futures[future]
                        exp_id = task["exp_id"]
                        try:
                            res = future.result()
                        except concurrent.futures.process.BrokenProcessPool as bpe:
                            logger.error(
                                f"\n{'='*75}\n"
                                f"CRITICAL: A worker process was terminated abruptly by the OS (BrokenProcessPool).\n"
                                f"Task: {exp_id}\n"
                                f"Primary causes:\n"
                                f"  1. OS Resource Limits: Spawning too many concurrent live SUMO processes\n"
                                f"     exhausts system RAM or socket resources.\n"
                                f"  2. External Process Termination / Keyboard Interrupt.\n"
                                f"\n"
                                f"RECOMMENDED FIX: Re-run with lower worker concurrency:\n"
                                f"  --workers 2  (or --workers 4)\n"
                                f"{'='*75}\n"
                            )
                            for f in futures:
                                f.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            return
                        except Exception as e:
                            logger.error(f"Task {exp_id} worker crashed unexpectedly: {e}", exc_info=True)
                            res = {
                                "exp_id": exp_id,
                                "top_id": task["top_id"],
                                "scenario": task["scenario"],
                                "controller": task["controller"],
                                "seed": task["seed"],
                                "run_success": False,
                                "valid": False,
                                "fail_reason": str(e),
                                "summary_data": None,
                                "elapsed_s": 0.0,
                            }
                        completed_count += 1
                        self._record_run_result(res, completed_count, total_runs, runs_csv_path)
                except KeyboardInterrupt:
                    logger.warning("Parallel batch execution interrupted by user! Canceling workers...")
                    for f in futures:
                        f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise

        total_elapsed = time.time() - t_start
        logger.info(
            f"All Parallel Batch Runs Finished in {total_elapsed:.1f}s: "
            f"{len(self.results)} valid, {len(self.failed_runs)} failed/invalid"
        )

        # Sort runs for deterministic final CSV report
        self.all_run_rows.sort(
            key=lambda r: (r.get("topology", ""), r.get("scenario", ""), r.get("seed", 0), r.get("controller", ""))
        )
        self._write_incremental_runs_csv(runs_csv_path)

        # Phase 4: Reports
        self.generate_comparison_reports()


# Convenience alias
BatchRunnerParallel = ParallelBatchRunner


def main():
    parser = argparse.ArgumentParser(
        description="EdgeFlow AI Standardized Parallel Batch Benchmark Orchestrator"
    )
    parser.add_argument("--config", type=str, default=None, help="Path to benchmark JSON configuration file")
    parser.add_argument("--preflight-only", action="store_true", help="Run preflight checks across networks and exit")
    parser.add_argument("--topology", type=str, default="four_intersection_v1", help="Topology name, comma-separated list, or 'all'")
    parser.add_argument("--scenarios", type=str, nargs="*", default=None, help="List of scenarios")
    parser.add_argument("--controllers", type=str, nargs="*", default=None, help="List of controllers")
    parser.add_argument("--seeds", type=int, nargs="*", default=None, help="List of random seeds")
    parser.add_argument("--warmup", type=int, default=300, help="Warmup duration in seconds")
    parser.add_argument("--duration", type=int, default=1800, help="Measurement window duration in seconds")
    parser.add_argument("--drain", type=int, default=600, help="Drain duration in seconds")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for campaign artifacts")
    parser.add_argument(
        "--mode", type=str, default="sumo_live",
        choices=["sumo_live", "deterministic_sim", "mock_demo"],
        help="Benchmark execution mode (default: sumo_live)",
    )
    parser.add_argument("--gui", action="store_true", help="Run SUMO with graphical interface")
    parser.add_argument(
        "--workers", "-w", "--max-workers", type=int, default=None,
        help="Number of parallel worker processes (default: CPU core count, max 16)",
    )

    args = parser.parse_args()

    cfg = {}
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.exists():
            print(f"Error: Config file not found at {args.config}")
            sys.exit(1)
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    scenarios = args.scenarios or cfg.get("scenarios")
    controllers = args.controllers or cfg.get("controllers")
    seeds = args.seeds or cfg.get("seeds")
    topology = args.topology if args.topology != "four_intersection_v1" or "topologies" not in cfg else cfg.get("topologies")
    warmup_s = args.warmup if args.warmup != 300 or "warmup_s" not in cfg else cfg.get("warmup_s")
    duration_s = args.duration if args.duration != 1800 or "duration_s" not in cfg else cfg.get("duration_s")
    drain_s = args.drain if args.drain != 600 or "drain_s" not in cfg else cfg.get("drain_s")
    mode = args.mode if args.mode != "sumo_live" or "mode" not in cfg else cfg.get("mode")
    output_dir = args.output_dir or cfg.get("output_dir")
    workers = args.workers or cfg.get("workers") or cfg.get("max_workers")

    batch = ParallelBatchRunner(
        scenarios=scenarios,
        controllers=controllers,
        seeds=seeds,
        topology=topology,
        duration_s=duration_s,
        warmup_s=warmup_s,
        drain_s=drain_s,
        output_dir=output_dir,
        mode=mode,
        gui=args.gui,
        workers=workers,
    )

    if args.preflight_only:
        ok = batch.run_preflight_only()
        sys.exit(0 if ok else 1)

    batch.run_all()


if __name__ == "__main__":
    main()
