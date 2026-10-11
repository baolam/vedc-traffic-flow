"""Local, evidence-backed SUMO repairs built from supported connection inputs.

Generated junctions are published as whole netconvert elements. Conflict
bitstrings are never edited; unrelated generated elements are discarded.
"""
import copy
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import xml.etree.ElementTree as ET

from contracts.hcm_qualification_v3 import PROTOCOL, TOPOLOGY_ID, REPAIR_ORDER
from .build_network import binary, write_xml
from .hcm_network import load_network, derived_phases

ROOT = Path(__file__).resolve().parents[2]
V2_REFERENCE = ROOT / "networks/hcm_neighborhood_benchmark_v3/repair-reference/v2-qualification"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reference_spec(name):
    """Resolve and verify curated v2 inputs without rewriting archived specs."""
    manifest = read(V2_REFERENCE / "relocation.json")
    original = PurePosixPath(manifest["original_output"].replace("\\", "/"))
    spec = read(reference_file(f"cases/{name}/spec.json", manifest))
    for key in ("network", "demand", "program", "topology", "bottleneck_control_trace"):
        if key in spec:
            relative = PurePosixPath(spec[key].replace("\\", "/")).relative_to(original)
            spec[key] = str(reference_file(relative.as_posix(), manifest))
    return spec


def reference_file(name, manifest=None):
    """Resolve one hash-checked file from the curated regression bundle."""
    manifest = manifest or read(V2_REFERENCE / "relocation.json")
    path = (V2_REFERENCE / name).resolve()
    if not path.is_relative_to(V2_REFERENCE.resolve()):
        raise ValueError(f"V2 reference escapes the tracked bundle: {name}")
    relative = path.relative_to(V2_REFERENCE.resolve()).as_posix()
    if not path.is_file() or manifest["files"].get(relative) != sha(path):
        raise ValueError(f"V2 reference is missing or changed: {relative}")
    return path


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def xml_value(element):
    return {"tag": element.tag, "attributes": dict(element.attrib),
            "children": [xml_value(c) for c in element]}


def key(element):
    if element.tag == "connection":
        return (element.tag, *(element.get(k, "") for k in ("from", "to", "fromLane", "toLane")))
    return (element.tag, element.get("id", element.get("name", "")))


def internal_owner(identifier, junctions):
    return next((j for j in sorted(junctions, key=len, reverse=True)
                 if identifier.startswith(":" + j + "_")), None)


def road_connections(root):
    return {key(c): c for c in root.findall("connection") if not c.get("from").startswith(":")}


def affected(element, junctions, incident):
    if element.tag in ("junction", "edge"):
        return (element.get("id") in junctions or internal_owner(element.get("id"), junctions)
                or (element.tag == "edge" and element.get("id") in incident))
    if element.tag == "connection":
        return (element.get("from") in incident and element.get("tl") in junctions
                or internal_owner(element.get("from"), junctions))
    return False


def validate_changes(before, after, junctions):
    """Reject connectivity, permission, timing, node-location and remote edits."""
    old_roads = {e.get("id"): e for e in before.findall("edge") if e.get("function") != "internal"}
    new_roads = {e.get("id"): e for e in after.findall("edge") if e.get("function") != "internal"}
    if old_roads.keys() != new_roads.keys() or len(old_roads) != PROTOCOL["expected_road_edges"]:
        raise ValueError("Road identity/count changed")
    incident = {eid for eid, e in old_roads.items() if e.get("from") in junctions or e.get("to") in junctions}
    for eid, old in old_roads.items():
        new = new_roads[eid]
        if old.attrib != new.attrib or len(old.findall("lane")) != len(new.findall("lane")):
            raise ValueError(f"Road connectivity/attributes changed: {eid}")
        for a, b in zip(old.findall("lane"), new.findall("lane")):
            allowed = {"shape", "length", "endOffset"} if eid in incident else set()
            if {k: v for k, v in a.attrib.items() if k not in allowed} != {k: v for k, v in b.attrib.items() if k not in allowed}:
                raise ValueError(f"Lane count, speed or permissions changed: {eid}")
            if [xml_value(c) for c in a] != [xml_value(c) for c in b]:
                raise ValueError(f"Lane behavior changed: {eid}")
    a, b = road_connections(before), road_connections(after)
    if a.keys() != b.keys():
        raise ValueError("Lane-to-lane connectivity changed")
    for identity, old in a.items():
        new = b[identity]
        for attr in ("tl", "linkIndex", "dir", "allow", "disallow"):
            if old.get(attr) != new.get(attr):
                raise ValueError(f"Movement identity/semantics changed: {identity} {attr}")
    old_tls = {t.get("id"): t for t in before.findall("tlLogic")}
    new_tls = {t.get("id"): t for t in after.findall("tlLogic")}
    if old_tls.keys() != new_tls.keys() or len(old_tls) != PROTOCOL["expected_controllers"]:
        raise ValueError("Controller identities changed")
    for tid, logic in old_tls.items():
        # The source program remains in the publication. Derived programs were
        # supplied to netconvert and are loaded separately for both controllers.
        if xml_value(logic) != xml_value(new_tls[tid]):
            raise ValueError(f"Source signal semantics changed: {tid}")
    old_nodes = {n.get("id"): n for n in before.findall("junction") if not n.get("id").startswith(":")}
    new_nodes = {n.get("id"): n for n in after.findall("junction") if not n.get("id").startswith(":")}
    if old_nodes.keys() != new_nodes.keys():
        raise ValueError("Junction identities changed")
    for jid, node in old_nodes.items():
        if any(node.get(k) != new_nodes[jid].get(k) for k in ("x", "y", "type", "incLanes")):
            raise ValueError(f"Signal/node relocation or lane ordering changed: {jid}")
    before_map, after_map = {key(e): e for e in before}, {key(e): e for e in after}
    changes = []
    for identity in sorted(before_map.keys() | after_map.keys()):
        old, new = before_map.get(identity), after_map.get(identity)
        av, bv = xml_value(old) if old is not None else None, xml_value(new) if new is not None else None
        if av == bv:
            continue
        if not all(affected(e, junctions, incident) for e in (old, new) if e is not None):
            raise ValueError(f"Unrelated network element changed: {identity}")
        changes.append({"identity": list(identity), "before": av, "after": bv})
    return changes


def connection_mapping(path):
    """SUMO signal link indices and junction request indices are separate."""
    net = load_network(path)
    root = ET.parse(path).getroot()
    result = []
    for e in net.getEdges():
        if e.getFunction() == "internal":
            continue
        for cs in e.getOutgoing().values():
            for c in cs:
                if not c.getTLSID():
                    continue
                lanes, lane = [], c.getViaLaneID()
                while lane and lane not in lanes:
                    lanes.append(lane)
                    edge = net.getLane(lane).getEdge().getID()
                    continuation = next((x for x in root.findall("connection")
                                         if x.get("from") == edge and x.get("via")), None)
                    lane = continuation.get("via") if continuation is not None else None
                result.append({"from": e.getID(), "to": c.getTo().getID(),
                               "fromLane": c.getFromLane().getIndex(), "toLane": c.getToLane().getIndex(),
                               "tls": c.getTLSID(), "signal_index": c.getTLLinkIndex(),
                               "request_index": c.getJunctionIndex(), "internal_lanes": lanes})
    return sorted(result, key=lambda x: (x["tls"], x["signal_index"], x["from"], x["to"]))


def build(source, directory, settings, topology):
    """Rebuild cumulative repairs directly from the immutable source each time."""
    directory.mkdir(parents=True, exist_ok=True)
    original = ET.parse(source).getroot()
    node_ids = {n["node_id"]: n["sumo_tls_id"] for n in topology["nodes"]}
    junctions = {node_ids[c] for c in settings["controllers"]}
    roads = {e.get("id"): e for e in original.findall("edge") if e.get("function") != "internal"}
    incident = {eid for eid, e in roads.items() if e.get("from") in junctions or e.get("to") in junctions}
    connections = ET.Element("connections")
    for c in road_connections(original).values():
        if c.get("tl") not in junctions:
            continue
        attrs = {k: c.get(k) for k in ("from", "to", "fromLane", "toLane", "tl", "linkIndex", "allow", "disallow") if c.get(k) is not None}
        if c.get("tl") in {node_ids[x] for x in settings.get("stop_line_waiting", [])}:
            logic = original.find(f"tlLogic[@id='{c.get('tl')}']")
            if any(p["state"][int(c.get("linkIndex"))] == "g" for p in derived_phases(logic)):
                # No safe interior waiting pocket: permissive traffic yields at
                # the external stop line. Internal driving lanes remain enabled.
                attrs["contPos"] = "0"
        canonical = next(n for n, tid in node_ids.items() if tid == c.get("tl"))
        shape = settings.get("connection_shapes", {}).get(f"{canonical}:{c.get('linkIndex')}")
        if shape:
            points = [tuple(map(float, xy.split(","))) for xy in shape.split()]
            if len(points) < 2 or any(len(p) != 2 or not all(math.isfinite(x) for x in p) for p in points):
                raise ValueError("Connector shapes require finite 2D coordinates")
            attrs["shape"] = shape
        position = settings.get("cont_positions", {}).get(f"{canonical}:{c.get('linkIndex')}")
        if position is not None:
            if not math.isfinite(float(position)) or float(position) < 0:
                raise ValueError("Internal waiting positions must be finite and nonnegative")
            attrs["contPos"] = str(position)
        ET.SubElement(connections, "connection", **attrs)
    by_signal = {f"{canonical}:{c.get('linkIndex')}": c
                 for c in road_connections(original).values()
                 for canonical, tid in node_ids.items() if c.get("tl") == tid}
    for yielding, priority in settings.get("yield_to", {}).items():
        minor = by_signal[yielding]
        if minor.get("tl") not in junctions:
            raise ValueError("Right-of-way repair outside the selected junctions")
        for movement in priority:
            major = by_signal[movement]
            if minor.get("tl") != major.get("tl"):
                raise ValueError("Prohibitions cannot span controllers")
            ET.SubElement(connections, "prohibition", prohibitor=f"{major.get('from')}->{major.get('to')}",
                          prohibited=f"{minor.get('from')}->{minor.get('to')}")
    logic_file = ET.Element("tlLogics")
    for old in original.findall("tlLogic"):
        if old.get("id") not in junctions:
            continue
        logic = ET.SubElement(logic_file, "tlLogic", **old.attrib)
        for p in derived_phases(old):
            ET.SubElement(logic, "phase", state=p["state"], duration=str(p["duration"]))
        for c in connections.findall("connection"):
            if c.get("tl") == old.get("id"):
                ET.SubElement(logic_file, "connection", **{k: c.get(k) for k in ("from", "to", "fromLane", "toLane", "tl", "linkIndex")})
    write_xml(connections, directory / "connections.con.xml")
    write_xml(logic_file, directory / "signals.tll.xml")
    args = [binary("netconvert"), "--sumo-net-file", str(source),
            "--connection-files", str(directory / "connections.con.xml"),
            "--tllogic-files", str(directory / "signals.tll.xml"),
            "--offset.disable-normalization", "true", "--no-internal-links", "false",
            "--internal-junctions.vehicle-width", str(settings.get("vehicle_width_m", 2.5)),
            "--output-file", str(directory / "generated.net.xml")]
    if settings.get("nodes"):
        nodes = ET.Element("nodes")
        for controller, attrs in settings["nodes"].items():
            ET.SubElement(nodes, "node", id=node_ids[controller], **attrs)
        write_xml(nodes, directory / "nodes.nod.xml")
        args.extend(["--node-files", str(directory / "nodes.nod.xml")])
    result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    (directory / "netconvert.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"netconvert failed: {directory / 'netconvert.log'}")
    generated = ET.parse(directory / "generated.net.xml").getroot()
    published = copy.deepcopy(original)
    replacements = {key(e): e for e in generated if affected(e, junctions, incident)}
    # SUMO depends on connection serialization order as well as element values.
    # Replace elements in place and retain the exact source order everywhere.
    elements = []
    for old in original:
        if affected(old, junctions, incident):
            replacement = replacements.pop(key(old), None)
            if replacement is not None:
                elements.append(copy.deepcopy(replacement))
        else:
            elements.append(copy.deepcopy(old))
    for new in replacements.values():
        position = max((i+1 for i, e in enumerate(elements) if e.tag == new.tag), default=len(elements))
        elements.insert(position, copy.deepcopy(new))
    published[:] = elements
    changes = validate_changes(original, published, junctions)
    network = directory / "network.net.xml"
    write_xml(published, network)
    old_mapping, new_mapping = connection_mapping(source), connection_mapping(network)
    save(directory / "internal-lane-mapping.json", [{"before": a, "after": b} for a, b in zip(old_mapping, new_mapping)])
    version = subprocess.run([binary("netconvert"), "--version"], capture_output=True, text=True, check=True).stdout
    save(directory / "manifest.json", {"source_sha256": sha(source), "network_sha256": sha(network),
         "builder_sha256": sha(__file__),
         "settings": settings, "commands": [args], "netconvert_version": version,
         "changes": changes, "changed_element_count": len(changes),
         "construction": "Derived signal programs and explicit lane connections rebuild conflicts; whole generated local elements are published. Source tlLogic elements retain their imported indices; simulation loads derived programs.",
         "evidence": "../../baseline/collision-inventory.json",
         "input_sha256": {p.name: sha(p) for p in directory.iterdir() if p.suffix == ".xml" and p.name != "generated.net.xml"}})
    junction_diagram(source, network, junctions, directory / "junctions.svg")
    return network


def footprint(front, angle, length, width):
    """Full oriented rectangle from SUMO's front-centre and clockwise degrees."""
    a = math.radians(angle)
    forward, lateral = (math.sin(a), math.cos(a)), (math.cos(a), -math.sin(a))
    return [[front[0] - forward[0]*d + lateral[0]*side*width/2,
             front[1] - forward[1]*d + lateral[1]*side*width/2]
            for d, side in ((0, -1), (0, 1), (length, 1), (length, -1))]


def polygons_overlap(a, b):
    for polygon in (a, b):
        for p, q in zip(polygon, polygon[1:] + polygon[:1]):
            axis = (p[1]-q[1], q[0]-p[0])
            xa = [x*axis[0]+y*axis[1] for x, y in a]
            xb = [x*axis[0]+y*axis[1] for x, y in b]
            if max(xa) <= min(xb) or max(xb) <= min(xa):
                return False
    return True


def inventory(case_directory, network, demand, topology):
    """Retain full FCD, extract all actors within 30 m and ±10 s per event."""
    topology = read(topology)
    tls_to_node = topology["sumo_to_canonical"]
    mappings = connection_mapping(network)
    lanes = {lane: m for m in mappings for lane in m["internal_lanes"]}
    types = {t.get("id"): {"length_m": float(t.get("length", "5")),
                            "width_m": float(t.get("width", "1.8")),
                            "min_gap_m": float(t.get("minGap", "2.5"))}
             for t in ET.parse(demand).getroot().findall("vType")}
    dimensions = case_directory / "vehicle_dimensions.json"
    if dimensions.exists():
        types.update(read(dimensions))
    else:
        shared = case_directory.parent.parent / "repair/runtime-vehicle-dimensions.json"
        if shared.exists():
            recorded = read(shared)
            attributes = {t.get("id"): dict(t.attrib) for t in ET.parse(demand).getroot().findall("vType")}
            if attributes == recorded["type_attributes"]:
                types.update(recorded["dimensions"])
    signals = list(csv.DictReader((case_directory / "signals.csv").open(encoding="utf-8")))
    events = []
    for c in ET.parse(case_directory / "collisions.xml").getroot().findall("collision"):
        event = dict(c.attrib)
        event.update(time_s=float(c.get("time")), trajectories=[])
        events.append(event)
    with gzip.open(case_directory / "fcd.xml.gz", "rb") as stream:
        for _, step in ET.iterparse(stream, events=("end",)):
            if step.tag != "timestep":
                continue
            time_s = float(step.get("time"))
            wanted = [e for e in events if abs(time_s-e["time_s"]) <= 10]
            for event in wanted:
                center = list(map(float, event["colliderFront"].split(",")))
                vehicles = []
                for v in step.findall("vehicle"):
                    xy = [float(v.get("x")), float(v.get("y"))]
                    if math.dist(xy, center) > 30 and v.get("id") not in (event["collider"], event["victim"]):
                        continue
                    actor = dict(v.attrib)
                    actor.update(types[v.get("type")])
                    actor["footprint"] = footprint(xy, float(v.get("angle")), actor["length_m"], actor["width_m"])
                    movement = lanes.get(v.get("lane"))
                    actor["movement"] = movement
                    actor["controller"] = tls_to_node.get(movement["tls"]) if movement else None
                    actor["waiting_internal"] = v.get("lane").startswith(":") and float(v.get("speed")) < .1
                    vehicles.append(actor)
                event["trajectories"].append({"time_s": time_s, "vehicles": vehicles})
            step.clear()
    for event in events:
        movement = lanes.get(event["lane"])
        event["movement"] = movement
        event["controller"] = tls_to_node.get(movement["tls"]) if movement else None
        event["controller_states"] = [s for s in signals if float(s["start_s"]) <= event["time_s"] < float(s["end_s"])]
        near = min(event["trajectories"], key=lambda f: abs(f["time_s"]-event["time_s"]), default={"vehicles": []})
        event["movement_pair"] = {role: next((v for v in near["vehicles"] if v["id"] == event[role]), None) for role in ("collider", "victim")}
        to_edge = movement["to"] if movement else None
        event["downstream_stopped_vehicles"] = [v for v in near["vehicles"] if v["lane"].rsplit("_", 1)[0] == to_edge and float(v["speed"]) < .1]
    result = {"events": events, "event_count": len(events), "history": "fcd.xml.gz",
              "trajectory_resolution_s": 1, "footprint_method": "Full dimension oriented rectangles from FCD; SUMO collisionFront/collisionBack are retained for actual curved-body endpoints."}
    save(case_directory / "collision-inventory.json", result)
    return result


def junction_diagram(before, after, junctions, path):
    roots = [ET.parse(p).getroot() for p in (before, after)]
    nodes = [n for n in roots[0].findall("junction") if n.get("id") in junctions]
    xmin, xmax = min(float(n.get("x")) for n in nodes)-40, max(float(n.get("x")) for n in nodes)+40
    ymin, ymax = min(float(n.get("y")) for n in nodes)-40, max(float(n.get("y")) for n in nodes)+40
    scale = min(650/(xmax-xmin), 650/(ymax-ymin))
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="750"><rect width="100%" height="100%" fill="white"/>']
    for panel, root in enumerate(roots):
        offset = 50+750*panel
        svg.append(f'<text x="{offset}" y="30" font-size="24">{"Before" if panel == 0 else "After"}</text>')
        for edge in root.findall("edge"):
            for lane in edge.findall("lane"):
                coords = [tuple(map(float, xy.split(",")[:2])) for xy in lane.get("shape", "").split()]
                if not coords or not any(xmin <= x <= xmax and ymin <= y <= ymax for x, y in coords):
                    continue
                points = " ".join(f"{offset+(x-xmin)*scale:.2f},{70+(ymax-y)*scale:.2f}" for x, y in coords)
                color = "#de7b16" if edge.get("function") == "internal" else "#2377aa"
                svg.append(f'<polyline points="{points}" stroke="{color}" stroke-width="2" fill="none"><title>{lane.get("id")}</title></polyline>')
        for n in nodes:
            x, y = offset+(float(n.get("x"))-xmin)*scale, 70+(ymax-float(n.get("y")))*scale
            svg.append(f'<circle cx="{x}" cy="{y}" r="4"/><text x="{x+6}" y="{y}" font-size="12">{n.get("id")}</text>')
    svg.append('</svg>')
    path.write_text("\n".join(svg), encoding="utf-8")


def verify_preservation(output):
    baseline = read(output / "preservation-before.json")
    changed, checked = [], 0
    for group, location in (("original", baseline["original_root"]), ("v2", baseline["v2_root"])):
        for name, checksum in baseline[group].items():
            path = Path(location) / name
            if not path.is_file() or sha(path) != checksum:
                changed.append(f"{group}/{name}")
            checked += 1
    result = {"pass": not changed, "files_checked": checked, "changed": changed}
    save(output / "preservation-after.json", result)
    return result


def repair(config, output, resume=False):
    from .qualify_hcm import Campaign, prepare, digest, atomic_json, current_case
    source = ROOT / config["repair_source_network"]
    settings_path = ROOT / config["repair_inputs"]
    requested = read(settings_path)
    status_path = output / "repair/status.json"
    previous = read(status_path) if status_path.exists() else {}
    if previous.get("status") == "repaired" and (output / "repair/freeze.json").exists():
        prepared = prepare(config, output)
        if read(output / "repair/freeze.json")["fingerprint"] == digest(prepared["identity"]):
            return prepared
    if (requested.get("connection_shapes") or requested.get("nodes")) and previous.get("status") in ("regression_failed", "structural_failure", "repaired") and previous.get("revision"):
        return geometry_repair(config, output, requested, previous, resume)
    context = prepare(config, output, source_network=source)
    campaign = Campaign(output, config, context, resume)
    baseline_dir = output / "repair/baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    cases = sorted(p.name for p in (V2_REFERENCE / "diagnostics").glob("qualification-*") if p.is_dir())
    if len(cases) != 6:
        raise ValueError("Expected the six existing diagnostic cases")
    baseline_events = []
    for name in cases:
        old = reference_spec(name)
        old.update(network=str(source), topology=str(context["inputs"] / "topology.json"),
                   program=str(context["inputs"] / f"{old['controller']}.add.xml"), repair_history=True)
        metrics = campaign.case("repair-baseline-"+name, old)
        case_dir = output / "cases" / ("repair-baseline-"+name)
        found = inventory(case_dir, source, Path(old["demand"]), Path(old["topology"]))
        previous = ET.parse(reference_file(f"diagnostics/{name}/collisions.xml")).getroot().findall("collision")
        signature = lambda xs: sorted((x["time"], x["collider"], x["victim"], x["lane"]) for x in xs)
        if signature(found["events"]) != signature([dict(c.attrib) for c in previous]):
            raise ValueError(f"Baseline collision events did not reproduce: {name}")
        baseline_events.append({"case": name, "events": found["events"], "metrics": metrics,
                                "evidence": f"../../cases/repair-baseline-{name}/collision-inventory.json"})
    save(baseline_dir / "collision-inventory.json", baseline_events)
    # Changes are cumulative and tested in the user's required order.
    controllers, waiting = [], []
    revision = 0
    for group in REPAIR_ORDER:
        controllers.extend(group)
        for strategy in ("rebuild_conflicts", "stop_line_waiting"):
            if strategy == "stop_line_waiting":
                waiting.extend(group)
            revision += 1
            settings = {"controllers": controllers[:], "stop_line_waiting": waiting[:],
                        "nodes": {k: v for k, v in requested.get("nodes", {}).items() if k in controllers}}
            settings["stop_line_waiting"] = sorted(set(settings["stop_line_waiting"]) |
                                                   (set(requested.get("force_stop_line_waiting", [])) & set(controllers)))
            directory = output / "repair/revisions" / f"{revision:02d}-{'-'.join(group)}-{strategy}"
            network = build(source, directory, settings, context["topology"])
            candidate = prepare(config, output, source_network=network)
            test_campaign = Campaign(output, config, candidate, resume)
            outcomes = []
            for name in [x["case"] for x in baseline_events if any(e["controller"] in group for e in x["events"])]:
                old = reference_spec(name)
                old.update(network=str(candidate["inputs"] / "network.net.xml"),
                           topology=str(candidate["inputs"] / "topology.json"),
                           program=str(candidate["inputs"] / f"{old['controller']}.add.xml"), repair_history=True)
                case_name = f"repair-{revision:02d}-{name}"
                m = test_campaign.case(case_name, old)
                case_dir = output / "cases" / case_name
                inv = inventory(case_dir, Path(old["network"]), Path(old["demand"]), Path(old["topology"]))
                outcomes.append({"case": case_name, "metrics": m, "event_controllers": [e["controller"] for e in inv["events"]]})
            save(directory / "regressions.json", outcomes)
            campaign = test_campaign
            # Continue to the next hotspot when this group's collisions clear.
            if all(not (set(x["event_controllers"]) & set(group)) and x["metrics"]["teleports"] == 0 for x in outcomes):
                break
        else:
            save(output / "repair/status.json", {"status": "structural_failure", "group": group,
                 "revision": str(directory.relative_to(output)), "reason": "Local conflict rebuild and external permissive waiting retain collisions; further safe geometry is unproven."})
            return candidate
    # All 40 previous qualification cases are engineering regression evidence.
    replays = []
    for record in read(reference_file("qualification_cases.json"))["cases"]:
        name = record["case"]
        spec = reference_spec(name)
        spec.update(network=str(candidate["inputs"] / "network.net.xml"),
                    topology=str(candidate["inputs"] / "topology.json"),
                    program=str(candidate["inputs"] / f"{spec['controller']}.add.xml"), repair_history=True)
        # Engineering replay does not use a v2 speed counterfactual as v3 evidence.
        spec.pop("bottleneck_control_trace", None)
        case_name = "repair-replay-"+name
        m = campaign.case(case_name, spec)
        replays.append({"case": case_name, "pass": m["engineering_pass"], "metrics": m})
        save(output / "repair/replay40.json", replays)
    if (requested.get("connection_shapes") or requested.get("nodes")) and not all(x["pass"] for x in replays):
        previous = {"status": "regression_failed", "revision": str(directory.relative_to(output))}
        save(output / "repair/status.json", previous)
        return geometry_repair(config, output, requested, previous, resume)
    return publish_repair(config, output, candidate, network, directory, replays,
                          adjacent_red_probe(campaign, candidate))


def publish_repair(config, output, candidate, network, directory, replays, probe):
    from .qualify_hcm import prepare, digest, atomic_json
    repaired = ROOT / config["repaired_network"]
    repaired.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copyfile(network, repaired)
    for pattern in ("*.con.xml", "*.tll.xml", "*.nod.xml"):
        for path in directory.glob(pattern):
            shutil.copyfile(path, repaired.parent / path.name)
    # Canonical topology is written only after the cumulative local build.
    atomic_json(ROOT / "contracts/topology" / f"{TOPOLOGY_ID}.json", candidate["topology"])
    shutil.copyfile(directory / "manifest.json", output / "repair/change-manifest.json")
    status = {"status": "repaired" if len(replays) == 40 and all(x["pass"] for x in replays) and probe.get("pass") else "regression_failed",
              "network_sha256": sha(repaired), "regressions": "replay40.json",
              "repair_input_sha256": sha(ROOT / config["repair_inputs"]), "revision": str(directory.relative_to(output)),
              "adjacent_red_probe": probe}
    save(output / "repair/status.json", status)
    if status["status"] == "repaired":
        frozen_context = prepare(config, output)
        save(output / "repair/freeze.json", {"fingerprint": digest(frozen_context["identity"]),
             "network_sha256": sha(repaired), "replay_sha256": sha(output / "repair/replay40.json"),
             "adjacent_red_probe_sha256": sha(output / "repair/adjacent-red-probe.json"),
             "calibration_seeds": PROTOCOL["calibration_seeds"], "qualification_seeds": PROTOCOL["qualification_seeds"]})
        return frozen_context
    return candidate


def geometry_repair(config, output, requested, previous, resume):
    """Continue from recorded regression failure without rerunning unchanged baselines."""
    from .qualify_hcm import Campaign, prepare, digest
    source = ROOT / config["repair_source_network"]
    previous_directory = output / previous["revision"]
    previous_manifest = read(previous_directory / "manifest.json")
    if sha(source) != previous_manifest["source_sha256"]:
        raise ValueError("Imported repair source changed since the diagnostic reproductions")
    settings = copy.deepcopy(previous_manifest["settings"])
    settings["connection_shapes"] = requested.get("connection_shapes", {})
    settings["nodes"] = requested.get("nodes", {})
    settings["cont_positions"] = requested.get("cont_positions", {})
    settings["yield_to"] = requested.get("yield_to", {})
    settings["vehicle_width_m"] = requested.get("vehicle_width_m", 2.5)
    settings["stop_line_waiting"] = sorted(set(settings["stop_line_waiting"]) |
                                           set(requested.get("force_stop_line_waiting", [])))
    baseline = read(output / "repair/baseline/collision-inventory.json")
    import shutil
    history = output / "repair" / ("replay40-before-" + digest(settings)[:8] + ".json")
    if not history.exists() and (output / "repair/replay40.json").exists():
        shutil.copyfile(output / "repair/replay40.json", history)
    topology = read(ROOT / "contracts/topology/hcm_neighborhood_benchmark_v2.json")
    directory = output / "repair/revisions" / ("10-J14-J17-geometry-" + digest(settings)[:8])
    network = build(source, directory, settings, topology)
    candidate = prepare(config, output, source_network=network)
    campaign = Campaign(output, config, candidate, resume)
    names = sorted({x["case"] for x in baseline} |
                   {"qualification-directional_shift-500-72002-native_fixed"})
    outcomes = []
    for name in names:
        spec = reference_spec(name)
        spec.update(network=str(candidate["inputs"] / "network.net.xml"),
                    topology=str(candidate["inputs"] / "topology.json"),
                    program=str(candidate["inputs"] / f"{spec['controller']}.add.xml"), repair_history=True)
        case_name = "repair-geometry-" + name
        metrics = campaign.case(case_name, spec)
        inv = inventory(output / "cases" / case_name, Path(spec["network"]),
                        Path(spec["demand"]), Path(spec["topology"]))
        outcomes.append({"case": case_name, "metrics": metrics, "pass": metrics["engineering_pass"],
                         "events": inv["events"]})
        if not metrics["engineering_pass"]:
            break
    save(directory / "regressions.json", outcomes)
    if not all(x["pass"] for x in outcomes):
        save(output / "repair/status.json", {"status": "structural_failure", "revision": str(directory.relative_to(output)),
             "reason": "Explicit local connector geometry still fails engineering regressions.", "evidence": str((directory / "regressions.json").relative_to(output))})
        return candidate
    replays = []
    for record in read(reference_file("qualification_cases.json"))["cases"]:
        name = record["case"]
        spec = reference_spec(name)
        spec.update(network=str(candidate["inputs"] / "network.net.xml"),
                    topology=str(candidate["inputs"] / "topology.json"),
                    program=str(candidate["inputs"] / f"{spec['controller']}.add.xml"), repair_history=True)
        spec.pop("bottleneck_control_trace", None)
        case_name = "repair-replay-geometry-" + name
        metrics = campaign.case(case_name, spec)
        replays.append({"case": case_name, "pass": metrics["engineering_pass"], "metrics": metrics})
        save(output / "repair/replay40.json", replays)
    probe = adjacent_red_probe(campaign, candidate)
    return publish_repair(config, output, candidate, network, directory, replays, probe)


def adjacent_red_probe(campaign, context):
    """Natural signal programs with dense bus queues in both link directions."""
    from .qualify_hcm import corrected_spec
    bus = next(t for path in context["imported"]["routes"] for t in ET.parse(path).getroot().findall("vType")
               if t.get("vClass") == "bus")
    if float(bus.get("length")) != 12:
        raise ValueError("Expected the original 12 m bus")
    demand = ET.Element("routes")
    demand.append(copy.deepcopy(bus))
    paths = ["32576061#0 32576061#1 32576061#2 32576061#3",
             "-32576061#3 -32576061#2 -32576061#1 -32576061#0"]
    for direction, path in enumerate(paths):
        for i in range(24):
            vehicle = ET.SubElement(demand, "vehicle", id=f"bus_{direction}_{i:02d}", type=bus.get("id"),
                                    depart=str(5*i+direction*.5), departLane="best", departSpeed="max")
            ET.SubElement(vehicle, "route", edges=path)
    demand[:] = [demand[0], *sorted(list(demand)[1:], key=lambda v: float(v.get("depart")))]
    route_file = context["inputs"] / "demand/adjacent-red-bus-queues.rou.xml"
    route_file.parent.mkdir(exist_ok=True)
    write_xml(demand, route_file)
    metadata = {"seed": 72006, "condition": "adjacent_red_bus_queues", "coverage_gate": True}
    spec = corrected_spec(context, route_file, metadata, "native_fixed")
    spec["horizon_s"] = PROTOCOL["demand_s"] + PROTOCOL["drain_s"]
    name = "verification-adjacent-red-bus-queues"
    metrics = campaign.case(name, spec)
    directory = campaign.output / "cases" / name
    records = list(csv.DictReader((directory / "signals.csv").open()))
    red_queues = {"32576061#1": 0, "-32576061#1": 0}
    downstream = {"32576061#1": ("J17", 7, "J14", 9, "32576061#0_0"),
                  "-32576061#1": ("J14", 1, "J17", 0, "-32576061#2_0")}
    with gzip.open(directory / "fcd.xml.gz", "rb") as stream:
        for _, step in ET.iterparse(stream, events=("end",)):
            if step.tag != "timestep":
                continue
            now = float(step.get("time"))
            for road, (controller, index, upstream, upstream_index, approach) in downstream.items():
                states = {r["controller"]: r["state"] for r in records
                          if float(r["start_s"]) <= now < float(r["end_s"])}
                state, upstream_state = states.get(controller, ""), states.get(upstream, "")
                approaching = (":366426721_9_", ":366426721_14_") if road == "32576061#1" else (":5750600545_0_", ":5750600545_4_")
                if state and state[index] == "r" and upstream_state and upstream_state[upstream_index] in "Gg" and any(
                        float(v.get("speed")) < .1 and (v.get("lane") in (road+"_0", approach) or v.get("lane").startswith(approaching))
                        for v in step.findall("vehicle")):
                    red_queues[road] += 1
            step.clear()
    result = {"pass": metrics["engineering_pass"] and metrics["completed"] == 48 and all(red_queues.values()),
              "red_queue_samples": red_queues, "metrics": metrics, "evidence": f"../cases/{name}/fcd.xml.gz"}
    save(campaign.output / "repair/adjacent-red-probe.json", result)
    return result
