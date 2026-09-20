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

