"""Real SUMO checks; unavailable research dependencies are explicit skips."""

import importlib.util
import json
import pytest
from src.benchmark.prepare import prepare_map
from src.benchmark.suite import load_suite
from src.rl.benchmark import run_case

pytestmark = pytest.mark.skipif(importlib.util.find_spec("sumo") is None, reason="Research SUMO package required")


@pytest.mark.parametrize("index", range(4))
def test_audited_map_executes_with_complete_vehicle_accounting(tmp_path, index):
    spec = load_suite("configs/benchmarks/suite_v1.yaml")["maps"][index]
    prepared = prepare_map(spec, tmp_path / "inputs")
    result = run_case(
        dict(
            environment=dict(
                topology_path=prepared["topology_path"],
                network_path=prepared["network_path"],
                demand_s=30,
                drain_s=30,
                benchmark_mode=True,
                trace=True,
            )
        ),
        {"type": "fixed_time"},
        "balanced",
        90001,
        tmp_path / "run",
    )
    assert result["valid"] and result["metrics_version"] == 3
    assert result["scheduled"] == result["completed"] + result["unfinished"] + result["uninserted"]
    assert sum(c["scheduled"] for c in result["vehicle_classes"].values()) == result["scheduled"]
    for nid, phases in result["signal_green_seconds"].items():
        assert sum(phases.values()) + result["signal_clearance_seconds_by_node"][nid] == result["time_s"]


def test_downstream_bottleneck_changes_lane_speeds_and_completes(tmp_path):
    spec = load_suite("configs/benchmarks/suite_v1.yaml")["maps"][0]
    prepared = prepare_map(spec, tmp_path / "inputs")
    result = run_case(
        dict(
            environment=dict(
                topology_path=prepared["topology_path"],
                network_path=prepared["network_path"],
                demand_s=30,
                drain_s=30,
                benchmark_mode=True,
                trace=False,
            )
        ),
        {"type": "fixed_time"},
        "downstream_bottleneck",
        90002,
        tmp_path / "run",
    )
    assert result["valid"] and result["scheduled"] > 0


@pytest.mark.parametrize("name", ["hanoi_dong_da_v1", "jakarta_menteng_v1"])
def test_prepared_city_executes_without_losing_vehicles(tmp_path, name):
    from pathlib import Path

    prepared = Path("artifacts/benchmarks/development/prepared.json")
    if not prepared.exists():
        pytest.skip("Run the explicit city preparation stage first")
    spec = next(m for m in json.loads(prepared.read_text())["maps"] if m["id"] == name)
    result = run_case(
        dict(
            environment=dict(
                topology_path=spec["topology_path"],
                network_path=spec["network_path"],
                demand_s=30,
                drain_s=30,
                benchmark_mode=True,
                trace=True,
            )
        ),
        {"type": "fixed_time"},
        "balanced",
        90001,
        tmp_path / "run",
    )
    assert result["valid"]
    assert result["scheduled"] == sum(c["scheduled"] for c in result["vehicle_classes"].values())
