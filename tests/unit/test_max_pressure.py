import sys
from pathlib import Path

# Add service directory to sys.path for testing
graph_control_dir = Path(__file__).parents[2] / "services" / "graph-control"
sys.path.insert(0, str(graph_control_dir))

from graph_contracts_helper import load_topology, validate_payload
from controller import MaxPressureController, FixedTimeController

def test_max_pressure_controller_selection():
    topology = load_topology("four_intersection_v1")
    controller = MaxPressureController(min_green_s=10.0, max_green_s=60.0)

    # Telemetry with heavy North-South traffic
    telemetry_ns_heavy = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 100.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_EW",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 12, "flow_veh_per_s": 0.5, "mean_speed_mps": 2.0, "occupancy_ratio": 0.6},
            {"approach_id": "J1_S_IN", "queue_vehicles": 10, "flow_veh_per_s": 0.4, "mean_speed_mps": 2.1, "occupancy_ratio": 0.5},
            {"approach_id": "J1_E_IN", "queue_vehicles": 2, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "J1_W_IN", "queue_vehicles": 1, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.2, "occupancy_ratio": 0.1}
        ]
    }

    cmd = controller.compute_command("J1", telemetry_ns_heavy, topology)
    assert cmd["node_id"] == "J1"
    assert cmd["target_phase_id"] == "J1_PHASE_NS"
    assert cmd["controller"] == "max_pressure"
    validate_payload(cmd, "control_command")

    # Telemetry with heavy East-West traffic
    telemetry_ew_heavy = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 150.0,
        "timestamp_ms": 1727005870000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 1, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "J1_S_IN", "queue_vehicles": 2, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "J1_E_IN", "queue_vehicles": 15, "flow_veh_per_s": 0.6, "mean_speed_mps": 1.5, "occupancy_ratio": 0.8},
            {"approach_id": "J1_W_IN", "queue_vehicles": 18, "flow_veh_per_s": 0.7, "mean_speed_mps": 1.2, "occupancy_ratio": 0.9}
        ]
    }

    cmd_ew = controller.compute_command("J1", telemetry_ew_heavy, topology)
    assert cmd_ew["target_phase_id"] == "J1_PHASE_EW"
    validate_payload(cmd_ew, "control_command")

def test_fixed_time_controller():
    topology = load_topology("four_intersection_v1")
    controller = FixedTimeController(cycle_time_s=30.0)

    telemetry = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": []
    }

    cmd1 = controller.compute_command("J1", telemetry, topology)
    validate_payload(cmd1, "control_command")
    cmd2 = controller.compute_command("J1", telemetry, topology)
    validate_payload(cmd2, "control_command")
    assert cmd1["target_phase_id"] != cmd2["target_phase_id"]
