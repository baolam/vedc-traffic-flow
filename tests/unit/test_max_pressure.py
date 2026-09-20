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

def test_max_pressure_three_way_junction():
    topology = load_topology("three_way_junction_v1")
    controller = MaxPressureController()

    telemetry = {
        "node_id": "TJ1",
        "source_type": "simulation",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "TJ1_PHASE_THROUGH",
        "approaches": [
            {"approach_id": "TJ1_NORTH_IN", "queue_vehicles": 2, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "TJ1_SOUTH_IN", "queue_vehicles": 1, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "TJ1_EAST_IN", "queue_vehicles": 20, "flow_veh_per_s": 0.8, "mean_speed_mps": 1.0, "occupancy_ratio": 0.9}
        ]
    }

    cmd = controller.compute_command("TJ1", telemetry, topology)
    assert cmd["target_phase_id"] == "TJ1_PHASE_SIDE_APPROACH"
    validate_payload(cmd, "control_command")

def test_max_pressure_multi_phase_junction():
    topology = load_topology("multi_phase_v1")
    controller = MaxPressureController()

    telemetry = {
        "node_id": "MP1",
        "source_type": "simulation",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "MP1_PHASE_NS_STRAIGHT",
        "approaches": [
            {"approach_id": "MP1_N_IN", "queue_vehicles": 1, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "MP1_S_IN", "queue_vehicles": 1, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "MP1_E_IN", "queue_vehicles": 1, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "MP1_W_IN", "queue_vehicles": 1, "flow_veh_per_s": 0.1, "mean_speed_mps": 5.0, "occupancy_ratio": 0.1},
            {"approach_id": "MP1_NE_DIAG_IN", "queue_vehicles": 25, "flow_veh_per_s": 0.9, "mean_speed_mps": 0.5, "occupancy_ratio": 0.95}
        ]
    }

    cmd = controller.compute_command("MP1", telemetry, topology)
    assert cmd["target_phase_id"] == "MP1_PHASE_DIAG_PROTECTED"
    validate_payload(cmd, "control_command")

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

def test_controllers_invalid_node_or_no_phases():
    topology = load_topology("four_intersection_v1")
    fixed_ctrl = FixedTimeController()
    mp_ctrl = MaxPressureController()

    telemetry = {
        "node_id": "UNKNOWN_NODE",
        "source_type": "simulation",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "PHASE_X",
        "approaches": []
    }

    # Non-existent node ID should return None
    assert fixed_ctrl.compute_command("UNKNOWN_NODE", telemetry, topology) is None
    assert mp_ctrl.compute_command("UNKNOWN_NODE", telemetry, topology) is None

    # Node with no phases should return None
    empty_phases_topo = {
        "topology_id": "empty_phases",
        "nodes": [{"node_id": "N1", "approaches": [], "phases": []}]
    }
    assert fixed_ctrl.compute_command("N1", telemetry, empty_phases_topo) is None
    assert mp_ctrl.compute_command("N1", telemetry, empty_phases_topo) is None

def test_fixed_time_phase_cycling():
    topology = load_topology("four_intersection_v1")
    controller = FixedTimeController(cycle_time_s=45.0)

    telemetry = {"node_id": "J1", "approaches": []}
    phases = [p["phase_id"] for p in topology["nodes"][0]["phases"]]

    # Verify cycling through all phases sequentially and wrapping around
    first_target = controller.compute_command("J1", telemetry, topology)["target_phase_id"]
    second_target = controller.compute_command("J1", telemetry, topology)["target_phase_id"]
    third_target = controller.compute_command("J1", telemetry, topology)["target_phase_id"]

    assert first_target == phases[1 % len(phases)]
    assert second_target == phases[0]
    assert third_target == phases[1 % len(phases)]

def test_max_pressure_telemetry_edge_cases():
    topology = load_topology("four_intersection_v1")
    controller = MaxPressureController()

    # Telemetry with empty approaches list -> defaults to selecting top phase gracefully
    telemetry_empty = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": []
    }
    cmd_empty = controller.compute_command("J1", telemetry_empty, topology)
    validate_payload(cmd_empty, "control_command")
    assert cmd_empty["target_phase_id"] in ["J1_PHASE_NS", "J1_PHASE_EW"]

    # Telemetry with missing approach IDs in dict -> unmentioned approaches count as 0 queue
    telemetry_partial = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_E_IN", "queue_vehicles": 20, "flow_veh_per_s": 0.5, "mean_speed_mps": 1.0}
            # N, S, W approaches omitted
        ]
    }
    cmd_partial = controller.compute_command("J1", telemetry_partial, topology)
    assert cmd_partial["target_phase_id"] == "J1_PHASE_EW"

