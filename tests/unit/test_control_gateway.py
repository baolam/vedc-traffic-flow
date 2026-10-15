import pytest
import time
from contracts.contracts_sdk import load_topology
from contracts.topics import topic, get_telemetry_topic
from src.control.gateway import ControlGateway
from src.control.controllers import FixedTimeController, MaxPressureController


@pytest.fixture
def topology():
    return load_topology("tabletop_j1_j2_v1")


@pytest.fixture
def controller():
    return FixedTimeController(cycle_time_s=60.0)


def test_gateway_initialization(topology, controller):
    gw = ControlGateway(controller=controller, topology=topology, controller_id="demo-coord")
    assert gw.controller_id == "demo-coord"
    assert "J1" in gw.owned
    assert "J2" in gw.owned


def test_gateway_ingest_health(topology, controller):
    gw = ControlGateway(controller=controller, topology=topology)
    now_ms = int(time.time() * 1000)

    health_payload = {
        "service": "esp32_actuator",
        "node_id": "J1",
        "status": "HEALTHY",
        "current_phase": "J1_PHASE_NS",
        "clearance": "GREEN",
        "safe_stop": False,
        "timestamp_ms": now_ms
    }
    gw.ingest_health(health_payload, now_ms)
    assert gw.health["J1"]["status"] == "HEALTHY"


def test_gateway_decision_vision_requires_esp32_health(topology, controller):
    gw = ControlGateway(controller=controller, topology=topology)
    now_ms = int(time.time() * 1000)

    telemetry = {
        "node_id": "J1",
        "source_type": "vision",
        "timestamp_ms": now_ms,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 3.0, "confidence": 0.9,
             "flow_veh_per_s": 0.2, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "J1_S_IN", "queue_vehicles": 2.0, "confidence": 0.9,
             "flow_veh_per_s": 0.2, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "J1_E_IN", "queue_vehicles": 1.0, "confidence": 0.9,
             "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.05},
            {"approach_id": "J1_W_IN", "queue_vehicles": 4.0, "confidence": 0.9,
             "flow_veh_per_s": 0.3, "mean_speed_mps": 4.0, "occupancy_ratio": 0.15},
        ]
    }

    # Without ESP32 actuator health, vision cannot confirm physical phase
    cmd = gw.decision(telemetry, now_ms=now_ms)
    assert cmd is None

    # After ingesting valid ESP32 actuator health
    gw.ingest_health({
        "service": "esp32_actuator",
        "node_id": "J1",
        "status": "HEALTHY",
        "current_phase": "J1_PHASE_NS",
        "clearance": "GREEN",
        "safe_stop": False,
        "timestamp_ms": now_ms
    }, now_ms=now_ms)

    # In tabletop_j1_j2_v1, J1 has neighbor J2. If J2 is missing, gateway guards against blind decisions
    cmd_no_neighbor = gw.decision(telemetry, now_ms=now_ms)
    assert cmd_no_neighbor is None

    # Ingest J2 neighbor telemetry & health
    gw.ingest_health({
        "service": "esp32_actuator",
        "node_id": "J2",
        "status": "HEALTHY",
        "current_phase": "J2_PHASE_NS",
        "clearance": "GREEN",
        "safe_stop": False,
        "timestamp_ms": now_ms
    }, now_ms=now_ms)

    gw.decision({
        "node_id": "J2",
        "source_type": "vision",
        "timestamp_ms": now_ms,
        "current_phase_id": "J2_PHASE_NS",
        "approaches": [
            {"approach_id": "J2_N_IN", "queue_vehicles": 0.0, "confidence": 0.9,
             "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0},
            {"approach_id": "J2_S_IN", "queue_vehicles": 0.0, "confidence": 0.9,
             "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0},
            {"approach_id": "J2_E_IN", "queue_vehicles": 0.0, "confidence": 0.9,
             "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0},
            {"approach_id": "J2_W_IN", "queue_vehicles": 0.0, "confidence": 0.9,
             "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0},
        ]
    }, now_ms=now_ms)

    # Now decision on J1 succeeds and produces valid ControlCommand
    cmd = gw.decision(telemetry, now_ms=now_ms, mqtt_topic=get_telemetry_topic("J1"))
    assert cmd is not None
    assert cmd["node_id"] == "J1"
    assert "target_phase_id" in cmd
    assert cmd["controller_id"] == gw.controller_id
