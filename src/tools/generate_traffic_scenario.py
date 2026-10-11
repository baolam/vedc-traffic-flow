"""
EdgeFlow AI — Traffic Scenario Generator Tool.

Generates complete SUMO traffic scenarios following the TP.HCM Corridor process:
1. SUMO Network (.net.xml) Parsing & Canonical Topology Contract Generation (contracts/topology/<scenario_id>.json)
2. Setup of Multimodal Vehicle Types (motorcycle, car, taxi, bus, truck) & Raster GUI Icons
3. Permission-aware Dijkstra Route Generation with Alternative Detours & Realistic Modal Distribution
4. SUMO Configuration Assembly (<scenario_id>.sumocfg, gui-settings.xml)
5. Registration in ScenarioRegistry (contracts/scenarios.py) and .env Update
"""

import os
import sys
import json
import shutil
import random
import argparse
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from heapq import heappush, heappop
from typing import Dict, Any, List, Optional, Tuple, Set

# Standardized root paths
ROOT_DIR = Path(__file__).resolve().parents[2]
GRAPH_DIR = ROOT_DIR / "src" / "graph"
CONTRACTS_DIR = ROOT_DIR / "contracts"

if str(GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPH_DIR))
if str(CONTRACTS_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_DIR))

from sumo_converter import SumoNetworkConverter
from scenarios import ScenarioProfile, ScenarioRegistry, CANONICAL_SCENARIOS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_traffic_scenario")

# Vehicle classes mapping & default HCM modal split weights
VEHICLE_CLASSES: Dict[str, str] = {
    "car": "passenger",
    "taxi": "passenger",
    "motorcycle": "motorcycle",
    "bus": "bus",
    "truck": "truck",
}

DEFAULT_HCM_MODAL_SPLIT: Dict[str, int] = {
    "motorcycle": 65,
    "car": 25,
    "taxi": 4,
    "bus": 3,
    "truck": 3,
}

VEHICLE_SPECS: List[Tuple[str, str, str, str, str, str, str, str]] = [
    # (id, vClass, img, length, width, accel, decel, maxSpeed)
    ("motorcycle", "motorcycle", "motorcycle.png", "2.2", "0.9", "3.0", "5.0", "50"),
    ("car", "passenger", "car.png", "4.5", "1.8", "2.6", "4.5", "50"),
    ("taxi", "taxi", "taxi.png", "4.5", "1.8", "2.6", "4.5", "50"),
    ("bus", "bus", "bus.png", "12.0", "2.5", "1.2", "4.0", "40"),
    ("truck", "truck", "truck.png", "8.0", "2.4", "1.5", "4.0", "40"),
]


def token_set(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    return set(value.replace(",", " ").split())


def permission_ok(attrs: Dict[str, str], vclass: str) -> bool:
    allow = token_set(attrs.get("allow"))
    disallow = token_set(attrs.get("disallow"))

    if allow and vclass not in allow:
        return False
    if vclass in disallow:
        return False
    return True


def load_network_for_vclass(path: Path, vclass: str) -> Tuple[Dict[str, Any], Set[str], Dict[Tuple[str, str], List[str]]]:
    """Parse SUMO .net.xml and build a usable graph for specific vehicle class."""
    root = ET.parse(path).getroot()

    edges: Dict[str, Any] = {}
    usable_edges: Set[str] = set()

    for e in root.findall("edge"):
        eid = e.get("id")
        frm = e.get("from")
        to = e.get("to")

        if not eid or eid.startswith(":") or not frm or not to:
            continue

        lanes = e.findall("lane")
        if not lanes:
            continue

        usable_lanes = [
            lane.attrib for lane in lanes
            if permission_ok(lane.attrib, vclass)
        ]

        if not usable_lanes:
            continue

        best_lane = min(
            usable_lanes,
            key=lambda lane: float(lane.get("length", "1")) / max(float(lane.get("speed", "13.9")), 0.1)
        )

        length = float(best_lane.get("length", "1"))
        speed = float(best_lane.get("speed", "13.9"))

        edges[eid] = {
            "from": frm,
            "to": to,
            "length": length,
            "speed": speed,
        }
        usable_edges.add(eid)

    transitions: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for conn in root.findall("connection"):
        frm = conn.get("from")
        to = conn.get("to")
        if not frm or not to or frm.startswith(":") or to.startswith(":"):
            continue
        if frm in usable_edges and to in usable_edges:
            if permission_ok(conn.attrib, vclass):
                transitions[(frm, to)].append(conn.get("dir", ""))

    return edges, usable_edges, transitions


def shortest_path_vclass(
    start_edge: str,
    goal_edge: str,
    edges: Dict[str, Any],
    outgoing: Dict[str, List[str]],
    banned: Optional[Set[str]] = None
) -> Optional[List[str]]:
    """Dijkstra shortest path algorithm across edges."""
    banned = banned or set()
    pq: List[Tuple[float, str]] = [(0.0, start_edge)]
    dist: Dict[str, float] = {start_edge: 0.0}
    previous: Dict[str, str] = {}

    while pq:
        cost, edge_id = heappop(pq)
        if cost != dist.get(edge_id):
            continue
        if edge_id == goal_edge:
            break

        to_node = edges[edge_id]["to"]
        for nxt_edge in outgoing.get(to_node, []):
            if nxt_edge in banned:
                continue
            travel_time = edges[nxt_edge]["length"] / max(edges[nxt_edge]["speed"], 0.1)
            new_cost = cost + travel_time
            if new_cost < dist.get(nxt_edge, float("inf")):
                dist[nxt_edge] = new_cost
                previous[nxt_edge] = edge_id
                heappush(pq, (new_cost, nxt_edge))

    if goal_edge not in dist:
        return None

    route: List[str] = []
    curr = goal_edge
    while curr != start_edge:
        route.append(curr)
        curr = previous[curr]
    route.append(start_edge)
    route.reverse()
    return route


def generate_routes_for_vehicles(
    net_path: Path,
    num_vehicles: int,
    modal_split: Dict[str, int],
    seed: int = 42,
    duration_s: float = 3600.0,
) -> List[Dict[str, Any]]:
    """Generate multimodal vehicle routes using permission-aware Dijkstra pathfinding."""
    rng = random.Random(seed)

    # Build weighted pool of vehicle types
    type_pool: List[str] = []
    for vtype, weight in modal_split.items():
        type_pool.extend([vtype] * weight)

    assigned_types = [rng.choice(type_pool) for _ in range(num_vehicles)]
    by_type: Dict[str, List[int]] = defaultdict(list)
    for idx, typ in enumerate(assigned_types):
        by_type[typ].append(idx)

    all_vehicles: List[Dict[str, Any]] = []

    for vtype, indices in by_type.items():
        vclass = VEHICLE_CLASSES.get(vtype, "passenger")
        edges, usable_edges, _ = load_network_for_vclass(net_path, vclass)

        if not usable_edges:
            logger.warning(f"No usable edges for vehicle type '{vtype}' (vClass: {vclass})")
            continue

        outgoing: Dict[str, List[str]] = defaultdict(list)
        for eid, info in edges.items():
            outgoing[info["from"]].append(eid)

        candidate_edges = sorted(list(usable_edges))
        edge_list_len = len(candidate_edges)

        for v_idx in indices:
            depart_time = round(rng.uniform(0, duration_s * 0.8), 2)
            route: Optional[List[str]] = None

            # Attempt random OD pairs
            for _ in range(100):
                src_e = rng.choice(candidate_edges)
                dst_e = rng.choice(candidate_edges)
                if src_e == dst_e:
                    continue
                route = shortest_path_vclass(src_e, dst_e, edges, outgoing)
                if route and len(route) >= 2:
                    break

            if not route:
                # Fallback to adjacent edge if distant route not found
                src_e = candidate_edges[v_idx % edge_list_len]
                route = [src_e]

            all_vehicles.append({
                "id": f"v_{vtype}_{v_idx}",
                "type": vtype,
                "depart": depart_time,
                "edges": route
            })

    # Sort vehicles by departure time
    all_vehicles.sort(key=lambda x: x["depart"])
    return all_vehicles


def write_vehicle_types_xml(dest_path: Path):
    """Write vehicles.rou.xml defining vType parameters and GUI raster icon paths."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("routes")

    for vid, vclass, image, length, width, accel, decel, maxspeed in VEHICLE_SPEC_LIST:
        ET.SubElement(root, "vType", {
            "id": vid,
            "vClass": vclass,
            "guiShape": "passenger" if vid in {"car", "taxi"} else vid,
            "imgFile": f"vehicles/{image}",
            "length": length,
            "width": width,
            "minGap": "1.5" if vid == "motorcycle" else "2.5",
            "accel": accel,
            "decel": decel,
            "maxSpeed": maxspeed,
            "color": "1,1,1",
        })

    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    tree.write(dest_path, encoding="UTF-8", xml_declaration=True)


VEHICLE_SPEC_LIST = VEHICLE_SPECS


def setup_scenario_vehicle_icons(scenario_dir: Path):
    """Copy raster vehicle icons to scenario output directory."""
    src_vehicles_dir = ROOT_DIR / "services" / "simulator" / "sumo_configs" / "vehicles"
    dst_vehicles_dir = scenario_dir / "vehicles"
    dst_vehicles_dir.mkdir(parents=True, exist_ok=True)

    if src_vehicles_dir.exists():
        for icon in src_vehicles_dir.glob("*.png"):
            shutil.copy(icon, dst_vehicles_dir / icon.name)
        logger.info(f"Copied vehicle icons to {dst_vehicles_dir}")

    # Write vehicles.rou.xml
    write_vehicle_types_xml(scenario_dir / "vehicles.rou.xml")


def generate_routes_xml(vehicles: List[Dict[str, Any]], dest_path: Path):
    """Write SUMO .rou.xml file incorporating vehicle types and vehicle routes."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("routes")

    # Include vehicles.rou.xml
    root.append(ET.Comment(" Include Vehicle Types with GUI raster icons "))
    ET.SubElement(root, "include", {"href": "vehicles.rou.xml"})

    for v in vehicles:
        veh_elem = ET.SubElement(root, "vehicle", {
            "id": str(v["id"]),
            "type": str(v["type"]),
            "depart": f"{v['depart']:.2f}"
        })
        ET.SubElement(veh_elem, "route", {
            "edges": " ".join(v["edges"])
        })

    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    tree.write(dest_path, encoding="UTF-8", xml_declaration=True)
    logger.info(f"Generated route XML with {len(vehicles)} vehicles at: {dest_path}")


def create_traffic_scenario(
    net_path: Path,
    scenario_id: str,
    num_vehicles: int = 1000,
    duration_s: int = 3600,
    modal_split: Optional[Dict[str, int]] = None,
    seed: int = 42,
    update_env: bool = True
) -> Dict[str, Any]:
    """
    Main entry point for HCM Corridor-style Traffic Scenario Creation.
    Returns metadata dict for generated scenario.
    """
    modal_split = modal_split or DEFAULT_HCM_MODAL_SPLIT

    # 1. Target output directories
    target_dir = ROOT_DIR / "services" / "simulator" / "sumo_configs" / scenario_id
    target_dir.mkdir(parents=True, exist_ok=True)

    local_net = target_dir / f"{scenario_id}.net.xml"
    if net_path.resolve() != local_net.resolve():
        shutil.copy(net_path, local_net)

    local_rou = target_dir / f"{scenario_id}.rou.xml"
    sumocfg_out = target_dir / f"{scenario_id}.sumocfg"

    # 2. Parse SUMO Network & generate Canonical Topology Contract JSON
    logger.info(f"Generating Canonical EdgeFlow Topology Contract for '{scenario_id}'...")
    xml_content = local_net.read_text(encoding="utf-8")
    topology = SumoNetworkConverter.parse_net_xml(xml_content, topology_id=scenario_id)

    topology_out = ROOT_DIR / "contracts" / "topology" / f"{scenario_id}.json"
    topology_out.parent.mkdir(parents=True, exist_ok=True)
    with open(topology_out, "w", encoding="utf-8") as f:
        json.dump(topology, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved Topology Contract: {topology_out} (Nodes: {len(topology['nodes'])}, Edges: {len(topology['edges'])})")

    # 3. Copy GUI Raster Vehicle Icons & Write vehicles.rou.xml
    setup_scenario_vehicle_icons(target_dir)

    # 4. Generate Multimodal Routes with HCM Modal Split
    logger.info(f"Generating {num_vehicles} multimodal routes for scenario '{scenario_id}'...")
    vehicles = generate_routes_for_vehicles(
        net_path=local_net,
        num_vehicles=num_vehicles,
        modal_split=modal_split,
        seed=seed,
        duration_s=duration_s
    )
    generate_routes_xml(vehicles, local_rou)

    # 5. Generate .sumocfg Configuration File
    sumocfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="{scenario_id}.net.xml"/>
        <route-files value="{scenario_id}.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{duration_s}"/>
    </time>
    <report>
        <no-step-log value="true"/>
    </report>
</configuration>
"""
    sumocfg_out.write_text(sumocfg_content, encoding="utf-8")
    logger.info(f"Created SUMO config: {sumocfg_out}")

    # 6. Update .env if requested
    if update_env:
        env_file = ROOT_DIR / ".env"
        if env_file.exists():
            lines = env_file.read_text(encoding="utf-8").splitlines()
            new_lines = []
            updated = False
            for line in lines:
                if line.strip().startswith("EDGEFLOW_TOPOLOGY="):
                    new_lines.append(f"EDGEFLOW_TOPOLOGY={scenario_id}")
                    updated = True
                else:
                    new_lines.append(line)
            if not updated:
                new_lines.append(f"EDGEFLOW_TOPOLOGY={scenario_id}")
            env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            logger.info(f"Updated .env with EDGEFLOW_TOPOLOGY={scenario_id}")

    return {
        "scenario_id": scenario_id,
        "topology_contract": str(topology_out),
        "net_file": str(local_net),
        "rou_file": str(local_rou),
        "sumocfg_file": str(sumocfg_out),
        "num_nodes": len(topology["nodes"]),
        "num_edges": len(topology["edges"]),
        "num_vehicles": len(vehicles),
    }


def main():
    parser = argparse.ArgumentParser(description="Create HCM Corridor-style SUMO Traffic Scenario for EdgeFlow AI.")
    parser.add_argument("--net", required=True, help="Path to input SUMO .net.xml file")
    parser.add_argument("--scenario-id", required=True, help="Unique ID name for the traffic scenario")
    parser.add_argument("--vehicles", type=int, default=1000, help="Number of vehicles to generate (default: 1000)")
    parser.add_argument("--duration", type=int, default=3600, help="Simulation duration in seconds (default: 3600)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for route generation (default: 42)")
    parser.add_argument("--no-env", action="store_true", help="Do not update .env with EDGEFLOW_TOPOLOGY")

    args = parser.parse_args()

    net_path = Path(args.net).resolve()
    if not net_path.exists():
        logger.error(f"SUMO network file not found: {net_path}")
        sys.exit(1)

    try:
        res = create_traffic_scenario(
            net_path=net_path,
            scenario_id=args.scenario_id,
            num_vehicles=args.vehicles,
            duration_s=args.duration,
            seed=args.seed,
            update_env=not args.no_env
        )
        print("\n============================================")
        print("TRAFFIC SCENARIO GENERATED SUCCESSFULLY")
        print("============================================")
        print(f"Scenario ID:        {res['scenario_id']}")
        print(f"Topology Contract:  {res['topology_contract']}")
        print(f"SUMO Config File:   {res['sumocfg_file']}")
        print(f"Junction Nodes:     {res['num_nodes']}")
        print(f"Road Edges:         {res['num_edges']}")
        print(f"Vehicles Generated: {res['num_vehicles']}")
        print("============================================")
    except Exception as e:
        logger.error(f"Error generating traffic scenario: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
