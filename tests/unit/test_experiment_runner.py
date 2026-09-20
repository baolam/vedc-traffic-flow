import os
import sys
import json
import shutil
import tempfile
import pytest
from pathlib import Path

# Add services/experiment-runner to path
curr = Path(__file__).resolve().parent
exp_runner_dir = curr.parent.parent / "services" / "experiment-runner"
if str(exp_runner_dir) not in sys.path:
    sys.path.insert(0, str(exp_runner_dir))

from manifest import ExperimentManifest, ScenarioConfig, ControllerConfig
from metrics_collector import MetricsCollector
from runner import SingleExperimentRunner
from batch_runner import BatchRunner

def test_experiment_manifest_yaml_roundtrip():
    manifest = ExperimentManifest(
        experiment_id="test_exp_001",
        topology="four_intersection_v1",
        scenario=ScenarioConfig(name="directional_surge", duration_s=60, random_seed=42),
        controller=ControllerConfig(type="max_pressure", decision_interval_s=1.0)
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "manifest.yaml")
        manifest.save_yaml(file_path)
        assert os.path.exists(file_path)

        loaded = ExperimentManifest.from_yaml(file_path)
        assert loaded.experiment_id == "test_exp_001"
        assert loaded.scenario.name == "directional_surge"
        assert loaded.controller.type == "max_pressure"
        assert loaded.scenario.random_seed == 42

def test_metrics_collector_processing_and_summary():
    collector = MetricsCollector()
    collector.start()

    sample_telemetry = {
        "node_id": "J1",
        "simulation_time_s": 5.0,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {
                "approach_id": "J1_N_IN",
                "queue_vehicles": 10,
                "flow_veh_per_s": 0.5,
                "mean_speed_mps": 0.2,
                "occupancy_ratio": 0.6
            }
        ]
    }

    collector.on_mqtt_message("edgeflow/v1/telemetry/J1", json.dumps(sample_telemetry))
    collector.stop()

    assert len(collector.telemetry_samples) == 1
    sample = collector.telemetry_samples[0]
    assert sample["node_id"] == "J1"
    assert sample["queue_vehicles"] == 10
    assert sample["waiting_vehicles"] == 10  # speed < 0.5

    summary = collector.compute_summary()
    assert summary["total_samples"] == 1
    assert summary["average_queue_veh"] == 10.0
    assert summary["maximum_queue_veh"] == 10

def test_single_experiment_runner_artifact_export():
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = ExperimentManifest(
            experiment_id="unit_test_exp_run",
            topology="four_intersection_v1",
            scenario=ScenarioConfig(name="balanced", duration_s=2, random_seed=123),
            controller=ControllerConfig(type="max_pressure", decision_interval_s=1.0)
        )

        runner = SingleExperimentRunner(manifest=manifest, artifacts_root=tmpdir)
        runner.run(mock_telemetry_if_no_mqtt=True)

        exp_dir = Path(tmpdir) / "unit_test_exp_run"
        assert exp_dir.exists()
        assert (exp_dir / "manifest.yaml").exists()
        assert (exp_dir / "environment.json").exists()
        assert (exp_dir / "metrics.csv").exists()
        assert (exp_dir / "events.jsonl").exists()
        assert (exp_dir / "summary.json").exists()

        # Check summary content
        with open(exp_dir / "summary.json", "r", encoding="utf-8") as f:
            summary = json.load(f)
            assert summary["manifest"]["experiment_id"] == "unit_test_exp_run"
            assert "average_waiting_time_s" in summary

def test_batch_runner_report_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = BatchRunner(
            scenarios=["balanced"],
            controllers=["fixed_time", "max_pressure"],
            seeds=[42, 101],
            duration_s=1,
            output_dir=tmpdir
        )
        batch.run_all()

        assert len(batch.results) == 4  # 1 scenario x 2 controllers x 2 seeds
        json_report = Path(tmpdir) / "benchmark_comparison_report.json"
        md_report = Path(tmpdir) / "benchmark_summary.md"

        assert json_report.exists()
        assert md_report.exists()

        with open(json_report, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["total_completed_runs"] == 4
            assert "improvements" in data
            assert "balanced" in data["improvements"]

def test_metrics_collector_invalid_json_handling():
    collector = MetricsCollector()
    collector.start()
    # Should log warning and return without raising exception
    collector.on_mqtt_message("edgeflow/v1/telemetry/J1", "{invalid_json_payload...")
    collector.stop()
    assert len(collector.telemetry_samples) == 0

def test_metrics_collector_non_telemetry_events():
    collector = MetricsCollector()
    collector.start()
    ack_payload = json.dumps({"command_id": "c1", "status": "APPLIED"})
    collector.on_mqtt_message("edgeflow/v1/ack/J1", ack_payload)
    collector.stop()

    assert len(collector.event_logs) == 1
    assert collector.event_logs[0]["topic"] == "edgeflow/v1/ack/J1"

def test_metrics_collector_empty_summary():
    collector = MetricsCollector()
    summary = collector.compute_summary()
    assert summary["total_samples"] == 0
    assert summary["average_waiting_time_s"] == 0.0
    assert summary["average_queue_veh"] == 0.0

