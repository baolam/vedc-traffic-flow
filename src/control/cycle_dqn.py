"""Native-phase fair cycle: a model-free baseline and a learned 5 s green-transfer residual.

Both use the cycle rule in contracts (CYCLE_RULE). At each node's cycle start a `selector` may pick one
transfer (donor -> recipient) or no-op; training and deployment share that single code path.
"""
import json
import uuid

import numpy as np

from contracts.benchmark import CYCLE_DQN as D, CYCLE_RULE as R, OBSERVATION_SPEC as OBS, TIMING
from contracts.contracts_sdk import validate_payload
from src.rl.policy import NumpyPolicy
from .controllers import BaseController
from .cycle_plan import allocate_greens, apply_transfer, cycle_length
from .fair_cycle import FairCycleController
from .observation import flow_index, observe_node
from .unified_dqn import FEATURES, MAX_PHASES, pad_rows

GRID = MAX_PHASES * MAX_PHASES + 1  # slot donor * MAX_PHASES + recipient, last slot = no-op
NOOP = GRID - 1
CANDIDATE_DIM = 2 * FEATURES + len(D["extras"])
_DONOR, _RECIPIENT = np.divmod(np.arange(NOOP), MAX_PHASES)


def candidate_mask(greens, phases):
    """Legal slots for padded greens (..., MAX_PHASES) and phase counts (...); the no-op is always legal."""
    g, p = np.asarray(greens), np.asarray(phases)[..., None]
    legal = ((_DONOR < p) & (_RECIPIENT < p) & (_DONOR != _RECIPIENT)
             & (g[..., _DONOR] - R["quantum_s"] >= R["min_green_s"])
             & (g[..., _RECIPIENT] + R["quantum_s"] <= R["max_green_s"]))
    return np.concatenate([legal, np.ones(legal.shape[:-1] + (1,), bool)], axis=-1)


def candidate_features(rows, greens, phases):
    """Candidate inputs (..., GRID, CANDIDATE_DIM) from padded phase rows (..., MAX_PHASES, FEATURES)."""
    rows, g = np.asarray(rows, np.float32), np.asarray(greens, np.float32)
    lead = rows.shape[:-2]
    cycle = np.maximum(R["base_s"], R["per_phase_s"] * np.asarray(phases, np.float32)) / 200
    extras = np.zeros(lead + (GRID, len(D["extras"])), np.float32)  # is_noop, donor, recipient, cycle_length
    extras[..., NOOP, 0] = 1
    extras[..., :NOOP, 1] = g[..., _DONOR] / R["max_green_s"]
    extras[..., :NOOP, 2] = g[..., _RECIPIENT] / R["max_green_s"]
    extras[..., 3] = cycle[..., None]
    pairs = np.zeros(lead + (GRID, 2 * FEATURES), np.float32)
    pairs[..., :NOOP, :FEATURES] = rows[..., _DONOR, :]
    pairs[..., :NOOP, FEATURES:] = rows[..., _RECIPIENT, :]
    return np.concatenate([pairs, extras], axis=-1)


class FairCycleNativeController(BaseController):
    """Serve every native phase each cycle for its planned green; greens follow wait/backlog pressure."""

    controller_name = "fair_cycle_native"

    def __init__(self, selector=None):
        self.selector = selector  # (node, view, base_greens) -> slot in [0, GRID)
        self._state = {}

    def reset(self):
        self._state.clear()

    def plans(self):
        """Greens of each node's running cycle (empty before its first cycle)."""
        return {nid: list(state["greens"]) for nid, state in self._state.items()}

    def _start_cycle(self, node, view, idx):
        local = {a["approach_id"]: a for a in view[node["node_id"]]["approaches"]}
        base = allocate_greens([FairCycleController._pressure(p, local, view) for p in node["phases"]])
        greens, slot = base, NOOP
        if self.selector is not None:
            slot = int(self.selector(node, view, base))
            if slot != NOOP:
                greens = apply_transfer(base, *divmod(slot, MAX_PHASES))
        assert sum(greens) + R["clearance_s"] * len(greens) == cycle_length(len(greens))
        return dict(idx=idx, greens=greens, base=base, slot=slot)

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        node = next((n for n in topology.get("nodes", []) if n["node_id"] == node_id), None)
        if not node or not 2 <= len(node["phases"]) <= MAX_PHASES:
            return None
        ids = [p["phase_id"] for p in node["phases"]]
        idx = ids.index(telemetry["current_phase_id"])
        green = telemetry.get("signal_state", "GREEN") == "GREEN"
        elapsed = float(telemetry.get("elapsed_green_s", 0))
        view = {**(network_state or {}), node_id: telemetry}
        state = self._state.get(node_id)
        if state is None or (idx == 0 and state["idx"] == len(ids) - 1 and green and elapsed == 0):
            state = self._state[node_id] = self._start_cycle(node, view, idx)
        state["idx"] = idx
        target = ids[(idx + 1) % len(ids)] if green and elapsed >= state["greens"][idx] else ids[idx]
        return {"command_id": str(uuid.uuid4()), "node_id": node_id, "target_phase_id": target,
                "min_green_s": float(TIMING["min_green_s"]), "max_green_s": float(TIMING["max_green_s"]),
                "controller": self.controller_name}


class FairCycleUnifiedController(FairCycleNativeController):
    """Learned residual (fair_cycle_unified): greedy candidate scoring over the legal transfers."""

    controller_name = "fair_cycle_unified"

    def __init__(self, model_path, inference_device="cpu"):
        if not model_path:
            raise ValueError("fair_cycle_unified requires an explicit model_path")
        with open(model_path, encoding="utf-8") as handle:
            self.artifact = a = json.load(handle)
        validate_payload(a, "unified_dqn_model")
        if (a["algorithm"] != self.controller_name or a["observation"] != OBS or a["timing"] != TIMING
                or a.get("cycle_rule") != R or a.get("candidate_extras") != D["extras"]):
            raise ValueError("Incompatible fair-cycle model specification")
        self.policy = NumpyPolicy(a["weights"])
        if (self.policy.state_dim, self.policy.action_dim) != (CANDIDATE_DIM, 1):
            raise ValueError("Weights do not match the candidate scorer")
        if inference_device != "cpu":
            raise ValueError("Unified DQN inference is CPU/NumPy")
        self._flow = {}
        super().__init__(selector=self._select)

    def _select(self, node, view, base):
        rows = pad_rows(observe_node(node, view, self._current_flow, self.artifact["observation"]["radius_hops"]))
        greens = np.zeros(MAX_PHASES, np.float32)
        greens[: len(base)] = base
        q = self.policy.predict(candidate_features(rows, greens, len(base))).ravel()
        return int(np.argmax(np.where(candidate_mask(greens, len(base)), q, -np.inf)))

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        if topology["topology_id"] != self.artifact["topology_id"]:
            raise ValueError("Model was trained for another map")
        self._current_flow = self._flow.setdefault(topology["topology_id"], flow_index(topology))
        return super().compute_command(node_id, telemetry, topology, network_state, current_time_s)
