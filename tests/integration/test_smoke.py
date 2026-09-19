import sys
from pathlib import Path

# Add service paths to sys.path for integration testing
base_dir = Path(__file__).parents[2]
for svc in ["simulator", "graph-control", "actuator"]:
    svc_path = base_dir / "services" / svc
    if str(svc_path) not in sys.path:
        sys.path.insert(0, str(svc_path))

from simulator_contracts_helper import load_topology, validate_payload
from traffic_engine import TrafficEngine
from controller import MaxPressureController
from state_machine import ActuatorStateMachine

def test_full_pipeline_smoke():
    # 1. Load Topology & Setup Services
    topology = load_topology("four_intersection_v1")
    sim_engine = TrafficEngine(topology)
    controller = MaxPressureController()
    actuator = ActuatorStateMachine()

    # 2. Simulator generates telemetry for J1
    sim_engine.step(dt_s=1.0)
    telemetry = sim_engine.generate_telemetry("J1", sim_time_s=1.0)
    validate_payload(telemetry, "telemetry")
    assert telemetry["node_id"] == "J1"

    # 3. Controller computes ControlCommand based on telemetry
    command = controller.compute_command("J1", telemetry, topology)
    validate_payload(command, "control_command")
    assert command["node_id"] == "J1"

    # 4. Actuator processes ControlCommand
    ack = actuator.process_command(command, now=100.0)
    validate_payload(ack, "control_ack")
    assert ack["status"] in ["APPLIED", "REJECTED"]
    assert ack.get("target_phase_id") == command["target_phase_id"]

    # 5. If APPLIED, update simulator active phase
    if ack["status"] == "APPLIED":
        sim_engine.update_node_phase("J1", ack["target_phase_id"])
        next_telemetry = sim_engine.generate_telemetry("J1", sim_time_s=2.0)
        assert next_telemetry["current_phase_id"] == command["target_phase_id"]
