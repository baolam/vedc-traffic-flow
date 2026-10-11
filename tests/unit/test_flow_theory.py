import sys
from pathlib import Path

# Add service directory to sys.path for testing
graph_control_dir = Path(__file__).parents[2] / "services" / "graph-control"
if str(graph_control_dir) not in sys.path:
    sys.path.insert(0, str(graph_control_dir))

from graph_contracts_helper import load_topology, validate_payload
from controller import FlowTheoryController

def test_flow_theory_controller_selection():
    topology = load_topology("four_intersection_v1")
    controller = FlowTheoryController(min_green_s=10.0, max_green_s=60.0)

    # Telemetry where NS has high queue and low occupancy (high receiving capacity)
    telemetry_ns_high_flow = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 100.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_EW",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 15, "flow_rate": 360.0, "occupancy": 0.2},
            {"approach_id": "J1_S_IN", "queue_vehicles": 12, "flow_rate": 300.0, "occupancy": 0.2},
            {"approach_id": "J1_E_IN", "queue_vehicles": 2, "flow_rate": 50.0, "occupancy": 0.1},
            {"approach_id": "J1_W_IN", "queue_vehicles": 1, "flow_rate": 50.0, "occupancy": 0.1}
        ]
    }

    cmd = controller.compute_command("J1", telemetry_ns_high_flow, topology)
    assert cmd["node_id"] == "J1"
    assert cmd["target_phase_id"] == "J1_PHASE_NS"
    assert cmd["controller"] == "flow_theory"
    validate_payload(cmd, "control_command")

def test_flow_theory_gridlock_prevention():
    topology = load_topology("four_intersection_v1")
    controller = FlowTheoryController(min_green_s=10.0, max_green_s=60.0)

    # Telemetry where NS has queue=20 but occupancy=1.0 (completely saturated downstream gridlock)
    # EW has queue=5 and occupancy=0.1 (smooth flow)
    telemetry_ns_saturated = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 200.0,
        "timestamp_ms": 1727005920000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 20, "flow_rate": 500.0, "occupancy": 1.0},
            {"approach_id": "J1_S_IN", "queue_vehicles": 20, "flow_rate": 500.0, "occupancy": 1.0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 5, "flow_rate": 100.0, "occupancy": 0.1},
            {"approach_id": "J1_W_IN", "queue_vehicles": 5, "flow_rate": 100.0, "occupancy": 0.1}
        ]
    }

    cmd = controller.compute_command("J1", telemetry_ns_saturated, topology)
    assert cmd["node_id"] == "J1"
    # Because NS is saturated (receiving_capacity = 0), CTM picks EW to prevent gridlock!
    assert cmd["target_phase_id"] == "J1_PHASE_EW"
    assert cmd["controller"] == "flow_theory"
    validate_payload(cmd, "control_command")


def test_flow_theory_canonical_flow_unit_and_precedence():
    """Verify canonical flow_veh_per_s (veh/s) directly drives sending capacity and takes precedence over flow_rate."""
    topology = load_topology("four_intersection_v1")
    controller = FlowTheoryController(min_green_s=10.0, max_green_s=60.0, saturation_flow_vps=0.5)

    # Both phases have zero queue and low occupancy.
    # NS has canonical flow_veh_per_s = 0.45 veh/s.
    # EW has legacy flow_rate = 36.0 (which would be 0.01 veh/s if divided by 3600).
    telemetry = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 300.0,
        "timestamp_ms": 1727006000000,
        "current_phase_id": "J1_PHASE_EW",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.45, "occupancy_ratio": 0.1},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.40, "occupancy_ratio": 0.1},
            {"approach_id": "J1_E_IN", "queue_vehicles": 0, "flow_rate": 36.0, "occupancy_ratio": 0.1},
            {"approach_id": "J1_W_IN", "queue_vehicles": 0, "flow_rate": 36.0, "occupancy_ratio": 0.1},
        ]
    }

    cmd = controller.compute_command("J1", telemetry, topology)
    # NS must win because of canonical flow_veh_per_s
    assert cmd["target_phase_id"] == "J1_PHASE_NS"
    assert cmd["controller"] == "flow_theory"
    validate_payload(cmd, "control_command")


def test_flow_theory_movement_downstream_mapping():
    """Verify FlowTheoryController resolves specific to_approach in network_state."""
    topology = load_topology("four_intersection_v1")
    controller = FlowTheoryController(min_green_s=10.0, max_green_s=60.0)

    telemetry = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 400.0,
        "timestamp_ms": 1727006100000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 10, "flow_veh_per_s": 0.3, "occupancy_ratio": 0.2},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_W_IN", "queue_vehicles": 10, "flow_veh_per_s": 0.3, "occupancy_ratio": 0.2},
        ]
    }

    # J3 (downstream of J1 NS) has specific approach J3_N_IN jammed (0.95), but other approaches clear (0.0).
    # If using specific approach, NS is gated. If using naive node average, (0.95 / 4 = 0.2375) it wouldn't gate!
    network_state = {
        "J3": {
            "approaches": [
                {"approach_id": "J3_N_IN", "occupancy_ratio": 0.95},
                {"approach_id": "J3_S_IN", "occupancy_ratio": 0.0},
                {"approach_id": "J3_E_IN", "occupancy_ratio": 0.0},
                {"approach_id": "J3_W_IN", "occupancy_ratio": 0.0},
            ]
        },
        "J2": {
            "approaches": [
                {"approach_id": "J2_W_IN", "occupancy_ratio": 0.1},
                {"approach_id": "J2_E_IN", "occupancy_ratio": 0.1},
                {"approach_id": "J2_N_IN", "occupancy_ratio": 0.1},
                {"approach_id": "J2_S_IN", "occupancy_ratio": 0.1},
            ]
        }
    }

    cmd = controller.compute_command("J1", telemetry, topology, network_state=network_state)
    assert cmd["target_phase_id"] == "J1_PHASE_EW"
    assert cmd["controller"] == "flow_theory"

