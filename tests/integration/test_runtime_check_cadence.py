"""Real SUMO: check_every thins schema/readback checks for training rollouts; the default checks every step."""
import json

import pytest

pytest.importorskip("traci")
from src.simulation.runtime import SumoRuntime

TOPOLOGY, NETWORK = "contracts/topology/four_intersection_rl_v1.json", "networks/four_intersection_rl_v1/network.net.xml"


def validations(tmp_path, **kwargs):
    runtime = SumoRuntime(TOPOLOGY, NETWORK, tmp_path, demand_s=30, drain_s=0, trace=False, **kwargs)
    count = []
    real = runtime.schema_validator

    class Counting:
        def validate(self, data):
            count.append(data["simulation_time_s"])
            real.validate(data)

    runtime.schema_validator = Counting()
    try:
        for _ in range(6):  # six 5 s decisions
            runtime.step({n["node_id"]: 0 for n in runtime.topology["nodes"]})
    finally:
        runtime.close()
    return count


def rollout(output):
    """A short alternating-phase rollout: rewards and the recorded backend."""
    runtime = SumoRuntime(TOPOLOGY, NETWORK, output, demand_s=120, drain_s=0, trace=False)
    rewards = []
    try:
        for k in range(24):
            rewards.append(runtime.step({n["node_id"]: (k // 4) % 2 for n in runtime.topology["nodes"]})[1])
    finally:
        runtime.close()
    return dict(rewards=rewards, provenance=runtime.metadata["provenance"])


def test_default_checks_every_decision_and_large_cadence_only_when_due(tmp_path):
    every = validations(tmp_path / "a")
    assert sorted(set(every)) == [5, 10, 15, 20, 25, 30]  # each of the 4 nodes at every decision
    thinned = validations(tmp_path / "b", check_every=15)
    assert sorted(set(thinned)) == [15, 30] and len(thinned) == 8


@pytest.mark.parametrize("bad", [0, -1, 2.5, True])
def test_check_every_must_be_a_positive_integer(tmp_path, bad):
    with pytest.raises(ValueError):
        SumoRuntime(TOPOLOGY, NETWORK, tmp_path / "run", check_every=bad)


def test_libsumo_backend_reproduces_traci(tmp_path, monkeypatch):
    """Same SUMO version: libsumo and TraCI give an identical reward trace; provenance records the backend."""
    import subprocess, sys
    pytest.importorskip("libsumo")
    code = ("import json,sys; from tests.integration.test_runtime_check_cadence import rollout; "
            "print(json.dumps(rollout(sys.argv[1])))")
    out = {}
    for backend in ("0", "1"):
        env = dict(__import__("os").environ, EDGEFLOW_LIBSUMO=backend)
        res = subprocess.run([sys.executable, "-c", code, str(tmp_path / backend)], env=env, capture_output=True,
                             text=True, check=True)  # own process: libsumo allows one simulation per process
        out[backend] = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["0"]["rewards"] == out["1"]["rewards"]
    assert (out["0"]["provenance"], out["1"]["provenance"]) == ("sumo_traci", "sumo_libsumo")
