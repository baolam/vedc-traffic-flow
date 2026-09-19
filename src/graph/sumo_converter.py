import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List

class SumoNetworkConverter:
    """
    Converter that parses SUMO network (.net.xml) or dictionary representations
    and generates EdgeFlow AI canonical Topology JSON contracts.
    Enforces explicit 'approaches' for every traffic phase.
    """

    @staticmethod
    def parse_net_xml(xml_content: str, topology_id: str = "sumo_converted_v1") -> Dict[str, Any]:
        """Parse raw SUMO .net.xml content into canonical topology contract."""
        root = ET.fromstring(xml_content)
        
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        
        # 1. Parse Junctions (Traffic Lights)
        for junc in root.findall("junction"):
            j_id = junc.attrib.get("id")
            j_type = junc.attrib.get("type", "")
            if not j_id or j_id.startswith(":"):
                continue  # skip internal SUMO junctions
                
            inc_lanes = junc.attrib.get("incLanes", "").split()
            # Convert incoming lanes to edge approach IDs
            approaches = list(set([lane.rsplit("_", 1)[0] for lane in inc_lanes if lane]))
            
            nodes_dict[j_id] = {
                "node_id": j_id,
                "name": f"SUMO Junction {j_id}",
                "type": j_type,
                "approaches": sorted(approaches) if approaches else [f"{j_id}_APP_1", f"{j_id}_APP_2"],
                "phases": []
            }

        # 2. Parse Traffic Light Logic (tlsLogic)
        for tl in root.findall("tlLogic"):
            tl_id = tl.attrib.get("id")
            if tl_id in nodes_dict:
                node = nodes_dict[tl_id]
                node_approaches = node["approaches"]
                
                phase_idx = 1
                for p in tl.findall("phase"):
                    state = p.attrib.get("state", "")
                    # Filter out yellow/red phases if state contains 'G' or 'g'
                    if "G" in state or "g" in state or not node["phases"]:
                        # Map green light indexes in state string to node approaches
                        active_apps = []
                        num_apps = len(node_approaches)
                        if num_apps > 0:
                            for idx, char in enumerate(state):
                                if char in ("G", "g"):
                                    app_target = node_approaches[idx % num_apps]
                                    if app_target not in active_apps:
                                        active_apps.append(app_target)
                        
                        if not active_apps and node_approaches:
                            active_apps = [node_approaches[(phase_idx - 1) % num_apps]]

                        node["phases"].append({
                            "phase_id": f"{tl_id}_PHASE_{phase_idx}",
                            "name": f"Phase {phase_idx} ({state})",
                            "approaches": active_apps
                        })
                        phase_idx += 1

        # Fallback for nodes without explicit tlsLogic in XML
        for n_id, node in nodes_dict.items():
            if not node["phases"]:
                apps = node["approaches"]
                half = max(1, len(apps) // 2)
                node["phases"] = [
                    {
                        "phase_id": f"{n_id}_PHASE_1",
                        "name": "Phase 1 Green",
                        "approaches": apps[:half]
                    },
                    {
                        "phase_id": f"{n_id}_PHASE_2",
                        "name": "Phase 2 Green",
                        "approaches": apps[half:] if len(apps) > half else apps
                    }
                ]

        # 3. Parse Edges
        edges = []
        for edge in root.findall("edge"):
            e_id = edge.attrib.get("id")
            src = edge.attrib.get("from")
            dst = edge.attrib.get("to")
            if e_id and src and dst and not e_id.startswith(":"):
                edges.append({
                    "edge_id": e_id,
                    "source": src,
                    "target": dst
                })

        return {
          "topology_id": topology_id,
          "version": "1.0",
          "nodes": list(nodes_dict.values()),
          "edges": edges
        }

    @staticmethod
    def dict_to_topology(graph_data: Dict[str, Any], topology_id: str = "custom_graph_v1") -> Dict[str, Any]:
        """Convert a simplified Network / Dictionary graph into canonical topology contract."""
        nodes = []
        for n in graph_data.get("nodes", []):
            node_id = n["node_id"]
            approaches = n.get("approaches", [f"{node_id}_IN_1", f"{node_id}_IN_2"])
            phases = []
            for idx, p in enumerate(n.get("phases", [])):
                p_approaches = p.get("approaches", approaches[:1])
                phases.append({
                    "phase_id": p.get("phase_id", f"{node_id}_PHASE_{idx+1}"),
                    "name": p.get("name", f"Phase {idx+1}"),
                    "approaches": p_approaches
                })
            if not phases:
                phases = [{
                    "phase_id": f"{node_id}_PHASE_1",
                    "name": "Phase 1",
                    "approaches": approaches
                }]
            nodes.append({
                "node_id": node_id,
                "name": n.get("name", f"Node {node_id}"),
                "approaches": approaches,
                "phases": phases
            })
            
        return {
            "topology_id": topology_id,
            "version": "1.0",
            "nodes": nodes,
            "edges": graph_data.get("edges", [])
        }
