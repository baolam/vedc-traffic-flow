"""Inspect and derive HCM inputs without changing geometry or green priorities."""
import heapq
import html
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

import sumolib

from contracts.hcm_qualification_v3 import PROTOCOL, TOPOLOGY_ID
from .build_network import write_xml


def signal_kind(state):
    if any(c in state for c in "yY"):
        return "yellow"
    if any(c in state for c in "Gg"):
        return "green"
    if state and set(state) == {"r"}:
        return "all_red"
    raise ValueError(f"Unsupported signal state: {state}")


def service_stages(logic):
    return [(i, p) for i, p in enumerate(logic.findall("phase"))
            if signal_kind(p.get("state")) == "green"]


def derived_phases(logic):
    phases = []
    for source_index, p in service_stages(logic):
        state = p.get("state")
        if not set(state) <= set("rGg"):
            raise ValueError(f"Unsupported service stage {state}")
        green = max(PROTOCOL["min_green_s"], min(PROTOCOL["max_green_s"], float(p.get("duration"))))
        phases.extend([
            {"duration": green, "state": state, "source_index": source_index},
            {"duration": PROTOCOL["yellow_s"], "state": "".join("y" if c in "Gg" else "r" for c in state)},
            {"duration": PROTOCOL["all_red_s"], "state": "r" * len(state)},
        ])
    if not phases:
        raise ValueError(f"No service stages for {logic.get('id')}")
    return phases


def load_network(path):
    return sumolib.net.readNet(str(path), withInternal=True, withConnections=True, withFoes=True)


def road_edges(net):
    return sorted((e for e in net.getEdges() if e.getFunction() != "internal"), key=lambda e: e.getID())


def connections(edge, vclass=None, straight=False):
    return sorted((c for cs in edge.getOutgoing().values() for c in cs
                   if c.getDirection() != "t" and (not straight or c.getDirection() == "s")
                   and (vclass is None or (c.allows(vclass) and c.getFromLane().allows(vclass) and c.getToLane().allows(vclass)))
                   and c.getTo().getFunction() != "internal"),
                  key=lambda c: (c.getTo().getID(), c.getFromLane().getID(), c.getToLane().getID()))


def valid_route(net, ids, vclass):
    if len(ids) < 2 or len(ids) != len(set(ids)):
        return False
    try:
        edges = [net.getEdge(e) for e in ids]
    except KeyError:
        return False
    if any(e.getFunction() == "internal" or not any(l.allows(vclass) for l in e.getLanes()) for e in edges):
        return False
    # Carry possible lanes through each connection; this also handles multi-lane fixtures.
    reachable = {l.getID() for l in edges[0].getLanes() if l.allows(vclass)}
    for a, b in zip(edges, edges[1:]):
        # Lane changes on a road are permitted, but every traversed connection must allow the class.
        reachable = {c.getToLane().getID() for c in connections(a, vclass)
                     if c.getTo() == b and c.getFromLane().allows(vclass)
                     and c.getToLane().allows(vclass) and reachable
                     and (not c.getViaLaneID() or net.getLane(c.getViaLaneID()).allows(vclass))}
        if not reachable:
            return False
    return True


def controlled_visits(net, ids, mapping):
    visits = []
    for a, b in zip(ids, ids[1:]):
        tls = sorted({c.getTLSID() for c in connections(net.getEdge(a))
                      if c.getTo().getID() == b and c.getTLSID() in mapping})
        visits.extend(mapping[t] for t in tls)
    return list(dict.fromkeys(visits))


def signal_paths(net, mapping):
    """Road paths end at the next controller, traversing unsignalized junctions."""
    results = []
    for tls, nid in sorted(mapping.items()):
        starts = {c.getTo().getID() for e in road_edges(net) for c in connections(e) if c.getTLSID() == tls}
        heap = [(net.getEdge(e).getLength(), (e,)) for e in sorted(starts)]
        heapq.heapify(heap)
        best = {}
        found = set()
        while heap:
            length, path = heapq.heappop(heap)
            eid = path[-1]
            if eid in best:
                continue
            best[eid] = length
            for c in connections(net.getEdge(eid)):
                target = c.getTLSID()
                if target in mapping:
                    key = (mapping[target], path)
                    if target != tls and key not in found:
                        results.append({"edge_id": f"{nid}_TO_{mapping[target]}_PATH_{len(found)+1}",
                                        "from_node": nid, "to_node": mapping[target],
                                        "sumo_road_path": list(path), "length_m": round(length, 6)})
                        found.add(key)
                    continue
                nxt = c.getTo().getID()
                if nxt not in path:
                    heapq.heappush(heap, (length + c.getTo().getLength(), path + (nxt,)))
    return sorted(results, key=lambda x: (x["from_node"], x["to_node"], x["sumo_road_path"]))


def longest_corridor(net, mapping):
    # A through-road corridor excludes turning branches; enumerate its simple chains exactly.
    candidates = []

    def walk(path, nodes, length):
        advanced = False
        for c in connections(net.getEdge(path[-1]), straight=True):
            eid = c.getTo().getID()
            nid = mapping.get(c.getTLSID())
            if eid in path or (nid and nid in nodes):
                continue
            advanced = True
            walk(path + [eid], nodes + ([nid] if nid else []), length + c.getTo().getLength())
        if not advanced and len(nodes) >= 2:
            candidates.append((length, tuple(nodes), tuple(path)))

    for edge in road_edges(net):
        walk([edge.getID()], [], edge.getLength())
    if not candidates:
        raise ValueError("No through-road signal corridor")
    length, nodes, path = sorted(candidates, key=lambda x: (-x[0], x[1], x[2]))[0]
    forward = list(zip(path, path[1:]))
    reverse = []
    for a, b in reversed(forward):
        ea, eb = net.getEdge(a), net.getEdge(b)
        reverse_a = [e for e in road_edges(net) if e.getFromNode() == eb.getToNode() and e.getToNode() == eb.getFromNode()]
        reverse_b = [e for e in road_edges(net) if e.getFromNode() == ea.getToNode() and e.getToNode() == ea.getFromNode()]
        reverse.extend((x.getID(), y.getID()) for x in reverse_a for y in reverse_b
                       if any(c.getTo() == y for c in connections(x)))
    return {"length_m": length, "nodes": list(nodes), "road_path": list(path),
            "forward_movements": forward, "reverse_movements": reverse,
            "definition": PROTOCOL["corridor_definition"]}


def inspect_network(path):
    net = load_network(path)
    root = ET.parse(path).getroot()
    logics = root.findall("tlLogic")
    tids = sorted({t.get("id") for t in logics})
    if len(tids) != len(logics):
        raise ValueError("Expected one imported program per signal controller")
    mapping = {tid: f"J{i+1:02d}" for i, tid in enumerate(tids)}
    errors, nodes = [], []
    for logic in sorted(logics, key=lambda t: t.get("id")):
        tid, nid = logic.get("id"), mapping[logic.get("id")]
        links = [c for e in road_edges(net) for cs in e.getOutgoing().values() for c in cs if c.getTLSID() == tid]
        phases = derived_phases(logic)
        indices = {c.getTLLinkIndex() for c in links}
        width = len(phases[0]["state"])
        if indices != set(range(width)) or any(len(p["state"]) != width for p in phases):
            errors.append(f"{nid}: noncontiguous or invalid signal mapping")
        served = {i for p in phases[::3] for i, c in enumerate(p["state"]) if c in "Gg"}
        if served != indices:
            errors.append(f"{nid}: unserved links {sorted(indices-served)}")
        conflicts = []
        for p in phases[::3]:
            protected = [c for c in links if p["state"][c.getTLLinkIndex()] == "G"]
            for i, a in enumerate(protected):
                for b in protected[i+1:]:
                    junction = a.getFrom().getToNode()
                    if junction == b.getFrom().getToNode() and junction.areFoes(a.getJunctionIndex(), b.getJunctionIndex()):
                        conflicts.append([a.getTLLinkIndex(), b.getTLLinkIndex(), p["source_index"]])
        if conflicts:
            errors.append(f"{nid}: conflicting protected greens {conflicts}")
        junctions = sorted({c.getFrom().getToNode().getID() for c in links})
        incoming = sorted({c.getFrom().getID() for c in links})
        approaches = {eid: f"{nid}_IN_{i+1:02d}" for i, eid in enumerate(incoming)}
        node = {"node_id": nid, "name": f"HCM controller {nid}", "sumo_tls_id": tid,
                "sumo_junction_ids": junctions, "approaches": list(approaches.values()),
                "approach_mapping": approaches, "signal_count": width, "phases": [],
                "derived_phases": phases, "protected_conflicts": conflicts,
                "coordinates": [list(net.getNode(j).getCoord()) for j in junctions]}
        node["sumo_links"] = [{"link_index": c.getTLLinkIndex(), "from_edge": c.getFrom().getID(),
                               "to_edge": c.getTo().getID(), "from_lane": c.getFromLane().getID(),
                               "to_lane": c.getToLane().getID(), "via_lane": c.getViaLaneID(),
                               "direction": c.getDirection()} for c in links]
        for i, p in enumerate(phases[::3]):
            movements = [{"movement_id": f"{nid}_LINK_{c.getTLLinkIndex():02d}",
                          "from_approach": approaches[c.getFrom().getID()], "to_edge": c.getTo().getID(),
                          "link_index": c.getTLLinkIndex(), "priority": p["state"][c.getTLLinkIndex()]}
                         for c in links if p["state"][c.getTLLinkIndex()] in "Gg"]
            node["phases"].append({"phase_id": f"{nid}_STAGE_{i+1:02d}", "sumo_phase_index": i*3,
                                   "imported_phase_index": p["source_index"], "sumo_state": p["state"],
                                   "nominal_green_s": p["duration"], "movements": movements,
                                   "approaches": sorted({m["from_approach"] for m in movements})})
        nodes.append(node)
    roads = [{"sumo_edge_id": e.getID(), "from": e.getFromNode().getID(), "to": e.getToNode().getID(),
              "length_m": e.getLength(), "lane_count": e.getLaneNumber(),
              "lanes": [{"id": l.getID(), "length_m": l.getLength(), "speed_mps": l.getSpeed(),
                         "permissions": sorted(l.getPermissions())} for l in e.getLanes()],
              "successors_without_uturn": sorted({c.getTo().getID() for c in connections(e)})} for e in road_edges(net)]
    short = [r["sumo_edge_id"] for r in roads if r["length_m"] < 30]
    if len(nodes) != PROTOCOL["expected_controllers"] or len(roads) != PROTOCOL["expected_road_edges"]:
        errors.append("Network dimensions do not match protocol")
    if any(not 2 <= len(n["phases"]) <= 4 for n in nodes):
        errors.append("Service-stage count outside 2–4")
    topology = {"topology_id": TOPOLOGY_ID, "version": "3.0", "nodes": nodes,
                "edges": signal_paths(net, mapping), "sumo_to_canonical": mapping,
                "road_network": roads, "corridor": longest_corridor(net, mapping)}
    audit = {"controllers": len(nodes), "road_edges": len(roads), "signal_counts": {n["node_id"]: n["signal_count"] for n in nodes},
             "stage_counts": {n["node_id"]: len(n["phases"]) for n in nodes},
             "short_edges_under_30m": short, "errors": errors,
             "limitations": ["Signal locations are inferred; field validity is unknown.",
                             "Local geometry repairs are simulation engineering corrections. Lane counts, permissions and controllers are retained.",
                             "Demand is synthetic and does not establish agreement with measured HCM traffic."],
             "unsignalized_junctions": sorted(j.get("id") for j in root.findall("junction")
                                               if not j.get("id").startswith(":") and j.get("id") not in tids)}
    audit["questionable_inferred_signals"] = [{"controller": n["node_id"], "sumo_tls_id": n["sumo_tls_id"],
        "field_verified": False, "short_adjacent_roads": sorted({link[key] for link in n["sumo_links"]
        for key in ("from_edge", "to_edge") if link[key] in short})} for n in nodes]
    adjacency = {r["sumo_edge_id"]: set(r["successors_without_uturn"]) for r in roads}
    undirected = {e: set(targets) for e, targets in adjacency.items()}
    for e, targets in adjacency.items():
        for target in targets:
            undirected[target].add(e)
    components, unseen = [], set(undirected)
    while unseen:
        pending, component = [min(unseen)], set()
        while pending:
            e = pending.pop()
            if e not in component:
                component.add(e)
                pending.extend(undirected[e]-component)
        unseen -= component
        components.append(sorted(component))
    audit["road_connection_components_without_uturn"] = components
    return net, topology, audit


def write_programs(topology, output):
    for controller in PROTOCOL["controllers"]:
        root = ET.Element("additional")
        for node in topology["nodes"]:
            actuated = controller == "native_actuated"
            logic = ET.SubElement(root, "tlLogic", id=node["sumo_tls_id"], programID=controller,
                                  offset="0", type="actuated" if actuated else "static")
            if actuated:
                for key, value in (("max-gap", PROTOCOL["actuation_gap_s"]),
                                   ("jam-threshold", PROTOCOL["actuation_jam_threshold_s"]),
                                   ("build-all-detectors", "true")):
                    ET.SubElement(logic, "param", key=key, value=str(value))
            for i, p in enumerate(node["derived_phases"]):
                attrs = {"state": p["state"], "duration": str(p["duration"]),
                         "next": str((i+1) % len(node["derived_phases"]))}
                if actuated and i % 3 == 0:
                    attrs.update(minDur=str(PROTOCOL["min_green_s"]), maxDur=str(PROTOCOL["max_green_s"]))
                ET.SubElement(logic, "phase", **attrs)
        write_xml(root, Path(output) / f"{controller}.add.xml")


def labeled_map(net, topology, path):
    edges = road_edges(net)
    coords = [xy for e in edges for xy in e.getShape()]
    xmin, ymin = min(x for x, y in coords), min(y for x, y in coords)
    xmax, ymax = max(x for x, y in coords), max(y for x, y in coords)
    scale = min(850 / (xmax-xmin), 1200 / (ymax-ymin))

    def point(xy):
        return (60 + (xy[0]-xmin)*scale, 70+(ymax-xy[1])*scale)

    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1900" height="2100" viewBox="0 0 1900 2100">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<text x="40" y="30" font-family="sans-serif" font-size="22">HCM reconstructed neighborhood: 29 controllers, 126 road edges</text>']
    for e in edges:
        points = [point(xy) for xy in e.getShape()]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        label = html.escape(f"{e.getID()}: {e.getLength():.1f} m")
        svg.append(f'<g><title>{label}</title><polyline points="{line}" stroke="#999" stroke-width="2" fill="none"/>'
                   '</g>')
    label_boxes = []
    for n in topology["nodes"]:
        for xy in n["coordinates"]:
            x, y = point(xy)
            for dx, dy in ((8, -8), (8, 18), (-35, -8), (-35, 18), (8, -25), (8, 35), (-35, -25), (-35, 35)):
                box = (x+dx, y+dy-13, x+dx+30, y+dy+3)
                if not any(box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1] for b in label_boxes):
                    break
            label_boxes.append(box)
            svg.append(f'<g><title>{html.escape(n["sumo_tls_id"])}</title><circle cx="{x}" cy="{y}" r="6" fill="#2166ac"/>'
                       f'<text x="{x+dx}" y="{y+dy}" font-family="sans-serif" font-size="13" font-weight="bold" stroke="white" stroke-width="3" paint-order="stroke">'
                       f'{n["node_id"]}</text></g>')
    svg.append('<text x="1000" y="65" font-family="sans-serif" font-size="18" font-weight="bold">Controlled junctions: signals / service stages / imported controller</text>')
    for i, n in enumerate(topology["nodes"]):
        text = html.escape(f'{n["node_id"]}: {n["signal_count"]} signals / {len(n["phases"])} stages / {n["sumo_tls_id"]}')
        svg.append(f'<text x="1000" y="{95+i*20}" font-family="sans-serif" font-size="13">{text}</text>')
    svg.append('<text x="1000" y="720" font-family="sans-serif" font-size="18" font-weight="bold">Directed road edge lengths (metres)</text>')
    for i, e in enumerate(edges):
        x, y = 1000+(i//63)*440, 750+(i%63)*18
        svg.append(f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="13">{html.escape(e.getID())}</text>')
        svg.append(f'<text x="{x+300}" y="{y}" font-family="sans-serif" font-size="13">{e.getLength():.2f} m</text>')
    svg.append('<text x="40" y="2000" font-family="sans-serif" font-size="14">Blue: controlled junction. Hover roads for SUMO IDs and lengths. Complete signal counts and road lengths are listed at right.</text>')
    svg.append('<text x="40" y="2025" font-family="sans-serif" font-size="14">Signals are inferred. Geometry, road lengths, lane counts, and locations are preserved from the imported network.</text></svg>')
    Path(path).write_text("\n".join(svg), encoding="utf-8")
