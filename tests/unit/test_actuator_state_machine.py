import sys
import uuid
from pathlib import Path

# Add actuator service directory to sys.path for testing
actuator_dir = Path(__file__).parents[2] / "services" / "actuator"
sys.path.insert(0, str(actuator_dir))

from actuator_contracts_helper import validate_payload
from state_machine import ActuatorStateMachine

def test_actuator_same_phase():
    sm = ActuatorStateMachine()
    cmd = {
        "command_id": str(uuid.uuid4()),
        "node_id": "J1",
        "target_phase_id": "J1_PHASE_NS",
        "min_green_s": 10.0,
        "max_green_s": 30.0,
        "controller": "max_pressure"
    }
    ack = sm.process_command(cmd, now=100.0)
    assert ack["status"] == "APPLIED"
    assert ack.get("target_phase_id") == "J1_PHASE_NS"
    validate_payload(ack, "control_ack")

def test_actuator_min_green_rejection():
    sm = ActuatorStateMachine()
    # Initialize node at time 100.0 on phase J1_PHASE_NS
    node = sm.get_or_create_node("J1", default_phase="J1_PHASE_NS")
    node.phase_start_time = 100.0

    # Try to switch to J1_PHASE_EW at time 105.0 (elapsed 5s < min_green 10s)
    cmd = {
        "command_id": str(uuid.uuid4()),
        "node_id": "J1",
        "target_phase_id": "J1_PHASE_EW",
        "min_green_s": 10.0,
        "max_green_s": 30.0,
        "controller": "max_pressure"
    }
    ack = sm.process_command(cmd, now=105.0)
    assert ack["status"] == "REJECTED"
    assert ack.get("target_phase_id") == "J1_PHASE_EW"
    assert "Min green time" in ack["reason"]
    validate_payload(ack, "control_ack")

def test_actuator_successful_transition():
    sm = ActuatorStateMachine()
    node = sm.get_or_create_node("J1", default_phase="J1_PHASE_NS")
    node.phase_start_time = 100.0

    # Try to switch at time 112.0 (elapsed 12s >= min_green 10s)
    cmd = {
        "command_id": str(uuid.uuid4()),
        "node_id": "J1",
        "target_phase_id": "J1_PHASE_EW",
        "min_green_s": 10.0,
        "max_green_s": 30.0,
        "controller": "max_pressure"
    }
    ack = sm.process_command(cmd, now=112.0)
    assert ack["status"] == "APPLIED"
    assert ack.get("target_phase_id") == "J1_PHASE_EW"
    assert node.current_phase_id == "J1_PHASE_EW"
    validate_payload(ack, "control_ack")
