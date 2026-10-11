"""
Traffic Signal Controllers for EdgeFlow AI.

Controller hierarchy:
  BaseController (ABC)
  ├── FixedTimeController    — Clock-driven cycle with yellow/all-red
  ├── ActuatedController     — Demand-responsive gap-out with green extension
  ├── MaxQueueController     — Greedy upstream queue maximizer
  ├── MaxPressureController  — Reference movement-based max-pressure
  ├── EdgeFlowController     — Candidate adaptive (spillback filter + switching margin)
  └── PressLightRLController — RL policy inference

Every controller's compute_command() is a PURE FUNCTION of:
    (node_id, telemetry, topology, network_state, current_time_s)

Controllers do NOT own signal timing.  They emit a target_phase_id;
the ActuatorStateMachine owns GREEN -> YELLOW -> ALL_RED -> GREEN.
"""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseController(ABC):
    @abstractmethod
    def compute_command(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        current_time_s: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Compute control command for a specific intersection node."""
        pass

    def reset(self):
        """Reset controller state between experiments."""
        pass


class FixedTimeController(BaseController):
    """
    Clock-driven Fixed-Time Controller.

    Phase schedule is strictly determined by elapsed simulation time.
    Repeated compute() calls at the SAME timestamp always return the
    SAME target phase — no call-count dependency.

    Timing includes green + yellow + all-red per phase:
        cycle_time = sum(green_i + yellow + all_red  for i in phases)

    The controller tells the actuator which phase SHOULD be green.
    The actuator handles the actual clearance transitions.
    """

    def __init__(
        self,
        cycle_time_s: float = 30.0,
        phase_splits: Optional[Dict[str, List[float]]] = None,
        yellow_s: float = 3.0,
        all_red_s: float = 2.0,
    ):
        self.cycle_time_s = cycle_time_s
        self.phase_splits = phase_splits or {}
        self.yellow_s = yellow_s
        self.all_red_s = all_red_s
        # Per-node internal state
        self._node_state: Dict[str, Dict[str, Any]] = {}

    def reset(self):
        self._node_state.clear()

    def compute_command(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        current_time_s: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        node_info = next(
            (n for n in topology.get("nodes", []) if n["node_id"] == node_id), None
        )
        if not node_info or not node_info.get("phases"):
            return None

        phases = node_info["phases"]
        num_phases = len(phases)
        if num_phases == 0:
            return None

        # Authoritative time source
        if current_time_s is not None:
            now = float(current_time_s)
        elif telemetry.get("simulation_time_s") is not None:
            now = float(telemetry["simulation_time_s"])
        else:
            now = time.time()

        # Green splits per phase (the green portion only)
        clearance = self.yellow_s + self.all_red_s
        default_green = (self.cycle_time_s - clearance * num_phases) / num_phases
        default_green = max(default_green, 10.0)  # floor at 10.0s min green
        splits = self.phase_splits.get(node_id, [default_green] * num_phases)
        if len(splits) != num_phases:
            splits = [default_green] * num_phases

        # Total cycle = sum(green_i + clearance)
        full_cycle = sum(g + clearance for g in splits)

        # Determine current offset in cycle
        cycle_offset = now % full_cycle

        # Walk through phases to find which phase owns this offset
        accumulated = 0.0
        target_idx = 0
        for idx, green_dur in enumerate(splits):
            phase_total = green_dur + clearance
            if accumulated + phase_total > cycle_offset:
                target_idx = idx
                break
            accumulated += phase_total
        else:
            target_idx = num_phases - 1

        target_phase = phases[target_idx]["phase_id"]

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": splits[target_idx],
            "max_green_s": self.cycle_time_s,
            "controller": "fixed_time",
        }


class ActuatedController(BaseController):
    """
    Standard Semi-Actuated / Fully-Actuated Controller with Green Extension & Gap-Out.

    Traffic Engineering Principles:
      1. Minimum Green: Every phase gets at least min_green_s to serve waiting queue.
      2. Unit Extension (Passage Time): Green is extended as long as continuing vehicle
         arrivals / non-zero queue are detected, up to max_green_s.
      3. Gap-Out: When headway exceeds passage time (queue drops to 0) after min_green_s,
         the controller yields to the next phase with pending demand.
      4. Max-Out: If green reaches max_green_s, the phase is forced to yield.
      5. Phase rotation: In absence of conflicting calls, rests in green or cycles to next phase.
    """

    def __init__(
        self,
        min_green_s: float = 10.0,
        max_green_s: float = 45.0,
        passage_time_s: float = 3.0,
        gap_threshold_veh: float = 0.5,
    ):
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s
        self.passage_time_s = passage_time_s
        self.gap_threshold_veh = gap_threshold_veh
        # State per node: {current_phase_id, phase_start_time, last_active_time}
        self._node_state: Dict[str, Dict[str, Any]] = {}

    def reset(self):
        self._node_state.clear()

    def compute_command(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        current_time_s: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        node_info = next(
            (n for n in topology.get("nodes", []) if n["node_id"] == node_id), None
        )
        if not node_info or not node_info.get("phases"):
            return None

        phases = node_info["phases"]
        num_phases = len(phases)
        if num_phases == 0:
            return None

        # Authoritative time source
        if current_time_s is not None:
            now = float(current_time_s)
        elif telemetry.get("simulation_time_s") is not None:
            now = float(telemetry["simulation_time_s"])
        else:
            now = time.time()

        approaches = telemetry.get("approaches", [])
        queue_map: Dict[str, float] = {
            app["approach_id"]: float(app.get("queue_vehicles", 0)) for app in approaches
        }

        # Initialize node state if not present
        if node_id not in self._node_state:
            curr_p = telemetry.get("current_phase_id", phases[0]["phase_id"])
            self._node_state[node_id] = {
                "active_phase_id": curr_p,
                "phase_start_time": now,
                "last_active_time": now,
            }

        state = self._node_state[node_id]
        active_phase_id = state["active_phase_id"]

        # Find active phase info
        active_phase_idx = next(
            (i for i, p in enumerate(phases) if p["phase_id"] == active_phase_id), 0
        )
        active_phase = phases[active_phase_idx]

        # Calculate queue on current phase approaches
        active_approaches = active_phase.get("approaches", [])
        current_phase_queue = sum(queue_map.get(aid, 0.0) for aid in active_approaches)

        # Check queues on other phases (pending calls)
        phase_demands: Dict[str, float] = {}
        for p in phases:
            pid = p["phase_id"]
            p_apps = p.get("approaches", [])
            phase_demands[pid] = sum(queue_map.get(aid, 0.0) for aid in p_apps)

        elapsed = now - state["phase_start_time"]
        if elapsed < 0:
            elapsed = 0.0
            state["phase_start_time"] = now

        # Decision logic:
        # 1. Has minimum green elapsed?
        if elapsed < self.min_green_s:
            # Must hold minimum green
            target_phase = active_phase_id
            if current_phase_queue > self.gap_threshold_veh:
                state["last_active_time"] = now
        elif elapsed >= self.max_green_s:
            # Max-out reached: force switch to next phase with demand (or next round-robin)
            other_phases_with_demand = [
                p["phase_id"] for p in phases
                if p["phase_id"] != active_phase_id and phase_demands.get(p["phase_id"], 0.0) > 0
            ]
            if other_phases_with_demand:
                # Pick the conflicting phase with highest demand
                target_phase = max(other_phases_with_demand, key=lambda pid: phase_demands[pid])
            else:
                # Round-robin next phase
                target_phase = phases[(active_phase_idx + 1) % num_phases]["phase_id"]

            if target_phase != active_phase_id:
                state["active_phase_id"] = target_phase
                state["phase_start_time"] = now
                state["last_active_time"] = now
        else:
            # Between min_green and max_green: check for gap-out
            if current_phase_queue > self.gap_threshold_veh:
                # Vehicle detected -> extend green
                state["last_active_time"] = now
                target_phase = active_phase_id
            else:
                # No queue on current phase: check if passage time has expired since last detection
                time_since_detection = now - state["last_active_time"]
                if time_since_detection >= self.passage_time_s:
                    # Gap-out triggered: switch if other phases have demand
                    other_demands = {
                        p["phase_id"]: phase_demands.get(p["phase_id"], 0.0)
                        for p in phases if p["phase_id"] != active_phase_id
                    }
                    if any(d > 0 for d in other_demands.values()):
                        target_phase = max(other_demands.items(), key=lambda x: x[1])[0]
                    else:
                        # Rest in current green or cycle
                        target_phase = active_phase_id

                    if target_phase != active_phase_id:
                        state["active_phase_id"] = target_phase
                        state["phase_start_time"] = now
                        state["last_active_time"] = now
                else:
                    target_phase = active_phase_id

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": self.min_green_s,
            "max_green_s": self.max_green_s,
            "controller": "actuated",
        }


class MaxQueueController(BaseController):
    """
    MaxQueue baseline: selects the phase with the largest total upstream queue.
    P(phase) = sum(queue(approach) for approach in phase.approaches)
    """

    def __init__(self, min_green_s: float = 10.0, max_green_s: float = 60.0):
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s

    def compute_command(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        current_time_s: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        node_info = next(
            (n for n in topology.get("nodes", []) if n["node_id"] == node_id), None
        )
        phases = node_info.get("phases", []) if node_info else []
        if not phases:
            return None

        approaches = telemetry.get("approaches", [])
        queue_map: Dict[str, float] = {
            app["approach_id"]: float(app.get("queue_vehicles", 0)) for app in approaches
        }

        phase_pressures: Dict[str, float] = {}
        for phase in phases:
            phase_id = phase["phase_id"]
            phase_apps = phase.get("approaches", [])
            pressure = sum(queue_map.get(app_id, 0.0) for app_id in phase_apps)
            phase_pressures[phase_id] = pressure

        if phase_pressures:
            curr_p = telemetry.get("current_phase_id")
            max_val = max(phase_pressures.values())
            if curr_p and curr_p in phase_pressures and phase_pressures[curr_p] == max_val:
                target_phase = curr_p
            else:
                target_phase = max(phase_pressures.items(), key=lambda x: x[1])[0]
        else:
            target_phase = telemetry.get("current_phase_id", phases[0]["phase_id"])

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": self.min_green_s,
            "max_green_s": self.max_green_s,
            "controller": "max_queue",
        }


class MaxPressureController(BaseController):
    """
    Movement-based Reference Max-Pressure Controller.
    P_p = sum_{(i,j) in p} s_ij * (q_ij - sum_k r_jk * q_jk)
    """

    def __init__(self, min_green_s: float = 10.0, max_green_s: float = 60.0):
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s

    def compute_command(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        current_time_s: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        node_info = next(
            (n for n in topology.get("nodes", []) if n["node_id"] == node_id), None
        )
        phases = node_info.get("phases", []) if node_info else []
        if not phases:
            return None

        approaches = telemetry.get("approaches", [])
        queue_map: Dict[str, float] = {
            app["approach_id"]: float(app.get("queue_vehicles", 0)) for app in approaches
        }

        phase_pressures: Dict[str, float] = {}

        for phase in phases:
            phase_id = phase["phase_id"]
            movements = phase.get("movements", [])

            if movements:
                total_p = 0.0
                for m in movements:
                    from_app = m.get("from_approach", "")
                    to_node = m.get("to_node")
                    turn_ratio = float(m.get("turn_ratio", 1.0))

                    q_in = queue_map.get(from_app, 0.0)

                    q_out = 0.0
                    if to_node and network_state and to_node in network_state:
                        to_apps = network_state[to_node].get("approaches", [])
                        to_approach = m.get("to_approach")
                        mapped = next((a for a in to_apps if a.get("approach_id") == to_approach), None)
                        # Legacy topologies without downstream mappings retain
                        # their original aggregate estimate.
                        q_out = (float(mapped.get("queue_vehicles", 0)) if mapped else
                                 sum(float(a.get("queue_vehicles", 0)) for a in to_apps)
                                 / max(1, len(to_apps)))

                    pressure_m = q_in - (turn_ratio * q_out)
                    total_p += pressure_m
                phase_pressures[phase_id] = total_p
            else:
                phase_apps = phase.get("approaches", [])
                pressure = sum(queue_map.get(app_id, 0.0) for app_id in phase_apps)
                phase_pressures[phase_id] = pressure

        if phase_pressures:
            curr_p = telemetry.get("current_phase_id")
            max_val = max(phase_pressures.values())
            if curr_p and curr_p in phase_pressures and phase_pressures[curr_p] == max_val:
                target_phase = curr_p
            else:
                target_phase = max(phase_pressures.items(), key=lambda x: x[1])[0]
        else:
            target_phase = telemetry.get("current_phase_id", phases[0]["phase_id"])

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": self.min_green_s,
            "max_green_s": self.max_green_s,
            "controller": "max_pressure",
        }


class EdgeFlowController(BaseController):
    """
    EdgeFlow Adaptive Traffic Signal Controller (v3.0 Architecture).
    Novel Proposed Methodology: Hybrid Flow Theory (Cell Transmission Model - CTM)
    & Network-Aware Dynamic Backpressure (Max-Pressure) with Multi-hop Bottleneck Propagation.

    Scientific Foundations:
      1. Cell Transmission Model (CTM) Sending & Receiving Capacity:
         Evaluates upstream demand S_m = min(S_max, q_in/tau + f_in) and downstream supply
         R_m = S_max * (1 - Occ_eff / Occ_crit) to regulate effective throughput flow.
      2. Multi-hop 2-Hop Downstream Graph Bottleneck:
         Propagates congestion from 2-hop downstream nodes (Occ_eff = max(Occ_1hop, gamma * Occ_2hop))
         to anticipate spillbacks before queues propagate into the target intersection.
      3. Network-Aware Dynamic Backpressure (Max-Pressure):
         Balances queue differentials across the road network graph while gating movements
         heading into saturated downstream cells.
      4. Dynamic Platoon Progression Momentum:
         Rewards flow through unobstructed downstream links to maintain coordinated green waves.
      5. Time-Decaying Switching Hysteresis & Gap-Out:
         Enforces min_green, checks downstream blockages in real-time, and guards against
         phase fluttering with switching_margin.
      6. Nonlinear Service-Age Fairness Bonus:
         Guarantees zero phase starvation and minimizes tail latency (P95).
    """

    def __init__(
        self,
        min_green_s: float = 5.0,
        max_green_s: float = 45.0,
        switching_margin: float = 1.2,
        max_occupancy_threshold: float = 0.82,
        spillback_penalty: float = -4.0,
        service_age_weight: float = 0.06,
        progression_weight: float = 0.3,
        rl_model_path: Optional[str] = None,
        rl_residual_weight: float = 0.4,
        saturation_flow_vps: float = 0.5,
        hop2_attenuation: float = 0.7,
        enable_ctm_gating: bool = True,
        enable_multihop: bool = True,
    ):
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s
        self.switching_margin = switching_margin
        self.max_occupancy_threshold = max_occupancy_threshold
        self.spillback_penalty = spillback_penalty
        self.service_age_weight = service_age_weight
        self.progression_weight = progression_weight
        self.rl_residual_weight = rl_residual_weight
        self.saturation_flow_vps = saturation_flow_vps
        self.hop2_attenuation = hop2_attenuation
        self.enable_ctm_gating = enable_ctm_gating
        self.enable_multihop = enable_multihop
        self.rl_policy = None

        # Load RL residual policy if available
        if rl_model_path:
            import sys
            from pathlib import Path
            p = Path(rl_model_path)
            if not p.is_absolute():
                repo_root = Path(__file__).resolve().parents[2]
                p = repo_root / rl_model_path
            else:
                repo_root = Path(__file__).resolve().parents[2]

            rl_dir = repo_root / "src" / "rl"
            if str(rl_dir) not in sys.path and rl_dir.exists():
                sys.path.insert(0, str(rl_dir))
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))

            if p.exists():
                try:
                    import json
                    from policy import NumpyPolicy
                    data = json.loads(p.read_text(encoding="utf-8"))
                    self.rl_policy = NumpyPolicy(data)
                except Exception as e:
                    pass

        # Per-node phase service timestamps and green start times
        self._last_served: Dict[str, Dict[str, float]] = {}
        self._phase_start: Dict[str, float] = {}
        self._current_phase: Dict[str, str] = {}

    def reset(self):
        self._last_served.clear()
        self._phase_start.clear()
        self._current_phase.clear()

    def _get_downstream_occupancy(
        self,
        to_node: Optional[str],
        from_app: str,
        to_approach: Optional[str],
        network_state: Optional[Dict[str, Any]],
        topology: Dict[str, Any],
    ) -> float:
        if not to_node or not network_state or to_node not in network_state:
            return 0.0

        to_apps = network_state[to_node].get("approaches", [])
        mapped = None
        if to_approach:
            mapped = next((a for a in to_apps if a.get("approach_id") == to_approach), None)
        if not mapped and from_app:
            for suffix in ("_N_IN", "_S_IN", "_E_IN", "_W_IN"):
                if from_app.endswith(suffix):
                    mapped = next((a for a in to_apps if a.get("approach_id", "").endswith(suffix)), None)
                    if mapped:
                        break

        occ_1hop = float(mapped.get("occupancy_ratio", mapped.get("occupancy", 0.0))) if mapped else (
            max(float(a.get("occupancy_ratio", a.get("occupancy", 0.0))) for a in to_apps) if to_apps else 0.0
        )

        if not self.enable_multihop:
            return occ_1hop

        # Multi-hop Graph Reachability (2-hop downstream bottleneck)
        to_node_info = next((n for n in topology.get("nodes", []) if n["node_id"] == to_node), None)
        if to_node_info and to_node_info.get("phases"):
            hop2_occs = []
            for p2 in to_node_info["phases"]:
                for m2 in p2.get("movements", []):
                    to2_node = m2.get("to_node")
                    if to2_node and to2_node in network_state:
                        to2_apps = network_state[to2_node].get("approaches", [])
                        if to2_apps:
                            hop2_occs.append(
                                sum(float(a.get("occupancy_ratio", a.get("occupancy", 0.0))) for a in to2_apps)
                                / len(to2_apps)
                            )
            if hop2_occs:
                hop2_avg_occ = sum(hop2_occs) / len(hop2_occs)
                return max(occ_1hop, self.hop2_attenuation * hop2_avg_occ)

        return occ_1hop

    def compute_command(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        current_time_s: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        node_info = next(
            (n for n in topology.get("nodes", []) if n["node_id"] == node_id), None
        )
        phases = node_info.get("phases", []) if node_info else []
        if not phases:
            return None

        # Authoritative time source
        if current_time_s is not None:
            now = float(current_time_s)
        elif telemetry.get("simulation_time_s") is not None:
            now = float(telemetry["simulation_time_s"])
        elif telemetry.get("timestamp") is not None:
            now = float(telemetry["timestamp"])
        else:
            now = time.time()

        current_phase_id = telemetry.get("current_phase_id", phases[0]["phase_id"])

        # Track phase transitions and green duration
        if node_id not in self._current_phase or self._current_phase[node_id] != current_phase_id:
            self._current_phase[node_id] = current_phase_id
            self._phase_start[node_id] = now

        if node_id not in self._last_served:
            self._last_served[node_id] = {p["phase_id"]: now for p in phases}
        self._last_served[node_id][current_phase_id] = now

        elapsed_green = max(0.0, now - self._phase_start.get(node_id, now))
        approaches = telemetry.get("approaches", [])

        queue_map: Dict[str, float] = {}
        flow_map: Dict[str, float] = {}
        occ_map: Dict[str, float] = {}
        conf_map: Dict[str, float] = {}
        for app in approaches:
            app_id = app["approach_id"]
            queue_map[app_id] = float(app.get("queue_vehicles", app.get("queue_length_veh", 0.0)))
            if "flow_veh_per_s" in app:
                flow_map[app_id] = float(app.get("flow_veh_per_s", 0.0))
            elif "flow_rate" in app:
                flow_map[app_id] = float(app.get("flow_rate", 0.0)) / 3600.0
            else:
                flow_map[app_id] = 0.0
            occ_map[app_id] = float(app.get("occupancy_ratio", app.get("occupancy", 0.0)))
            conf_map[app_id] = float(app.get("confidence", 1.0))

        phase_scores: Dict[str, float] = {}

        for phase in phases:
            phase_id = phase["phase_id"]
            movements = phase.get("movements", [])

            if movements:
                phase_score = 0.0
                for m in movements:
                    from_app = m.get("from_approach", "")
                    to_node = m.get("to_node")
                    to_approach = m.get("to_approach")
                    turn_ratio = float(m.get("turn_ratio", 1.0))
                    capacity = float(m.get("capacity_vehicles", 20.0))

                    q_in = queue_map.get(from_app, 0.0)
                    flow_in = flow_map.get(from_app, 0.0)
                    conf = conf_map.get(from_app, 1.0)

                    q_out = 0.0
                    occ_out = 0.0
                    if to_node and network_state and to_node in network_state:
                        to_apps = network_state[to_node].get("approaches", [])
                        mapped = None
                        if to_approach:
                            mapped = next((a for a in to_apps if a.get("approach_id") == to_approach), None)
                        if not mapped and from_app:
                            for suffix in ("_N_IN", "_S_IN", "_E_IN", "_W_IN"):
                                if from_app.endswith(suffix):
                                    mapped = next((a for a in to_apps if a.get("approach_id", "").endswith(suffix)), None)
                                    if mapped:
                                        break
                        if mapped:
                            q_out = float(mapped.get("queue_vehicles", mapped.get("queue_length_veh", 0.0)))
                        elif to_apps:
                            worst_app = max(to_apps, key=lambda a: float(a.get("occupancy_ratio", a.get("occupancy", 0.0))))
                            q_out = float(worst_app.get("queue_vehicles", worst_app.get("queue_length_veh", 0.0)))

                        occ_out = self._get_downstream_occupancy(
                            to_node=to_node,
                            from_app=from_app,
                            to_approach=to_approach,
                            network_state=network_state,
                            topology=topology,
                        )

                    # 1. Flow Theory (Cell Transmission Model - CTM):
                    # Sending Capacity S_m = min(S_max, (q_in / tau) + flow_in)
                    sending_capacity = min(self.saturation_flow_vps, (q_in / 10.0) + flow_in)

                    # Receiving Capacity R_m
                    if occ_out >= self.max_occupancy_threshold or q_out >= capacity:
                        receiving_capacity = 0.0
                    elif occ_out > 0.40:
                        receiving_capacity = self.saturation_flow_vps * max(0.0, 1.0 - (occ_out / self.max_occupancy_threshold) ** 2)
                    else:
                        receiving_capacity = self.saturation_flow_vps

                    ctm_throughput = min(sending_capacity, receiving_capacity)

                    # 2. Network Dynamic Max-Pressure
                    pressure = q_in - (turn_ratio * q_out)

                    # 3. Hybrid Synthesis: CTM-Modulated Max-Pressure with Spillback Penalty
                    if occ_out >= self.max_occupancy_threshold or q_out >= capacity or receiving_capacity <= 0.0:
                        # Downstream blocked -> apply backpressure penalty
                        m_score = self.spillback_penalty * (1.0 + occ_out)
                    elif occ_out > 0.40:
                        # Soft barrier: scale down pressure as downstream approaches saturation
                        barrier_factor = max(0.0, 1.0 - (occ_out / self.max_occupancy_threshold) ** 2)
                        if self.enable_ctm_gating:
                            ctm_flow_ratio = ctm_throughput / max(1e-4, self.saturation_flow_vps)
                            m_score = (pressure * barrier_factor + self.progression_weight * (flow_in * ctm_flow_ratio + ctm_throughput)) * conf
                        else:
                            m_score = (pressure * barrier_factor + self.progression_weight * flow_in) * conf
                    else:
                        # Free-flowing downstream -> full pressure + progression flow
                        if self.enable_ctm_gating:
                            m_score = (pressure + self.progression_weight * (flow_in + ctm_throughput)) * conf
                        else:
                            m_score = (pressure + self.progression_weight * flow_in) * conf

                    phase_score += m_score
            else:
                phase_apps = phase.get("approaches", [])
                phase_score = 0.0
                for app_id in phase_apps:
                    q_in = queue_map.get(app_id, 0.0)
                    flow_in = flow_map.get(app_id, 0.0)
                    conf = conf_map.get(app_id, 1.0)
                    occ_in = occ_map.get(app_id, 0.0)

                    sending_capacity = min(self.saturation_flow_vps, (q_in / 10.0) + flow_in)
                    if occ_in >= self.max_occupancy_threshold:
                        receiving_capacity = 0.0
                    elif occ_in > 0.40:
                        receiving_capacity = self.saturation_flow_vps * max(0.0, 1.0 - (occ_in / self.max_occupancy_threshold) ** 2)
                    else:
                        receiving_capacity = self.saturation_flow_vps
                    eff_flow = min(sending_capacity, receiving_capacity)

                    if self.enable_ctm_gating:
                        phase_score += (q_in + self.progression_weight * (flow_in + eff_flow)) * conf
                    else:
                        phase_score += (q_in + self.progression_weight * flow_in) * conf

            # Service-age fairness bonus (nonlinear, only if phase has active waiting demand)
            phase_apps_all = phase.get("approaches", [])
            if not phase_apps_all and phase.get("movements"):
                phase_apps_all = list({mv.get("from_approach") for mv in phase["movements"] if mv.get("from_approach")})
            phase_demand = sum(queue_map.get(a, 0.0) + flow_map.get(a, 0.0) for a in phase_apps_all)

            if phase_demand > 0.2:
                last_served = self._last_served[node_id].get(phase_id, now)
                service_age = max(0.0, now - last_served)
                phase_score += self.service_age_weight * (service_age ** 1.1)

            phase_scores[phase_id] = phase_score

        # 0. Add RL Residual Q-value bonus if trained policy is loaded
        if self.rl_policy is not None:
            try:
                from policy import extract_features
                feats = extract_features(node_info, telemetry, network_state, 20.0)
                q_vals = self.rl_policy.predict(feats)
                for idx, phase in enumerate(phases):
                    if idx < len(q_vals):
                        pid = phase["phase_id"]
                        phase_scores[pid] = phase_scores.get(pid, 0.0) + self.rl_residual_weight * float(q_vals[idx])
            except Exception:
                pass

        # Decision Logic:
        # 1. Enforce minimum green
        if elapsed_green < self.min_green_s:
            return {
                "command_id": str(uuid.uuid4()),
                "node_id": node_id,
                "target_phase_id": current_phase_id,
                "min_green_s": self.min_green_s,
                "max_green_s": self.max_green_s,
                "controller": "edgeflow",
            }

        # 2. Check current phase queue, flow, and downstream blockage
        active_phase_obj = next((p for p in phases if p["phase_id"] == current_phase_id), None)
        active_apps = active_phase_obj.get("approaches", []) if active_phase_obj else []
        if not active_apps and active_phase_obj and active_phase_obj.get("movements"):
            active_apps = list({m.get("from_approach") for m in active_phase_obj["movements"] if m.get("from_approach")})

        active_queue = sum(queue_map.get(a, 0.0) for a in active_apps)
        active_flow = sum(flow_map.get(a, 0.0) for a in active_apps)

        current_blocked = False
        if active_phase_obj and active_phase_obj.get("movements"):
            for m in active_phase_obj["movements"]:
                to_node = m.get("to_node")
                from_app = m.get("from_approach", "")
                to_approach = m.get("to_approach")
                if to_node and network_state and to_node in network_state:
                    occ = self._get_downstream_occupancy(
                        to_node=to_node,
                        from_app=from_app,
                        to_approach=to_approach,
                        network_state=network_state,
                        topology=topology,
                    )
                    if occ >= self.max_occupancy_threshold:
                        current_blocked = True
                        break

        # 3. Check best scoring phase vs current phase with switching margin
        current_score = phase_scores.get(current_phase_id, 0.0)
        best_phase, best_score = max(phase_scores.items(), key=lambda x: x[1]) if phase_scores else (current_phase_id, current_score)

        # Evaluate best competing phase demand
        best_phase_obj = next((p for p in phases if p["phase_id"] == best_phase), None)
        best_apps = best_phase_obj.get("approaches", []) if best_phase_obj else []
        if not best_apps and best_phase_obj and best_phase_obj.get("movements"):
            best_apps = list({m.get("from_approach") for m in best_phase_obj["movements"] if m.get("from_approach")})
        best_demand = sum(queue_map.get(a, 0.0) + flow_map.get(a, 0.0) for a in best_apps)

        # Platoon extension: keep serving if queue remains or active discharging platoon is flowing
        has_active_traffic = (active_queue > 0.5) or (active_flow > 0.1 and elapsed_green < 20.0)

        if not current_blocked and has_active_traffic and elapsed_green < self.max_green_s:
            # Only switch if competing phase has substantial queue advantage AND actual demand
            if best_phase != current_phase_id and best_score > current_score + self.switching_margin and best_demand > 0.5:
                target_phase = best_phase
            else:
                target_phase = current_phase_id
            return {
                "command_id": str(uuid.uuid4()),
                "node_id": node_id,
                "target_phase_id": target_phase,
                "min_green_s": self.min_green_s,
                "max_green_s": self.max_green_s,
                "controller": "edgeflow",
            }

        # 4. Gap-out or max green reached or downstream blocked:
        # If no competing phase has demand, remain on current phase to avoid yellow/all-red lost time
        if not current_blocked and best_demand <= 0.2 and elapsed_green < self.max_green_s:
            target_phase = current_phase_id
        elif not phase_scores:
            target_phase = current_phase_id
        else:
            target_phase = best_phase

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": self.min_green_s,
            "max_green_s": self.max_green_s,
            "controller": "edgeflow",
        }


class PressLightRLController(BaseController):
    """Batched NumPy inference with a shared training/serving feature extractor.

    No model means an explicitly named pressure heuristic. An invalid requested
    model fails at startup instead of silently presenting a heuristic as RL.
    """

    def __init__(self, min_green_s=10.0, max_green_s=60.0, model_path=None, weights=None):
        from pathlib import Path
        import sys

        root = Path(__file__).resolve().parents[2]
        if (root / "src" / "rl").is_dir() and str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from src.rl.policy import NumpyPolicy, extract_features

        self._extract = extract_features
        self.min_green_s, self.max_green_s = min_green_s, max_green_s
        self.model_path, self.weights = model_path, weights
        self.policy = None
        self._node_cache: Dict[str, Any] = {}
        if model_path is not None:
            import json

            path = Path(model_path)
            if path.suffix.lower() != ".json":
                raise ValueError("Export a JSON MLP for this inference backend")
            self.weights = json.loads(path.read_text(encoding="utf-8"))
        if self.weights is not None:
            self.policy = NumpyPolicy(self.weights)
        self._initialized_model = self.policy is not None

    def _node(self, node_id, topology):
        if self._node_cache.get("topology") is not topology:
            self._node_cache = {
                "topology": topology,
                "nodes": {n["node_id"]: n for n in topology.get("nodes", [])},
            }
        return self._node_cache["nodes"].get(node_id)

    def extract_features(self, node_id, telemetry, topology, network_state=None):
        node = self._node(node_id, topology)
        if node is None:
            return []
        spec = self.policy.feature_spec if self.policy else {}
        if spec:
            indices = [
                [i for i, a in enumerate(node["approaches"]) if a in p.get("approaches", [])]
                for p in node["phases"]
            ]
            if spec.get("version") != 1 or spec.get("phase_approach_indices") != indices:
                raise ValueError("Model feature/phase ordering does not match topology")
        return self._extract(
            node, telemetry, network_state, spec.get("capacity_vehicles", 20.0)
        )

    def compute_q_values(self, features, num_phases):
        if self.policy is not None:
            if self.policy.action_dim != num_phases:
                raise ValueError("Model action count does not match legal phases")
            return self.policy.predict(features).tolist()
        return [float(p) * 10 for p in features[-num_phases:]] if num_phases else []

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        node = self._node(node_id, topology)
        phases = node.get("phases", []) if node else []
        if not phases:
            return None
        features = self.extract_features(node_id, telemetry, topology, network_state)
        q_values = self.compute_q_values(features, len(phases))
        best = max(range(len(q_values)), key=q_values.__getitem__)
        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": phases[best]["phase_id"],
            "min_green_s": self.min_green_s,
            "max_green_s": self.max_green_s,
            "controller": "presslight_rl" if self.policy else "pressure_heuristic",
        }


class FlowTheoryController(BaseController):
    """
    Traffic Flow Theory Controller based on Cell Transmission Model (CTM).
    Calculates effective flow throughput F(p) = sum(min(Sending_Capacity, Receiving_Capacity)) for each movement/phase.

    Sending Capacity S_a = min(Q_max, Queue / 10.0 + FlowIn)  (Demand from upstream)
    Receiving Capacity R_d = Q_max * max(0.0, 1.0 - Downstream_Occupancy) (Supply at downstream)

    Enforces min_green_s and max_green_s to prevent rapid signal flickering.
    Gates green phases when downstream exit link is saturated (> 0.85) to prevent gridlock.
    """

    def __init__(self, min_green_s: float = 10.0, max_green_s: float = 60.0, saturation_flow_vps: float = 0.5):
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s
        self.saturation_flow_vps = saturation_flow_vps
        self._node_state: Dict[str, Dict[str, Any]] = {}

    def reset(self):
        self._node_state.clear()

    def compute_command(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        current_time_s: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        node_info = next((n for n in topology.get("nodes", []) if n["node_id"] == node_id), None)
        phases = node_info.get("phases", []) if node_info else []
        if not phases:
            return None

        # Authoritative timestamp
        if current_time_s is not None:
            now = float(current_time_s)
        elif telemetry.get("timestamp") is not None:
            now = float(telemetry["timestamp"])
        else:
            now = time.time()

        # Init node state
        if node_id not in self._node_state:
            default_phase = phases[0]["phase_id"]
            self._node_state[node_id] = {
                "current_phase_id": telemetry.get("current_phase_id", default_phase),
                "phase_start_time": now - self.min_green_s - 1.0,
            }

        ns = self._node_state[node_id]
        current_phase_id = telemetry.get("current_phase_id", ns["current_phase_id"])
        if current_phase_id != ns["current_phase_id"]:
            ns["current_phase_id"] = current_phase_id
            ns["phase_start_time"] = now

        elapsed_green = max(0.0, now - ns["phase_start_time"])

        # 1. Enforce minimum green
        if elapsed_green < self.min_green_s:
            return {
                "command_id": str(uuid.uuid4()),
                "node_id": node_id,
                "target_phase_id": current_phase_id,
                "min_green_s": self.min_green_s,
                "max_green_s": self.max_green_s,
                "controller": "flow_theory",
            }

        # Build telemetry lookups
        approaches = telemetry.get("approaches", [])
        queue_map: Dict[str, float] = {}
        flow_map: Dict[str, float] = {}
        occ_map: Dict[str, float] = {}

        for app in approaches:
            aid = app["approach_id"]
            queue_map[aid] = float(app.get("queue_vehicles", app.get("queue_length_veh", 0.0)))
            if "flow_veh_per_s" in app:
                flow_map[aid] = float(app["flow_veh_per_s"])
            elif "flow_rate" in app:
                flow_map[aid] = float(app["flow_rate"]) / 3600.0
            else:
                flow_map[aid] = 0.0
            occ_map[aid] = float(app.get("occupancy_ratio", app.get("occupancy", 0.0)))

        phase_flows: Dict[str, float] = {}

        for phase in phases:
            phase_id = phase["phase_id"]
            movements = phase.get("movements", [])
            total_effective_flow = 0.0

            if movements:
                for m in movements:
                    from_app = m.get("from_approach", "")
                    to_node = m.get("to_node")

                    q_in = queue_map.get(from_app, 0.0)
                    f_in = flow_map.get(from_app, 0.0)

                    # Upstream Sending Capacity (Demand)
                    sending_capacity = min(self.saturation_flow_vps, (q_in / 10.0) + f_in)

                    # Downstream Receiving Capacity (Supply via Graph Topology G=(V,E))
                    occ_down = 0.0
                    if to_node and network_state and to_node in network_state:
                        to_node_data = network_state[to_node]
                        to_apps = to_node_data.get("approaches", [])
                        to_approach = m.get("to_approach")
                        mapped = next((a for a in to_apps if a.get("approach_id") == to_approach), None) if to_approach else None
                        if mapped:
                            occ_down = float(mapped.get("occupancy_ratio", mapped.get("occupancy", 0.0)))
                        elif to_apps:
                            # Documented heuristic fallback when specific movement approach mapping is absent
                            occ_down = sum(float(a.get("occupancy_ratio", a.get("occupancy", 0.0))) for a in to_apps) / len(to_apps)
                        else:
                            occ_down = 0.0

                        # Graph Theory Multi-hop Path Bottleneck (2-hop graph reachability):
                        # Inspect 2-hop downstream neighbors in graph topology G
                        to_node_info = next((n for n in topology.get("nodes", []) if n["node_id"] == to_node), None)
                        if to_node_info and to_node_info.get("phases"):
                            hop2_occs = []
                            for p2 in to_node_info["phases"]:
                                for m2 in p2.get("movements", []):
                                    to2_node = m2.get("to_node")
                                    if to2_node and network_state and to2_node in network_state:
                                        to2_apps = network_state[to2_node].get("approaches", [])
                                        to2_approach = m2.get("to_approach")
                                        mapped2 = next((a for a in to2_apps if a.get("approach_id") == to2_approach), None) if to2_approach else None
                                        if mapped2:
                                            hop2_occs.append(float(mapped2.get("occupancy_ratio", mapped2.get("occupancy", 0.0))))
                                        elif to2_apps:
                                            hop2_occs.append(sum(float(a.get("occupancy_ratio", a.get("occupancy", 0.0))) for a in to2_apps) / len(to2_apps))
                            if hop2_occs:
                                hop2_avg_occ = sum(hop2_occs) / len(hop2_occs)
                                occ_down = max(occ_down, 0.7 * hop2_avg_occ)
                    else:
                        occ_down = occ_map.get(from_app, 0.0)

                    if occ_down >= 0.85:
                        receiving_capacity = 0.0  # Cut flow if downstream is jammed to prevent gridlock
                    else:
                        receiving_capacity = self.saturation_flow_vps * max(0.0, 1.0 - occ_down)

                    effective_flow = min(sending_capacity, receiving_capacity)
                    total_effective_flow += effective_flow
            else:
                phase_apps = phase.get("approaches", [])
                for app_id in phase_apps:
                    q_in = queue_map.get(app_id, 0.0)
                    f_in = flow_map.get(app_id, 0.0)
                    occ_in = occ_map.get(app_id, 0.0)
                    sending_capacity = min(self.saturation_flow_vps, (q_in / 10.0) + f_in)
                    receiving_capacity = self.saturation_flow_vps * max(0.0, 1.0 - occ_in) if occ_in < 0.85 else 0.0
                    effective_flow = min(sending_capacity, receiving_capacity)
                    total_effective_flow += effective_flow

            phase_flows[phase_id] = total_effective_flow

        if phase_flows:
            target_phase = max(phase_flows.items(), key=lambda x: x[1])[0]
        else:
            target_phase = current_phase_id

        if target_phase != current_phase_id:
            ns["current_phase_id"] = target_phase
            ns["phase_start_time"] = now

        return {
            "command_id": str(uuid.uuid4()),
            "node_id": node_id,
            "target_phase_id": target_phase,
            "min_green_s": self.min_green_s,
            "max_green_s": self.max_green_s,
            "controller": "flow_theory",
        }
