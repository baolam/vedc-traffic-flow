"""Shared numerical policy code; IDs and ordering come from contracts topology."""
import numpy as np


def extract_features(node, telemetry, network_state=None, capacity=20.0):
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    observations = {a["approach_id"]: a for a in telemetry.get("approaches", [])}
    queues = {key: float(value.get("queue_vehicles", 0)) for key, value in observations.items()}
    phases = node.get("phases", [])
    current = telemetry.get("current_phase_id", phases[0]["phase_id"] if phases else "")
    result = []
    for app in node.get("approaches", []):
        result.extend((min(1., max(0., queues.get(app, 0) / capacity)),
                       min(1., max(0., float(observations.get(app, {}).get("occupancy_ratio", 0))))))
    result.extend(float(p["phase_id"] == current) for p in phases)
    downstream = {}
    for key, value in (network_state or {}).items():
        apps = value.get("approaches", [])
        downstream[key] = sum(float(a.get("queue_vehicles", 0)) for a in apps) / max(1, len(apps))
    for phase in phases:
        movements = phase.get("movements", [])
        if movements:
            pressure = sum(queues.get(m.get("from_approach"), 0)
                           - float(m.get("turn_ratio", 1)) * downstream.get(m.get("to_node"), 0)
                           for m in movements)
        else:
            pressure = sum(queues.get(a, 0) for a in phase.get("approaches", []))
        result.append(min(1., max(-1., pressure / capacity)))
    values = np.asarray(result, dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite policy observations")
    return values


class NumpyPolicy:
    """Validate once and retain contiguous arrays for fast repeated inference."""

    def __init__(self, weights):
        self.w1 = np.ascontiguousarray(weights["w1"], dtype=np.float32)
        self.w2 = np.ascontiguousarray(weights["w2"], dtype=np.float32)
        if self.w1.ndim != 2 or self.w2.ndim != 2:
            raise ValueError("MLP weights must be matrices")
        hidden, self.state_dim = self.w1.shape
        self.action_dim = self.w2.shape[0]
        self.b1 = np.asarray(weights.get("b1", np.zeros(hidden)), dtype=np.float32)
        self.b2 = np.asarray(weights.get("b2", np.zeros(self.action_dim)), dtype=np.float32)
        if (not hidden or not self.state_dim or not self.action_dim
                or self.w2.shape[1] != hidden or self.b1.shape != (hidden,)
                or self.b2.shape != (self.action_dim,)):
            raise ValueError("Incompatible MLP weight dimensions")
        for name, expected in (("state_dim", self.state_dim), ("action_dim", self.action_dim),
                               ("hidden_dim", hidden)):
            if name in weights and weights[name] != expected:
                raise ValueError(f"Invalid {name} metadata")
        if not all(np.isfinite(a).all() for a in (self.w1, self.b1, self.w2, self.b2)):
            raise ValueError("Model contains non-finite weights")
        self.feature_spec = weights.get("feature_spec", {})

    def predict(self, observations):
        x = np.asarray(observations, dtype=np.float32)
        if x.ndim not in (1, 2) or x.shape[-1] != self.state_dim or not np.isfinite(x).all():
            raise ValueError(f"Expected finite observations with final dimension {self.state_dim}")
        result = np.maximum(x @ self.w1.T + self.b1, 0) @ self.w2.T + self.b2
        if not np.isfinite(result).all():
            raise ValueError("Non-finite Q values")
        return result
