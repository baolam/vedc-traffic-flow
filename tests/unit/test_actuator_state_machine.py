"""
Tests for the ActuatorStateMachine (P0 Updated).

Validates clock-driven signal transitions, min-green enforcement,
command expiry, schema validation, and multi-node isolation.
"""

import sys
import uuid
from pathlib import Path

# Add actuator service directory to sys.path for testing
actuator_dir = Path(__file__).parents[2] / "services" / "actuator"
sys.path.insert(0, str(actuator_dir))

from state_machine import ActuatorStateMachine


def _cmd(node_id="J1", target="J1_PHASE_NS", min_green=10.0, max_green=30.0, **kw):
    c = {
        "command_id": str(uuid.uuid4()),
        "node_id": node_id,
        "target_phase_id": target,
        "min_green_s": min_green,
        "max_green_s": max_green,
        "controller": "test",
    }
    c.update(kw)
    return c


def test_actuator_same_phase():
    sm = ActuatorStateMachine()
    cmd = _cmd(target="J1_PHASE_NS")
    ack = sm.process_command(cmd, now=100.0)
    assert ack["status"] == "APPLIED"
    assert ack["target_phase_id"] == "J1_PHASE_NS"


def test_actuator_min_green_rejection():
    sm = ActuatorStateMachine()
    node = sm.get_or_create_node("J1", default_phase="J1_PHASE_NS")
    node.phase_start_time = 100.0
    node.state_start_time = 100.0

    cmd = _cmd(target="J1_PHASE_EW", min_green=10.0)
    ack = sm.process_command(cmd, now=105.0)  # 5s < 10s
    assert ack["status"] == "REJECTED"
    assert "Min green" in ack["reason"]


def test_actuator_successful_transition():
    """Transition should be ACCEPTED (not instant APPLIED) and complete via clock."""
    sm = ActuatorStateMachine()
    node = sm.get_or_create_node("J1", default_phase="J1_PHASE_NS")
    node.phase_start_time = 100.0
    node.state_start_time = 100.0

    cmd = _cmd(target="J1_PHASE_EW", min_green=10.0)
    ack = sm.process_command(cmd, now=112.0)  # 12s >= 10s

    # Should initiate transition, NOT instant apply
    assert ack["status"] == "ACCEPTED"
    assert node.state == "YELLOW"

    # Advance through clearance
    sm.step(now=115.0)  # YELLOW done (3s)
    assert node.state == "ALL_RED"

    sm.step(now=117.0)  # ALL_RED done (2s)
    assert node.state == "GREEN"
    assert node.current_phase_id == "J1_PHASE_EW"


def test_actuator_command_expiry():
    sm = ActuatorStateMachine()
    cmd = _cmd(target="J1_PHASE_EW", expires_at_ms=100000)
    ack = sm.process_command(cmd, now=105.0)  # 105000 > 100000
    assert ack["status"] == "EXPIRED"
    assert "expired" in ack["reason"].lower()


def test_actuator_invalid_command_schema():
    sm = ActuatorStateMachine()
    invalid_cmd = {
        "command_id": str(uuid.uuid4()),
        "target_phase_id": "J1_PHASE_EW",
        # Missing node_id
    }
    ack = sm.process_command(invalid_cmd, now=0.0)
    assert ack["status"] == "REJECTED"


def test_actuator_multi_node_isolation():
    sm = ActuatorStateMachine()
    node_j1 = sm.get_or_create_node("J1", default_phase="J1_PHASE_NS")
    node_j2 = sm.get_or_create_node("J2", default_phase="J2_PHASE_NS")
    node_j1.phase_start_time = 100.0
    node_j1.state_start_time = 100.0
    node_j2.phase_start_time = 100.0
    node_j2.state_start_time = 100.0

    cmd_j1 = _cmd(node_id="J1", target="J1_PHASE_EW", min_green=10.0)
    ack_j1 = sm.process_command(cmd_j1, now=115.0)
    assert ack_j1["status"] == "ACCEPTED"
    assert node_j1.state == "YELLOW"
    assert node_j2.current_phase_id == "J2_PHASE_NS"  # J2 unaffected
    assert node_j2.state == "GREEN"


def test_actuator_reset():
    sm = ActuatorStateMachine()
    sm.get_or_create_node("J1")
    sm.get_or_create_node("J2")
    assert len(sm.nodes) == 2

    sm.reset_all()
    assert len(sm.nodes) == 0


def test_full_clearance_timing():
    """Verify exact timing: 3s yellow + 2s all-red."""
    sm = ActuatorStateMachine(yellow_duration_s=3.0, all_red_duration_s=2.0)
    node = sm.get_or_create_node("J1", default_phase="J1_PHASE_NS")
    node.phase_start_time = 0.0
    node.state_start_time = 0.0

    # Initiate at t=10
    cmd = _cmd(target="J1_PHASE_EW", min_green=0.0)
    sm.process_command(cmd, now=10.0)
    assert node.state == "YELLOW"

    # t=12: still YELLOW
    sm.step(now=12.0)
    assert node.state == "YELLOW"

    # t=13: YELLOW complete -> ALL_RED
    sm.step(now=13.0)
    assert node.state == "ALL_RED"

    # t=14: still ALL_RED
    sm.step(now=14.0)
    assert node.state == "ALL_RED"

    # t=15: ALL_RED complete -> GREEN EW
    result = sm.step(now=15.0)
    assert node.state == "GREEN"
    assert node.current_phase_id == "J1_PHASE_EW"
    assert len(result["applied_events"]) == 1
