"""
EdgeFlow AI — Dashboard Load-Test Topology Generator.

Generates a synthetic topology contract (contracts/topology/<topology_id>.json) with N
grid-arranged intersection nodes, purely to stress-test the React dashboard's layout at device
counts the hand-authored scenarios (four_intersection_v1, cologne8, grid4x4: 4-32 nodes) never
reach -- search dropdowns, the station quick-switcher, Junction Monitoring's list, the live
topology graph, and the Control & Tuning override panel.

Not a simulation scenario: nodes have the same shape as four_intersection_v1 (approaches, phases,
movements) so every dashboard page that reads a topology contract works unmodified, but there is
no SUMO config and no physics behind it -- pair this with simulate_device_fleet.py to also get
live-looking telemetry flowing through the API for every generated node.

Usage:
    python src/tools/generate_load_test_topology.py --count 150
    python src/tools/generate_load_test_topology.py --count 800 --topology-id stress_800
"""

import argparse
import json
import math
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
TOPOLOGY_DIR = ROOT_DIR / "contracts" / "topology"

# Grid spacing in the same arbitrary SUMO-style x/y units four_intersection_v1 uses -- TopologyMap
# normalizes/scales whatever span it finds, so the absolute numbers don't matter, only their layout.
GRID_SPACING = 140


def node_id_for(index: int) -> str:
    # "L" (load test) prefix keeps these unmistakably synthetic and never collides with the
    # hand-authored J1-J4 / A0-D3 / cluster_... node IDs used by real scenarios. Exactly 5 chars
    # ("L0000") so TopologyMap's formatNodeLabel shows it in full instead of truncating to "..0000"
    # -- a 2-letter prefix ("LT0000", 6 chars) would trip that truncation on every single node.
    return f"L{index:04d}"


def build_node(index: int, row: int, col: int, total_cols: int, total_rows: int) -> dict:
    nid = node_id_for(index)
    approaches = [f"{nid}_N_IN", f"{nid}_S_IN", f"{nid}_E_IN", f"{nid}_W_IN"]

    # Phase movements point at the next node to the right (EW) / below (NS) when one exists in the
    # grid, otherwise exit the network -- same pattern four_intersection_v1 uses for its corners.
    south_neighbor = node_id_for(index + total_cols) if row < total_rows - 1 else None
    east_neighbor = node_id_for(index + 1) if col < total_cols - 1 else None

    phases = [
        {
            "phase_id": f"{nid}_PHASE_NS",
            "name": "North-South Green",
            "approaches": [f"{nid}_N_IN", f"{nid}_S_IN"],
            "movements": [
                {
                    "from_approach": f"{nid}_N_IN",
                    "to_edge": f"E_{nid}_{south_neighbor}_SB" if south_neighbor else "EXIT_SOUTH",
                    "to_node": south_neighbor,
                    "turn_ratio": 0.8 if south_neighbor else 1.0,
                    "capacity_vehicles": 20 if south_neighbor else 100
                },
                {
                    "from_approach": f"{nid}_S_IN",
                    "to_edge": "EXIT_NORTH",
                    "to_node": None,
                    "turn_ratio": 1.0,
                    "capacity_vehicles": 100
                }
            ]
        },
        {
            "phase_id": f"{nid}_PHASE_EW",
            "name": "East-West Green",
            "approaches": [f"{nid}_E_IN", f"{nid}_W_IN"],
            "movements": [
                {
                    "from_approach": f"{nid}_W_IN",
                    "to_edge": f"E_{nid}_{east_neighbor}_EB" if east_neighbor else "EXIT_WEST",
                    "to_node": east_neighbor,
                    "turn_ratio": 0.8 if east_neighbor else 1.0,
                    "capacity_vehicles": 20 if east_neighbor else 100
                },
                {
                    "from_approach": f"{nid}_E_IN",
                    "to_edge": "EXIT_EAST",
                    "to_node": None,
                    "turn_ratio": 1.0,
                    "capacity_vehicles": 100
                }
            ]
        }
    ]

    return {
        "node_id": nid,
        "name": f"Load Test Junction {index + 1}",
        "street_name": f"Synthetic Row {row + 1} / Col {col + 1}",
        # Consumed directly by services/api (get_network_state) and TopologyMap.jsx's hasXY branch.
        "x": col * GRID_SPACING,
        "y": row * GRID_SPACING,
        "approaches": approaches,
        "phases": phases
    }


def build_topology(count: int, topology_id: str) -> dict:
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)

    nodes = []
    for index in range(count):
        row, col = divmod(index, cols)
        nodes.append(build_node(index, row, col, cols, rows))

    edges = []
    for index in range(count):
        row, col = divmod(index, cols)
        nid = node_id_for(index)
        if col < cols - 1 and index + 1 < count:
            east_id = node_id_for(index + 1)
            edges.append({"edge_id": f"E_{nid}_{east_id}_EB", "source": nid, "target": east_id, "capacity_vehicles": 20})
            edges.append({"edge_id": f"E_{east_id}_{nid}_WB", "source": east_id, "target": nid, "capacity_vehicles": 20})
        if row < rows - 1 and index + cols < count:
            south_id = node_id_for(index + cols)
            edges.append({"edge_id": f"E_{nid}_{south_id}_SB", "source": nid, "target": south_id, "capacity_vehicles": 20})
            edges.append({"edge_id": f"E_{south_id}_{nid}_NB", "source": south_id, "target": nid, "capacity_vehicles": 20})

    return {
        "topology_id": topology_id,
        "version": "1.0",
        "nodes": nodes,
        "edges": edges
    }


def main():
    parser = argparse.ArgumentParser(description="Generate a synthetic N-node topology contract for dashboard load testing.")
    parser.add_argument("--count", type=int, default=150, help="Number of synthetic intersection nodes to generate (default: 150).")
    parser.add_argument("--topology-id", type=str, default=None, help="Topology ID / output filename stem (default: load_test_<count>).")
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be >= 1")

    topology_id = args.topology_id or f"load_test_{args.count}"
    topology = build_topology(args.count, topology_id)

    TOPOLOGY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TOPOLOGY_DIR / f"{topology_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(topology, f, indent=2)

    print(f"Wrote {len(topology['nodes'])} nodes / {len(topology['edges'])} edges -> {out_path}")
    print(f"Topology ID: {topology_id}")
    print("Next steps:")
    print(f"  1. python src/tools/simulate_device_fleet.py --topology-id {topology_id}")
    print(f"  2. Open the dashboard -- the Map selector on Overview will now list \"{topology_id}\".")


if __name__ == "__main__":
    main()
