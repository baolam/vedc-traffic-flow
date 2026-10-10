"""Shared features, legal actions and fail-closed research inference."""
import json
import uuid
import numpy as np

from contracts.contracts_sdk import validate_payload
from contracts.research import (FAIR_CYCLE_FEATURE_SPEC, FEATURE_SPEC, SIGNAL_STATES,
                                TIMING, TOPOLOGY_ID, validate_research_topology)
from src.rl.policy import NumpyPolicy
from .controllers import BaseController


def action_mask(node, telemetry):
    phases = [p["phase_id"] for p in node["phases"]]
    if len(phases) != 2 or telemetry["signal_state"] not in SIGNAL_STATES:
        raise ValueError("Research policy requires two phases and an explicit signal state")
    current = phases.index(telemetry["current_phase_id"])
    elapsed = float(telemetry["elapsed_green_s"])
    if not np.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid elapsed green")
    mask = np.ones(2, dtype=bool)
    if telemetry["signal_state"] != "GREEN":
        pending = phases.index(telemetry["pending_phase_id"])
        mask[:] = False
        mask[pending] = True
    elif elapsed < TIMING["min_green_s"]:
        mask[1-current] = False
    elif elapsed >= TIMING["max_green_s"]:
        mask[current] = False
    return mask


def extract_features(node, telemetry, network_state):
    action_mask(node, telemetry)  # Validate signal metadata even for training.
    local = {a["approach_id"]: a for a in telemetry["approaches"]}
    movements = {m["from_approach"]: m for p in node["phases"] for m in p["movements"]}
    result, downstream, valid = [], [], []
    for app in node["approaches"]:
        data = local[app]
        q, occ, confidence = (float(data[k]) for k in ("queue_vehicles", "occupancy_ratio", "confidence"))
        if q < 0 or not 0 <= occ <= 1 or not 0 <= confidence <= 1:
            raise ValueError("Invalid approach measurement")
        result.extend((q / 20, occ))
        valid.append(confidence)
        m = movements[app]
        if m["to_node"]:
            target = {a["approach_id"]: a for a in network_state[m["to_node"]]["approaches"]}[m["to_approach"]]
            dq, do = float(target["queue_vehicles"]), float(target["occupancy_ratio"])
            if dq < 0 or not 0 <= do <= 1:
                raise ValueError("Invalid downstream measurement")
            downstream.extend((dq / 20, do))
        else:
            downstream.extend((0., 0.))
    result.extend(downstream)
    result.extend(float(p["phase_id"] == telemetry["current_phase_id"]) for p in node["phases"])
    result.extend(float(s == telemetry["signal_state"]) for s in SIGNAL_STATES)
    result.append(telemetry["elapsed_green_s"] / 60)
    ages = [telemetry["phase_service_age_s"][p["phase_id"]] for p in node["phases"]]
    if any(age < 0 for age in ages):
        raise ValueError("Negative service age")
    result.extend(age / 60 for age in ages)
    result.extend(valid)
    array = np.asarray(result, dtype=np.float32)
    if array.shape != (len(FEATURE_SPEC["ordering"]),) or not np.isfinite(array).all():
        raise ValueError("Invalid research observation")
    return array


def extract_fair_cycle_features(node, telemetry, network_state, base_split, previous_split,
                                demand_s=1800, horizon_s=2400):
    """The training and deployment feature path for the bounded residual policy."""
    base = extract_features(node, telemetry, network_state)
    local = {a["approach_id"]: a for a in telemetry["approaches"]}
    extra = []
    for approach in node["approaches"]:
        value = local[approach]
        waits = [float(value[key]) for key in ("stopped_wait_sum_s", "oldest_stopped_wait_s",
                                               "external_due_count", "external_wait_sum_s",
                                               "oldest_external_wait_s")]
        if not np.isfinite(waits).all() or any(wait < 0 for wait in waits):
            raise ValueError("Invalid required fair-cycle wait measurement")
        extra.extend((waits[0] / 2400., waits[1] / 1200., waits[2] / 20.,
                      waits[3] / 2400., waits[4] / 1200.))
    now = float(telemetry["simulation_time_s"])
    if not np.isfinite(now) or demand_s <= 0 or horizon_s <= 0 or now < 0:
        raise ValueError("Invalid fair-cycle time horizon")
    if len(base_split) != 2 or len(previous_split) != 2 or min(*base_split, *previous_split) <= 0:
        raise ValueError("Invalid fair-cycle split")
    extra.extend((max(0., demand_s - now) / demand_s, max(0., horizon_s - now) / horizon_s,
                  base_split[0] / sum(base_split), previous_split[0] / sum(previous_split)))
    result = np.concatenate((base, np.asarray(extra, dtype=np.float32)))
    if result.shape != (len(FAIR_CYCLE_FEATURE_SPEC["ordering"]),) or not np.isfinite(result).all():
        raise ValueError("Invalid fair-cycle observation")
    return result


class SharedDQNController(BaseController):
    def __init__(self, model_path):
        if not model_path:
            raise ValueError("shared_dqn requires an explicit model_path")
        with open(model_path, encoding="utf-8") as handle:
            self.artifact = json.load(handle)
        validate_payload(self.artifact, "shared_dqn_model")
        if self.artifact["feature_spec"] != FEATURE_SPEC or self.artifact["timing"] != TIMING:
            raise ValueError("Incompatible feature specification or signal timing")
        if self.artifact["topology_id"] != TOPOLOGY_ID:
            raise ValueError("Incompatible model topology")
        self.policy = NumpyPolicy(self.artifact["weights"])
        if self.policy.state_dim != len(FEATURE_SPEC["ordering"]) or self.policy.action_dim != 2:
            raise ValueError("Incompatible research model dimensions")

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        if topology["topology_id"] != self.artifact["topology_id"]:
            raise ValueError("Model/topology mismatch")
        validate_research_topology(topology)
        node = next(n for n in topology["nodes"] if n["node_id"] == node_id)
        x = extract_features(node, telemetry, network_state)
        action = int(np.argmax(np.where(action_mask(node, telemetry), self.policy.predict(x), -np.inf)))
        return {"command_id": str(uuid.uuid4()), "node_id": node_id,
                "target_phase_id": node["phases"][action]["phase_id"],
                "min_green_s": TIMING["min_green_s"], "max_green_s": TIMING["max_green_s"],
                "controller": "shared_dqn"}


from .fair_cycle import FairCycleController


class FairCycleRLController(FairCycleController):
    """Fair-cycle controller with a masked, three-action timing residual."""

    controller_name = "fair_cycle_rl"

    def __init__(self, model_path, cycle_time_s=None, min_green_share=None):
        if not model_path:
            raise ValueError("fair_cycle_rl requires an explicit model_path")
        with open(model_path, encoding="utf-8") as handle:
            self.artifact = json.load(handle)
        validate_payload(self.artifact, "fair_cycle_dqn_model")
        artifact_timing = self.artifact.get("timing", {})
        cycle_time_s = artifact_timing.get("cycle_time_s", 70) if cycle_time_s is None else cycle_time_s
        min_green_share = artifact_timing.get("min_green_share", 1 / 3) if min_green_share is None else min_green_share
        super().__init__(cycle_time_s, min_green_share)
        if (self.artifact["feature_spec"] != FAIR_CYCLE_FEATURE_SPEC
                or self.artifact["topology_id"] != TOPOLOGY_ID
                or self.artifact["timing"] != {**TIMING, "cycle_time_s": cycle_time_s,
                                                "min_green_share": min_green_share}):
            raise ValueError("Incompatible fair-cycle model feature, topology or timing contract")
        self.policy = NumpyPolicy(self.artifact["weights"])
        if self.policy.state_dim != len(FAIR_CYCLE_FEATURE_SPEC["ordering"]) or self.policy.action_dim != 3:
            raise ValueError("Fair-cycle model must accept v1 fair-cycle features and 3 residual actions")

    def _policy_adjustment(self, node_id, phases, telemetry, network_state, base_split):
        state = self._state.get(node_id, {})
        observation = extract_fair_cycle_features(
            next(n for n in self._topology_nodes if n["node_id"] == node_id),
            telemetry, network_state, base_split, state.get("split", base_split))
        mask = self.residual_mask_for(base_split[0])
        q = self.policy.predict(observation)
        action = int(np.argmax(np.where(mask, q, -np.inf)))
        return (-5, 0, 5)[action]

    def residual_mask_for(self, ns_green):
        return super().residual_mask_for(ns_green)

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        validate_research_topology(topology)
        self._topology_nodes = topology["nodes"]
        return super().compute_command(node_id, telemetry, topology, network_state, current_time_s)
