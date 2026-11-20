import json

import numpy as np
import pytest

from contracts.benchmark import OBSERVATION_SPEC, TIMING, UNIFIED_DQN
from src.control.factory import create_controller
from src.control.unified_dqn import PHASE_ALGORITHMS, MAX_PHASES, input_dim, output_dim, pad_node, phase_scores
from src.rl.policy import NumpyPolicy
from tests.unit.test_observation import chain, telemetry


def artifact(algorithm, topology_id="chain", seed=0, **override):
    architecture, reward = UNIFIED_DQN["algorithms"][algorithm]
    rng = np.random.default_rng(seed)
    h = UNIFIED_DQN["hidden"]
    a = dict(schema="unified_dqn_v1", algorithm=algorithm, architecture=architecture, reward_version=reward,
             observation=OBSERVATION_SPEC, timing=TIMING, topology_id=topology_id,
             weights=dict(w1=rng.normal(size=(h, input_dim(architecture))).tolist(),
                          w2=rng.normal(size=(output_dim(architecture), h)).tolist()),
             provenance=dict(network_sha256="n", topology_sha256="t", learner_seed=17))
    a.update(override)
    return a


def write(tmp_path, a):
    path = tmp_path / "m.json"
    path.write_text(json.dumps(a))
    return str(path)


@pytest.mark.parametrize("algorithm", PHASE_ALGORITHMS)
def test_controller_runs_and_returns_legal_phase(tmp_path, algorithm):
    top = chain()
    tel = telemetry(top)
    c = create_controller(algorithm, model_path=write(tmp_path, artifact(algorithm)))
    commands = c.compute_commands(tel, top)
    assert set(commands) == {n["node_id"] for n in top["nodes"]}
    assert all(cmd["controller"] == algorithm for cmd in commands.values())
    # min green not reached -> must hold the current phase
    tel["C"]["elapsed_green_s"] = 1.0
    assert c.compute_commands(tel, top)["C"]["target_phase_id"] == "C_P0"
    single = c.compute_command("C", tel["C"], top, tel)
    assert single["target_phase_id"] == "C_P0"


def test_padded_head_ignores_padding_slots():
    obs = np.ones((3, len(OBSERVATION_SPEC["features"])), np.float32)
    assert pad_node(obs).shape == (MAX_PHASES * obs.shape[1],)
    policy = NumpyPolicy(artifact("shared_dqn_unified")["weights"])
    assert phase_scores("padded_vector_head", policy, obs).shape == (3,)
    with pytest.raises(ValueError):
        pad_node(np.ones((MAX_PHASES + 1, obs.shape[1]), np.float32))


def test_rejects_wrong_map_spec_algorithm_and_shape(tmp_path):
    top, tel = chain(), None
    c = create_controller("phase_dqn_unified", model_path=write(tmp_path, artifact("phase_dqn_unified", "other")))
    with pytest.raises(ValueError):
        c.compute_commands(telemetry(top), top)
    bad_obs = dict(OBSERVATION_SPEC, radius_hops=1)
    for bad in (artifact("phase_dqn_unified", observation=bad_obs),
                artifact("phase_dqn_unified", reward_version="node_pressure_v1"),
                artifact("phase_dqn_unified", architecture="padded_vector_head")):
        with pytest.raises(ValueError):
            create_controller("phase_dqn_unified", model_path=write(tmp_path, bad))
    with pytest.raises(ValueError):
        create_controller("phase_dqn_unified")


@pytest.mark.parametrize("algorithm", PHASE_ALGORITHMS)
def test_decisions_depend_on_weights(tmp_path, algorithm):
    top = chain()
    a = create_controller(algorithm, model_path=write(tmp_path, artifact(algorithm, seed=1)))
    b = create_controller(algorithm, model_path=write(tmp_path, artifact(algorithm, seed=2)))
    rng = np.random.default_rng(0)
    differing = 0
    for _ in range(30):
        tel = telemetry(top)
        for node in tel.values():
            node["approaches"][0]["queue_vehicles"], node["approaches"][1]["queue_vehicles"] = rng.random(2) * 20
            node["current_phase_id"] = node["node_id"] + "_P" + str(rng.integers(2))
        ca, cb = a.compute_commands(tel, top), b.compute_commands(tel, top)
        differing += sum(ca[k]["target_phase_id"] != cb[k]["target_phase_id"] for k in ca)
    assert differing > 0
