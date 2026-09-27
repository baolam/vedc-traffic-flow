import json

import numpy as np
import pytest

from src.rl.policy import NumpyPolicy
from src.rl.train_dqn import DQNAgent, ReplayBuffer, train_presslight
from src.rl.traffic_env import TrafficSignalEnv
from src.rl.evaluate import evaluate
from controller import PressLightRLController


def test_export_preserves_batched_and_single_predictions(tmp_path):
    agent = DQNAgent(12, 2, seed=4)
    observations = np.random.default_rng(7).random((8, 12))
    path = tmp_path / "model.json"
    agent.save_weights(path)
    policy = NumpyPolicy(json.loads(path.read_text()))
    np.testing.assert_allclose(policy.predict(observations), agent.forward(observations)[1])
    np.testing.assert_allclose(policy.predict(observations[0]), agent.forward(observations[0])[1])
    with pytest.raises(ValueError):
        policy.predict(np.zeros(13))
    with pytest.raises(ValueError):
        policy.predict(np.full(12, np.nan))


def test_corrupt_weights_fail_instead_of_falling_back(tmp_path):
    data = DQNAgent(12, 2).export_weights()
    data["w2"][0] = [1.0]
    with pytest.raises(ValueError):
        PressLightRLController(weights=data)
    with pytest.raises(FileNotFoundError):
        PressLightRLController(model_path=str(tmp_path / "missing.json"))


def test_target_is_frozen_then_synchronized_and_training_is_reproducible():
    a = DQNAgent(4, 2, seed=9, target_update_interval=2)
    b = DQNAgent(4, 2, seed=9, target_update_interval=2)
    before = [p.copy() for p in a.target]
    batch = (np.ones((8, 4)), np.zeros(8, dtype=int), np.full(8, -2), np.zeros((8, 4)), np.ones(8))
    a.update(batch)
    b.update(batch)
    for target, old in zip(a.target, before):
        np.testing.assert_array_equal(target, old)
    assert any(not np.array_equal(p, t) for p, t in zip(a.parameters, a.target))
    a.update(batch)
    b.update(batch)
    for p, q, t in zip(a.parameters, b.parameters, a.target):
        np.testing.assert_array_equal(p, q)
        np.testing.assert_array_equal(p, t)


def test_terminal_regression_reduces_error_with_bounded_exploration():
    agent = DQNAgent(4, 2, seed=2, lr=.01, epsilon=.1, epsilon_min=.05, epsilon_decay=.5)
    batch = (np.ones((16, 4)), np.zeros(16, dtype=int), np.full(16, -2), np.zeros((16, 4)), np.ones(16))
    before = abs(agent.forward(np.ones(4))[1][0] + 2)
    for _ in range(100):
        agent.update(batch)
        agent.decay_exploration()
    assert abs(agent.forward(np.ones(4))[1][0] + 2) < before * .1
    assert agent.epsilon == .05


def test_replay_copies_observations_and_wraps():
    replay = ReplayBuffer(2, seed=5)
    state = np.ones(4)
    replay.push(state, 0, 1, state, False)
    state[:] = 99
    assert replay.sample(1)[0][0, 0] == 1
    replay.push(np.ones(4) * 2, 0, 2, state, False)
    replay.push(np.ones(4) * 3, 1, 3, state, True)
    assert len(replay) == 2
    assert set(replay.sample(2)[2]) == {2, 3}


def test_training_and_controller_features_match_and_demand_is_action_independent():
    env_a, env_b = TrafficSignalEnv(max_steps=12), TrafficSignalEnv(max_steps=12)
    controller = PressLightRLController()
    for scenario in env_a.SCENARIOS:
        obs, _ = env_a.reset(seed=123, scenario=scenario)
        env_b.reset(seed=123, scenario=scenario)
        np.testing.assert_array_equal(obs, controller.extract_features(
            env_a.target_node, env_a.telemetry(), env_a.topology, env_a.network_state))
        for _ in range(12):
            obs, _, terminated, truncated, _ = env_a.step(0)
            env_b.step(1)
            np.testing.assert_array_equal(obs, controller.extract_features(
                env_a.target_node, env_a.telemetry(), env_a.topology, env_a.network_state))
        np.testing.assert_array_equal(env_a.arrivals, env_b.arrivals)
        assert not terminated and truncated
        with pytest.raises(RuntimeError):
            env_a.step(0)


def test_train_and_evaluate_record_provenance_and_reject_seed_leakage(tmp_path):
    path = tmp_path / "new_model.json"
    result = train_presslight(episodes=3, max_steps_per_episode=48, output_path=path, seed=50)
    assert result["updates"] > 0
    assert not result["valid_for_research"]
    with pytest.raises(ValueError, match="overlap"):
        evaluate(path, seeds=[51], output_path=tmp_path / "bad.json")
    report = evaluate(path, seeds=[10001, 10002], steps=12, output_path=tmp_path / "eval.json")
    assert len(report["runs"]) == 18
    for scenario in TrafficSignalEnv.SCENARIOS:
        for seed in report["seeds"]:
            hashes = {r["demand_sha256"] for r in report["runs"] if r["scenario"] == scenario and r["seed"] == seed}
            assert len(hashes) == 1
