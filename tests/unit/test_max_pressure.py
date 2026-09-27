import sys
from pathlib import Path

# Add service directory to sys.path for testing
graph_control_dir = Path(__file__).parents[2] / "services" / "graph-control"
sys.path.insert(0, str(graph_control_dir))

from graph_contracts_helper import load_topology, validate_payload
from controller import MaxPressureController, FixedTimeController, MaxQueueController, EdgeFlowController, PressLightRLController

def test_max_queue_controller_selection():
    topology = load_topology("four_intersection_v1")
    controller = MaxQueueController(min_green_s=10.0, max_green_s=60.0)

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
    assert cmd["controller"] == "max_queue"
    validate_payload(cmd, "control_command")


def test_max_pressure_movement_downstream_aware():
    topology = load_topology("four_intersection_v1")
    controller = MaxPressureController(min_green_s=10.0, max_green_s=60.0)

    # J1 has equal incoming queue on NS and EW (both 10 vehicles).
    # But downstream node J3 (target of J1_N_IN) has heavy queue (15 vehicles),
    # while downstream node J2 (target of J1_W_IN) has 0 queue.
    telemetry_j1 = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 100.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 10, "flow_veh_per_s": 0.5, "mean_speed_mps": 2.0, "occupancy_ratio": 0.5},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "mean_speed_mps": 5.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "mean_speed_mps": 5.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_W_IN", "queue_vehicles": 10, "flow_veh_per_s": 0.5, "mean_speed_mps": 2.0, "occupancy_ratio": 0.5}
        ]
    }

    network_state = {
        "J3": {
            "approaches": [
                {"approach_id": "J3_S_IN", "queue_vehicles": 15, "occupancy_ratio": 0.9}
            ]
        },
        "J2": {
            "approaches": [
                {"approach_id": "J2_E_IN", "queue_vehicles": 0, "occupancy_ratio": 0.0}
            ]
        }
    }

    cmd = controller.compute_command("J1", telemetry_j1, topology, network_state=network_state)
    assert cmd["node_id"] == "J1"
    # EW phase should have higher pressure because J2 downstream queue is 0, while J3 downstream queue is 15
    assert cmd["target_phase_id"] == "J1_PHASE_EW"
    assert cmd["controller"] == "max_pressure"
    validate_payload(cmd, "control_command")


def test_edgeflow_controller_spillback_and_switching_margin():
    topology = load_topology("four_intersection_v1")
    controller = EdgeFlowController(switching_margin=2.0)

    # Currently active: J1_PHASE_NS
    # NS incoming queue = 8, EW incoming queue = 9.
    # Difference (9 - 8 = 1.0) is smaller than switching_margin (2.0) -> holds J1_PHASE_NS to prevent fluttering!
    telemetry_small_diff = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 100.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 8, "flow_veh_per_s": 0.3, "mean_speed_mps": 3.0, "occupancy_ratio": 0.4},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "mean_speed_mps": 5.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "mean_speed_mps": 5.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_W_IN", "queue_vehicles": 9, "flow_veh_per_s": 0.3, "mean_speed_mps": 3.0, "occupancy_ratio": 0.4}
        ]
    }

    cmd_hold = controller.compute_command("J1", telemetry_small_diff, topology)
    assert cmd_hold["target_phase_id"] == "J1_PHASE_NS"
    assert cmd_hold["controller"] == "edgeflow"
    validate_payload(cmd_hold, "control_command")

    # When difference becomes significant (15 vs 8 > 2.0 margin), switches to EW
    telemetry_large_diff = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 105.0,
        "timestamp_ms": 1727005825000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 8, "flow_veh_per_s": 0.3, "mean_speed_mps": 3.0, "occupancy_ratio": 0.4},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "mean_speed_mps": 5.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 0, "flow_veh_per_s": 0.0, "mean_speed_mps": 5.0, "occupancy_ratio": 0.0},
            {"approach_id": "J1_W_IN", "queue_vehicles": 15, "flow_veh_per_s": 0.5, "mean_speed_mps": 2.0, "occupancy_ratio": 0.6}
        ]
    }
    cmd_switch = controller.compute_command("J1", telemetry_large_diff, topology)
    assert cmd_switch["target_phase_id"] == "J1_PHASE_EW"


def test_fixed_time_clock_driven_stability():
    """
    Appendix A2 verification: calling compute_command multiple times with the SAME timestamp
    must NOT cycle the phase!
    """
    topology = load_topology("four_intersection_v1")
    controller = FixedTimeController(cycle_time_s=30.0)  # 15s NS, 15s EW

    telemetry = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": []
    }

    # Same timestamp 10.0 called 3 consecutive times:
    cmd1 = controller.compute_command("J1", telemetry, topology, current_time_s=10.0)
    cmd2 = controller.compute_command("J1", telemetry, topology, current_time_s=10.0)
    cmd3 = controller.compute_command("J1", telemetry, topology, current_time_s=10.0)

    assert cmd1["target_phase_id"] == "J1_PHASE_NS"
    assert cmd2["target_phase_id"] == "J1_PHASE_NS"
    assert cmd3["target_phase_id"] == "J1_PHASE_NS"

    # Advance time by 16s (past 15s green split) -> transitions to EW
    cmd4 = controller.compute_command("J1", telemetry, topology, current_time_s=26.0)
    assert cmd4["target_phase_id"] == "J1_PHASE_EW"

    # Advance time by another 16s (past 30s) -> transitions back to NS
    cmd5 = controller.compute_command("J1", telemetry, topology, current_time_s=42.0)
    assert cmd5["target_phase_id"] == "J1_PHASE_NS"


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

    assert fixed_ctrl.compute_command("UNKNOWN_NODE", telemetry, topology) is None
    assert mp_ctrl.compute_command("UNKNOWN_NODE", telemetry, topology) is None

    empty_phases_topo = {
        "topology_id": "empty_phases",
        "nodes": [{"node_id": "N1", "approaches": [], "phases": []}]
    }
    assert fixed_ctrl.compute_command("N1", telemetry, empty_phases_topo) is None
    assert mp_ctrl.compute_command("N1", telemetry, empty_phases_topo) is None


def test_presslight_rl_controller_selection():
    topology = load_topology("four_intersection_v1")
    controller = PressLightRLController()

    telemetry_ns_heavy = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 100.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_EW",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 14, "occupancy_ratio": 0.7},
            {"approach_id": "J1_S_IN", "queue_vehicles": 12, "occupancy_ratio": 0.6},
            {"approach_id": "J1_E_IN", "queue_vehicles": 1, "occupancy_ratio": 0.05},
            {"approach_id": "J1_W_IN", "queue_vehicles": 1, "occupancy_ratio": 0.05}
        ]
    }

    cmd = controller.compute_command("J1", telemetry_ns_heavy, topology)
    assert cmd is not None
    assert cmd["node_id"] == "J1"
    assert cmd["target_phase_id"] == "J1_PHASE_NS"
    assert cmd["controller"] == "pressure_heuristic"
    validate_payload(cmd, "control_command")


def test_presslight_with_exported_weights(tmp_path):
    from src.rl.train_dqn import DQNAgent
    topology = load_topology("four_intersection_v1")
    weights_path = str(tmp_path / "weights.json")
    DQNAgent(12, 2, seed=7).save_weights(weights_path)
    
    controller = PressLightRLController(model_path=weights_path)
    
    telemetry = {
        "node_id": "J1",
        "source_type": "simulation",
        "simulation_time_s": 50.0,
        "timestamp_ms": 1727005820000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 5, "occupancy_ratio": 0.25},
            {"approach_id": "J1_S_IN", "queue_vehicles": 4, "occupancy_ratio": 0.2},
            {"approach_id": "J1_E_IN", "queue_vehicles": 2, "occupancy_ratio": 0.1},
            {"approach_id": "J1_W_IN", "queue_vehicles": 1, "occupancy_ratio": 0.05}
        ]
    }

    cmd = controller.compute_command("J1", telemetry, topology)
    assert cmd is not None
    assert cmd["node_id"] == "J1"
    assert cmd["target_phase_id"] in ["J1_PHASE_NS", "J1_PHASE_EW"]
    assert cmd["controller"] == "presslight_rl"
    validate_payload(cmd, "control_command")
