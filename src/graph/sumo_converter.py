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

        # 2. Parse Connections to map linkIndex to from_edge and to_edge
        tl_connections: Dict[str, Dict[int, Dict[str, Any]]] = {}
        for conn in root.findall("connection"):
            tl_id = conn.attrib.get("tl")
            link_idx_str = conn.attrib.get("linkIndex")
            from_edge = conn.attrib.get("from")
            to_edge = conn.attrib.get("to")
            
            if tl_id and link_idx_str is not None and from_edge:
                try:
                    link_idx = int(link_idx_str)
                    if tl_id not in tl_connections:
                        tl_connections[tl_id] = {}
                    tl_connections[tl_id][link_idx] = {
                        "from_edge": from_edge,
                        "to_edge": to_edge
                    }
                except ValueError:
                    pass

        # 3. Parse Traffic Light Logic (tlsLogic)
        for tl in root.findall("tlLogic"):
            tl_id = tl.attrib.get("id")
            if tl_id in nodes_dict:
                node = nodes_dict[tl_id]
                node_approaches = node["approaches"]
                conns = tl_connections.get(tl_id, {})
                
                phase_idx = 1
                for raw_sumo_phase_idx, p in enumerate(tl.findall("phase")):
                    state = p.attrib.get("state", "")
                    # Filter out yellow/red phases if state contains 'G' or 'g'
                    if "G" in state or "g" in state or not node["phases"]:
                        active_apps = []
                        movements = []
                        
                        for idx, char in enumerate(state):
                            if char in ("G", "g"):
                                if idx in conns:
                                    app_target = conns[idx]["from_edge"]
                                    to_e = conns[idx]["to_edge"]
                                    if app_target not in active_apps:
                                        active_apps.append(app_target)
                                    movements.append({
                                        "from_approach": app_target,
                                        "to_edge": to_e,
                                        "link_index": idx
                                    })
                                elif len(node_approaches) > 0:
                                    app_target = node_approaches[idx % len(node_approaches)]
                                    if app_target not in active_apps:
                                        active_apps.append(app_target)
                        
                        if not active_apps and node_approaches:
                            active_apps = [node_approaches[(phase_idx - 1) % len(node_approaches)]]

                        phase_dict = {
                            "phase_id": f"{tl_id}_PHASE_{phase_idx}",
                            "name": f"Phase {phase_idx} ({state})",
                            "approaches": active_apps,
                            "sumo_phase_index": raw_sumo_phase_idx
                        }
                        if movements:
                            phase_dict["movements"] = movements

                        node["phases"].append(phase_dict)
                        phase_idx += 1

        # Fallback for traffic light nodes without explicit tlsLogic in XML
        for n_id, node in nodes_dict.items():
            if not node["phases"] and node.get("type", "").startswith("traffic_light"):
                apps = node["approaches"]
                half = max(1, len(apps) // 2)
                node["phases"] = [
                    {
                        "phase_id": f"{n_id}_PHASE_1",
                        "name": "Phase 1 Green",
                        "approaches": apps[:half],
                        "sumo_phase_index": 0
                    },
                    {
                        "phase_id": f"{n_id}_PHASE_2",
                        "name": "Phase 2 Green",
                        "approaches": apps[half:] if len(apps) > half else apps,
                        "sumo_phase_index": 2 if len(apps) > 2 else 1
                    }
                ]

        # 4. Parse Edges
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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert SUMO .net.xml network into canonical EdgeFlow AI topology contract JSON.")
    parser.add_argument("--input", "-i", required=True, help="Path to input SUMO .net.xml file")
    parser.add_argument("--output", "-o", required=True, help="Path to output JSON topology file")
    parser.add_argument("--topology-id", default="sumo_converted_v1", help="Topology contract ID")

    args = parser.parse_args()
    with open(args.input, "r", encoding="utf-8") as f:
        xml_content = f.read()

    topology = SumoNetworkConverter.parse_net_xml(xml_content, topology_id=args.topology_id)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(topology, f, indent=2, ensure_ascii=False)
    print(f"Successfully converted {args.input} -> {args.output} (topology_id: {args.topology_id})")
