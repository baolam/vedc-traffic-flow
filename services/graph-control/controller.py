import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseController(ABC):
    @abstractmethod
    def compute_command(self, node_id: str, telemetry: Dict[str, Any], topology: Dict[str, Any]) -> Dict[str, Any]:
        """Compute control command for a specific intersection node given telemetry and topology."""
        pass


class FixedTimeController(BaseController):
    """Fixed-Time Controller cycling between available topology phases."""
    def __init__(self, cycle_time_s: float = 30.0):
        self.cycle_time_s = cycle_time_s
        self.phase_counters: Dict[str, int] = {}

    def compute_command(self, node_id: str, telemetry: Dict[str, Any], topology: Dict[str, Any]) -> Dict[str, Any]:
        node_info = next((n for n in topology.get("nodes", []) if n["node_id"] == node_id), None)
        if not node_info or not node_info.get("phases"):
            target_phase = telemetry.get("current_phase_id", "J1_PHASE_NS")
        else:
            phases = node_info["phases"]
            current_idx = self.phase_counters.get(node_id, 0)
            next_idx = (current_idx + 1) % len(phases)
            self.phase_counters[node_id] = next_idx
            target_phase = phases[next_idx]["phase_id"]

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": 10.0,
            "max_green_s": self.cycle_time_s,
            "controller": "fixed_time"
        }


class MaxPressureController(BaseController):
    """
    Generic Max-Pressure Controller.
    Calculates queue pressure for each phase of an intersection node using the topology phase's
    explicit 'approaches' definition. Works seamlessly across 3-way, 4-way, 5-way, and complex SUMO graphs.
    Pressure P(phase) = sum(Queue(approach) for approach in phase.approaches)
    """
    def __init__(self, min_green_s: float = 10.0, max_green_s: float = 60.0):
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s

    def compute_command(self, node_id: str, telemetry: Dict[str, Any], topology: Dict[str, Any]) -> Dict[str, Any]:
        node_info = next((n for n in topology.get("nodes", []) if n["node_id"] == node_id), None)
        phases = node_info.get("phases", []) if node_info else []

        approaches = telemetry.get("approaches", [])
        queue_map: Dict[str, float] = {app["approach_id"]: float(app.get("queue_vehicles", 0)) for app in approaches}

        phase_pressures: Dict[str, float] = {}

        for phase in phases:
            phase_id = phase["phase_id"]
            phase_apps = phase.get("approaches", [])
            pressure = sum(queue_map.get(app_id, 0.0) for app_id in phase_apps)
            phase_pressures[phase_id] = pressure

        if phase_pressures:
            target_phase = max(phase_pressures.items(), key=lambda x: x[1])[0]
        else:
            target_phase = telemetry.get("current_phase_id", "J1_PHASE_NS")

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": self.min_green_s,
            "max_green_s": self.max_green_s,
            "controller": "max_pressure"
        }
