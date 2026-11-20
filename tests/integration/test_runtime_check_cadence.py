"""Real SUMO: check_every thins schema/readback checks for training rollouts; the default checks every step."""
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


def test_default_checks_every_decision_and_large_cadence_only_when_due(tmp_path):
    every = validations(tmp_path / "a")
    assert sorted(set(every)) == [5, 10, 15, 20, 25, 30]  # each of the 4 nodes at every decision
    thinned = validations(tmp_path / "b", check_every=15)
    assert sorted(set(thinned)) == [15, 30] and len(thinned) == 8


@pytest.mark.parametrize("bad", [0, -1, 2.5, True])
def test_check_every_must_be_a_positive_integer(tmp_path, bad):
    with pytest.raises(ValueError):
        SumoRuntime(TOPOLOGY, NETWORK, tmp_path / "run", check_every=bad)
