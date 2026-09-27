"""
EdgeFlow AI - Actuator Service Package.
Enforces physical safety timing constraints (GREEN -> YELLOW -> ALL_RED -> GREEN).
"""

from .state_machine import ActuatorStateMachine, SignalNodeState

__all__ = ["ActuatorStateMachine", "SignalNodeState"]
