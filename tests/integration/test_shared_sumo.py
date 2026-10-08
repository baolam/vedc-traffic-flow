"""Real SUMO tests; install src/rl/requirements-sumo.txt to run."""
import json
from pathlib import Path
import numpy as np
import pytest

pytest.importorskip("traci")
pytest.importorskip("gymnasium")
from src.rl.sumo_env import FairCycleSumoEnv, SumoNetworkEnv
from contracts.research import RESEARCH_SCENARIOS


def env(tmp_path, **kwargs):
    return SumoNetworkEnv("contracts/topology/four_intersection_rl_v1.json",
                          "networks/four_intersection_rl_v1/network.net.xml", tmp_path,
                          trace=True, **kwargs)


def test_deterministic_reset_features_and_actual_clearance(tmp_path):
    e = env(tmp_path, demand_s=20, drain_s=60)
    traces = []
    try:
        for _ in range(2):
            obs, info = e.reset(seed=20001)
            history = []
            done = False
            while not done:
                action = {k: 1 for k in obs}
                obs, reward, term, trunc, info = e.step(action)
                history.append((np.stack(list(obs.values())), reward))
                done = term or trunc
            assert info["metrics"]["valid"]
            assert info["metrics"]["scheduled"] == sum(info["metrics"][k] for k in ("completed", "unfinished", "uninserted"))
            signals = [json.loads(line) for line in (e.runtime.output / "signals.jsonl").read_text().splitlines()]
            traces.append(history)
            j1 = {r["time_s"]: r for r in signals if r["node_id"] == "J1"}
            assert all(j1[t]["state"] == "GREEN" for t in range(10))
            assert all(j1[t]["state"] == "YELLOW" for t in range(10,13))
            assert all(j1[t]["state"] == "ALL_RED" for t in range(13,15))
            assert j1[15]["state"] == "GREEN" and j1[15]["phase"] == "J1_PHASE_EW"
            assert j1[75]["state"] == "YELLOW"  # Unconditional max green.
            assert all(r["expected"] == r["actual"] for r in signals)
        for a, b in zip(*traces):
            np.testing.assert_array_equal(a[0], b[0])
            assert a[1] == b[1]
    finally:
        e.close()


def test_fair_cycle_env_returns_one_full_safe_cycle(tmp_path):
    e = FairCycleSumoEnv("contracts/topology/four_intersection_rl_v1.json",
                         "networks/four_intersection_rl_v1/network.net.xml", tmp_path,
                         demand_s=1800, drain_s=600, trace=True)
    try:
        obs, info = e.reset(seed=20003, options={"scenario": "balanced"})
        assert all(value.shape == (52,) for value in obs.values())
        next_obs, reward, terminated, truncated, info = e.step({key: 1 for key in obs})
        assert info["elapsed_s"] == 70
        assert not terminated and not truncated
        assert set(next_obs) == set(obs)
        assert info["action_masks"]["J1"][1]
        signals = [json.loads(line) for line in (e.runtime.output / "signals.jsonl").read_text().splitlines()]
        j1 = list({row["time_s"]: row for row in signals if row["node_id"] == "J1"}.values())
        assert sum(row["state"] == "GREEN" for row in j1) == 60
        assert sum(row["state"] != "GREEN" for row in j1) == 10
        assert all(row["expected"] == row["actual"] for row in j1)
    finally:
        e.close()


def test_fair_cycle_policy_runs_through_benchmark_inference(tmp_path):
    from src.rl.benchmark import run_case
    from src.rl.shared_dqn import Learner
    from src.simulation.runtime import file_hash

    topology = "contracts/topology/four_intersection_rl_v1.json"
    network = "networks/four_intersection_rl_v1/network.net.xml"
    model = tmp_path / "policy.json"
    learner = Learner({"algorithm": "fair_cycle_dqn", "device": "cpu", "replay_capacity": 4}, 17)
    learner.export(model, {"network_sha256": file_hash(network), "topology_sha256": file_hash(topology)})
    result = run_case({"environment": {"topology_path": topology, "network_path": network,
                                       "demand_s": 20, "drain_s": 80, "trace": True}},
                      {"type": "fair_cycle_rl", "model_path": str(model)}, "balanced", 20004,
                      tmp_path / "run")
    assert result["valid"]
    assert result["metrics_version"] == 2
    assert result["p95_wait_s"] >= 0
    assert result["max_approach_p95_wait_s"] >= 0
    assert sum(sum(phases.values()) for phases in result["signal_green_seconds"].values()) <= 4 * result["time_s"]


@pytest.mark.parametrize("scenario", list(RESEARCH_SCENARIOS))
def test_real_scenarios_unfinished_and_uninserted_accounting(tmp_path, scenario):
    e = env(tmp_path, demand_s=60, drain_s=0)
    try:
        obs, _ = e.reset(seed=20002, options={"scenario": scenario, "intensity": 5.})
        done = False
        while not done:
            obs, reward, term, trunc, info = e.step({k: 0 for k in obs})
            done = term or trunc
        m = info["metrics"]
        assert trunc and not term
        assert m["unfinished"] > 0 and m["uninserted"] > 0
        assert m["delay_per_scheduled_s"] > 0 and m["valid"]
    finally:
        e.close()
