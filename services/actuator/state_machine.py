import time
from typing import Dict, Any, Optional
from actuator_contracts_helper import validate_payload

class SignalNodeState:
    def __init__(self, node_id: str, initial_phase: str = "J1_PHASE_NS", yellow_duration_s: float = 3.0, all_red_duration_s: float = 2.0):
        self.node_id = node_id
        self.current_phase_id = initial_phase
        self.state = "GREEN"  # GREEN, YELLOW, ALL_RED
        self.phase_start_time = time.time()
        self.yellow_duration_s = yellow_duration_s
        self.all_red_duration_s = all_red_duration_s
        self.last_transition_time = 0.0

    def elapsed_green_time(self, now: Optional[float] = None) -> float:
        if now is None:
            now = time.time()
        return now - self.phase_start_time


class ActuatorStateMachine:
    """
    Enforces safe phase transitions (Min Green -> Yellow Clearance -> All-Red Clearance)
    and produces standard ControlACK responses.
    """
    def __init__(self, yellow_duration_s: float = 3.0, all_red_duration_s: float = 2.0):
        self.yellow_duration_s = yellow_duration_s
        self.all_red_duration_s = all_red_duration_s
        self.nodes: Dict[str, SignalNodeState] = {}

    def get_or_create_node(self, node_id: str, default_phase: str = "J1_PHASE_NS") -> SignalNodeState:
        if node_id not in self.nodes:
            self.nodes[node_id] = SignalNodeState(
                node_id=node_id,
                initial_phase=default_phase,
                yellow_duration_s=self.yellow_duration_s,
                all_red_duration_s=self.all_red_duration_s
            )
        return self.nodes[node_id]

    def process_command(self, command: Dict[str, Any], now: Optional[float] = None) -> Dict[str, Any]:
        if now is None:
            now = time.time()

        try:
            validate_payload(command, "control_command")
        except Exception as e:
            return {
                "command_id": command.get("command_id", "unknown"),
                "node_id": command.get("node_id", "unknown"),
                "target_phase_id": command.get("target_phase_id", "unknown"),
                "status": "REJECTED",
                "timestamp_ms": int(now * 1000),
                "reason": f"Invalid ControlCommand schema: {str(e)}"
            }

        cmd_id = command["command_id"]
        node_id = command["node_id"]
        target_phase = command["target_phase_id"]
        min_green_s = float(command.get("min_green_s", 10.0))

        node = self.get_or_create_node(node_id, default_phase=target_phase)
        elapsed = node.elapsed_green_time(now=now)

        # Same phase requested
        if target_phase == node.current_phase_id:
            return {
                "command_id": cmd_id,
                "node_id": node_id,
                "target_phase_id": target_phase,
                "status": "APPLIED",
                "timestamp_ms": int(now * 1000),
                "reason": f"Phase {target_phase} is already active. Green time extended."
            }

        # Check min green condition
        if elapsed < min_green_s:
            return {
                "command_id": cmd_id,
                "node_id": node_id,
                "target_phase_id": target_phase,
                "status": "REJECTED",
                "timestamp_ms": int(now * 1000),
                "reason": f"Min green time constraint not met ({elapsed:.1f}s < {min_green_s}s)"
            }

        # Check if node is in active clearance transition
        transition_buffer = self.yellow_duration_s + self.all_red_duration_s
        if node.last_transition_time > 0 and (now - node.last_transition_time) < transition_buffer:
            rem = transition_buffer - (now - node.last_transition_time)
            return {
                "command_id": cmd_id,
                "node_id": node_id,
                "target_phase_id": target_phase,
                "status": "REJECTED",
                "timestamp_ms": int(now * 1000),
                "reason": f"Phase transition currently in progress ({rem:.1f}s clearance remaining)"
            }

        # Perform phase transition: GREEN -> YELLOW -> ALL_RED -> GREEN (target)
        node.state = "YELLOW"
        node.last_transition_time = now
        node.state = "ALL_RED"
        node.current_phase_id = target_phase
        node.state = "GREEN"
        node.phase_start_time = now

        return {
            "command_id": cmd_id,
            "node_id": node_id,
            "target_phase_id": target_phase,
            "status": "APPLIED",
            "timestamp_ms": int(now * 1000),
            "reason": f"Safely transitioned to phase {target_phase} via Yellow ({self.yellow_duration_s}s) and All-Red ({self.all_red_duration_s}s)."
        }

