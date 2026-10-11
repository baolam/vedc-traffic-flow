import argparse
import random
import xml.etree.ElementTree as ET
from collections import defaultdict
from heapq import heappush, heappop


def load_net(path):
    root = ET.parse(path).getroot()

    nodes = {j.get("id") for j in root.findall("junction") if j.get("id")}

    edges = {}
    outgoing = defaultdict(list)

    for e in root.findall("edge"):
        eid = e.get("id")
        frm = e.get("from")
        to = e.get("to")

        if not eid or eid.startswith(":") or not frm or not to:
            continue

        lanes = e.findall("lane")
        if not lanes:
            continue

        length = float(lanes[0].get("length", "1"))
        speed = float(lanes[0].get("speed", "13.9"))

        edges[eid] = {
            "from": frm,
            "to": to,
            "length": length,
            "speed": speed,
        }

        outgoing[frm].append(eid)

    return nodes, edges, outgoing


def shortest_path(start, goal, edges, outgoing, banned=None):
    banned = set(banned or [])

    pq = [(0.0, start)]
    dist = {start: 0.0}
    previous = {}

    while pq:
        cost, node = heappop(pq)

        if cost != dist.get(node):
            continue

        if node == goal:
            break

        for edge_id in outgoing.get(node, []):
            if edge_id in banned:
                continue

            edge = edges[edge_id]

            next_node = edge["to"]
            travel_time = edge["length"] / max(edge["speed"], 0.1)
            new_cost = cost + travel_time

            if new_cost < dist.get(next_node, float("inf")):
                dist[next_node] = new_cost
                previous[next_node] = edge_id
                heappush(pq, (new_cost, next_node))

    if goal not in dist:
        return None

    route = []
    current = goal

    while current != start:
        edge_id = previous[current]
        route.append(edge_id)
        current = edges[edge_id]["from"]

    route.reverse()

    return route


def route_length(route, edges):
    return sum(edges[e]["length"] for e in route)


def valid_route(route, edges):
    if not route:
        return False

    for a, b in zip(route, route[1:]):
        if edges[a]["to"] != edges[b]["from"]:
            return False

    return True


def generate_alternatives(
    start,
    goal,
    base_route,
    edges,
    outgoing,
    rng,
    count,
    max_detour
):
    alternatives = []
    seen = {tuple(base_route)}

    if len(base_route) < 3:
        return alternatives

    base_length = route_length(base_route, edges)

    for _ in range(count * 10):

        banned = set()

        candidates = list(range(1, len(base_route) - 1))
        rng.shuffle(candidates)

        number_to_block = max(
            1,
            min(3, len(base_route) // 8)
        )

        for index in candidates[:number_to_block]:
            banned.add(base_route[index])

        route = shortest_path(
            start,
            goal,
            edges,
            outgoing,
            banned
        )

        if not route:
            continue

        if tuple(route) in seen:
            continue

        if not valid_route(route, edges):
            continue

        new_length = route_length(route, edges)

        if new_length > base_length * max_detour:
            continue

        overlap = (
            len(set(route) & set(base_route))
            / max(1, len(set(base_route)))
        )

        if overlap > 0.90:
            continue

        seen.add(tuple(route))
        alternatives.append(route)

        if len(alternatives) >= count:
            break

    return alternatives


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-n",
        "--net-file",
        required=True
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True
    )

    parser.add_argument(
        "-v",
        "--vehicles",
        type=int,
        default=1000
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42
    )

    parser.add_argument(
        "--end",
        type=float,
        default=3600
    )

    parser.add_argument(
        "--min-distance",
        type=float,
        default=300
    )

    parser.add_argument(
        "--alternatives",
        type=int,
        default=3
    )

    parser.add_argument(
        "--max-detour",
        type=float,
        default=1.60
    )

    parser.add_argument(
        "--alt-prob",
        type=float,
        default=0.75
    )

    args = parser.parse_args()

    rng = random.Random(args.seed)

    nodes, edges, outgoing = load_net(args.net_file)

    print("Nodes:", len(nodes))
    print("Edges:", len(edges))

    starts = [
        node
        for node in nodes
        if outgoing.get(node)
    ]

    vehicles = []

    vehicle_types = [
        ("motorcycle", 65),
        ("car", 25),
        ("taxi", 4),
        ("bus", 3),
        ("truck", 3),
    ]

    type_pool = []

    for vehicle_type, weight in vehicle_types:
        type_pool.extend(
            [vehicle_type] * weight
        )

    backup_count = 0

    for vehicle_index in range(args.vehicles):

        found = False

        for _ in range(5000):

            start = rng.choice(starts)
            goal = rng.choice(list(nodes))

            if start == goal:
                continue

            base_route = shortest_path(
                start,
                goal,
                edges,
                outgoing
            )

            if not base_route:
                continue

            if route_length(
                base_route,
                edges
            ) < args.min_distance:
                continue

            found = True
            break

        if not found:
            raise RuntimeError(
                "Không tìm được OD pair phù hợp. "
                "Hãy giảm --min-distance hoặc --vehicles."
            )

        alternatives = generate_alternatives(
            start,
            goal,
            base_route,
            edges,
            outgoing,
            rng,
            args.alternatives,
            args.max_detour
        )

        backup_count += len(alternatives)

        chosen_route = base_route

        if alternatives and rng.random() < args.alt_prob:
            chosen_route = rng.choice(alternatives)

        depart = rng.uniform(
            0,
            max(0, args.end - 1)
        )

        vehicles.append(
            {
                "id": str(vehicle_index),
                "type": rng.choice(type_pool),
                "depart": depart,
                "route": chosen_route,
            }
        )

    vehicles.sort(
        key=lambda x: x["depart"]
    )

    root = ET.Element("routes")

    # QUAN TRỌNG:
    # Không tạo <vType> ở đây.
    # vType đã nằm trong vehicles.rou.xml.

    for vehicle in vehicles:

        element = ET.SubElement(
            root,
            "vehicle",
            {
                "id": vehicle["id"],
                "type": vehicle["type"],
                "depart": f'{vehicle["depart"]:.1f}',
                "departLane": "best",
                "departSpeed": "max",
            }
        )

        ET.SubElement(
            element,
            "route",
            {
                "edges": " ".join(
                    vehicle["route"]
                )
            }
        )

    tree = ET.ElementTree(root)

    ET.indent(
        tree,
        space="  "
    )

    tree.write(
        args.output,
        encoding="utf-8",
        xml_declaration=True
    )

    print()
    print("================================")
    print("ROUTE GENERATION COMPLETED")
    print("================================")
    print("Nodes:", len(nodes))
    print("Edges:", len(edges))
    print("Vehicles:", len(vehicles))
    print("Backup routes found:", backup_count)
    print("Output:", args.output)


if __name__ == "__main__":
    main()