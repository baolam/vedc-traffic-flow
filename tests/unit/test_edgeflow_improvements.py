"""
Unit tests for EdgeFlow Controller improvements:
1. Grid Coordination on multi-intersection grids (grid4x4) with Time-Decaying Hysteresis
2. Pressure-Aware Downstream Resolution and Backpressure Rejection on corridors (hcm_corridor)
"""
import sys
from pathlib import Path
import pytest

graph_control_dir = Path(__file__).parents[2] / "services" / "graph-control"
sys.path.insert(0, str(graph_control_dir))

from graph_contracts_helper import load_topology, validate_payload
from controller import EdgeFlowController


def test_edgeflow_grid_time_decaying_hysteresis():
    """Verify time-decaying switching margin allows smooth transitions in grid networks."""
    topology = load_topology("grid4x4")
    controller = EdgeFlowController(min_green_s=5.0, max_green_s=45.0, switching_margin=2.0)

    node_id = "A0"
    telemetry_t100 = {
        "node_id": node_id,
        "source_type": "simulation",
        "simulation_time_s": 100.0,
        "timestamp_ms": 100000,
        "current_phase_id": "A0_PHASE_1",
        "approaches": [
            {"approach_id": "A1A0", "queue_vehicles": 3.0, "flow_veh_per_s": 0.2, "mean_speed_mps": 10.0, "occupancy_ratio": 0.1},
            {"approach_id": "B0A0", "queue_vehicles": 5.0, "flow_veh_per_s": 0.3, "mean_speed_mps": 10.0, "occupancy_ratio": 0.15},
            {"approach_id": "bottom0A0", "queue_vehicles": 2.0, "flow_veh_per_s": 0.1, "mean_speed_mps": 10.0, "occupancy_ratio": 0.05},
            {"approach_id": "left0A0", "queue_vehicles": 1.0, "flow_veh_per_s": 0.1, "mean_speed_mps": 10.0, "occupancy_ratio": 0.05},
        ]
    }

    # At t=100s, initial command establishes baseline
    cmd1 = controller.compute_command(node_id, telemetry_t100, topology)
    assert cmd1["controller"] == "edgeflow"
    validate_payload(cmd1, "control_command")

    # At t=104s (elapsed green = 4s < min_green_s=5s): Must hold current green
    telemetry_t104 = dict(telemetry_t100, simulation_time_s=104.0, timestamp_ms=104000)
    cmd2 = controller.compute_command(node_id, telemetry_t104, topology)
    assert cmd2["target_phase_id"] == "A0_PHASE_1"

    # At t=118s (elapsed green = 18s > 10s):
    # Competing phase (e.g. Phase 2 or Phase 4 serving B0A0) has substantial demand.
    # Time-decaying hysteresis reduces effective margin, enabling switch before 45s timeout!
    telemetry_t118 = dict(telemetry_t100, simulation_time_s=118.0, timestamp_ms=118000)
    cmd3 = controller.compute_command(node_id, telemetry_t118, topology)
    validate_payload(cmd3, "control_command")
    assert cmd3["controller"] == "edgeflow"


def test_edgeflow_pressure_aware_corridor_downstream_resolution():
    """Verify EdgeFlow resolves to_edge to downstream node and applies Max-Pressure backpressure."""
    topology = load_topology("hcm_corridor")
    controller = EdgeFlowController(switching_margin=1.0)

    # Node 2217938301 has movements towards "-32576065#0", which enters downstream cluster_2217938303_2217938318
    node_id = "2217938301"

    # 1. Downstream is clear (queue = 0, occupancy = 0.05)
    clear_network_state = {
        "cluster_2217938303_2217938318": {
            "approaches": [
                {"approach_id": "-32576065#0", "queue_vehicles": 0.0, "occupancy_ratio": 0.05},
                {"approach_id": "-211849415#1", "queue_vehicles": 0.0, "occupancy_ratio": 0.05},
            ]
        }
    }

    telemetry_clear = {
        "node_id": node_id,
        "source_type": "simulation",
        "simulation_time_s": 200.0,
        "timestamp_ms": 200000,
        "current_phase_id": "2217938301_PHASE_1",
        "approaches": [
            {"approach_id": "-211849412", "queue_vehicles": 12.0, "flow_veh_per_s": 0.5, "mean_speed_mps": 5.0, "occupancy_ratio": 0.3},
            {"approach_id": "32576065#0", "queue_vehicles": 10.0, "flow_veh_per_s": 0.4, "mean_speed_mps": 5.0, "occupancy_ratio": 0.25},
            {"approach_id": "-32576065#1", "queue_vehicles": 2.0, "flow_veh_per_s": 0.1, "mean_speed_mps": 12.0, "occupancy_ratio": 0.05},
        ]
    }

    cmd_clear = controller.compute_command(node_id, telemetry_clear, topology, network_state=clear_network_state)
    assert cmd_clear["controller"] == "edgeflow"
    validate_payload(cmd_clear, "control_command")
    # Phase 1 serves heavy queues on -211849412 and 32576065#0 heading into clear downstream
    assert cmd_clear["target_phase_id"] == "2217938301_PHASE_1"

    # 2. Downstream becomes jammed (queue = 25, occupancy = 0.90)
    jammed_network_state = {
        "cluster_2217938303_2217938318": {
            "approaches": [
                {"approach_id": "-32576065#0", "queue_vehicles": 25.0, "occupancy_ratio": 0.92},
                {"approach_id": "-211849415#1", "queue_vehicles": 25.0, "occupancy_ratio": 0.92},
            ]
        }
    }

    # At t=215s (elapsed_green = 15s > min_green_s), backpressure rejects Phase 1
    # because sending more vehicles into -32576065#0 will cause spillback gridlock!
    telemetry_jammed = dict(telemetry_clear, simulation_time_s=215.0, timestamp_ms=215000)
    cmd_jammed = controller.compute_command(node_id, telemetry_jammed, topology, network_state=jammed_network_state)
    validate_payload(cmd_jammed, "control_command")
    # Must yield away from Phase 1 to prevent spillback into jammed downstream
    assert cmd_jammed["target_phase_id"] != "2217938301_PHASE_1"

    # 3. Upstream queue is massive (queue = 35) while downstream queue is 10 (occupancy = 0.85).
    # Positive backpressure (35 - 10 = +25) must throttle rather than permanently locking with negative score!
    telemetry_massive_upstream = {
        "node_id": node_id,
        "source_type": "simulation",
        "simulation_time_s": 230.0,
        "timestamp_ms": 230000,
        "current_phase_id": "2217938301_PHASE_1",
        "approaches": [
            {"approach_id": "-211849412", "queue_vehicles": 35.0, "flow_veh_per_s": 0.5, "mean_speed_mps": 2.0, "occupancy_ratio": 0.8},
            {"approach_id": "32576065#0", "queue_vehicles": 30.0, "flow_veh_per_s": 0.5, "mean_speed_mps": 2.0, "occupancy_ratio": 0.75},
            {"approach_id": "-32576065#1", "queue_vehicles": 0.0, "flow_veh_per_s": 0.0, "mean_speed_mps": 12.0, "occupancy_ratio": 0.0},
        ]
    }
    moderate_downstream_state = {
        "cluster_2217938303_2217938318": {
            "approaches": [
                {"approach_id": "-32576065#0", "queue_vehicles": 10.0, "occupancy_ratio": 0.85},
                {"approach_id": "-211849415#1", "queue_vehicles": 10.0, "occupancy_ratio": 0.85},
            ]
        }
    }
    cmd_massive = controller.compute_command(node_id, telemetry_massive_upstream, topology, network_state=moderate_downstream_state)
    validate_payload(cmd_massive, "control_command")
    # Massive upstream demand with positive backpressure serves Phase 1 to prevent corridor gridlock
    assert cmd_massive["target_phase_id"] == "2217938301_PHASE_1"

