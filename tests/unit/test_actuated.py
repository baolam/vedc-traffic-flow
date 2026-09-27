"""
Unit tests for ActuatedController.

Verifies:
  1. Minimum green hold (does not switch before min_green_s).
  2. Green extension when queue/vehicles detected on current phase.
  3. Gap-out when current queue drops to 0 and passage time expires.
  4. Max-out when max_green_s is reached.
  5. Round-robin / conflicting demand selection.
"""

import pytest
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
for p in [repo_root / "services" / "graph-control",
          repo_root / "contracts"]:
    if str(p) not in sys.path and p.exists():
        sys.path.insert(0, str(p))

from controller import ActuatedController


@pytest.fixture
def topology():
    return {
        "nodes": [
            {
                "node_id": "J1",
                "phases": [
                    {
                        "phase_id": "P_NS",
                        "approaches": ["J1_N_IN", "J1_S_IN"],
                    },
                    {
                        "phase_id": "P_EW",
                        "approaches": ["J1_E_IN", "J1_W_IN"],
                    },
                ],
            }
        ]
    }


def test_actuated_holds_min_green(topology):
    ctrl = ActuatedController(min_green_s=10.0, max_green_s=30.0, passage_time_s=3.0)
    
    # At t=0, starts in P_NS
    tel = {
        "node_id": "J1",
        "current_phase_id": "P_NS",
        "simulation_time_s": 0.0,
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 0},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 5},
            {"approach_id": "J1_W_IN", "queue_vehicles": 5},
        ]
    }
    cmd = ctrl.compute_command("J1", tel, topology, current_time_s=0.0)
    assert cmd["target_phase_id"] == "P_NS"

    # At t=5 (below min_green 10s), even with heavy EW queue and 0 NS queue, holds min_green
    cmd = ctrl.compute_command("J1", tel, topology, current_time_s=5.0)
    assert cmd["target_phase_id"] == "P_NS"


def test_actuated_extends_green_with_queue(topology):
    ctrl = ActuatedController(min_green_s=10.0, max_green_s=30.0, passage_time_s=3.0)
    
    # t=0 init
    tel_0 = {
        "node_id": "J1",
        "current_phase_id": "P_NS",
        "simulation_time_s": 0.0,
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 4},
            {"approach_id": "J1_S_IN", "queue_vehicles": 3},
            {"approach_id": "J1_E_IN", "queue_vehicles": 2},
            {"approach_id": "J1_W_IN", "queue_vehicles": 2},
        ]
    }
    ctrl.compute_command("J1", tel_0, topology, current_time_s=0.0)

    # At t=12 (> min_green 10s), current NS approach still has queue -> extends green
    tel_12 = {
        "node_id": "J1",
        "current_phase_id": "P_NS",
        "simulation_time_s": 12.0,
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 3},
            {"approach_id": "J1_S_IN", "queue_vehicles": 2},
            {"approach_id": "J1_E_IN", "queue_vehicles": 4},
            {"approach_id": "J1_W_IN", "queue_vehicles": 4},
        ]
    }
    cmd = ctrl.compute_command("J1", tel_12, topology, current_time_s=12.0)
    assert cmd["target_phase_id"] == "P_NS"


def test_actuated_gaps_out_and_switches(topology):
    ctrl = ActuatedController(min_green_s=10.0, max_green_s=30.0, passage_time_s=3.0)
    
    # t=0 init
    tel = {
        "node_id": "J1",
        "current_phase_id": "P_NS",
        "simulation_time_s": 0.0,
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 2},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 5},
            {"approach_id": "J1_W_IN", "queue_vehicles": 5},
        ]
    }
    ctrl.compute_command("J1", tel, topology, current_time_s=0.0)

    # t=10: NS queue becomes 0
    tel_10 = {
        "node_id": "J1",
        "current_phase_id": "P_NS",
        "simulation_time_s": 10.0,
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 0},
            {"approach_id": "J1_S_IN", "queue_vehicles": 0},
            {"approach_id": "J1_E_IN", "queue_vehicles": 5},
            {"approach_id": "J1_W_IN", "queue_vehicles": 5},
        ]
    }
    ctrl.compute_command("J1", tel_10, topology, current_time_s=10.0)

    # t=14 (> 10 + passage_time 3s): gap-out triggers switch to P_EW (which has queue 5)
    cmd = ctrl.compute_command("J1", tel_10, topology, current_time_s=14.0)
    assert cmd["target_phase_id"] == "P_EW"
    assert cmd["controller"] == "actuated"


def test_actuated_forces_max_out(topology):
    ctrl = ActuatedController(min_green_s=10.0, max_green_s=25.0, passage_time_s=3.0)
    
    # t=0 init with continuous NS queue
    tel = {
        "node_id": "J1",
        "current_phase_id": "P_NS",
        "simulation_time_s": 0.0,
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 10},
            {"approach_id": "J1_S_IN", "queue_vehicles": 10},
            {"approach_id": "J1_E_IN", "queue_vehicles": 8},
            {"approach_id": "J1_W_IN", "queue_vehicles": 8},
        ]
    }
    ctrl.compute_command("J1", tel, topology, current_time_s=0.0)

    # t=20 (< max_green 25s): still in P_NS
    cmd = ctrl.compute_command("J1", tel, topology, current_time_s=20.0)
    assert cmd["target_phase_id"] == "P_NS"

    # t=26 (>= max_green 25s): forces switch to P_EW
    cmd = ctrl.compute_command("J1", tel, topology, current_time_s=26.0)
    assert cmd["target_phase_id"] == "P_EW"
