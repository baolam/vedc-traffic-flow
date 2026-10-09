"""Generate the straight-through four-junction research network and mapping."""
import argparse
import json
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

from contracts.research import TOPOLOGY_ID

ROOT = Path(__file__).resolve().parents[2]
NETWORK_DIR = ROOT / "networks" / TOPOLOGY_ID


def binary(name):
    import shutil
    import sumolib
    candidate = shutil.which(name)
    if candidate:
        return candidate
    import sumo
    path = Path(sumo.__file__).parent / "bin" / (name + (".exe" if __import__('os').name == 'nt' else ''))
    return str(path) if path.exists() else sumolib.checkBinary(name)


def write_xml(root, path):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def build():
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    coords = {"J1": (100, 300), "J2": (300, 300), "J3": (100, 100), "J4": (300, 100)}
    adjacent = {"J1": {"S": "J3", "E": "J2"}, "J2": {"S": "J4", "W": "J1"},
                "J3": {"N": "J1", "E": "J4"}, "J4": {"N": "J2", "W": "J3"}}
    vectors = {"N": (0, 200), "S": (0, -200), "E": (200, 0), "W": (-200, 0)}
    opposite = dict(zip("NSEW", "SNWE"))
    nodes, edges, connections = ET.Element("nodes"), ET.Element("edges"), ET.Element("connections")
    topology = {"topology_id": TOPOLOGY_ID, "version": "1.0", "nodes": [], "edges": [], "routes": []}
    for nid, (x, y) in coords.items():
        ET.SubElement(nodes, "node", id=nid, x=str(x), y=str(y), type="traffic_light")
        node = {"node_id": nid, "approaches": [f"{nid}_{d}_IN" for d in "NSEW"], "phases": []}
        for d, (dx, dy) in vectors.items():
            origin = adjacent[nid].get(d, f"{nid}_{d}_BOUNDARY")
            if d not in adjacent[nid]:
                ET.SubElement(nodes, "node", id=origin, x=str(x+dx), y=str(y+dy), type="priority")
                ET.SubElement(edges, "edge", id=f"{nid}_{d}_OUT", **{"from": nid, "to": origin,
                              "numLanes": "1", "speed": "13.89"})
            ET.SubElement(edges, "edge", id=f"{nid}_{d}_IN", **{"from": origin, "to": nid,
                          "numLanes": "1", "speed": "13.89"})
        for axis in ("NS", "EW"):
            phase = {"phase_id": f"{nid}_PHASE_{axis}", "approaches": [], "movements": []}
            for d in axis:
                app = f"{nid}_{d}_IN"
                target = adjacent[nid].get(opposite[d])
                out = f"{target}_{d}_IN" if target else f"{nid}_{opposite[d]}_OUT"
                phase["approaches"].append(app)
                phase["movements"].append({"from_approach": app, "to_edge": out, "to_node": target,
                                            "to_approach": out if target else None,
                                            "turn_ratio": 1.0, "capacity_vehicles": 20})
                ET.SubElement(connections, "connection", **{"from": app, "to": out, "fromLane": "0", "toLane": "0"})
                if d not in adjacent[nid]:
                    topology["routes"].append({"route_id": app, "origin": nid, "axis": axis,
                                              "edges": [app, out, f"{target}_{opposite[d]}_OUT"]})
            node["phases"].append(phase)
        topology["nodes"].append(node)
    for element, name in ((nodes, "nodes.nod.xml"), (edges, "edges.edg.xml"), (connections, "connections.con.xml")):
        write_xml(element, NETWORK_DIR / name)
    net = NETWORK_DIR / "network.net.xml"
    subprocess.run([binary("netconvert"), "--node-files", str(NETWORK_DIR / "nodes.nod.xml"),
                    "--edge-files", str(NETWORK_DIR / "edges.edg.xml"), "--connection-files",
                    str(NETWORK_DIR / "connections.con.xml"), "--output-file", str(net),
                    "--no-turnarounds", "true"], check=True, capture_output=True)
    generated = ET.parse(net).getroot()
    for node in topology["nodes"]:
        links = [c for c in generated.findall("connection") if c.get("tl") == node["node_id"]]
        node["sumo_links"] = [{"index": int(c.get("linkIndex")), "from": c.get("from"), "to": c.get("to")} for c in links]
        for phase in node["phases"]:
            state = ["r"] * len(links)
            for link in node["sumo_links"]:
                if link["from"] in phase["approaches"]:
                    state[link["index"]] = "G"
            phase["sumo_state"] = "".join(state)
    topology["edges"] = [{"edge_id": e.get("id"), "from_node": e.get("from"), "to_node": e.get("to")} for e in edges]
    (ROOT / "contracts" / "topology" / f"{TOPOLOGY_ID}.json").write_text(json.dumps(topology, indent=2) + "\n")
    return net


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(build())
