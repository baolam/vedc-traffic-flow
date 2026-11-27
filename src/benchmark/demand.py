"""Frozen, permission-aware synthetic fleet demand, independent of controller actions."""

import numpy as np
import xml.etree.ElementTree as ET
from contracts.benchmark import CORE_CASES, FLEET, VEHICLES
from contracts.scenarios import ScenarioRegistry
from contracts.research import RESEARCH_SCENARIOS
from src.simulation.build_network import write_xml


def generate_demand(topology, scenario, seed, duration, intensity, path):
    if scenario not in CORE_CASES:
        raise ValueError("Unknown benchmark workload")
    core = topology["topology_id"] == "four_intersection_rl_v1"
    if core and scenario in CORE_CASES[:4]:
        from src.simulation.runtime import generate_demand as reference_demand

        result = reference_demand(topology, scenario, seed, duration, intensity, path)
        for row in result.values():
            row["vehicle_class"] = "car"
        return result
    fleet = {"car": 100} if core else FLEET
    rng = np.random.default_rng(seed)
    root = ET.Element("routes")
    for name, (vclass, length, width, accel, decel, speed) in VEHICLES.items():
        ET.SubElement(
            root,
            "vType",
            id=name,
            vClass=vclass,
            length=str(length),
            width=str(width),
            accel=str(accel),
            decel=str(decel),
            maxSpeed=str(speed),
            minGap="1.5" if name == "motorcycle" else "2.5",
            minGapLat=".2",
        )
    pools = {}
    for kind in fleet:
        pools[kind] = [r for r in topology["routes"] if kind in r.get("allowed_classes", list(fleet))]
        if not pools[kind]:
            raise ValueError(f"No permitted route for required fleet class {kind}")
    for route in topology["routes"]:
        ET.SubElement(root, "route", id=route["route_id"], edges=" ".join(route["edges"]))
    result = {}
    factor = {"sparse": 0.25, "near_capacity": 0.9, "oversaturated": 1.2}.get(scenario, 1)
    rates = ScenarioRegistry.get_flow_rates(RESEARCH_SCENARIOS["balanced"]["profile"]) if core else None
    route_rate = (
        sum(rates[f"f_{route['origin']}_{route['axis']}"] for route in topology["routes"])
        if core
        else 0.1 * len(topology["routes"])
    )
    t = 0.0
    while True:
        t += rng.exponential(1 / (route_rate * intensity * factor))
        if t >= duration:
            break
        kind = str(rng.choice(list(fleet), p=np.array(list(fleet.values())) / 100))
        routes = pools[kind]
        weights = np.ones(len(routes))
        if scenario in ("directional_surge", "directional_surge_ew", "directional_reversal"):
            heavy = (
                "EW"
                if scenario == "directional_surge_ew" or (scenario == "directional_reversal" and t >= duration / 3)
                else "NS"
            )
            weights = np.array([5.0 if r.get("axis") == heavy else 1.0 for r in routes])
        if scenario == "directional_reversal" and t >= 2 * duration / 3 and rng.random() > 0.25:
            continue
        route = routes[int(rng.choice(len(routes), p=weights / weights.sum()))]
        vid = f"v{len(result):06d}"
        row = dict(depart=round(t, 6), route=route["route_id"], vehicle_class=kind)
        result[vid] = row
        ET.SubElement(
            root, "vehicle", id=vid, type=kind, route=row["route"], depart=str(row["depart"]), departLane="best"
        )
    write_xml(root, path)
    return result
