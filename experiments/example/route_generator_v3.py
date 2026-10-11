import argparse
import random
import xml.etree.ElementTree as ET
from collections import defaultdict
from heapq import heappush, heappop


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


def tokens(value):
    if not value:
        return set()
    return set(value.replace(",", " ").split())


def permission_ok(attrs, vclass):
    allow = tokens(attrs.get("allow"))
    disallow = tokens(attrs.get("disallow"))

    if allow and vclass not in allow:
        return False

    if vclass in disallow:
        return False

    return True


def load_network(net_file, vclass):

    root = ET.parse(net_file).getroot()

    edges = {}
    usable = set()

    # -----------------------------
    # Load usable edges
    # -----------------------------

    for e in root.findall("edge"):

        eid = e.get("id")
        frm = e.get("from")
        to = e.get("to")

        if (
            not eid
            or eid.startswith(":")
            or not frm
            or not to
        ):
            continue

        lanes = e.findall("lane")

        if not lanes:
            continue

        allowed_lanes = [
            lane
            for lane in lanes
            if permission_ok(lane, vclass)
        ]

        if not allowed_lanes:
            continue

        best_lane = min(
            allowed_lanes,
            key=lambda lane:
                float(lane.get("length", "1"))
                /
                max(
                    float(lane.get("speed", "13.9")),
                    0.1
                )
        )

        edges[eid] = {
            "from": frm,
            "to": to,
            "length": float(
                best_lane.get("length", "1")
            ),
            "speed": float(
                best_lane.get("speed", "13.9")
            ),
            "lanes": {
                lane.get("index")
                for lane in allowed_lanes
            },
        }

        usable.add(eid)

    # -----------------------------
    # Load legal edge transitions
    # -----------------------------

    transitions = defaultdict(list)

    for c in root.findall("connection"):

        a = c.get("from")
        b = c.get("to")

        if a not in usable or b not in usable:
            continue

        if not permission_ok(c, vclass):
            continue

        from_lane = c.get("fromLane")

        if from_lane is not None:

            if from_lane not in edges[a]["lanes"]:
                continue

        transitions[a].append(b)

    # -----------------------------
    # Fallback topology
    # -----------------------------

    if not transitions:

        for a, ea in edges.items():

            transitions[a] = [
                b
                for b, eb in edges.items()
                if ea["to"] == eb["from"]
            ]

    for a in list(transitions):

        transitions[a] = list(
            dict.fromkeys(
                b
                for b in transitions[a]
                if b in edges
            )
        )

    return edges, transitions


# ============================================================
# SHORTEST PATH
# ============================================================

def shortest_path(
    start,
    goal,
    edges,
    transitions,
    banned=None
):

    banned = set(banned or [])

    queue = [
        (0.0, start)
    ]

    dist = {
        start: 0.0
    }

    previous = {}

    while queue:

        cost, current = heappop(queue)

        if cost != dist.get(current):
            continue

        if current == goal:
            break

        for nxt in transitions.get(
            current,
            []
        ):

            if nxt in banned:
                continue

            edge = edges[nxt]

            weight = (
                edge["length"]
                /
                max(edge["speed"], 0.1)
            )

            new_cost = cost + weight

            if new_cost < dist.get(
                nxt,
                float("inf")
            ):

                dist[nxt] = new_cost

                previous[nxt] = current

                heappush(
                    queue,
                    (
                        new_cost,
                        nxt
                    )
                )

    if goal not in dist:
        return None

    route = []

    current = goal

    while current != start:

        route.append(current)

        current = previous[current]

    route.append(start)

    route.reverse()

    return route


# ============================================================
# ROUTE VALIDATION
# ============================================================

def valid_route(
    route,
    edges,
    transitions
):

    if not route:
        return False

    for a, b in zip(
        route,
        route[1:]
    ):

        if b not in transitions.get(
            a,
            []
        ):
            return False

    return all(
        e in edges
        for e in route
    )


def route_length(
    route,
    edges
):

    return sum(
        edges[e]["length"]
        for e in route
    )


# ============================================================
# BACKUP ROUTES
# ============================================================

def generate_backups(
    start,
    goal,
    base,
    edges,
    transitions,
    rng,
    count,
    max_detour
):

    backups = []

    seen = {
        tuple(base)
    }

    base_length = route_length(
        base,
        edges
    )

    if len(base) < 3:
        return backups

    for _ in range(
        max(
            20,
            count * 15
        )
    ):

        banned = set()

        indexes = list(
            range(
                1,
                len(base) - 1
            )
        )

        rng.shuffle(indexes)

        block_count = max(
            1,
            min(
                3,
                len(indexes)
            )
        )

        for idx in indexes[
            :block_count
        ]:

            banned.add(
                base[idx]
            )

        candidate = shortest_path(
            start,
            goal,
            edges,
            transitions,
            banned
        )

        if not candidate:
            continue

        key = tuple(candidate)

        if key in seen:
            continue

        if not valid_route(
            candidate,
            edges,
            transitions
        ):
            continue

        candidate_length = route_length(
            candidate,
            edges
        )

        if (
            candidate_length
            >
            base_length * max_detour
        ):
            continue

        overlap = (
            len(
                set(candidate)
                &
                set(base)
            )
            /
            max(
                1,
                len(set(base))
            )
        )

        if overlap > 0.90:
            continue

        seen.add(key)

        backups.append(candidate)

        if len(backups) >= count:
            break

    return backups


# ============================================================
# RANDOM WALK
# ============================================================

def random_walk_route(
    start,
    edges,
    transitions,
    rng,
    min_edges,
    max_edges
):

    route = [
        start
    ]

    current = start

    for _ in range(max_edges - 1):

        next_edges = [
            e
            for e in transitions.get(
                current,
                []
            )
        ]

        if not next_edges:
            break

        # Prefer not to immediately repeat an edge.
        non_repeat = [
            e
            for e in next_edges
            if e != current
        ]

        if non_repeat:
            next_edges = non_repeat

        current = rng.choice(
            next_edges
        )

        route.append(current)

        # Randomly terminate after minimum length.
        if (
            len(route)
            >= min_edges
            and
            rng.random() < 0.20
        ):
            break

    if len(route) < min_edges:
        return None

    if not valid_route(
        route,
        edges,
        transitions
    ):
        return None

    return route


# ============================================================
# VEHICLE TYPE
# ============================================================

def choose_vehicle_type(rng):

    pool = []

    for typ, weight in TYPE_WEIGHTS.items():

        pool.extend(
            [typ] * weight
        )

    return rng.choice(pool)


# ============================================================
# NORMAL VEHICLE
# ============================================================

def generate_normal(
    edges,
    transitions,
    rng,
    args
):

    usable = list(edges)

    for _ in range(
        args.max_od_attempts
    ):

        start = rng.choice(
            usable
        )

        goal = rng.choice(
            usable
        )

        if start == goal:
            continue

        base = shortest_path(
            start,
            goal,
            edges,
            transitions
        )

        if not base:
            continue

        if (
            route_length(
                base,
                edges
            )
            <
            args.min_distance
        ):
            continue

        backups = generate_backups(
            start,
            goal,
            base,
            edges,
            transitions,
            rng,
            args.alternatives,
            args.max_detour
        )

        chosen = base

        if (
            backups
            and
            rng.random()
            <
            args.alt_prob
        ):

            chosen = rng.choice(
                backups
            )

        return {
            "route": chosen,
            "departPos": None,
            "arrivalPos": None,
            "backup_count": len(backups),
        }

    return None


# ============================================================
# RANDOM ENDPOINT VEHICLE
# ============================================================

def generate_random_endpoint(
    edges,
    transitions,
    rng,
    args
):

    usable = list(edges)

    for _ in range(
        args.max_od_attempts
    ):

        start = rng.choice(
            usable
        )

        goal = rng.choice(
            usable
        )

        if start == goal:
            continue

        route = shortest_path(
            start,
            goal,
            edges,
            transitions
        )

        if not route:
            continue

        # Allow vehicle to start somewhere
        # in the middle of its first edge.
        first_length = edges[
            route[0]
        ]["length"]

        depart_pos = rng.uniform(
            0,
            max(
                0.1,
                first_length * 0.8
            )
        )

        # Allow vehicle to finish somewhere
        # in the middle of its final edge.
        last_length = edges[
            route[-1]
        ]["length"]

        arrival_pos = rng.uniform(
            max(
                0.1,
                last_length * 0.2
            ),
            max(
                0.2,
                last_length * 0.9
            )
        )

        return {
            "route": route,
            "departPos": depart_pos,
            "arrivalPos": arrival_pos,
            "backup_count": 0,
        }

    return None


# ============================================================
# IRREGULAR VEHICLE
# ============================================================

def generate_irregular(
    edges,
    transitions,
    rng,
    args
):

    usable = list(edges)

    for _ in range(
        args.max_od_attempts
    ):

        start = rng.choice(
            usable
        )

        route = random_walk_route(
            start,
            edges,
            transitions,
            rng,
            args.irregular_min_edges,
            args.irregular_max_edges
        )

        if not route:
            continue

        # Random start/end position.
        first_length = edges[
            route[0]
        ]["length"]

        last_length = edges[
            route[-1]
        ]["length"]

        depart_pos = rng.uniform(
            0,
            max(
                0.1,
                first_length * 0.7
            )
        )

        arrival_pos = rng.uniform(
            max(
                0.1,
                last_length * 0.2
            ),
            max(
                0.2,
                last_length * 0.9
            )
        )

        return {
            "route": route,
            "departPos": depart_pos,
            "arrivalPos": arrival_pos,
            "backup_count": 0,
        }

    return None


# ============================================================
# WRITE XML
# ============================================================

def write_routes(
    output,
    vehicles
):

    root = ET.Element(
        "routes"
    )

    # IMPORTANT:
    # Do not create <vType> here.
    # vehicles.rou.xml already owns vTypes.

    vehicles.sort(
        key=lambda x: x["depart"]
    )

    for index, item in enumerate(
        vehicles
    ):

        attrs = {
            "id": str(index),
            "type": item["type"],
            "depart": f'{item["depart"]:.1f}',
            "departLane": "best",
            "departSpeed": "max",
        }

        if item["departPos"] is not None:

            attrs[
                "departPos"
            ] = f'{item["departPos"]:.2f}'

        if item["arrivalPos"] is not None:

            attrs[
                "arrivalPos"
            ] = f'{item["arrivalPos"]:.2f}'

        vehicle = ET.SubElement(
            root,
            "vehicle",
            attrs
        )

        ET.SubElement(
            vehicle,
            "route",
            {
                "edges":
                    " ".join(
                        item["route"]
                    )
            }
        )

    tree = ET.ElementTree(
        root
    )

    ET.indent(
        tree,
        space="  "
    )

    tree.write(
        output,
        encoding="utf-8",
        xml_declaration=True
    )


# ============================================================
# MAIN
# ============================================================

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
        default=3000
    )

    parser.add_argument(
        "--end",
        type=float,
        default=3600
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42
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

    # -----------------------------
    # New demand variations
    # -----------------------------

    parser.add_argument(
        "--random-end-percent",
        type=float,
        default=15.0
    )

    parser.add_argument(
        "--irregular-percent",
        type=float,
        default=15.0
    )

    parser.add_argument(
        "--irregular-min-edges",
        type=int,
        default=4
    )

    parser.add_argument(
        "--irregular-max-edges",
        type=int,
        default=20
    )

    parser.add_argument(
        "--max-od-attempts",
        type=int,
        default=5000
    )

    args = parser.parse_args()

    if (
        args.random_end_percent
        +
        args.irregular_percent
        > 100
    ):
        raise ValueError(
            "random-end-percent + irregular-percent "
            "phải <= 100"
        )

    rng = random.Random(
        args.seed
    )

    # -----------------------------
    # Build graph per vehicle class
    # -----------------------------

    graphs = {}

    for vehicle_type, vclass in VEHICLE_CLASSES.items():

        edges, transitions = load_network(
            args.net_file,
            vclass
        )

        graphs[
            vehicle_type
        ] = (
            edges,
            transitions
        )

        print(
            f"[{vehicle_type}] "
            f"vClass={vclass} "
            f"usableEdges={len(edges)}"
        )

    # -----------------------------
    # Demand split
    # -----------------------------

    random_count = round(
        args.vehicles
        *
        args.random_end_percent
        /
        100
    )

    irregular_count = round(
        args.vehicles
        *
        args.irregular_percent
        /
        100
    )

    normal_count = (
        args.vehicles
        -
        random_count
        -
        irregular_count
    )

    print()
    print(
        "=========================================="
    )
    print(
        "DEMAND"
    )
    print(
        "=========================================="
    )

    print(
        "Total:",
        args.vehicles
    )

    print(
        "Normal:",
        normal_count
    )

    print(
        "Random endpoint:",
        random_count
    )

    print(
        "Irregular:",
        irregular_count
    )

    vehicles = []

    backup_total = 0

    # ========================================================
    # NORMAL
    # ========================================================

    for _ in range(
        normal_count
    ):

        vehicle_type = choose_vehicle_type(
            rng
        )

        edges, transitions = graphs[
            vehicle_type
        ]

        item = generate_normal(
            edges,
            transitions,
            rng,
            args
        )

        if item is None:
            continue

        item["type"] = vehicle_type

        item["depart"] = rng.uniform(
            0,
            max(
                0,
                args.end - 1
            )
        )

        vehicles.append(
            item
        )

        backup_total += item[
            "backup_count"
        ]

    # ========================================================
    # RANDOM ENDPOINT
    # ========================================================

    for _ in range(
        random_count
    ):

        vehicle_type = choose_vehicle_type(
            rng
        )

        edges, transitions = graphs[
            vehicle_type
        ]

        item = generate_random_endpoint(
            edges,
            transitions,
            rng,
            args
        )

        if item is None:
            continue

        item["type"] = vehicle_type

        item["depart"] = rng.uniform(
            0,
            max(
                0,
                args.end - 1
            )
        )

        vehicles.append(
            item
        )

    # ========================================================
    # IRREGULAR
    # ========================================================

    for _ in range(
        irregular_count
    ):

        vehicle_type = choose_vehicle_type(
            rng
        )

        edges, transitions = graphs[
            vehicle_type
        ]

        item = generate_irregular(
            edges,
            transitions,
            rng,
            args
        )

        if item is None:
            continue

        item["type"] = vehicle_type

        item["depart"] = rng.uniform(
            0,
            max(
                0,
                args.end - 1
            )
        )

        vehicles.append(
            item
        )

    # ========================================================
    # WRITE
    # ========================================================

    write_routes(
        args.output,
        vehicles
    )

    print()
    print(
        "=========================================="
    )
    print(
        "ROUTE GENERATION COMPLETE"
    )
    print(
        "=========================================="
    )

    print(
        "Requested:",
        args.vehicles
    )

    print(
        "Generated:",
        len(vehicles)
    )

    print(
        "Backup routes:",
        backup_total
    )

    print(
        "Output:",
        args.output
    )


if __name__ == "__main__":
    main()