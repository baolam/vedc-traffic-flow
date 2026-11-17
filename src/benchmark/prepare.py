"""Audit SUMO networks into explicit phase maps and boundary routes."""

import json
from collections import deque
from pathlib import Path
import xml.etree.ElementTree as ET
from .evidence import file_hash, write_json


def prepare_map(spec, output):
    if "bbox" in spec:
        spec = download_city(spec, Path(output) / "source")
    network = Path(spec["network_path"])
    root = ET.parse(network).getroot()
    edges = {e.get("id"): e for e in root.findall("edge") if not e.get("id").startswith(":")}
    connections = [c for c in root.findall("connection") if c.get("from") in edges and c.get("to") in edges]
    incoming = {c.get("from") for c in connections}
    exits = set(edges) - incoming
    adjacency = {key: [] for key in edges}
    for c in connections:
        adjacency[c.get("from")].append(c.get("to"))
    from contracts.benchmark import VEHICLES

    static_signals = []
    nodes = []
    routes = []
    for logic in root.findall("tlLogic"):
        nid = logic.get("id")
        links = [c for c in connections if c.get("tl") == nid]
        if not links:
            continue
        approaches = sorted({c.get("from") for c in links})
        states = list(
            dict.fromkeys(
                p.get("state")
                for p in logic.findall("phase")
                if "y" not in p.get("state").lower() and "g" in p.get("state").lower()
            )
        )
        if len(states) < 2:
            static_signals.append(nid)
            continue
        phases = []
        for i, state in enumerate(states):
            if max(int(c.get("linkIndex")) for c in links) >= len(state):
                raise ValueError("Incomplete signal mapping")
            served = sorted({c.get("from") for c in links if state[int(c.get("linkIndex"))] in "Gg"})
            phases.append(
                dict(
                    phase_id=f"{nid}_PHASE_{i}",
                    approaches=served,
                    sumo_state=state,
                    movements=[dict(from_approach=a, to_node=None, to_approach=None) for a in served],
                )
            )
        nodes.append(
            dict(
                node_id=nid,
                approaches=approaches,
                phases=phases,
                sumo_links=[
                    dict(index=int(c.get("linkIndex")), **{"from": c.get("from"), "to": c.get("to")}) for c in links
                ],
            )
        )
        for app in approaches:
            queue = deque([[app]])
            seen = {app}
            found = None
            farthest = [app]
            while queue:
                path = queue.popleft()
                if len(path) > len(farthest):
                    farthest = path
                if path[-1] in exits and len(path) >= 2:
                    found = path
                    break
                for target in sorted(adjacency[path[-1]]):
                    if target not in seen:
                        seen.add(target)
                        queue.append(path + [target])
            if found is None:
                found = farthest
            if len(found) < 2:
                raise ValueError(f"No valid route reachable from {app}")
            if app not in {r["route_id"] for r in routes}:
                shape = edges[app].find("lane").get("shape").split()
                first, last = [tuple(map(float, point.split(","))) for point in (shape[0], shape[-1])]
                axis = "NS" if abs(last[1] - first[1]) >= abs(last[0] - first[0]) else "EW"
                routes.append(dict(route_id=app, origin=nid, axis=axis, edges=found))
    if not 2 <= len(nodes) or len(nodes) + len(static_signals) > 32:
        raise ValueError(f"Expected 2–32 controlled signals, found {len(nodes)}")
    owners = {a: n["node_id"] for n in nodes for a in n["approaches"]}
    for node in nodes:
        for phase in node["phases"]:
            phase["movements"] = [
                dict(
                    from_approach=c.get("from"),
                    to_node=owners.get(c.get("to")),
                    to_approach=c.get("to") if c.get("to") in owners else None,
                )
                for c in connections
                if c.get("tl") == node["node_id"] and phase["sumo_state"][int(c.get("linkIndex"))] in "Gg"
            ]

    def permits(attrs, vclass):
        allow = attrs.get("allow", "").split()
        disallow = attrs.get("disallow", "").split()
        return (not allow or "all" in allow or vclass in allow) and "all" not in disallow and vclass not in disallow

    for route in routes:
        allowed = []
        for kind, (vclass, *_) in VEHICLES.items():
            permitted = all(
                any(permits(lane.attrib, vclass) for lane in edges[edge].findall("lane")) for edge in route["edges"]
            )
            for source, target in zip(route["edges"], route["edges"][1:]):
                choices = [c for c in connections if c.get("from") == source and c.get("to") == target]
                permitted = permitted and any(
                    permits(c.attrib, vclass)
                    and permits(edges[source].findall("lane")[int(c.get("fromLane"))].attrib, vclass)
                    and permits(edges[target].findall("lane")[int(c.get("toLane"))].attrib, vclass)
                    for c in choices
                )
            if permitted:
                allowed.append(kind)
        route["allowed_classes"] = allowed
    if spec["id"] != "four_intersection_rl_v1":
        names = {n["node_id"]: f"J{i + 1}" for i, n in enumerate(nodes)}
        app_names = {}
        for node in nodes:
            groups = {side: [] for side in "NSEW"}
            for app in node["approaches"]:
                shape = edges[app].find("lane").get("shape").split()
                first, last = [tuple(map(float, p.split(","))) for p in (shape[0], shape[-1])]
                dx, dy = last[0] - first[0], last[1] - first[1]
                side = ("W" if dx > 0 else "E") if abs(dx) > abs(dy) else ("S" if dy > 0 else "N")
                groups[side].append(app)
            for side, apps in groups.items():
                for i, app in enumerate(sorted(apps)):
                    suffix = "" if len(apps) == 1 else f"_{i}"
                    app_names[app] = f"{names[node['node_id']]}_{side}{suffix}_IN"
        for node in nodes:
            native = node["node_id"]
            node["node_id"] = names[native]
            node["sumo_tls_id"] = native
            node["sumo_edges"] = {app_names[a]: a for a in node["approaches"]}
            node["approaches"] = [app_names[a] for a in node["approaches"]]
            for i, phase in enumerate(node["phases"]):
                phase["phase_id"] = f"{names[native]}_PHASE_{i}"
                phase["approaches"] = [app_names[a] for a in phase["approaches"]]
                for movement in phase["movements"]:
                    movement["from_approach"] = app_names[movement["from_approach"]]
                    if movement["to_node"] is not None:
                        movement["to_node"] = names[movement["to_node"]]
                        movement["to_approach"] = app_names[movement["to_approach"]]
        for route in routes:
            route["route_id"] = app_names[route["route_id"]]
            route["origin"] = names[route["origin"]]
    topology = dict(topology_id=spec["id"], version="1.0", nodes=nodes, routes=routes)
    if spec["id"] == "four_intersection_rl_v1":
        topology = json.loads(Path(spec["topology_path"]).read_text())
    output = Path(output)
    write_json(output / "topology.json", topology)
    if spec["id"] == "four_intersection_rl_v1":
        import shutil

        shutil.copyfile(spec["topology_path"], output / "topology.json")
    canonical = Path("contracts/topology") / f"{spec['id']}.json"
    if spec["id"] != "four_intersection_rl_v1":
        if canonical.exists() and json.loads(canonical.read_text()) != topology:
            raise ValueError("Canonical mapping changed; choose a new topology version")
        if not canonical.exists():
            write_json(canonical, topology)
    write_json(
        output / "audit.json",
        dict(
            network_sha256=file_hash(network),
            controlled_signals=len(nodes),
            inferred_signal_plans=True,
            unmanaged_static_signals=static_signals,
            source=str(network.resolve()),
        ),
    )
    import shutil

    frozen_network = output / "network.net.xml"
    if frozen_network.resolve() != network.resolve():
        shutil.copyfile(network, frozen_network)
    return dict(
        spec, topology_path=str((output / "topology.json").resolve()), network_path=str(frozen_network.resolve())
    )


def download_city(spec, output):
    """Freeze a bounded OSM extract; shrink only when the signal cap is exceeded."""
    import subprocess
    import urllib.request
    import urllib.error
    from src.simulation.build_network import binary

    west, south, east, north = spec["bbox"]
    center = ((west + east) / 2, (south + north) / 2)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for attempt in range(8):
        scale = 0.85**attempt
        bbox = [
            center[0] + (west - center[0]) * scale,
            center[1] + (south - center[1]) * scale,
            center[0] + (east - center[0]) * scale,
            center[1] + (north - center[1]) * scale,
        ]
        source = output / f"source-{attempt}.osm.xml"
        if not source.exists():
            request = urllib.request.Request(
                "https://api.openstreetmap.org/api/0.6/map?bbox=" + ",".join(map(str, bbox)),
                headers={"User-Agent": "EdgeFlow-research/1.0", "Accept-Encoding": "gzip"},
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = response.read(32 * 1024 * 1024 + 1)
                    if response.headers.get("Content-Encoding") == "gzip":
                        import gzip
                        import io

                        with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                            data = compressed.read(32 * 1024 * 1024 + 1)
            except urllib.error.HTTPError as error:
                detail = error.read(8192).decode(errors="replace")
                if error.code == 400 and "too many" in detail.lower():
                    write_json(output / f"source-{attempt}-rejected.json", dict(bbox=bbox, reason=detail))
                    continue
                raise RuntimeError(f"OSM download failed ({error.code}): {detail}") from error
            if len(data) > 32 * 1024 * 1024:
                raise ValueError("City extract exceeds 32 MiB; use a smaller source area")
            ET.fromstring(data)
            temporary = source.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(source)
        network = output / f"network-{attempt}.net.xml"
        if not network.exists():
            command = [
                binary("netconvert"),
                "--osm-files",
                str(source),
                "--output-file",
                str(network),
                "--junctions.join",
                "true",
                "--no-turnarounds",
                "true",
            ]
            if spec.get("lefthand"):
                command.extend(["--lefthand", "true"])
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
        count = len(ET.parse(network).getroot().findall("tlLogic"))
        if count > 32:
            continue
        if count < 4:
            raise ValueError("City crop has fewer than four signals; inspect source geometry")
        write_json(
            output / "source.json",
            dict(
                bbox=bbox,
                sha256=file_hash(source),
                attribution="OpenStreetMap contributors",
                license="ODbL-1.0",
                lefthand=spec.get("lefthand", False),
            ),
        )
        return dict(spec, network_path=str(network.resolve()))
    raise ValueError("No crop satisfied the 32-signal limit")
