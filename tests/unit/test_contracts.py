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
