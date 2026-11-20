import numpy as np
import pytest
import torch

from contracts.benchmark import DQN_RECIPE, OBSERVATION_SPEC, UNIFIED_DQN
from src.control.unified_dqn import FEATURES, MAX_PHASES, UnifiedDQNController
from src.rl.unified_train import Replay, build_net, discount, export_artifact, node_pressure_reward, q_all
from tests.unit.test_observation import chain, telemetry, set_queue


def test_discount_is_physical_time_based():
    assert discount(DQN_RECIPE, 5) == pytest.approx(0.99)
    assert discount(DQN_RECIPE, 70) == pytest.approx(0.99 ** 14)
    assert discount(DQN_RECIPE, 70) == pytest.approx(0.869, abs=1e-3)


def test_node_pressure_reward_uses_incoming_minus_receiving():
    top = chain()
    tel = telemetry(top)
    set_queue(tel, "C", "C_W", 10)
    set_queue(tel, "C", "C_S", 10)
    set_queue(tel, "D", "D_W", 4)
    node = next(n for n in top["nodes"] if n["node_id"] == "C")
    assert node_pressure_reward(node, tel) == pytest.approx(-(20 - 4) / 20)
    last = next(n for n in top["nodes"] if n["node_id"] == "E")
    assert node_pressure_reward(last, tel) == pytest.approx(0.0)  # boundary: no receiving approaches


def test_replay_ring_and_state_roundtrip():
    r = Replay(3)
    row = dict(s=np.ones((MAX_PHASES, FEATURES)), action=1, reward=-1.0, s2=np.zeros((MAX_PHASES, FEATURES)),
               m2=np.ones(MAX_PHASES), terminal=False, dt=5.0)
    for i in range(5):
        r.add(**{**row, "reward": float(i)})
    assert r.size == 3 and sorted(r.a["reward"].tolist()) == [2.0, 3.0, 4.0]
    other = Replay(3)
    other.load(r.state())
    assert other.size == 3 and other.ptr == r.ptr
    assert other.sample(8, np.random.default_rng(0))["s"].shape == (8, MAX_PHASES, FEATURES)


@pytest.mark.parametrize("algorithm", UNIFIED_DQN["algorithms"])
def test_exported_numpy_policy_matches_torch_and_loads(tmp_path, algorithm):
    architecture = UNIFIED_DQN["algorithms"][algorithm][0]
    net = build_net(architecture)
    (tmp_path / "n.net").write_text("n")
    (tmp_path / "t.json").write_text("t")
    spec = dict(id="chain", network_path=str(tmp_path / "n.net"), topology_path=str(tmp_path / "t.json"))
    export_artifact(spec, algorithm, net, 17, tmp_path / "m.json")  # raises on torch/numpy mismatch
    controller = UnifiedDQNController(str(tmp_path / "m.json"))
    top = chain()
    commands = controller.compute_commands(telemetry(top), {**top, "topology_id": "chain"})
    assert len(commands) == len(top["nodes"])
    x = torch.rand(4, MAX_PHASES, FEATURES)
    assert q_all(architecture, net, x).shape == (4, MAX_PHASES)
    assert OBSERVATION_SPEC["max_phases"] == MAX_PHASES
