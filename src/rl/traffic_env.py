"""Fast single-intersection synthetic training environment (not a SUMO benchmark).

Demand and downstream observations are frozen per seed, independent of actions.
There is no physical signal timing or vehicle propagation between intersections;
SUMO and actuator validation are still required before deployment.
"""
import numpy as np

from contracts import contracts_sdk
from .policy import extract_features


class TrafficSignalEnv:
    SCENARIOS = ("balanced", "directional_surge", "downstream_congestion")

    def __init__(self, topology_id="four_intersection_v1", target_node="J1",
                 step_duration_s=5.0, max_steps=120, seed=101, capacity_vehicles=20.0):
        if step_duration_s <= 0 or max_steps < 1 or capacity_vehicles <= 0:
            raise ValueError("Step duration, horizon and capacity must be positive")
        self.topology_id, self.target_node = topology_id, target_node
        self.step_duration_s, self.max_steps, self.seed = step_duration_s, max_steps, seed
        self.capacity_vehicles = capacity_vehicles

        self.topology = contracts_sdk.load_topology(topology_id)
        self.node_info = next((n for n in self.topology["nodes"] if n["node_id"] == target_node), None)
        if not self.node_info or not self.node_info.get("phases"):
            raise ValueError(f"Node {target_node!r} must have legal phases")
        self.phases = self.node_info["phases"]
        self.approaches = self.node_info["approaches"]
        self.action_space_n = len(self.phases)
        self.observation_dim = 2 * len(self.approaches) + 2 * len(self.phases)
        self.served = np.asarray([[a in p.get("approaches", []) for a in self.approaches]
                                 for p in self.phases], dtype=bool)
        self.feature_spec = {"version": 1, "capacity_vehicles": capacity_vehicles,
                             "phase_approach_indices": [np.flatnonzero(row).tolist() for row in self.served]}
        self.reset(seed=seed)

    def reset(self, seed=None, scenario="balanced"):
        if scenario not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        if seed is not None:
            self.seed = seed
        rng = np.random.default_rng(self.seed)
        self.scenario = scenario
        self.current_step, self.simulation_time_s, self.current_phase_idx = 0, 0.0, 0
        self.queue = rng.integers(1, 9, size=len(self.approaches)).astype(np.float32)
        rates = np.full((self.max_steps, len(self.approaches)), 0.18)
        # Randomize the busy phase; a policy cannot solve the task by memorizing NS.
        busy = int(rng.integers(self.action_space_n))
        window = slice(self.max_steps // 3, 2 * self.max_steps // 3)
        if scenario == "directional_surge":
            rates[window] = np.where(self.served[busy], 0.48, 0.08)
        self.arrivals = rng.poisson(rates * self.step_duration_s).astype(np.float32)
        self.receiving = np.ones((self.max_steps + 1, len(self.approaches)), dtype=np.float32)
        self.downstream_nodes = {}
        for p in self.phases:
            for movement in p.get("movements", []):
                if movement.get("to_node"):
                    self.downstream_nodes[movement["from_approach"]] = movement["to_node"]
        if scenario == "downstream_congestion" and self.downstream_nodes:
            candidates = list(self.downstream_nodes)
            blocked = candidates[int(rng.integers(len(candidates)))]
            self.receiving[window, self.approaches.index(blocked)] = 0.15
        self.total_discharged = self.waiting_vehicle_seconds = 0.0
        self.network_state = {}
        self._refresh_state()
        return self._get_obs(), {"source_mode": "synthetic_training", "seed": self.seed,
                                 "scenario": scenario, "simulation_time_s": 0.0}

    def _refresh_state(self):
        self.queue_state = dict(zip(self.approaches, self.queue.tolist()))
        self.occ_state = {a: min(1., q / self.capacity_vehicles) for a, q in self.queue_state.items()}
        self.network_state = {}
        for approach, node_id in self.downstream_nodes.items():
            idx = self.approaches.index(approach)
            blocked = self.receiving[self.current_step, idx] < 1
            node = next(n for n in self.topology["nodes"] if n["node_id"] == node_id)
            self.network_state[node_id] = {"approaches": [
                {"approach_id": a, "queue_vehicles": 19. if blocked else 0.,
                 "occupancy_ratio": .95 if blocked else 0.} for a in node["approaches"]]}

    def telemetry(self):
        return {"node_id": self.target_node, "source_type": "simulation",
                "simulation_time_s": self.simulation_time_s,
                "current_phase_id": self.phases[self.current_phase_idx]["phase_id"],
                "approaches": [{"approach_id": a, "queue_vehicles": self.queue_state[a],
                                "occupancy_ratio": self.occ_state[a]}
                               for a in self.approaches]}

    def _get_obs(self):
        return extract_features(self.node_info, self.telemetry(), self.network_state, self.capacity_vehicles)

    def step(self, action):
        if not isinstance(action, (int, np.integer)) or not 0 <= action < self.action_space_n:
            raise ValueError(f"Invalid action: {action}")
        if self.current_step >= self.max_steps:
            raise RuntimeError("Episode ended; call reset before stepping again")
        self.current_phase_idx = int(action)
        available = self.queue + self.arrivals[self.current_step]
        service = self.served[action] * 0.65 * self.step_duration_s * self.receiving[self.current_step]
        discharged = np.minimum(available, service)
        self.queue = (available - discharged).astype(np.float32)
        self.total_discharged += float(discharged.sum())
        self.waiting_vehicle_seconds += float(self.queue.sum()) * self.step_duration_s
        self.current_step += 1
        self.simulation_time_s = self.current_step * self.step_duration_s
        self._refresh_state()
        reward = -float(self.queue.sum()) / self.capacity_vehicles
        info = {"total_queue": float(self.queue.sum()), "discharged_vehicles": float(discharged.sum()),
                "total_discharged": self.total_discharged, "waiting_vehicle_seconds": self.waiting_vehicle_seconds,
                "simulation_time_s": self.simulation_time_s, "step": self.current_step,
                "source_mode": "synthetic_training", "valid_for_research": False}
        return self._get_obs(), reward, False, self.current_step >= self.max_steps, info
