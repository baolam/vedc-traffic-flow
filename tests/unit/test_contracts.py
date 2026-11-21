import json
import os
import sys
from pathlib import Path

contracts_dir = Path(__file__).parents[2] / "contracts"
if str(contracts_dir) not in sys.path:
    sys.path.insert(0, str(contracts_dir))

import contracts_sdk

def test_list_and_load_all_topologies():
    topologies = contracts_sdk.list_topologies()
    assert "four_intersection_v1" in topologies
    assert "three_way_junction_v1" in topologies
    assert "multi_phase_v1" in topologies

    for topo_id in topologies:
        topo = contracts_sdk.load_topology(topo_id)
        assert topo["topology_id"] == topo_id
        # Verify every node phase explicitly specifies approaches
        for node in topo.get("nodes", []):
            assert "approaches" in node
            for phase in node.get("phases", []):
                assert "approaches" in phase
                assert isinstance(phase["approaches"], list)

def test_telemetry_fixture():
    fixture_file = Path(__file__).parents[1] / "fixtures" / "telemetry_j1_normal.json"
    assert fixture_file.exists()
    with open(fixture_file, "r") as f:
        data = json.load(f)
    assert data["node_id"] == "J1"
    assert data["source_type"] == "simulation"
    contracts_sdk.validate_payload(data, "telemetry")

def test_validate_payload_invalid():
    import pytest
    import jsonschema

    # Missing required field node_id
    invalid_telemetry = {
        "source_type": "simulation",
        "simulation_time_s": 10.0
    }
    with pytest.raises(jsonschema.ValidationError):
        contracts_sdk.validate_payload(invalid_telemetry, "telemetry")

def test_load_schema_and_topology_not_found():
    import pytest
    with pytest.raises(FileNotFoundError):
        contracts_sdk.load_schema("non_existent_schema")

    with pytest.raises(FileNotFoundError):
        contracts_sdk.load_topology("non_existent_topology")

def test_normalize_topology_phases_heuristics():
    raw_topology = {
        "topology_id": "test_heuristic_topo",
        "nodes": [
            {
                "node_id": "H1",
                "approaches": ["H1_N_IN", "H1_S_IN", "H1_E_IN", "H1_W_IN"],
                "phases": [
                    {"phase_id": "H1_PHASE_NS"},  # missing approaches -> should derive N and S
                    {"phase_id": "H1_PHASE_EW", "approaches": None},  # None approaches -> should derive E and W
                    {"phase_id": "H1_PHASE_CUSTOM"}  # custom phase -> fallback to all approaches
                ]
            }
        ]
    }
    normalized = contracts_sdk.normalize_topology_phases(raw_topology)
    node_phases = normalized["nodes"][0]["phases"]
    
    assert set(node_phases[0]["approaches"]) == {"H1_N_IN", "H1_S_IN"}
    assert set(node_phases[1]["approaches"]) == {"H1_E_IN", "H1_W_IN"}
    assert set(node_phases[2]["approaches"]) == {"H1_N_IN", "H1_S_IN", "H1_E_IN", "H1_W_IN"}

def test_get_topology_summary():
    summary = contracts_sdk.get_topology_summary("four_intersection_v1")
    assert summary["topology_id"] == "four_intersection_v1"
    assert summary["total_nodes"] == 4
    assert summary["total_edges"] >= 0
    assert summary["total_phases"] > 0

def test_oo_topology_contract():
    contract = contracts_sdk.load_topology_contract("four_intersection_v1")
    assert contract.topology_id == "four_intersection_v1"
    assert len(contract.nodes) == 4
    
    node_j1 = contract.get_node("J1")
    assert node_j1 is not None
    assert node_j1.node_id == "J1"
    assert len(node_j1.phases) > 0
    
    phase_ns = node_j1.get_phase("J1_PHASE_NS")
    assert phase_ns is not None
    assert "J1_N_IN" in phase_ns.approaches
    
    dict_back = contract.to_dict()
    assert dict_back["topology_id"] == "four_intersection_v1"

def test_one_word_topology_names_and_aliases():
    # 1-word topology names
    for name in ["corridor", "junction", "grid16", "cologne"]:
        topo = contracts_sdk.load_topology(name)
        assert topo["topology_id"] == name
        assert len(topo["nodes"]) > 0

    # Aliases
    assert contracts_sdk.resolve_topology_id("four_intersection_v1") == "corridor"
    assert contracts_sdk.resolve_topology_id("three_way_junction_v1") == "junction"
    assert contracts_sdk.resolve_topology_id("grid4x4") == "grid16"
    assert contracts_sdk.resolve_topology_id("cologne8") == "cologne"




def test_list_station_records():
    topologies = contracts_sdk.list_topologies()
    records = contracts_sdk.list_station_records()

    # Every registered topology is represented, and the total record count matches the sum
    # of each topology's own node count.
    assert set(r["topology_id"] for r in records) == set(topologies)
    expected_total = sum(len(contracts_sdk.load_topology(tid).get("nodes", [])) for tid in topologies)
    assert len(records) == expected_total

    # Purely simulated scenarios have no geo coordinates -- fields resolve to None, not absent.
    four_intersection = [r for r in records if r["topology_id"] == "four_intersection_v1"]
    assert len(four_intersection) == 4
    assert all(r["lat"] is None and r["lng"] is None for r in four_intersection)
    j1 = next(r for r in four_intersection if r["node_id"] == "J1")
    assert j1["name"] == "Intersection 1"
    assert j1["approach_count"] == 4
    assert j1["phase_count"] == 2

    # hcm_corridor has both geo coordinates and a SUMO node "type" (priority/traffic_light/...).
    hcm = [r for r in records if r["topology_id"] == "hcm_corridor"]
    assert len(hcm) == 50
    assert all(r["lat"] is not None and r["lng"] is not None for r in hcm)
    assert all(r["type"] is not None for r in hcm)

    # Scoping to one topology_id returns only that scenario's records.
    scoped = contracts_sdk.list_station_records("junction")
    assert len(scoped) == 1
    assert scoped[0]["topology_id"] == "junction"


def test_signal_fault_topics_and_schema():
    import topics
    import jsonschema
    import pytest

    # Verify topic builders and filters
    assert topics.SIGNAL_FAULT_PUB_PATTERN == "edgeflow/v1/signal_fault/{node_id}/{category}"
    assert topics.SIGNAL_FAULT_SUB_PATTERN == "edgeflow/v1/signal_fault/#"
    assert topics.get_signal_fault_topic("J1", "disconnect") == "edgeflow/v1/signal_fault/J1/disconnect"
    assert topics.get_signal_fault_topic("J1", "feedback_error") == "edgeflow/v1/signal_fault/J1/feedback_error"
    assert topics.get_signal_fault_topic("J1", "emergency") == "edgeflow/v1/signal_fault/J1/emergency"
    assert topics.get_signal_fault_topic("J1", "hardware") == "edgeflow/v1/signal_fault/J1/hardware"

    with pytest.raises(ValueError):
        topics.get_signal_fault_topic("J1", "invalid_cat")

    # Verify generic topic() helper
    assert topics.topic("signal_fault", "J1", category="emergency") == "edgeflow/v1/signal_fault/J1/emergency"

    # Verify schema validation
    valid_event = {
        "event_id": "evt-1234",
        "node_id": "J1",
        "category": "emergency",
        "fault_code": "ERR_SAFE_STOP_ENGAGED",
        "severity": "CRITICAL",
        "current_phase": "J1_PHASE_NS",
        "clearance_state": "FLASHING_YELLOW",
        "reason": "Physical safe-stop button pressed by user",
        "details": {"gpio": 16, "raw_level": 0},
        "timestamp_ms": 1700000000000
    }
    contracts_sdk.validate_payload(valid_event, "signal_fault_event")

    # Invalid event missing category
    invalid_event = {
        "event_id": "evt-1234",
        "node_id": "J1",
        "fault_code": "ERR_SAFE_STOP_ENGAGED",
        "severity": "CRITICAL",
        "timestamp_ms": 1700000000000
    }
    with pytest.raises(jsonschema.ValidationError):
        contracts_sdk.validate_payload(invalid_event, "signal_fault_event")
