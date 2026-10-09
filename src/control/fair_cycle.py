"""Wait-aware cyclic timing with a hard minimum service allocation."""
import math
import uuid

from .controllers import BaseController


class FairCycleController(BaseController):
    """Serve both canonical phases every cycle and adapt their green split.

    ``cycle_time_s`` includes both clearance intervals. The allocation is
    selected when NS green starts and remains fixed until the next NS start.
    """

    controller_name = "fair_cycle"

    def __init__(self, cycle_time_s=70, min_green_share=1 / 3):
        if cycle_time_s not in (50, 70, 90):
            raise ValueError("fair_cycle cycle_time_s must be 50, 70 or 90")
        if min_green_share not in (.25, 1 / 3):
            raise ValueError("fair_cycle min_green_share must be .25 or 1/3")
        green_budget = cycle_time_s - 2 * 5
        minimum = math.ceil(green_budget * min_green_share / 5) * 5
        if minimum > green_budget / 2 or green_budget - minimum > 60:
            raise ValueError("Fair cycle cannot satisfy minimum and maximum green")
        self.cycle_time_s = cycle_time_s
        self.min_green_share = min_green_share
        self.minimum_green_s = minimum
        self.maximum_ns_green_s = min(60, green_budget - minimum)
        self._state = {}
        self._external_adjustments = {}

    def reset(self):
        self._state.clear()
        self._external_adjustments.clear()

    @staticmethod
    def _pressure(phase, local, network_state):
        total = 0.
        for movement in phase.get("movements", []):
            approach_id = movement["from_approach"]
            item = local[approach_id]
            demand = (float(item.get("queue_vehicles", 0))
                      + float(item.get("external_due_count", 0))
                      + (float(item.get("stopped_wait_sum_s", 0))
                         + float(item.get("external_wait_sum_s", 0))) / 120.)
            downstream_occupancy = 0.
            to_node, to_approach = movement.get("to_node"), movement.get("to_approach")
            if to_node and to_approach and to_node in network_state:
                downstream = {a["approach_id"]: a for a in network_state[to_node].get("approaches", [])}
                if to_approach in downstream:
                    downstream_occupancy = float(downstream[to_approach].get("occupancy_ratio", 0))
            total += demand / (1. + max(0., min(1., downstream_occupancy)))
        return total

    def _allocation(self, phases, telemetry, network_state):
        local = {a["approach_id"]: a for a in telemetry.get("approaches", [])}
        pressures = [self._pressure(phase, local, network_state or {}) for phase in phases]
        green_budget = self.cycle_time_s - 10
        if sum(pressures) <= 0:
            requested_ns = green_budget / 2
        else:
            requested_ns = green_budget * pressures[0] / sum(pressures)
        ns = 5 * round(requested_ns / 5)
        ns = max(self.minimum_green_s, min(self.maximum_ns_green_s, ns))
        return ns, green_budget - ns

    def _policy_adjustment(self, node_id, phases, telemetry, network_state, base_split):
        return 0

    def _new_cycle(self, node_id, phases, telemetry, network_state):
        base_ns, base_ew = self._allocation(phases, telemetry, network_state or {})
        adjustment = self._external_adjustments.pop(node_id, None)
        if adjustment is None:
            adjustment = self._policy_adjustment(node_id, phases, telemetry,
                                                 network_state or {}, (base_ns, base_ew))
        ns = max(self.minimum_green_s, min(self.maximum_ns_green_s, base_ns + adjustment))
        ns = 5 * round(ns / 5)
        ew = self.cycle_time_s - 10 - ns
        old = self._state.get(node_id, {})
        self._state[node_id] = {
            "phase": telemetry.get("current_phase_id", phases[0]["phase_id"]),
            "split": (ns, ew), "base_split": (base_ns, base_ew),
            "previous_split": old.get("split", (ns, ew)), "cycle": old.get("cycle", -1) + 1,
        }

    def begin_cycle(self, node_id, telemetry, topology, network_state=None, adjustment=0):
        if adjustment not in (-5, 0, 5):
            raise ValueError("Fair-cycle residual must be -5, 0 or +5 seconds")
        node = next(n for n in topology["nodes"] if n["node_id"] == node_id)
        self._external_adjustments[node_id] = adjustment
        self._new_cycle(node_id, node["phases"], telemetry, network_state or {})

    def current_split(self, node_id):
        return self._state[node_id]["split"]

    def current_base_split(self, node_id):
        return self._state[node_id]["base_split"]

    def preview_cycle(self, node_id, telemetry, topology, network_state=None):
        node = next(n for n in topology["nodes"] if n["node_id"] == node_id)
        previous = self._state.get(node_id, {}).get("split")
        base = self._allocation(node["phases"], telemetry, network_state or {})
        return base, previous or base

    def residual_mask_for(self, ns_green):
        return [ns_green - 5 >= self.minimum_green_s, True,
                ns_green + 5 <= self.maximum_ns_green_s]

    def residual_mask(self, node_id):
        return self.residual_mask_for(self._state[node_id]["base_split"][0])

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        node = next((n for n in topology.get("nodes", []) if n["node_id"] == node_id), None)
        if not node or len(node.get("phases", [])) != 2:
            return None
        phases = node["phases"]
        current = telemetry.get("current_phase_id", phases[0]["phase_id"])
        elapsed = float(telemetry.get("elapsed_green_s", 0))
        now = float(current_time_s if current_time_s is not None else telemetry.get("simulation_time_s", 0))
        state = self._state.get(node_id)
        if state is None:
            self._new_cycle(node_id, phases, telemetry, network_state or {})
            state = self._state[node_id]
        elif (current == phases[0]["phase_id"] and state["phase"] == phases[1]["phase_id"]
              and telemetry.get("signal_state") == "GREEN" and elapsed == 0):
            self._new_cycle(node_id, phases, telemetry, network_state or {})
            state = self._state[node_id]
        ns_green, ew_green = state["split"]
        green_limit = ns_green if current == phases[0]["phase_id"] else ew_green
        target = current
        if telemetry.get("signal_state", "GREEN") == "GREEN" and elapsed >= green_limit:
            target = phases[1]["phase_id"] if current == phases[0]["phase_id"] else phases[0]["phase_id"]
        state["phase"] = current
        return {"command_id": str(uuid.uuid4()), "node_id": node_id,
                "target_phase_id": target, "min_green_s": 10., "max_green_s": 60.,
                "controller": self.controller_name}
