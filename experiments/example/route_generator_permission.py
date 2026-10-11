import argparse
import random
import xml.etree.ElementTree as ET
from collections import defaultdict
from heapq import heappush, heappop


# SUMO vClass used by the vehicle types in the project.
VEHICLE_CLASSES = {
    "car": "passenger",
    "taxi": "passenger",
    "motorcycle": "motorcycle",
    "bus": "bus",
    "truck": "truck",
}

TYPE_WEIGHTS = {
    "motorcycle": 65,
    "car": 25,
    "taxi": 4,
    "bus": 3,
    "truck": 3,
}


def token_set(value):
    if not value:
        return set()
    return set(value.replace(",", " ").split())


def permission_ok(attrs, vclass):
    """Check SUMO allow/disallow on a lane/connection.

    If allow is present, vclass must be allowed.
    If disallow is present, vclass must not be disallowed.
    """
    allow = token_set(attrs.get("allow"))
    disallow = token_set(attrs.get("disallow"))

    if allow and vclass not in allow:
        return False
    if vclass in disallow:
        return False
    return True


def lane_is_usable(lane, vclass):
    return permission_ok(lane, vclass)


def load_network(path, vclass):
    root = ET.parse(path).getroot()

    edges = {}
    usable_edges = set()

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
            lane for lane in lanes
            if lane_is_usable(lane, vclass)
        ]

        if not usable_lanes:
            continue

        # Use the fastest usable lane as the free-flow cost.
        best_lane = min(
            usable_lanes,
            key=lambda lane: float(lane.get("length", "1"))
            / max(float(lane.get("speed", "13.9")), 0.1)
        )

        length = float(best_lane.get("length", "1"))
        speed = float(best_lane.get("speed", "13.9"))

        edges[eid] = {
            "from": frm,
            "to": to,
            "length": length,
            "speed": speed,
            "lanes": {lane.get("index") for lane in usable_lanes},
        }
        usable_edges.add(eid)

    # Edge-to-edge transitions from SUMO <connection>.
    transitions = defaultdict(list)
    connection_count = 0

    for c in root.findall("connection"):
        a = c.get("from")
        b = c.get("to")

        if a not in usable_edges or b not in usable_edges:
            continue

        # A connection can have lane-specific restrictions.
        if not permission_ok(c, vclass):
            continue

        from_lane = c.get("fromLane")
        if from_lane is not None and from_lane not in edges[a]["lanes"]:
            continue

        transitions[a].append(b)
        connection_count += 1

    # Fallback: if there are no usable explicit connections, use topology.
    if connection_count == 0:
        by_from = defaultdict(list)
        for eid, e in edges.items():
            by_from[e["from"]].append(eid)

        for a, ea in edges.items():
            transitions[a] = [
                b for b, eb in edges.items()
                if ea["to"] == eb["from"]
            ]

    # Deduplicate transitions.
    for a in list(transitions):
        transitions[a] = list(dict.fromkeys(transitions[a]))

    outgoing = defaultdict(list)
    for a, bs in transitions.items():
        for b in bs:
            if b in edges:
                outgoing[a].append(b)

    return edges, outgoing, connection_count


def shortest_path(start_edge, goal_edge, edges, outgoing, banned=None):
    banned = set(banned or ())
    pq = [(0.0, start_edge)]
    dist = {start_edge: 0.0}
    prev = {}

    while pq:
        cost, current = heappop(pq)

        if cost != dist.get(current):
            continue

        if current == goal_edge:
            break

        for nxt in outgoing.get(current, ()):
            if nxt in banned:
                continue

            e = edges[nxt]
            weight = e["length"] / max(e["speed"], 0.1)
            new_cost = cost + weight

            if new_cost < dist.get(nxt, float("inf")):
                dist[nxt] = new_cost
                prev[nxt] = current
                heappush(pq, (new_cost, nxt))

    if goal_edge not in dist:
        return None

    route = []
    cur = goal_edge

    while cur != start_edge:
        route.append(cur)
        cur = prev[cur]

    route.append(start_edge)
    route.reverse()
    return route


def valid_route(route, edges, outgoing):
    if not route:
        return False

    for a, b in zip(route, route[1:]):
        if b not in outgoing.get(a, ()):
            return False

    return all(e in edges for e in route)


def route_length(route, edges):
    return sum(edges[e]["length"] for e in route)


def make_alternatives(start, goal, base, edges, outgoing, rng,
                      count, max_detour):
    result = []
    seen = {tuple(base)}
    base_len = route_length(base, edges)

    if len(base) < 3:
        return result

    for attempt in range(max(20, count * 15)):
        banned = set()

        # Block a few interior edges from the base route.
        indices = list(range(1, len(base) - 1))
        rng.shuffle(indices)

        block_count = max(1, min(3, len(indices)))
        for idx in indices[:block_count]:
            banned.add(base[idx])

        route = shortest_path(
            start, goal, edges, outgoing, banned
        )

        if not route:
            continue

        key = tuple(route)

        if key in seen:
            continue

        if not valid_route(route, edges, outgoing):
            continue

        new_len = route_length(route, edges)

        if new_len > base_len * max_detour:
            continue

        # Require meaningful diversity.
        overlap = len(set(route) & set(base)) / max(1, len(set(base)))
        if overlap > 0.90:
            continue

        seen.add(key)
        result.append(route)

        if len(result) >= count:
            break

    return result


def build_type_pool():
    pool = []
    for typ, weight in TYPE_WEIGHTS.items():
        pool.extend([typ] * weight)
    return pool


def generate_for_type(net_file, vehicle_type, vehicle_count, args, rng):
    vclass = VEHICLE_CLASSES[vehicle_type]

    edges, outgoing, connection_count = load_network(
        net_file, vclass
    )

    usable = list(edges.keys())

    if len(usable) < 2:
        raise RuntimeError(
            f"Không đủ edge cho vehicle type '{vehicle_type}' "
            f"(vClass={vclass})."
        )

    vehicles = []
    backup_count = 0

    for i in range(vehicle_count):
        found = False

        for _ in range(args.max_od_attempts):
            start = rng.choice(usable)
            goal = rng.choice(usable)

            if start == goal:
                continue

            base = shortest_path(
                start, goal, edges, outgoing
            )

            if not base:
                continue

            if route_length(base, edges) < args.min_distance:
                continue

            found = True
            break

        if not found:
            continue

        alternatives = make_alternatives(
            start,
            goal,
            base,
            edges,
            outgoing,
            rng,
            args.alternatives,
            args.max_detour,
        )

        backup_count += len(alternatives)

        route = base

        if alternatives and rng.random() < args.alt_prob:
            route = rng.choice(alternatives)

        vehicles.append({
            "type": vehicle_type,
            "depart": rng.uniform(
                0,
                max(0.0, args.end - 1)
            ),
            "route": route,
        })

    return vehicles, len(edges), connection_count, backup_count


def write_routes(output, vehicles):
    root = ET.Element("routes")

    # IMPORTANT:
    # No <vType> is written here.
    # The existing vehicles.rou.xml owns all vType definitions.

    for i, vehicle in enumerate(
        sorted(vehicles, key=lambda x: x["depart"])
    ):
        v = ET.SubElement(
            root,
            "vehicle",
            {
                "id": str(i),
                "type": vehicle["type"],
                "depart": f'{vehicle["depart"]:.1f}',
                "departLane": "best",
                "departSpeed": "max",
            },
        )

        ET.SubElement(
            v,
            "route",
            {
                "edges": " ".join(vehicle["route"])
            },
        )

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(
        output,
        encoding="utf-8",
        xml_declaration=True
    )


def main():
    ap = argparse.ArgumentParser(
        description="SUMO permission-aware graph route generator"
    )

    ap.add_argument("-n", "--net-file", required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("-v", "--vehicles", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--end", type=float, default=3600)
    ap.add_argument("--min-distance", type=float, default=300)
    ap.add_argument("--alternatives", type=int, default=3)
    ap.add_argument("--max-detour", type=float, default=1.60)
    ap.add_argument("--alt-prob", type=float, default=0.75)
    ap.add_argument("--max-od-attempts", type=int, default=5000)

    args = ap.parse_args()
    rng = random.Random(args.seed)

    type_pool = build_type_pool()

    # Pre-assign vehicle classes according to weights.
    assigned_types = [
        rng.choice(type_pool)
        for _ in range(args.vehicles)
    ]

    by_type = defaultdict(list)
    for idx, typ in enumerate(assigned_types):
        by_type[typ].append(idx)

    all_vehicles = []
    total_backups = 0

    print("============================================")
    print("SUMO PERMISSION-AWARE ROUTE GENERATOR")
    print("============================================")

    for vehicle_type, indices in by_type.items():
        print(
            f"\n[{vehicle_type}] "
            f"count={len(indices)} "
            f"vClass={VEHICLE_CLASSES[vehicle_type]}"
        )

        generated, edge_count, conn_count, backups = generate_for_type(
            args.net_file,
            vehicle_type,
            len(indices),
            args,
            rng,
        )

        total_backups += backups
        all_vehicles.extend(generated)

        print("  usable edges:", edge_count)
        print("  usable connections:", conn_count)
        print("  generated:", len(generated))
        print("  backup routes:", backups)

    # Randomize IDs after all vehicle types have been generated.
    rng.shuffle(all_vehicles)

    write_routes(args.output, all_vehicles)

    print("\n============================================")
    print("DONE")
    print("============================================")
    print("Requested vehicles:", args.vehicles)
    print("Generated vehicles:", len(all_vehicles))
    print("Backup routes found:", total_backups)
    print("Output:", args.output)
    print("\nNOTE:")
    print("vType is NOT written to routes.rou.xml.")
    print("Vehicle types must already exist in vehicles.rou.xml.")


if __name__ == "__main__":
    main()
