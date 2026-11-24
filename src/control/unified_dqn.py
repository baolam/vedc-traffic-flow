"""Map-independent DQN family (unified_dqn_v1): scalar phase scorer or padded vector head."""
import json
import os
import uuid
import numpy as np
from contracts.benchmark import OBSERVATION_SPEC as OBS, TIMING, UNIFIED_DQN as U
from contracts.contracts_sdk import validate_payload
from src.rl.policy import NumpyPolicy
from .controllers import BaseController, MaxPressureController
from .observation import flow_index, observe_node
from .phase_dqn import phase_mask

FEATURES, MAX_PHASES = len(OBS["features"]), OBS["max_phases"]


PHASE_ARCHITECTURES = ("scalar_phase_scorer", "padded_vector_head")
MP_MARGIN = float(os.environ.get("EDGEFLOW_MP_MARGIN", "nan"))  # experiment: residual on a base controller; nan = off
RESIDUAL_BASE = os.environ.get("EDGEFLOW_RESIDUAL_BASE", "max_pressure")  # experiment: the residual's default policy
RESIDUAL_ALT = os.environ.get("EDGEFLOW_RESIDUAL_ALT", "")  # experiment: overrides may only pick this controller's phase
ALT_MARGIN = float(os.environ.get("EDGEFLOW_ALT_MARGIN", "nan"))  # experiment: two-tier residual; nan = off
_BASES = {}  # controller name -> [controller, last sim time seen]


def controller_index(name, node, telemetry, view, topology):
    """Index of a factory controller's target phase for this node."""
    if name not in _BASES:
        from .factory import create_controller  # lazy: factory imports this module

        _BASES[name] = [MaxPressureController() if name == "max_pressure" else create_controller(name), -1.0]
    entry = _BASES[name]
    now = telemetry["timestamp_ms"] / 1000
    if now < entry[1]:  # sim clock went back: a new run in this process, so drop the controller's per-node timers
        entry[0].reset()
    entry[1] = now
    target = entry[0].compute_command(node["node_id"], telemetry, topology, view, current_time_s=now)["target_phase_id"]
    return [p["phase_id"] for p in node["phases"]].index(target)


def base_index(node, telemetry, view, topology):
    """Index of the base controller's target phase for this node (the residual's default action)."""
    return controller_index(RESIDUAL_BASE, node, telemetry, view, topology)


def alt_index(node, telemetry, view, topology):
    return controller_index(RESIDUAL_ALT, node, telemetry, view, topology) if RESIDUAL_ALT else None


def residual_choice(values, mask, mp_index, alt=None):
    """Greedy legal phase, except keep the base's legal phase unless the best Q beats it by MP_MARGIN * |Q|.
    With an alt index (RESIDUAL_ALT), the only allowed override is the alt controller's phase; with ALT_MARGIN set
    as well (two-tier), any phase may still override at MP_MARGIN and the alt's phase already at ALT_MARGIN."""
    two_tier = not np.isnan(ALT_MARGIN)
    if alt is not None and not two_tier and not np.isnan(MP_MARGIN) and mask[mp_index]:
        mask = mask & np.isin(np.arange(len(mask)), (mp_index, alt))
    masked = np.where(mask, values, -np.inf)
    best = int(np.argmax(masked))
    if np.isnan(MP_MARGIN) or not mask[mp_index]:
        return best
    scale = abs(masked[mp_index])
    if masked[best] - masked[mp_index] > MP_MARGIN * scale:
        return best
    if two_tier and alt is not None and mask[alt] and masked[alt] - masked[mp_index] > ALT_MARGIN * scale:
        return alt
    return mp_index
PHASE_ALGORITHMS = tuple(a for a, (arch, _) in U["algorithms"].items() if arch in PHASE_ARCHITECTURES)


def input_dim(architecture):
    return dict(scalar_phase_scorer=FEATURES, padded_vector_head=FEATURES * MAX_PHASES)[architecture]


def output_dim(architecture):
    return dict(scalar_phase_scorer=1, padded_vector_head=MAX_PHASES)[architecture]


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
        if a["algorithm"] not in PHASE_ALGORITHMS:
            raise ValueError("Not a phase-selection model; use its own controller")
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
        mask = phase_mask(node, telemetry)
        choice = (int(np.argmax(np.where(mask, values, -np.inf))) if np.isnan(MP_MARGIN)
                  else residual_choice(values, mask, base_index(node, telemetry, view, topology),
                                    alt_index(node, telemetry, view, topology)))
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
