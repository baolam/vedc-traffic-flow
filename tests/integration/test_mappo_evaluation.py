from pathlib import Path

import pytest


def test_process_isolated_evaluation_runs_sumo_and_reuses_cached_case(tmp_path):
    pytest.importorskip("traci")
    from src.rl.evaluation import evaluate_cases

    config = {"environment": {
        "topology_path": "contracts/topology/four_intersection_rl_v1.json",
        "network_path": "networks/four_intersection_rl_v1/network.net.xml",
        "demand_s": 120, "drain_s": 60, "wait_penalty_lambda": 0.0,
    }}
    controller = {"type": "fair_cycle", "parameters": {
        "cycle_time_s": 90, "min_green_share": 0.25,
    }}
    cache = tmp_path / "validation-cache"
    rows, first = evaluate_cases(config, controller, ("balanced",), (31001,), tmp_path,
                                 cache_root=cache, workers=1, timeout_s=90.)
    cached, second = evaluate_cases(config, controller, ("balanced",), (31001,), tmp_path,
                                    cache_root=cache, workers=1, timeout_s=90.)

    assert rows[0]["valid"]
    assert cached == rows
    assert first["cache_misses"] == 1 and second["cache_hits"] == 1
    assert Path(next(cache.rglob("metrics.json"))).is_file()
