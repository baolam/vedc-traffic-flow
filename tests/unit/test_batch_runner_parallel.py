"""
Unit tests for ParallelBatchRunner (batch_runner_parallel.py).
"""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path

# Add services/experiment-runner to path
curr = Path(__file__).resolve().parent
exp_runner_dir = curr.parent.parent / "services" / "experiment-runner"
if str(exp_runner_dir) not in sys.path:
    sys.path.insert(0, str(exp_runner_dir))

# Also add contracts, graph-control, actuator
repo_root = curr.parent.parent
for p in [repo_root / "contracts", repo_root / "services" / "graph-control",
          repo_root / "services" / "actuator", repo_root]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from batch_runner_parallel import ParallelBatchRunner, BatchRunnerParallel


def test_parallel_batch_runner_init():
    runner = ParallelBatchRunner(
        scenarios=["balanced"],
        controllers=["fixed_time"],
        seeds=[101],
        workers=4,
    )
    assert runner.workers == 4
    assert runner.scenarios == ["balanced"]
    assert runner.controllers == ["fixed_time"]
    assert runner.seeds == [101]
    assert runner.topologies == ["four_intersection_v1"]
    assert BatchRunnerParallel is ParallelBatchRunner


def test_parallel_batch_runner_campaign_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ParallelBatchRunner(
            scenarios=["balanced"],
            controllers=["fixed_time"],
            seeds=[101],
            output_dir=tmpdir,
            workers=3,
        )
        runner._write_campaign_manifest()

        manifest_file = Path(tmpdir) / "campaign_manifest.json"
        assert manifest_file.exists()

        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["workers"] == 3
        assert data["parallel_execution"] is True
        assert data["total_planned_runs"] == 1


def test_parallel_batch_runner_execution_deterministic():
    """Test running a 4-run batch (1 scenario x 2 controllers x 2 seeds) in parallel with 2 workers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ParallelBatchRunner(
            scenarios=["balanced"],
            controllers=["fixed_time", "max_pressure"],
            seeds=[42, 101],
            duration_s=3,
            output_dir=tmpdir,
            mode="deterministic_sim",
            workers=2,
        )
        runner.run_all()

        assert len(runner.results) == 4
        assert len(runner.failed_runs) == 0

        json_report = Path(tmpdir) / "benchmark_comparison_report.json"
        md_report = Path(tmpdir) / "benchmark_summary.md"
        csv_report = Path(tmpdir) / "benchmark_runs.csv"
        test_results = Path(tmpdir) / "test_results.md"

        assert json_report.exists()
        assert md_report.exists()
        assert csv_report.exists()
        assert test_results.exists()

        with open(json_report, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["total_valid_runs"] == 4
            assert data["total_failed_runs"] == 0
            assert "improvements" in data

        # Verify CSV has 4 data rows + 1 header row
        with open(csv_report, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            assert len(lines) == 5  # header + 4 rows


def test_parallel_batch_runner_preflight():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ParallelBatchRunner(
            topology="four_intersection_v1",
            output_dir=tmpdir,
        )
        ok = runner.run_preflight_only()
        assert ok is True
        assert (Path(tmpdir) / "preflight.json").exists()
        assert (Path(tmpdir) / "mapping_audit.json").exists()
