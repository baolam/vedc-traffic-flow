"""
Unit tests for ActuatorStateMachine custom clearance timing, safety modes,
emergency manual overrides, and Dashboard Control Plane endpoints.
"""

import sys
import time
from pathlib import Path
import pytest

# Ensure root contracts and src are on sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.control.actuator import ActuatorStateMachine, SignalNodeState
from services.api.main import (
    app, LIVE_STATE,
    get_actuator_config, update_actuator_config, ActuatorConfigRequest,
    trigger_emergency_override, OverrideRequest,
    get_system_aggregated_reports
)


def test_actuator_custom_clearance_timing():
    """Verify ActuatorStateMachine respects custom yellow and all-red durations."""
    sm = ActuatorStateMachine(yellow_duration_s=4.0, all_red_duration_s=3.0)
    node = sm.get_or_create_node("J1", default_phase="J1_PHASE_NS")
    
    assert node.yellow_duration_s == 4.0
    assert node.all_red_duration_s == 3.0
    assert node.state == "GREEN"

    # Issue command to switch phase to EW at t=15s (min_green >= 10s)
    cmd = {
        "command_id": "cmd-test-1",
        "node_id": "J1",
        "target_phase_id": "J1_PHASE_EW",
        "min_green_s": 10.0,
        "max_green_s": 60.0,
        "controller": "max_pressure",
        "timestamp_ms": 15000,
        "expires_at_ms": 25000
    }
    ack = sm.process_command(cmd, now=15.0)
    assert ack["status"] == "ACCEPTED"
    assert node.state == "YELLOW"

    # Advance time 3s -> still in YELLOW (since yellow_duration_s = 4.0s)
    res1 = sm.step(now=18.0)
    assert node.state == "YELLOW"
    assert len(res1["applied_events"]) == 0

    # Advance time 4.1s -> enters ALL_RED
    res2 = sm.step(now=19.1)
    assert node.state == "ALL_RED"
    assert len(res2["applied_events"]) == 0

    # Advance time 2s in ALL_RED -> still ALL_RED (since all_red_duration_s = 3.0s)
    res3 = sm.step(now=21.0)
    assert node.state == "ALL_RED"
    assert len(res3["applied_events"]) == 0

    # Advance time 3.1s in ALL_RED -> GREEN applied on target phase J1_PHASE_EW
    res4 = sm.step(now=22.2)
    assert node.state == "GREEN"
    assert node.current_phase_id == "J1_PHASE_EW"
    assert len(res4["applied_events"]) == 1
    assert res4["applied_events"][0]["phase_id"] == "J1_PHASE_EW"


def test_get_actuator_config_endpoint():
    """Test GET /api/v1/actuator/config returns default configuration."""
    cfg = get_actuator_config()
    assert "yellow_duration_s" in cfg
    assert "all_red_duration_s" in cfg
    assert "min_green_s" in cfg
    assert "max_green_s" in cfg
    assert "mode" in cfg
    assert cfg["yellow_duration_s"] == 3.0
    assert cfg["all_red_duration_s"] == 2.0


def test_update_actuator_config_endpoint():
    """Test POST /api/v1/actuator/config updates dynamic parameters and safety mode."""
    req = ActuatorConfigRequest(
        yellow_duration_s=4.5,
        all_red_duration_s=2.5,
        min_green_s=12.0,
        max_green_s=50.0,
        mode="FLASHING_YELLOW"
    )
    res = update_actuator_config(req)
    assert res["status"] == "SUCCESS"
    assert res["actuator_config"]["yellow_duration_s"] == 4.5
    assert res["actuator_config"]["all_red_duration_s"] == 2.5
    assert res["actuator_config"]["mode"] == "FLASHING_YELLOW"

    # Reset back to normal
    update_actuator_config(ActuatorConfigRequest(
        yellow_duration_s=3.0,
        all_red_duration_s=2.0,
        min_green_s=10.0,
        max_green_s=60.0,
        mode="NORMAL"
    ))


def test_trigger_emergency_override_endpoint():
    """Test POST /api/v1/control/override issues manual priority command."""
    req = OverrideRequest(
        node_id="J1",
        target_phase_id="J1_PHASE_NS",
        min_green_s=10.0,
        max_green_s=60.0
    )
    res = trigger_emergency_override(req)
    assert res["status"] == "ACCEPTED"
    assert res["node_id"] == "J1"
    assert res["target_phase_id"] == "J1_PHASE_NS"
    assert "command_id" in res
    assert "cmd-override-J1" in res["command_id"]

    # Verify control ACK was logged in live state
    assert "J1" in LIVE_STATE["control_acks"]
    acks = LIVE_STATE["control_acks"]["J1"]
    assert len(acks) > 0
    assert acks[0]["node_id"] == "J1"
    assert acks[0]["status"] == "ACCEPTED"


def test_system_aggregated_reports_endpoint():
    """Test GET /api/v1/system/reports returns aggregated metrics and recent system logs."""
    res = get_system_aggregated_reports()
    assert "topology_id" in res
    assert "controller" in res
    assert "mean_network_wait_time_s" in res
    assert "total_throughput_veh_per_min" in res
    assert res["safety_compliance_rate_pct"] == 100.0
    assert "recent_system_logs" in res
    assert len(res["recent_system_logs"]) >= 3
