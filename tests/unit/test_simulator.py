import sys
from pathlib import Path

# Add services/simulator to sys.path for test imports
simulator_dir = Path(__file__).parents[2] / "services" / "simulator"
if str(simulator_dir) not in sys.path:
    sys.path.insert(0, str(simulator_dir))

import pytest
from simulator_contracts_helper import load_topology, validate_payload
from traffic_engine import TrafficEngine, create_traffic_engine

def test_load_topology():
    topology = load_topology("four_intersection_v1")
    assert topology["topology_id"] == "four_intersection_v1"
    assert len(topology["nodes"]) == 4

def test_traffic_engine_init():
    topology = load_topology("four_intersection_v1")
    engine = TrafficEngine(topology)
    assert len(engine.nodes) == 4
    assert "J1" in engine.nodes
    assert engine.nodes["J1"].current_phase_id == "J1_PHASE_NS"

def test_traffic_engine_step():
    topology = load_topology("four_intersection_v1")
    engine = TrafficEngine(topology)
    initial_q_ns = engine.nodes["J1"].approaches["J1_N_IN"].queue_vehicles
    
    # Step engine
    engine.step(dt_s=2.0)
    
    # Check that state updated
    q_ns = engine.nodes["J1"].approaches["J1_N_IN"].queue_vehicles
    assert q_ns >= 0.0

def test_traffic_engine_phase_update():
    topology = load_topology("four_intersection_v1")
    engine = TrafficEngine(topology)
    
    engine.update_node_phase("J1", "J1_PHASE_EW")
    assert engine.nodes["J1"].current_phase_id == "J1_PHASE_EW"

def test_telemetry_schema_validation():
    topology = load_topology("four_intersection_v1")
    engine = TrafficEngine(topology)
    
    telemetry = engine.generate_telemetry("J1", sim_time_s=15.5)
    assert telemetry["node_id"] == "J1"
    assert telemetry["source_type"] == "simulation"
    assert telemetry["simulation_time_s"] == 15.5
    assert len(telemetry["approaches"]) == 4
    
    # Schema validation against contracts/schemas/telemetry.json
    validate_payload(telemetry, "telemetry")

def test_sumo_engine_fallback():
    topology = load_topology("four_intersection_v1")
    # Instantiating with use_sumo=True should either use SUMO or fallback gracefully to synthetic
    engine = TrafficEngine(topology, use_sumo=True)
    telemetry = engine.generate_telemetry("J1", sim_time_s=10.0)
    assert telemetry["node_id"] == "J1"
    assert telemetry["source_type"] == "simulation"
    validate_payload(telemetry, "telemetry")

def test_sumo_configs_existence():
    sumo_config_dir = Path(__file__).parents[2] / "services" / "simulator" / "sumo_configs"
    assert (sumo_config_dir / "four_intersection_v1.sumocfg").exists()
    assert (sumo_config_dir / "four_intersection_v1.net.xml").exists()
    assert (sumo_config_dir / "four_intersection_v1.rou.xml").exists()

def test_sumo_engine_node_initialization():
    topology = load_topology("four_intersection_v1")
    try:
        from sumo_engine import SumoTrafficEngine, TRACI_AVAILABLE
        if TRACI_AVAILABLE:
            # Check node configuration mapping
            dummy_engine = SumoTrafficEngine.__new__(SumoTrafficEngine)
            dummy_engine.topology = topology
            dummy_engine.nodes = {}
            dummy_engine.traffic_light_ids = {"J1", "J2"}
            dummy_engine.edge_ids = set()
            dummy_engine.is_connected = True
            dummy_engine._init_nodes()
            assert len(dummy_engine.nodes) == 4
            assert "J1" in dummy_engine.nodes
            assert dummy_engine.nodes["J1"]["current_phase_id"] == "J1_PHASE_NS"

            # Test updating phase for unsignalized node not in traffic_light_ids does not raise or invoke setPhase
            dummy_engine.update_node_phase("J3", "J3_PHASE_EW")
            assert dummy_engine.nodes["J3"]["current_phase_id"] == "J3_PHASE_EW"
    except ImportError:
        pytest.skip("SUMO module not available in environment")

