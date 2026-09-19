import sys
from pathlib import Path

# Add src/graph to sys.path
src_graph_dir = Path(__file__).parents[2] / "src" / "graph"
if str(src_graph_dir) not in sys.path:
    sys.path.insert(0, str(src_graph_dir))

from sumo_converter import SumoNetworkConverter

SAMPLE_SUMO_NET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<net version="1.16">
    <junction id="J1" type="traffic_light" incLanes="edge_N_0 edge_S_0 edge_E_0 edge_W_0">
    </junction>
    <tlLogic id="J1" type="static" programID="0" offset="0">
        <phase duration="30" state="GGrrGGrr"/>
        <phase duration="30" state="rrGGrrGG"/>
    </tlLogic>
    <edge id="edge_N" from="N_NODE" to="J1"/>
    <edge id="edge_S" from="S_NODE" to="J1"/>
    <edge id="edge_E" from="E_NODE" to="J1"/>
    <edge id="edge_W" from="W_NODE" to="J1"/>
</net>
"""

def test_sumo_net_xml_conversion():
    topology = SumoNetworkConverter.parse_net_xml(SAMPLE_SUMO_NET_XML, topology_id="converted_test_net")
    assert topology["topology_id"] == "converted_test_net"
    assert len(topology["nodes"]) == 1
    
    node = topology["nodes"][0]
    assert node["node_id"] == "J1"
    assert len(node["approaches"]) == 4
    assert len(node["phases"]) == 2
    
    # Enforce that every phase explicitly defines approaches
    for phase in node["phases"]:
        assert "approaches" in phase
        assert isinstance(phase["approaches"], list)
        assert len(phase["approaches"]) > 0

def test_dict_to_topology_conversion():
    graph_dict = {
        "nodes": [
            {
                "node_id": "T1",
                "approaches": ["APP_A", "APP_B", "APP_C"],
                "phases": [
                    {"phase_id": "P1", "name": "Phase 1", "approaches": ["APP_A", "APP_B"]},
                    {"phase_id": "P2", "name": "Phase 2", "approaches": ["APP_C"]}
                ]
            }
        ]
    }
    topology = SumoNetworkConverter.dict_to_topology(graph_dict, topology_id="dict_converted_v1")
    assert topology["topology_id"] == "dict_converted_v1"
    assert len(topology["nodes"][0]["phases"]) == 2
    assert topology["nodes"][0]["phases"][0]["approaches"] == ["APP_A", "APP_B"]
    assert topology["nodes"][0]["phases"][1]["approaches"] == ["APP_C"]
