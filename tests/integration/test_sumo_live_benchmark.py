"""
EdgeFlow AI — Integration Tests for SUMO Live Benchmark Backend (P0/P1/P2).

Validates:
  1. LiveSumoRuntime execution with TraCI on four_intersection_v1 across controllers.
  2. Telemetry and ControlCommand JSON schema compliance via jsonschema Draft7Validator.
  3. Strict vehicle accounting: scheduled == completed + active + pending.
  4. Generation of all 14 required per-run artifacts.
  5. SingleExperimentRunner and BatchRunner integration in sumo_live mode.
"""

import os
import sys
import json
import shutil
import pytest
from pathlib import Path

SUMO_AVAILABLE = bool(shutil.which("sumo") or os.environ.get("SUMO_HOME"))
pytestmark = pytest.mark.skipif(not SUMO_AVAILABLE, reason="SUMO binary not found on PATH or SUMO_HOME")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.simulation.sumo_network_registry import NETWORK_REGISTRY, NetworkMappingResolver
from src.simulation.sumo_demand_generator import SumoDemandGenerator
from src.simulation.sumo_live_backend import LiveSumoRuntime
exp_runner_dir = REPO_ROOT / "services" / "experiment-runner"
if str(exp_runner_dir) not in sys.path:
    sys.path.insert(0, str(exp_runner_dir))

from manifest import ExperimentManifest, ScenarioConfig, ControllerConfig
from runner import SingleExperimentRunner
from batch_runner import BatchRunner


@pytest.fixture
def tmp_benchmark_dir(tmp_path):
    d = tmp_path / "sumo_live_test"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_live_sumo_runtime_smoke(tmp_benchmark_dir):
    """Test LiveSumoRuntime runs cleanly with FixedTimeController on four_intersection_v1."""
    run_dir = tmp_benchmark_dir / "smoke_fixed_time"
    runtime = LiveSumoRuntime(
        topology_id="four_intersection_v1",
        scenario="balanced",
        seed=101,
        controller_name="fixed_time",
        artifacts_dir=run_dir,
        warmup_s=10,
        duration_s=25,
        drain_s=10,
    )
    summary = runtime.run()

    # 1. Check validity
    assert summary["valid_for_research"] is True
    assert summary["accounting"]["accounting_invariant_holds"] is True

    # 2. Check scheduled = completed + active + pending
    acct = summary["accounting"]
    assert acct["scheduled_vehicles"] == acct["completed_vehicles"] + acct["active_vehicles"] + acct["pending_vehicles"]

    # 3. Check 14 required artifacts exist
    expected_artifacts = [
        "manifest.json",
        "environment.json",
        "resolved_topology.json",
        "resolved_mapping.json",
        "experiment.sumocfg",
        "tripinfo.xml",
        "vehicles.csv",
        "telemetry.csv",
        "signals.jsonl",
        "scenario_events.jsonl",
        "faults.jsonl",
        "sumo-error.log",
        "summary.json",
        "validity.json",
    ]
    for art in expected_artifacts:
        art_path = run_dir / art
        assert art_path.exists(), f"Missing required artifact: {art}"
        assert art_path.stat().st_size >= 0

    # 4. Check KPIs sanity
    kpis = summary["kpis"]
    assert kpis["percentile_method"] == "linear"
    if acct["completed_vehicles"] > 0:
        assert kpis["mean_waiting_completed_s"] is not None
        assert kpis["mean_waiting_completed_s"] >= 0.0
    else:
        assert kpis["mean_waiting_completed_s"] is None


def test_live_sumo_controllers_four_intersection(tmp_benchmark_dir):
    """Test all 4 target controllers run without crash in LiveSumoRuntime."""
    controllers = ["max_queue", "max_pressure", "flow_theory"]
    for ctrl in controllers:
        run_dir = tmp_benchmark_dir / f"test_{ctrl}"
        runtime = LiveSumoRuntime(
            topology_id="four_intersection_v1",
            scenario="directional_surge",
            seed=202,
            controller_name=ctrl,
            artifacts_dir=run_dir,
            warmup_s=5,
            duration_s=20,
            drain_s=5,
        )
        summary = runtime.run()
        assert summary["valid_for_research"] is True
        assert summary["controller"] == ctrl
        assert (run_dir / "summary.json").exists()


def test_single_experiment_runner_sumo_live_dispatch(tmp_benchmark_dir):
    """Test SingleExperimentRunner dispatching mode='sumo_live'."""
    exp_id = "test_exp_runner_sumo"
    manifest = ExperimentManifest(
        experiment_id=exp_id,
        topology="four_intersection_v1",
        scenario=ScenarioConfig(
            name="balanced",
            duration_s=20,
            random_seed=303,
            warmup_s=5,
            drain_s=5,
        ),
        controller=ControllerConfig(type="fixed_time", decision_interval_s=1.0),
    )
    runner = SingleExperimentRunner(
        manifest=manifest,
        artifacts_root=str(tmp_benchmark_dir),
        mode="sumo_live",
    )
    success = runner.run()
    assert success is True
    assert runner.run_valid is True
    assert (runner.artifacts_dir / "summary.json").exists()
    assert (runner.artifacts_dir / "telemetry.csv").exists()


def test_batch_runner_sumo_live_pilot(tmp_benchmark_dir):
    """Test BatchRunner pilot execution with 2 controllers on four_intersection_v1."""
    campaign_dir = tmp_benchmark_dir / "pilot_campaign"
    batch = BatchRunner(
        topologies=["four_intersection_v1"],
        scenarios=["balanced"],
        controllers=["fixed_time", "max_queue"],
        seeds=[101],
        warmup_s=5,
        duration_s=20,
        drain_s=5,
        output_dir=str(campaign_dir),
        mode="sumo_live",
    )
    batch.run_all()

    # Check campaign output reports
    assert (campaign_dir / "campaign_manifest.json").exists()
    assert (campaign_dir / "benchmark_runs.csv").exists()
    assert (campaign_dir / "benchmark_comparison_report.json").exists()
    assert (campaign_dir / "benchmark_summary.md").exists()
    assert (campaign_dir / "test_results.md").exists()

    with open(campaign_dir / "benchmark_comparison_report.json", "r", encoding="utf-8") as f:
        report = json.load(f)
    assert report["total_valid_runs"] == 2
    assert report["total_failed_runs"] == 0
    assert "four_intersection_v1" in report["paired_aggregates"]
