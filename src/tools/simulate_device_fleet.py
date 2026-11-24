"""
EdgeFlow AI — Device Fleet Telemetry Simulator (dashboard load-test companion).

Feeds plausible-looking telemetry for every node of a topology contract into the API's
documented ingestion endpoint (POST /api/v1/telemetry), over plain HTTP -- no MQTT broker, no
simulator/vision service, no access to any other service's internals. This is what turns a
load-test topology from "generate_load_test_topology.py" (or any existing small topology) from
all-zeros/WAITING_FOR_TELEMETRY into a dashboard full of live-looking stations, so the layout can
actually be judged at scale instead of staring at empty placeholder cards.

A --churn fraction of nodes "go quiet" each tick (so some stations show SIGNAL_LOST / WAITING)
and a --congest fraction get an inflated queue (so some show ATTENTION / CONGESTION) -- the point
is to see the dashboard's full mix of status colors and badge states at N devices, not just a wall
of identical green chips.

Usage:
    python src/tools/simulate_device_fleet.py --topology-id load_test_150
    python src/tools/simulate_device_fleet.py --topology-id load_test_150 --duration 120 --churn 0.1
"""

import argparse
import random
import sys
import time

import requests

PHASE_HOLD_TICKS = 4  # how many ticks a node's current_phase_id stays put before switching


def fetch_topology(api_base: str, topology_id: str) -> dict:
    resp = requests.get(f"{api_base}/api/v1/topologies/{topology_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def build_batch(nodes: list, topology_id: str, tick: int, churn: float, congest: float) -> list:
    now_ms = int(time.time() * 1000)
    batch = []

    for node in nodes:
        if random.random() < churn:
            continue  # simulate a node that's gone silent this tick (-> SIGNAL_LOST once stale)

        phases = node.get("phases") or []
        phase_ids = [p["phase_id"] for p in phases] or [f"{node['node_id']}_PHASE_NS"]
        # Deterministic-but-varied: each node switches phase on its own offset cycle instead of
        # everyone flipping in lockstep, which would look fake on the live topology graph.
        phase_index = ((tick + hash(node["node_id"])) // PHASE_HOLD_TICKS) % len(phase_ids)
        current_phase_id = phase_ids[phase_index]

        is_congested = random.random() < congest
        approaches = []
        for app_id in node.get("approaches", []):
            # The dashboard flags a node ATTENTION once its 4 approaches sum past 12 vehicles
            # (NetworkOverview's ATTENTION_QUEUE_VEH) -- keep "normal" well under that per-approach
            # (sum ~0-10) so congest actually reads as the minority case it's meant to simulate,
            # not the default.
            queue = random.uniform(5, 9) if is_congested else random.uniform(0, 2.5)
            approaches.append({
                "approach_id": app_id,
                "queue_vehicles": round(queue, 1),
                "flow_veh_per_s": round(random.uniform(0.1, 2.2), 2),
                "mean_speed_mps": round(random.uniform(1.5, 14.0), 1),
                "occupancy_ratio": round(min(queue / 20, 1.0), 2),
                "confidence": round(random.uniform(0.85, 1.0), 2)
            })

        batch.append({
            "node_id": node["node_id"],
            "topology_id": topology_id,
            "source_type": "mock_demo",
            "timestamp_ms": now_ms,
            "current_phase_id": current_phase_id,
            "approaches": approaches
        })

    return batch


def main():
    parser = argparse.ArgumentParser(description="Feed synthetic live telemetry for every node of a topology into the API, for dashboard load testing.")
    parser.add_argument("--topology-id", type=str, required=True, help="Topology contract ID to simulate (e.g. load_test_150).")
    parser.add_argument("--api-base", type=str, default="http://localhost:8000", help="API base URL (default: http://localhost:8000).")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between telemetry ticks (default: 2.0).")
    parser.add_argument("--duration", type=float, default=None, help="Stop after this many seconds (default: run until Ctrl+C).")
    parser.add_argument("--churn", type=float, default=0.05, help="Fraction of nodes that silently skip a tick, to exercise SIGNAL_LOST/WAITING states (default: 0.05).")
    parser.add_argument("--congest", type=float, default=0.08, help="Fraction of nodes reporting an inflated queue, to exercise ATTENTION/CONGESTION states (default: 0.08).")
    args = parser.parse_args()

    try:
        topology = fetch_topology(args.api_base, args.topology_id)
    except requests.RequestException as exc:
        print(f"Could not load topology '{args.topology_id}' from {args.api_base}: {exc}", file=sys.stderr)
        print("Is the API running, and does contracts/topology/ have this topology ID?", file=sys.stderr)
        raise SystemExit(1)

    nodes = topology.get("nodes", [])
    if not nodes:
        raise SystemExit(f"Topology '{args.topology_id}' has no nodes.")

    print(f"Simulating {len(nodes)} devices for topology '{args.topology_id}' -> {args.api_base}")
    print(f"interval={args.interval}s  churn={args.churn}  congest={args.congest}  (Ctrl+C to stop)")

    tick = 0
    start = time.time()
    try:
        while args.duration is None or (time.time() - start) < args.duration:
            batch = build_batch(nodes, args.topology_id, tick, args.churn, args.congest)
            try:
                resp = requests.post(f"{args.api_base}/api/v1/telemetry", json=batch, timeout=10)
                resp.raise_for_status()
                print(f"tick {tick:4d}  sent {len(batch)}/{len(nodes)} nodes  ({len(nodes) - len(batch)} churned)")
            except requests.RequestException as exc:
                print(f"tick {tick:4d}  POST failed: {exc}", file=sys.stderr)
            tick += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
