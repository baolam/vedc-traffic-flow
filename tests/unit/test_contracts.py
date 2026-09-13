import json
import os
from pathlib import Path

def test_load_topology():
    topology_file = Path(__file__).parents[2] / "contracts" / "topology" / "four_intersection_v1.json"
    assert topology_file.exists()
    with open(topology_file, "r") as f:
        data = json.load(f)
    assert data["topology_id"] == "four_intersection_v1"
    assert len(data["nodes"]) == 4

def test_telemetry_fixture():
    fixture_file = Path(__file__).parents[1] / "fixtures" / "telemetry_j1_normal.json"
    assert fixture_file.exists()
    with open(fixture_file, "r") as f:
        data = json.load(f)
    assert data["node_id"] == "J1"
    assert data["source_type"] == "simulation"
