"""Map-independent DQN family (unified_dqn_v1): scalar phase scorer or padded vector head."""
import json
import uuid
import numpy as np
from contracts.benchmark import OBSERVATION_SPEC as OBS, TIMING, UNIFIED_DQN as U
from contracts.contracts_sdk import validate_payload
from src.rl.policy import NumpyPolicy
from .controllers import BaseController
from .observation import flow_index, observe_node
from .phase_dqn import phase_mask

FEATURES, MAX_PHASES = len(OBS["features"]), OBS["max_phases"]


def input_dim(architecture):
    return FEATURES if architecture == "scalar_phase_scorer" else FEATURES * MAX_PHASES


def output_dim(architecture):
    return 1 if architecture == "scalar_phase_scorer" else MAX_PHASES


def pad_rows(observation):
    if len(observation) > MAX_PHASES:
        raise ValueError(f"More than {MAX_PHASES} phases is unsupported")
    padded = np.zeros((MAX_PHASES, FEATURES), np.float32)
    padded[: len(observation)] = observation
    return padded


def pad_node(observation):
    return pad_rows(observation).reshape(-1)


def phase_scores(architecture, policy, observation):
    """One Q value per native phase for a node observation of shape (phases, features)."""
    if architecture == "scalar_phase_scorer":
        return policy.predict(observation).ravel()
    return policy.predict(pad_node(observation))[: len(observation)]


class UnifiedDQNController(BaseController):
    def __init__(self, model_path, inference_device="cpu"):
        if not model_path:
            raise ValueError("Unified DQN controllers require an explicit model_path")
        with open(model_path, encoding="utf-8") as handle:
            self.artifact = a = json.load(handle)
        validate_payload(a, "unified_dqn_model")
        architecture, reward = U["algorithms"][a["algorithm"]]
        if (a["architecture"], a["reward_version"]) != (architecture, reward):
            raise ValueError("Artifact architecture/reward do not match its algorithm")
        if a["observation"] != OBS or a["timing"] != TIMING:
            raise ValueError("Incompatible observation specification or timing")
        self.name, self.architecture, self.radius = a["algorithm"], architecture, a["observation"]["radius_hops"]
        self.policy = NumpyPolicy(a["weights"])
        if (self.policy.state_dim, self.policy.action_dim) != (input_dim(architecture), output_dim(architecture)):
            raise ValueError("Weights do not match the declared architecture")
        if inference_device != "cpu":
            raise ValueError("Unified DQN inference is CPU/NumPy")
        self._index = {}

    def _flow(self, topology):
        return self._index.setdefault(topology["topology_id"], flow_index(topology))

    def _command(self, node, telemetry, view, topology):
        values = phase_scores(self.architecture, self.policy,
                              observe_node(node, view, self._flow(topology), self.radius))
        choice = int(np.argmax(np.where(phase_mask(node, telemetry), values, -np.inf)))
        return dict(command_id=str(uuid.uuid4()), node_id=node["node_id"],
                    target_phase_id=node["phases"][choice]["phase_id"],
                    min_green_s=TIMING["min_green_s"], max_green_s=TIMING["max_green_s"], controller=self.name)

    def _check(self, topology):
        if topology["topology_id"] != self.artifact["topology_id"]:
            raise ValueError("Model was trained for another map")

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        self._check(topology)
        node = next(n for n in topology["nodes"] if n["node_id"] == node_id)
        return self._command(node, telemetry, {**(network_state or {}), node_id: telemetry}, topology)

    def compute_commands(self, network_state, topology, current_time_s=None):
        self._check(topology)
        return {n["node_id"]: self._command(n, network_state[n["node_id"]], network_state, topology)
                for n in topology["nodes"]}
