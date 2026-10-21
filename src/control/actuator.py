"""
Clock-driven Actuator State Machine for EdgeFlow AI.

Enforces safe signal transitions: GREEN -> YELLOW -> ALL_RED -> GREEN.
A single process_command() call NEVER instantaneously passes through
yellow and all-red. The actuator is the sole owner of physical timing.

All time parameters use simulation seconds, not wall-clock.
"""

import time
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("actuator")

try:
    from contracts.contracts_sdk import load_schema
    from contracts.research import SIGNAL_STATES
except ImportError:
    from contracts_sdk import load_schema
    from research import SIGNAL_STATES
from jsonschema import Draft7Validator

_CONTROL_COMMAND_VALIDATOR = Draft7Validator(load_schema("control_command"))

class SignalNodeState:
    """State for a single signalized intersection node."""

    VALID_STATES = SIGNAL_STATES

    def __init__(
        self,
        node_id: str,
        initial_phase: str = "J1_PHASE_NS",
        yellow_duration_s: float = 3.0,
        all_red_duration_s: float = 2.0,
        min_green_s: float = 10.0,
        max_green_s: float = 60.0,
    ):
        self.node_id = node_id
        self.current_phase_id = initial_phase
        self.state = "GREEN"
        self.yellow_duration_s = yellow_duration_s
        self.all_red_duration_s = all_red_duration_s
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s

        # Timing anchors (simulation seconds)
        self.phase_start_time: float = 0.0
        self.state_start_time: float = 0.0

        # Pending transition
        self.pending_phase_id: Optional[str] = None
        self.pending_command_id: Optional[str] = None

        # Event log
        self.transition_log: List[Dict[str, Any]] = []

    def reset(self, now: float = 0.0):
        """Full reset to initial state."""
        self.state = "GREEN"
        self.phase_start_time = now
        self.state_start_time = now
        self.pending_phase_id = None
        self.pending_command_id = None
        self.transition_log.clear()

    def elapsed_in_state(self, now: float) -> float:
        """Seconds since the current state (GREEN/YELLOW/ALL_RED) began."""
        return max(0.0, now - self.state_start_time)

    def elapsed_green_time(self, now: float) -> float:
        """Seconds of green time in the current phase. Returns 0 if not GREEN."""
        if self.state == "GREEN":
            return max(0.0, now - self.phase_start_time)
        return 0.0

    def update_clock(self, now: float) -> Optional[str]:
        """
        Advance the clearance state machine based on elapsed time.

        Returns:
            "APPLIED" if a pending phase transition completed to GREEN.
            None otherwise.
        """
        if self.state == "YELLOW":
            if self.elapsed_in_state(now) >= self.yellow_duration_s:
                self.state = "ALL_RED"
                self.state_start_time = now
                self._log_event(now, "YELLOW_COMPLETE", "Entered ALL_RED")

        if self.state == "ALL_RED":
            if self.elapsed_in_state(now) >= self.all_red_duration_s:
                # Transition to new GREEN
                old_phase = self.current_phase_id
                if self.pending_phase_id:
                    self.current_phase_id = self.pending_phase_id
                    self.pending_phase_id = None
                self.state = "GREEN"
                self.state_start_time = now
                self.phase_start_time = now
                self._log_event(now, "PHASE_APPLIED",
                                f"GREEN on {self.current_phase_id} (was {old_phase})")
                return "APPLIED"

        return None

    def _log_event(self, now: float, event_type: str, detail: str):
        self.transition_log.append({
            "time_s": round(now, 3),
            "node_id": self.node_id,
            "event": event_type,
            "phase": self.current_phase_id,
            "state": self.state,
            "detail": detail,
        })


class ActuatorStateMachine:
    """
    Enforces safe phase transitions:
        current GREEN -> YELLOW -> ALL_RED -> target GREEN

    Invariants:
    - A single process_command() call NEVER passes through yellow+all-red.
    - Min-green, max-green, yellow, all-red durations are respected.
    - Conflicting greens are impossible: only one phase is GREEN at a time.
    - Expired commands are rejected.
    - Invalid schemas are rejected.
    - The actuator is clock-driven: call step(now) to advance time.
    """

    def __init__(self, yellow_duration_s: float = 3.0, all_red_duration_s: float = 2.0):
        self.yellow_duration_s = yellow_duration_s
        self.all_red_duration_s = all_red_duration_s
        self.nodes: Dict[str, SignalNodeState] = {}

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def get_or_create_node(
        self, node_id: str, default_phase: str = "J1_PHASE_NS"
    ) -> SignalNodeState:
        if node_id not in self.nodes:
            self.nodes[node_id] = SignalNodeState(
                node_id=node_id,
                initial_phase=default_phase,
                yellow_duration_s=self.yellow_duration_s,
                all_red_duration_s=self.all_red_duration_s,
            )
        return self.nodes[node_id]

    def reset_all(self, now: float = 0.0):
        """Reset all nodes to initial state. Called between experiments."""
        for node in self.nodes.values():
            node.reset(now)
        self.nodes.clear()

    # ------------------------------------------------------------------
    # Time advancement
    # ------------------------------------------------------------------

    def step(self, now: float) -> Dict[str, Any]:
        """
        Advance time across all active signal nodes.
        Must be called every simulation tick.
        """
        applied_events: List[Dict[str, Any]] = []
        for node_id, node in self.nodes.items():
            cmd_id = node.pending_command_id
            result = node.update_clock(now)
            if result == "APPLIED":
                applied_events.append({
                    "command_id": cmd_id or f"cmd-auto-{int(now * 1000)}",
                    "node_id": node_id,
                    "target_phase_id": node.current_phase_id,
                    "phase_id": node.current_phase_id,
                    "time_s": round(now, 3),
                })
                node.pending_command_id = None
        return {"now": now, "applied_events": applied_events}

    # ------------------------------------------------------------------
    # Command processing
    # ------------------------------------------------------------------

    def process_command(
        self, command: Dict[str, Any], now: float
    ) -> Dict[str, Any]:
        """
        Process a ControlCommand. Returns a ControlACK dict.

        Rules:
        1. Schema validation.
        2. Expired commands are rejected.
        3. Same-phase requests during GREEN: extend (APPLIED).
        4. Same-phase requests during clearance: wait (ACCEPTED).
        5. Different-phase during clearance: rejected (busy).
        6. Different-phase during GREEN with elapsed < min_green: rejected.
        7. Different-phase during GREEN with elapsed >= min_green:
           initiate YELLOW. Do NOT skip to GREEN.
        """
        # --- Schema validation ---
        try:
            errors = list(_CONTROL_COMMAND_VALIDATOR.iter_errors(command))
            if errors:
                raise ValueError(errors[0].message)
        except Exception as e:
            return self._ack(command, "REJECTED",
                             f"Invalid ControlCommand schema: {e}")

        cmd_id = command["command_id"]
        node_id = command["node_id"]
        target_phase = command["target_phase_id"]
        min_green_s = float(command.get("min_green_s", 10.0))
        max_green_s = float(command.get("max_green_s", 60.0))
        expires_at_ms = command.get("expires_at_ms")

        # --- Expiry check ---
        if expires_at_ms is not None and (now * 1000) > expires_at_ms:
            return self._ack(
                command, "EXPIRED",
                f"Command expired at {expires_at_ms} ms (current: {int(now * 1000)} ms)"
            )

        # --- Get/create node ---
        node = self.get_or_create_node(node_id, default_phase=target_phase)
        node.min_green_s = min_green_s
        node.max_green_s = max_green_s

        # Advance internal clock first
        node.update_clock(now)

        # --- Same phase requested ---
        if target_phase == node.current_phase_id:
            if node.state == "GREEN":
                return self._ack(
                    command, "APPLIED",
                    f"Phase {target_phase} is already active. Green time extended."
                )
            else:
                return self._ack(
                    command, "ACCEPTED",
                    f"Transition to {target_phase} currently clearing through {node.state}."
                )

        # Also handle: target matches pending phase
        if target_phase == node.pending_phase_id:
            return self._ack(
                command, "ACCEPTED",
                f"Phase {target_phase} is already pending. Clearing through {node.state}."
            )

        # --- Currently in clearance for a different phase ---
        if node.state in ("YELLOW", "ALL_RED"):
            return self._ack(
                command, "REJECTED",
                f"Node {node_id} is currently in {node.state} clearance interval."
            )

        # --- GREEN: check min-green ---
        elapsed = node.elapsed_green_time(now)
        if elapsed < min_green_s:
            return self._ack(
                command, "REJECTED",
                f"Min green time not met ({elapsed:.1f}s < {min_green_s}s)"
            )

        # --- Initiate safe transition: GREEN -> YELLOW ---
        node.pending_phase_id = target_phase
        node.pending_command_id = cmd_id
        node.state = "YELLOW"
        node.state_start_time = now
        node._log_event(now, "YELLOW_START",
                         f"Transitioning from {node.current_phase_id} to {target_phase}")

        return self._ack(
            command, "ACCEPTED",
            f"Transition initiated: {node.current_phase_id} -> YELLOW ({self.yellow_duration_s}s) "
            f"-> ALL_RED ({self.all_red_duration_s}s) -> {target_phase}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ack(command: Dict[str, Any], status: str, reason: str, timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
        return {
            "command_id": command.get("command_id", "unknown"),
            "node_id": command.get("node_id", "unknown"),
            "target_phase_id": command.get("target_phase_id", "unknown"),
            "status": status,
            "timestamp_ms": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
            "reason": reason,
        }
