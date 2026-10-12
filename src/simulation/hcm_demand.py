"""Exact-count, permission-aware seeded synthetic boundary OD demand."""
import copy
import heapq
import random
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

from contracts.hcm_qualification_v3 import PROTOCOL
from .build_network import write_xml
from .hcm_network import connections, controlled_visits, road_edges, valid_route


def type_inventory(type_files, demand_files):
    types = {}
    for path in type_files:
        for t in ET.parse(path).getroot().findall("vType"):
            types[t.get("id")] = t
    counts = Counter(v.get("type", "DEFAULT_VEHTYPE") for path in demand_files
                     for v in ET.parse(path).getroot().findall("vehicle"))
    if not counts or set(counts) - set(types):
        raise ValueError("Imported demand must supply explicit defined vehicle types and proportions")
    return types, counts


def allocate_counts(count, proportions):
    total = sum(proportions.values())
    result = {k: count*v//total for k, v in sorted(proportions.items())}
    order = sorted(proportions, key=lambda k: (-(count*proportions[k] % total), k))
    for k in order[:count-sum(result.values())]:
        result[k] += 1
    return result


def route_pool(net, vclass, mapping):
    edges = [e for e in road_edges(net) if any(l.allows(vclass) for l in e.getLanes())]
    adjacency = {e.getID(): sorted({c.getTo().getID() for c in connections(e, vclass)}) for e in edges}
    incoming = {target for targets in adjacency.values() for target in targets}
    starts = sorted(set(adjacency) - incoming)
    ends = {eid for eid, targets in adjacency.items() if not targets}
    pool = []
    for start in starts:
        heap, visited = [(net.getEdge(start).getLength(), (start,))], set()
        while heap:
            length, route = heapq.heappop(heap)
            eid = route[-1]
            if eid in visited:
                continue
            visited.add(eid)
            if eid in ends and len(route) > 1:
                visits = controlled_visits(net, route, mapping)
                # Define eligible neighborhood OD pairs before sampling; avoid short local trips.
                if len(visits) >= 3 and valid_route(net, route, vclass):
                    pool.append({"edges": list(route), "controllers": visits, "length_m": length})
            for target in adjacency[eid]:
                if target not in route:
                    heapq.heappush(heap, (length + net.getEdge(target).getLength(), route + (target,)))
    if not pool:
        raise ValueError(f"No valid multi-controller boundary OD routes for {vclass}")
    return sorted(pool, key=lambda p: (p["edges"][0], p["edges"][-1], p["edges"]))


def direction(route, corridor):
    movements = set(zip(route, route[1:]))
    f = len(movements.intersection(map(tuple, corridor["forward_movements"])))
    r = len(movements.intersection(map(tuple, corridor["reverse_movements"])))
    return "forward" if f > r else "reverse" if r > f else "other"


def generate_demand(net, topology, types, proportions, pools, count, seed, condition, path):
    if count <= 0 or condition not in PROTOCOL["conditions"] + ["calibration"]:
        raise ValueError("Invalid count or condition")
    rng = random.Random(seed)
    allocations = allocate_counts(count, proportions)
    order = [tid for tid, n in allocations.items() for _ in range(n)]
    rng.shuffle(order)
    root = ET.Element("routes")
    for tid, t in sorted(types.items()):
        vtype = copy.deepcopy(t)
        # Image paths are GUI-only and relative to the imported directory.
        vtype.attrib.pop("imgFile", None)
        root.append(vtype)
    vehicle_routes, visits, dir_counts = {}, Counter(), Counter()
    shifted_candidates = {}
    for vclass, pool in pools.items():
        for favored in ("forward", "reverse"):
            weights = [PROTOCOL["shift_weight"] if direction(p["edges"], topology["corridor"]) == favored else 1 for p in pool]
            if max(weights) == 1:
                raise ValueError(f"No eligible {favored} corridor OD pairs for {vclass}")
            shifted_candidates[vclass, favored] = weights
    for i, tid in enumerate(order):
        depart = (i + rng.random()) * PROTOCOL["demand_s"] / count
        vclass = types[tid].get("vClass", "passenger")
        pool = pools[vclass]
        favored = None
        if condition == "directional_shift":
            if 900 <= depart < 1800:
                favored = "forward"
            elif 1800 <= depart < 2700:
                favored = "reverse"
        item = rng.choices(pool, weights=shifted_candidates[vclass, favored], k=1)[0] if favored else rng.choice(pool)
        if not valid_route(net, item["edges"], vclass):
            raise ValueError(f"Invalid generated route for {tid}")
        vid = f"veh_{i:06d}"
        v = ET.SubElement(root, "vehicle", id=vid, type=tid, depart=f"{depart:.6f}", departLane="best", departSpeed="max")
        ET.SubElement(v, "route", edges=" ".join(item["edges"]))
        vehicle_routes[vid] = item["edges"]
        visits.update(item["controllers"])
        window = "forward_window" if 900 <= depart < 1800 else "reverse_window" if 1800 <= depart < 2700 else "outside"
        dir_counts[window + ":" + direction(item["edges"], topology["corridor"])] += 1
    if len(root.findall("vehicle")) != count:
        raise ValueError("Route generation failed to produce the exact requested count")
    write_xml(root, path)
    fraction = sum(len(controlled_visits(net, r, topology["sumo_to_canonical"])) >= 3 for r in vehicle_routes.values()) / count
    coverage = {n["node_id"]: visits[n["node_id"]] for n in topology["nodes"]}
    return {"scheduled": count, "seed": seed, "condition": condition, "type_counts": allocations,
            "imported_type_counts": dict(proportions), "multi_signal_fraction": fraction,
            "controller_vehicles": coverage,
            "coverage_gate": fraction >= PROTOCOL["multi_signal_fraction"] and min(coverage.values()) >= PROTOCOL["min_controller_vehicles"],
            "corridor_od_counts": dict(dir_counts), "route_population": PROTOCOL["route_population"]}


def select_bottleneck(net, demand):
    usage = Counter(e for v in ET.parse(demand).getroot().findall("vehicle")
                    for e in v.find("route").get("edges").split())
    candidates = [e for e in road_edges(net) if e.getLength() >= PROTOCOL["bottleneck_min_length_m"]
                  and usage[e.getID()] > 0
                  and connections(e) and any(c.getDirection() != "t" for cs in e.getIncoming().values() for c in cs)]
    if not candidates:
        raise ValueError("No route-used internal road edge suitable for a bottleneck")
    edge = sorted(candidates, key=lambda e: (-usage[e.getID()], e.getID()))[0]
    return {"edge_id": edge.getID(), "route_vehicles": usage[edge.getID()], "length_m": edge.getLength(),
            "lane_speeds_mps": {l.getID(): l.getSpeed() for l in edge.getLanes()}}
