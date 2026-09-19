import time
import random
from typing import Dict, Any, List
from simulator_contracts_helper import validate_payload

class ApproachState:
    def __init__(self, approach_id: str, capacity: float = 30.0):
        self.approach_id = approach_id
        self.capacity = capacity
        self.queue_vehicles: float = random.uniform(3.0, 8.0)
        self.flow_veh_per_s: float = 0.0
        self.mean_speed_mps: float = 5.0
        self.occupancy_ratio: float = self.queue_vehicles / self.capacity
        self.confidence: float = 1.0

    def step(self, is_green: bool, dt_s: float = 1.0):
        arrival_rate = random.uniform(0.2, 0.4)  # vehicles per second coming in
        
        if is_green:
            discharge_rate = random.uniform(0.5, 0.8)  # vehicles per second leaving
            net_change = (arrival_rate - discharge_rate) * dt_s
            self.queue_vehicles = max(0.0, self.queue_vehicles + net_change)
            self.flow_veh_per_s = round(discharge_rate, 2)
            
            # Speed increases as queue decreases
            if self.queue_vehicles < 2.0:
                self.mean_speed_mps = round(random.uniform(9.0, 12.0), 2)
            else:
                self.mean_speed_mps = round(max(2.0, 10.0 - self.queue_vehicles * 0.5), 2)
        else:
            discharge_rate = 0.0
            net_change = arrival_rate * dt_s
            self.queue_vehicles = min(self.capacity, self.queue_vehicles + net_change)
            self.flow_veh_per_s = 0.0
            self.mean_speed_mps = round(max(0.5, 5.0 * (1.0 - self.queue_vehicles / self.capacity)), 2)

        self.occupancy_ratio = round(min(1.0, max(0.0, self.queue_vehicles / self.capacity)), 2)
        self.queue_vehicles = round(self.queue_vehicles, 1)


class NodeTrafficState:
    def __init__(self, node_id: str, approaches: List[str], phases: List[Dict[str, Any]]):
        self.node_id = node_id
        self.phases = phases
        self.current_phase_id = phases[0]["phase_id"] if phases else "J1_PHASE_NS"
        self.approaches: Dict[str, ApproachState] = {
            app_id: ApproachState(app_id) for app_id in approaches
        }

    def approach_belongs_to_phase(self, approach_id: str, phase_id: str) -> bool:
        app_upper = approach_id.upper()
        phase_upper = phase_id.upper()
        if "PHASE_NS" in phase_upper or "_NS" in phase_upper:
            return "_N_" in app_upper or "_S_" in app_upper or app_upper.endswith("_N") or app_upper.endswith("_S")
        elif "PHASE_EW" in phase_upper or "_EW" in phase_upper:
            return "_E_" in app_upper or "_W_" in app_upper or app_upper.endswith("_E") or app_upper.endswith("_W")
        return False

    def step(self, dt_s: float = 1.0):
        for app_id, app_state in self.approaches.items():
            is_green = self.approach_belongs_to_phase(app_id, self.current_phase_id)
            app_state.step(is_green=is_green, dt_s=dt_s)

    def set_phase(self, phase_id: str):
        self.current_phase_id = phase_id


class TrafficEngine:
    """
    Traffic engine simulating network-level node dynamics for SUMO / Digital Twin simulator.
    """
    def __init__(self, topology: Dict[str, Any]):
        self.topology = topology
        self.nodes: Dict[str, NodeTrafficState] = {}
        self._init_nodes()

    def _init_nodes(self):
        for node in self.topology.get("nodes", []):
            node_id = node["node_id"]
            approaches = node.get("approaches", [])
            phases = node.get("phases", [])
            self.nodes[node_id] = NodeTrafficState(node_id, approaches, phases)

    def step(self, dt_s: float = 1.0):
        for node_state in self.nodes.values():
            node_state.step(dt_s=dt_s)

    def update_node_phase(self, node_id: str, phase_id: str):
        if node_id in self.nodes:
            self.nodes[node_id].set_phase(phase_id)

    def generate_telemetry(self, node_id: str, sim_time_s: float) -> Dict[str, Any]:
        if node_id not in self.nodes:
            raise ValueError(f"Unknown node_id: {node_id}")

        node = self.nodes[node_id]
        telemetry = {
            "node_id": node_id,
            "source_type": "simulation",
            "simulation_time_s": round(sim_time_s, 2),
            "timestamp_ms": int(time.time() * 1000),
            "current_phase_id": node.current_phase_id,
            "approaches": [
                {
                    "approach_id": app.approach_id,
                    "queue_vehicles": app.queue_vehicles,
                    "flow_veh_per_s": app.flow_veh_per_s,
                    "mean_speed_mps": app.mean_speed_mps,
                    "occupancy_ratio": app.occupancy_ratio,
                    "confidence": app.confidence
                }
                for app in node.approaches.values()
            ]
        }
        validate_payload(telemetry, "telemetry")
        return telemetry
