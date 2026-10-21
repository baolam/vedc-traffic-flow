"""
EdgeFlow AI — SUMO Network Registry and Multi-Level Topology Mapping (P0/P1).

Authoritative registry for canonical SUMO networks:
  - four_intersection_v1
  - grid4x4
  - cologne8
  - hcm_corridor

Enforces:
  1. Exact net XML paths and cryptographic SHA-256 pinning.
  2. Multi-level mapping:
     - Canonical node ID <-> TLS ID (distinguishing controlled TLS vs uncontrolled nodes)
     - Canonical approach ID <-> incoming lanes/edges
     - Stable green phases ONLY (no yellow, no all-red, no transition states in action set)
     - Movements: from_approach, to_edge, link_index, to_node, to_approach, is_boundary_exit
     - Geometric direction mapping: (dx, dy) vector -> axis ('NS'/'EW') and side ('NORTH', 'SOUTH', 'EAST', 'WEST')
  3. Preflight validation & mapping audit export (mapping_audit.json / mapping_audit.csv).
"""

import os
import sys
import math
import json
import hashlib
import csv
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import xml.etree.ElementTree as ET

logger = logging.getLogger("network-registry")

# Root resolution
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import sumolib


# ==============================================================================
# Canonical Network Registry Definition
# ==============================================================================

NETWORK_REGISTRY: Dict[str, Dict[str, Any]] = {
    "four_intersection_v1": {
        "topology_id": "four_intersection_v1",
        "display_name": "Four Intersections Grid v1",
        "net_rel_path": "services/simulator/sumo_configs/four_intersection_v1/four_intersection_v1.net.xml",
        "expected_net_sha256": [
            "98eec91d0f66ad925ecb881e911fedec018c552f9a416e548a503e76b77f0b9b",  # Canonical (LF)
            "5105ee4e92315ad533ff5621dc8f8bbaf2ad72d19f6e2863091644ad24897c51",  # Windows (CRLF)
            "c52327a5fa6cb9aea03f170ecace465222cc03c354ce6a32e06904cffd6d4deb",
        ],
        "topo_rel_path": "contracts/topology/four_intersection_v1.json",
        "expected_topo_sha256": [
            "53f5800d8774566facd09cae0c126613247540315d5dc1c9a8680196be2732f0",  # Canonical (LF)
            "2d5ace16693cb48591d71759da7e9fac6928975135574336bf34e57783d92e4a",  # Windows (CRLF)
        ],
        "controlled_tls_ids": ["J1", "J2", "J3", "J4"],
        "bottleneck_edge": "J3_N_IN",
        "normal_speed_mps": 13.89,
        "congested_speed_mps": 1.50,
        "primary_surge_axis": "NS",
    },
    "grid4x4": {
        "topology_id": "grid4x4",
        "display_name": "4x4 Manhattan Grid (16 Signalized Intersections)",
        "net_rel_path": "services/simulator/sumo_configs/grid4x4/grid4x4.net.xml",
        "expected_net_sha256": [
            "0af71d655e4d0c0e2f0a39883b60a1f95d662e930794a9c76bf961402608869d",
        ],
        "topo_rel_path": "contracts/topology/grid4x4.json",
        "expected_topo_sha256": [
            "f3372ba98c4f560da99e97bdc67d1c3fa6709849c0ad81515268ea8f0c6cb6f3",  # Canonical (LF)
            "5b08c09b6004a07b8a4174ff2c422beb8bdc15a504f114a7d68c7d9a382fdd9e",  # Windows (CRLF)
        ],
        "controlled_tls_ids": [
            "A0", "A1", "A2", "A3",
            "B0", "B1", "B2", "B3",
            "C0", "C1", "C2", "C3",
            "D0", "D1", "D2", "D3",
        ],
        "bottleneck_edge": "A1A0",
        "normal_speed_mps": 13.89,
        "congested_speed_mps": 1.50,
        "primary_surge_axis": "NS",
    },
    "cologne8": {
        "topology_id": "cologne8",
        "display_name": "Cologne TAPAS Subnetwork (8 Signalized Intersections)",
        "net_rel_path": "services/simulator/sumo_configs/cologne8/cologne8.net.xml",
        "expected_net_sha256": [
            "51194519fd4d69726612d38b44606637c31389b86079f909139ba8f1aaffd2a8",
        ],
        "topo_rel_path": "contracts/topology/cologne8.json",
        "expected_topo_sha256": [
            "fae7e17c9a632d3b510118a3e852697142fd75b8b611c1b1b807e02a4c5f5b49",  # Canonical (LF)
            "7c350306e765f56833908ae3eae45ad1201a212adce9328d35067ffc387c01fe",  # Windows (CRLF)
        ],
        "controlled_tls_ids": [
            "26110729", "247379907", "256201389",
            "cluster_1098574052_1098574061_247379905",
            "252017285", "280120513", "32319828", "62426694",
        ],
        "bottleneck_edge": "-186623965#16",
        "normal_speed_mps": 13.89,
        "congested_speed_mps": 1.50,
        "primary_surge_axis": "NS",
    },
    "hcm_corridor": {
        "topology_id": "hcm_corridor",
        "display_name": "Ho Chi Minh City Arterial Corridor (29 Signalized Intersections)",
        "net_rel_path": "services/simulator/sumo_configs/hcm_corridor/hcm_corridor.net.xml",
        "expected_net_sha256": [
            "d62975213c5c4a3e9afeb71ffa611900e3c7e302d6201da04cddc160f10586c7",  # Canonical (LF)
            "83c61b6dc6c0ff9484ad239a6d2ece7af52c0637485855684d738bc4f6a5f9d3",  # Windows (CRLF)
        ],
        "topo_rel_path": "contracts/topology/hcm_corridor.json",
        "expected_topo_sha256": [
            "ab242b1e56603b1a93ea2a10821118dbdeddb79fbf462f10d8031100ca5d3d3a",  # Enriched with GPS/Leaflet (LF & CRLF)
            "bbea84ac877f2e52a5f33e9d226ede2c09ec7397f53a7107675bc90d265c8954",  # Canonical (LF)
            "06f895b3e6bf315d0bada97de05a1eec9e5124b1a27b6a5cdb4804e9a305f210",  # Windows (CRLF)
        ],
        "controlled_tls_ids": [
            "2217938301", "2217938309", "2217938311", "2217938313", "2217938327",
            "2217939289", "2217939291", "2938641215", "2942327970", "2942327993",
            "366384741", "366400259", "366415782", "366426721", "366459280",
            "5750599983", "5750600545", "5750600562", "5750600584", "7819058842",
            "cluster_11553495261_366408179", "cluster_2217938303_2217938318",
            "cluster_2938641203_366431367_5750600582", "cluster_2942327942_366465117",
            "cluster_2942327969_745747032", "cluster_2942327973_8348405138",
            "cluster_5750600569_5750600570", "cluster_5750600571_5750600573",
            "cluster_5750600572_5750600575",
        ],
        "bottleneck_edge": "32577015#8",
        "normal_speed_mps": 13.89,
        "congested_speed_mps": 1.50,
        "primary_surge_axis": "NS",
    },
}


def compute_file_sha256(file_path: Path) -> str:
    """
    Compute deterministic SHA-256 hash of a file.
    Normalizes CRLF (\\r\\n) to LF (\\n) for text/XML/JSON files so that
    cryptographic verification is platform-agnostic across Windows, Linux, and macOS.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    data = file_path.read_bytes()
    if file_path.suffix.lower() in [".xml", ".json", ".txt", ".csv"]:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


# ==============================================================================
# Geometric Direction Classifier
# ==============================================================================

def classify_edge_geometry(edge: sumolib.net.edge.Edge) -> Dict[str, Any]:
    """
    Classify incoming edge direction using endpoint geometry near the junction.
    
    Returns:
      - vector: (dx, dy) of the final segment towards the junction
      - length_m: length of final segment
      - axis: 'NS' if abs(dy) >= abs(dx) else 'EW'
      - from_side: 'NORTH', 'SOUTH', 'EAST', or 'WEST'
      - bearing_deg: compass angle (0=North, 90=East, 180=South, 270=West)
    """
    shape = edge.getShape()
    if len(shape) < 2:
        return {
            "vector": (0.0, 0.0),
            "length_m": 0.0,
            "axis": "NS",
            "from_side": "NORTH",
            "bearing_deg": 0.0,
        }

    p1, p2 = shape[-2], shape[-1]
    dx = float(p2[0] - p1[0])
    dy = float(p2[1] - p1[1])
    length = math.hypot(dx, dy)

    # Compass bearing (0 degrees = North [0, 1], 90 degrees = East [1, 0])
    # atan2(dx, dy): angle from North in radians
    bearing_rad = math.atan2(dx, dy)
    bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0

    # Direction vehicle travels: (dx, dy)
    # Side vehicle comes FROM: opposite of travel direction
    if abs(dy) >= abs(dx):
        axis = "NS"
        from_side = "NORTH" if dy < 0 else "SOUTH"
    else:
        axis = "EW"
        from_side = "EAST" if dx < 0 else "WEST"

    return {
        "vector": (round(dx, 2), round(dy, 2)),
        "length_m": round(length, 2),
        "axis": axis,
        "from_side": from_side,
        "bearing_deg": round(bearing_deg, 1),
    }


# ==============================================================================
# Multi-Level Network Mapping Resolver
# ==============================================================================

class NetworkMappingResolver:
    """
    Builds and validates authoritative multi-level mappings for a SUMO network.
    """

    def __init__(self, topology_id: str, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or REPO_ROOT
        if topology_id not in NETWORK_REGISTRY:
            raise ValueError(
                f"Unknown topology '{topology_id}'. Valid: {list(NETWORK_REGISTRY.keys())}"
            )
        self.info = NETWORK_REGISTRY[topology_id]
        self.topology_id = topology_id
        self.net_path = self.repo_root / self.info["net_rel_path"]
        self.topo_path = self.repo_root / self.info["topo_rel_path"]

        # Validate file existence & cryptographic hashes
        self._verify_hashes()

        # Load sumolib Net
        self.sumo_net = sumolib.net.readNet(str(self.net_path))

        # Build mapping
        self.mapping = self._build_mapping()

    def _verify_hashes(self):
        actual_net_sha = compute_file_sha256(self.net_path)
        raw_net_sha = hashlib.sha256(self.net_path.read_bytes()).hexdigest()
        expected_net = self.info["expected_net_sha256"]
        valid_net_shas = expected_net if isinstance(expected_net, list) else [expected_net]
        if actual_net_sha not in valid_net_shas and raw_net_sha not in valid_net_shas:
            raise ValueError(
                f"NET SHA-256 MISMATCH for {self.topology_id}:\n"
                f"  Expected one of: {valid_net_shas}\n"
                f"  Actual (norm):   {actual_net_sha}\n"
                f"  Actual (raw):    {raw_net_sha}"
            )
        self.actual_net_sha = actual_net_sha

        actual_topo_sha = compute_file_sha256(self.topo_path)
        raw_topo_sha = hashlib.sha256(self.topo_path.read_bytes()).hexdigest()
        expected_topo = self.info["expected_topo_sha256"]
        valid_topo_shas = expected_topo if isinstance(expected_topo, list) else [expected_topo]
        if actual_topo_sha not in valid_topo_shas and raw_topo_sha not in valid_topo_shas:
            raise ValueError(
                f"TOPOLOGY SHA-256 MISMATCH for {self.topology_id}:\n"
                f"  Expected one of: {valid_topo_shas}\n"
                f"  Actual (norm):   {actual_topo_sha}\n"
                f"  Actual (raw):    {raw_topo_sha}"
            )
        self.actual_topo_sha = actual_topo_sha

    def _build_mapping(self) -> Dict[str, Any]:
        """Parse net XML and build multi-level topology mapping."""
        tree = ET.parse(self.net_path)
        root = tree.getroot()

        # 1. Parse connections to map (tl_id, linkIndex) -> list of connection records
        tl_links: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        for c in root.findall("connection"):
            tl_id = c.get("tl")
            if tl_id and c.get("linkIndex") is not None:
                try:
                    lidx = int(c.get("linkIndex"))
                    from_e = c.get("from")
                    to_e = c.get("to")
                    from_lane = int(c.get("fromLane", 0))
                    to_lane = int(c.get("toLane", 0))
                    dir_code = c.get("dir", "s")

                    conn_info = {
                        "from_edge": from_e,
                        "from_lane": from_lane,
                        "to_edge": to_e,
                        "to_lane": to_lane,
                        "dir": dir_code,
                    }
                    tl_links.setdefault(tl_id, {}).setdefault(lidx, []).append(conn_info)
                except ValueError:
                    continue

        # 2. Parse tlLogic elements
        tls_programs: Dict[str, Dict[str, Any]] = {}
        for tl in root.findall("tlLogic"):
            tid = tl.get("id")
            program_id = tl.get("programID", "0")
            phases = []
            stable_green_phases = []

            for raw_idx, p in enumerate(tl.findall("phase")):
                state = p.get("state", "")
                dur = float(p.get("duration", 0))
                has_yellow = "y" in state or "Y" in state
                all_red = "G" not in state and "g" not in state
                is_stable_green = (not has_yellow) and (not all_red)

                phase_rec = {
                    "raw_index": raw_idx,
                    "state": state,
                    "duration_s": dur,
                    "is_stable_green": is_stable_green,
                }
                phases.append(phase_rec)
                if is_stable_green:
                    stable_green_phases.append(phase_rec)

            tls_programs[tid] = {
                "program_id": program_id,
                "all_phases": phases,
                "stable_green_phases": stable_green_phases,
            }

        # 3. Controlled TLS vs uncontrolled nodes
        controlled_tls_set = set(self.info["controlled_tls_ids"])
        all_net_tls_ids = set(tl.getID() for tl in self.sumo_net.getTrafficLights())

        # Verify all controlled TLS exist in net
        missing_tls = controlled_tls_set - all_net_tls_ids
        if missing_tls:
            raise ValueError(f"Controlled TLS IDs not in net: {missing_tls}")

        # 4. Resolve node mappings
        nodes_mapping: Dict[str, Dict[str, Any]] = {}
        approach_audit: List[Dict[str, Any]] = []

        with open(self.topo_path, "r", encoding="utf-8") as f:
            topo_json = json.load(f)

        for n in topo_json.get("nodes", []):
            nid = n["node_id"]
            is_controlled = nid in controlled_tls_set

            node_obj = self.sumo_net.getNode(nid)
            incoming_edges = [e.getID() for e in node_obj.getIncoming()] if node_obj else n.get("approaches", [])
            outgoing_edges = [e.getID() for e in node_obj.getOutgoing()] if node_obj else []

            # Geometric classification of incoming edges
            approaches_geo: Dict[str, Dict[str, Any]] = {}
            for eid in incoming_edges:
                edge_obj = self.sumo_net.getEdge(eid) if self.sumo_net.hasEdge(eid) else None
                if edge_obj:
                    geo = classify_edge_geometry(edge_obj)
                    approaches_geo[eid] = geo
                    approach_audit.append({
                        "topology_id": self.topology_id,
                        "node_id": nid,
                        "approach_id": eid,
                        "vector_dx": geo["vector"][0],
                        "vector_dy": geo["vector"][1],
                        "bearing_deg": geo["bearing_deg"],
                        "axis": geo["axis"],
                        "from_side": geo["from_side"],
                        "length_m": geo["length_m"],
                    })

            # Phases mapping: for controlled TLS, resolve stable green phases
            resolved_phases: List[Dict[str, Any]] = []
            if is_controlled and nid in tls_programs:
                tl_prog = tls_programs[nid]
                stable_greens = tl_prog["stable_green_phases"]

                # If topology defines canonical phase IDs (e.g. four_intersection_v1 has J1_PHASE_NS, J1_PHASE_EW)
                canonical_phases = n.get("phases", [])

                for p_idx, green_rec in enumerate(stable_greens):
                    state_str = green_rec["state"]
                    raw_sumo_idx = green_rec["raw_index"]

                    # Default phase ID or use canonical if aligned
                    if p_idx < len(canonical_phases) and canonical_phases[p_idx].get("phase_id"):
                        phase_id = canonical_phases[p_idx]["phase_id"]
                    else:
                        phase_id = f"{nid}_PHASE_{p_idx + 1}"

                    # Determine which connections and movements are green in this state
                    active_approaches = []
                    movements = []
                    conns_for_tl = tl_links.get(nid, {})

                    for lidx, char in enumerate(state_str):
                        if char in ("G", "g"):
                            if lidx in conns_for_tl:
                                for c_info in conns_for_tl[lidx]:
                                    from_app = c_info["from_edge"]
                                    to_e = c_info["to_edge"]
                                    if from_app not in active_approaches:
                                        active_approaches.append(from_app)

                                    # Find destination node and approach
                                    to_edge_obj = self.sumo_net.getEdge(to_e) if self.sumo_net.hasEdge(to_e) else None
                                    to_node_id = to_edge_obj.getToNode().getID() if to_edge_obj else None
                                    is_boundary = (to_node_id not in controlled_tls_set)

                                    movements.append({
                                        "from_approach": from_app,
                                        "from_lane": c_info["from_lane"],
                                        "to_edge": to_e,
                                        "to_lane": c_info["to_lane"],
                                        "link_index": lidx,
                                        "signal_type": char,  # 'G' or 'g'
                                        "to_node": to_node_id if not is_boundary else None,
                                        "to_approach": to_e if not is_boundary else None,
                                        "is_boundary_exit": is_boundary,
                                    })

                    resolved_phases.append({
                        "phase_id": phase_id,
                        "name": f"Green Phase {p_idx + 1}",
                        "sumo_phase_index": raw_sumo_idx,
                        "state": state_str,
                        "duration_s": green_rec["duration_s"],
                        "approaches": active_approaches or incoming_edges,
                        "movements": movements,
                    })

            nodes_mapping[nid] = {
                "node_id": nid,
                "is_controlled_tls": is_controlled,
                "tls_id": nid if is_controlled else None,
                "approaches": incoming_edges,
                "outgoing_edges": outgoing_edges,
                "approaches_geometry": approaches_geo,
                "phases": resolved_phases,
            }

        # Check bottleneck edge
        bn = self.info["bottleneck_edge"]
        if not self.sumo_net.hasEdge(bn):
            raise ValueError(f"Configured bottleneck edge '{bn}' not found in net for {self.topology_id}")

        return {
            "topology_id": self.topology_id,
            "display_name": self.info["display_name"],
            "net_path": str(self.net_path.resolve()),
            "topo_path": str(self.topo_path.resolve()),
            "net_sha256": self.actual_net_sha,
            "topo_sha256": self.actual_topo_sha,
            "controlled_tls_ids": self.info["controlled_tls_ids"],
            "uncontrolled_node_ids": [nid for nid in nodes_mapping if not nodes_mapping[nid]["is_controlled_tls"]],
            "bottleneck": {
                "edge_id": bn,
                "normal_speed_mps": self.info["normal_speed_mps"],
                "congested_speed_mps": self.info["congested_speed_mps"],
            },
            "primary_surge_axis": self.info["primary_surge_axis"],
            "nodes": nodes_mapping,
            "approach_audit": approach_audit,
        }

    def export_audit(self, output_dir: Path):
        """Export mapping_audit.json and mapping_audit.csv."""
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "mapping_audit.json"
        csv_path = output_dir / "mapping_audit.csv"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.mapping, f, indent=2)

        audit_rows = self.mapping.get("approach_audit", [])
        if audit_rows:
            fieldnames = list(audit_rows[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(audit_rows)


# ==============================================================================
# Global Preflight Check
# ==============================================================================

def run_preflight_check(topologies: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Run preflight verification across requested or all canonical topologies.
    Returns audit status dict.
    """
    targets = topologies or list(NETWORK_REGISTRY.keys())
    results: Dict[str, Any] = {
        "status": "PASS",
        "verified_topologies": {},
        "failed_topologies": {},
        "summary": {}
    }

    total_tls = 0
    total_phases = 0
    total_movements = 0

    for top_id in targets:
        try:
            resolver = NetworkMappingResolver(top_id)
            mapping = resolver.mapping
            ctrl_tls = mapping["controlled_tls_ids"]
            nodes = mapping["nodes"]

            n_phases = sum(len(nodes[nid]["phases"]) for nid in ctrl_tls)
            n_movs = sum(
                sum(len(p.get("movements", [])) for p in nodes[nid]["phases"])
                for nid in ctrl_tls
            )

            total_tls += len(ctrl_tls)
            total_phases += n_phases
            total_movements += n_movs

            results["verified_topologies"][top_id] = {
                "display_name": mapping["display_name"],
                "net_sha256": mapping["net_sha256"],
                "topo_sha256": mapping["topo_sha256"],
                "controlled_tls_count": len(ctrl_tls),
                "uncontrolled_node_count": len(mapping["uncontrolled_node_ids"]),
                "total_stable_green_phases": n_phases,
                "total_verified_movements": n_movs,
                "bottleneck_edge": mapping["bottleneck"]["edge_id"],
                "preflight_pass": True,
            }
        except Exception as e:
            results["status"] = "FAIL"
            results["failed_topologies"][top_id] = {
                "error": str(e),
                "preflight_pass": False,
            }

    results["summary"] = {
        "total_verified_networks": len(results["verified_topologies"]),
        "total_failed_networks": len(results["failed_topologies"]),
        "total_controlled_tls": total_tls,
        "total_stable_green_phases": total_phases,
        "total_verified_movements": total_movements,
    }

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = run_preflight_check()
    print(json.dumps(res, indent=2))
