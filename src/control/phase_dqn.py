"""Map-bound phase scoring with framework-free production inference."""

import json
import uuid
import numpy as np
from contracts.benchmark import PHASE_FEATURES, PHASE_NORMALIZATION, TIMING
from contracts.contracts_sdk import validate_payload
from src.rl.policy import NumpyPolicy
from .controllers import BaseController


def phase_mask(node, telemetry):
    phases = [p["phase_id"] for p in node["phases"]]
    current = phases.index(telemetry["current_phase_id"])
    mask = np.ones(len(phases), dtype=bool)
    if telemetry["signal_state"] != "GREEN":
        mask[:] = False
        mask[phases.index(telemetry.get("pending_phase_id") or phases[current])] = True
    elif telemetry["elapsed_green_s"] < TIMING["min_green_s"]:
        mask[:] = False
        mask[current] = True
    elif telemetry["elapsed_green_s"] >= TIMING["max_green_s"]:
        mask[current] = False
    if not mask.any():
        raise ValueError("No legal signal phase")
    return mask


def phase_features(node, telemetry, network):
    local = {a["approach_id"]: a for a in telemetry["approaches"]}
    rows = []
    for phase in node["phases"]:
        served = [local[a] for a in sorted(set(phase["approaches"]))]
        downstream = {}
        for movement in phase.get("movements", []):
            target, approach = movement.get("to_node"), movement.get("to_approach")
            if target is not None:
                downstream[(target, approach)] = next(
                    a for a in network[target]["approaches"] if a["approach_id"] == approach
                )
        received = list(downstream.values())
        confidence = [a["confidence"] for a in served + received]
        if not served or min(confidence) <= 0:
            raise ValueError("Required phase observations unavailable")
        rows.append(
            [
                sum(a["queue_vehicles"] for a in served) / 20,
                np.mean([a["occupancy_ratio"] for a in served]),
                sum(a["queue_vehicles"] for a in received) / 20,
                max((a["occupancy_ratio"] for a in received), default=0),
                sum(a["queue_vehicles"] for key, a in local.items() if key not in phase["approaches"]) / 20,
                telemetry["phase_service_age_s"][phase["phase_id"]] / 60,
                telemetry["elapsed_green_s"] / 60,
                float(phase["phase_id"] == telemetry["current_phase_id"]),
                *[float(telemetry["signal_state"] == s) for s in ("GREEN", "YELLOW", "ALL_RED")],
                min(confidence),
            ]
        )
    result = np.asarray(rows, dtype=np.float32)
    if result.shape != (len(node["phases"]), len(PHASE_FEATURES)) or not np.isfinite(result).all():
        raise ValueError("Invalid phase observations")
    return result


class PhaseDQNController(BaseController):
    def __init__(self, model_path, inference_device="cpu"):
        with open(model_path) as handle:
            self.artifact = json.load(handle)
        validate_payload(self.artifact, "phase_dqn_model")
        if (
            self.artifact["features"] != PHASE_FEATURES
            or self.artifact["normalization"] != PHASE_NORMALIZATION
            or self.artifact["timing"] != TIMING
        ):
            raise ValueError("Incompatible phase model protocol")
        self.policy = NumpyPolicy(self.artifact["weights"])
        if self.policy.state_dim != 12 or self.policy.action_dim != 1 or self.policy.w1.shape[0] != 64:
            raise ValueError("Expected 12-input scalar phase scorer")
        if inference_device not in ("cpu", "cuda"):
            raise ValueError("Inference device must be cpu or cuda")
        if inference_device == "cuda":
            from src.rl.phase_cuda import CudaPolicy

            self.policy = CudaPolicy(self.artifact["weights"])

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        if topology["topology_id"] != self.artifact["topology_id"]:
            raise ValueError("Model was trained for another map")
        node = next(n for n in topology["nodes"] if n["node_id"] == node_id)
        values = self.policy.predict(phase_features(node, telemetry, network_state)).ravel()
        index = int(np.argmax(np.where(phase_mask(node, telemetry), values, -np.inf)))
        return dict(
            command_id=str(uuid.uuid4()),
            node_id=node_id,
            target_phase_id=node["phases"][index]["phase_id"],
            min_green_s=10,
            max_green_s=60,
            controller="phase_dqn",
        )

    def compute_commands(self, network_state, topology, current_time_s=None):
        if topology["topology_id"] != self.artifact["topology_id"]:
            raise ValueError("Model was trained for another map")
        features = [phase_features(n, network_state[n["node_id"]], network_state) for n in topology["nodes"]]
        scores = self.policy.predict(np.concatenate(features)).ravel()
        commands = {}
        offset = 0
        for node, x in zip(topology["nodes"], features):
            nid = node["node_id"]
            selected = int(
                np.argmax(np.where(phase_mask(node, network_state[nid]), scores[offset : offset + len(x)], -np.inf))
            )
            commands[nid] = dict(
                command_id=str(uuid.uuid4()),
                node_id=nid,
                target_phase_id=node["phases"][selected]["phase_id"],
                min_green_s=10,
                max_green_s=60,
                controller="phase_dqn",
            )
            offset += len(x)
        return commands
