"""Isolated SUMO diagnostic case. No research runtime or other-service imports."""
import csv
import gzip
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

from contracts.hcm_qualification_v3 import PROTOCOL
from .build_network import binary
from .hcm_network import load_network, signal_kind, valid_route


def vehicle_accounting(scheduled, departed, arrived, running):
    uninserted = scheduled - departed
    valid = (arrived <= departed <= scheduled and running == departed-arrived
             and len(scheduled) == len(arrived)+len(running)+len(uninserted))
    return {"scheduled": len(scheduled), "completed": len(arrived), "running": len(running),
            "uninserted": len(uninserted), "accounting_gate": valid}


def reconcile_signals(seconds, horizon):
    per_node = all(set(v) == {"green", "yellow", "all_red"} and sum(v.values()) == horizon for v in seconds.values())
    network = {k: sum(v[k] for v in seconds.values()) for k in ("green", "yellow", "all_red")}
    return {"per_controller": seconds, "network": network,
            "gate": per_node and sum(network.values()) == horizon*len(seconds)}


def percentile95(values):
    values = sorted(values)
    if not values:
        return 0.0
    index = .95 * (len(values)-1)
    low = int(index)
    high = min(low+1, len(values)-1)
    return values[low] + (values[high]-values[low])*(index-low)


def mean_edge_speed(samples, begin_s, end_s):
    occupied = [row for row in samples if begin_s < row[0] <= end_s and row[2] > 0]
    vehicles = sum(row[2] for row in occupied)
    return sum(row[2] * row[3] for row in occupied) / vehicles if vehicles else None


def bottleneck_speed_response(control_samples, treatment_samples, minimum_reduction):
    control = mean_edge_speed(control_samples, 1200, 1800)
    treatment = mean_edge_speed(treatment_samples, 1200, 1800)
    reduction = ((control-treatment)/control if control and treatment is not None else None)
    return {"control_mean_speed_mps": control, "treatment_mean_speed_mps": treatment,
            "relative_speed_reduction": reduction,
            "gate": reduction is not None and reduction >= minimum_reduction}


def run_case(spec, output):
    import traci
    import traci.constants as tc

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    topology = json.loads(Path(spec["topology"]).read_text(encoding="utf-8"))
    vehicles = ET.parse(spec["demand"]).getroot().findall("vehicle")
    routes = {v.get("id"): v.find("route").get("edges").split() for v in vehicles}
    net = load_network(spec["network"])
    types = {v.get("id"): v.get("vClass", "passenger") for v in ET.parse(spec["demand"]).getroot().findall("vType")}
    route_gate = len(routes) == len(vehicles) and all(v.get("type") in types and valid_route(
        net, routes[v.get("id")], types[v.get("type")]) for v in vehicles)
    if not route_gate:
        raise ValueError("Invalid routes, duplicate IDs or class permissions")
    scheduled = set(routes)
    departures = {v.get("id"): float(v.get("depart")) for v in vehicles}
    horizon = int(spec.get("horizon_s", PROTOCOL["demand_s"] + PROTOCOL["drain_s"]))
    cmd = [binary("sumo"), "--net-file", spec["network"], "--route-files", spec["demand"],
           "--additional-files", spec["program"], "--seed", str(spec["seed"]), "--step-length", "1",
           "--begin", "0", "--end", str(horizon), "--collision.check-junctions", "true",
           "--collision.action", "warn", "--time-to-teleport", "300", "--ignore-route-errors", "false",
           "--max-depart-delay", "-1", "--no-step-log", "true", "--duration-log.disable", "true",
           "--tripinfo-output", str(output / "tripinfo.xml"), "--tripinfo-output.write-unfinished", "true",
           "--error-log", str(output / "sumo-warnings.log"),
           "--collision-output", str(output / "collisions.xml")]
    if spec.get("repair_history"):
        cmd.extend(["--fcd-output", str(output / "fcd.xml.gz")])
    elif spec.get("diagnostic_outputs"):
        cmd.extend(["--fcd-output", str(output / "fcd.xml")])
    started = time.monotonic()
    conn = None
    departed, arrived = set(), set()
    collisions, teleports, unexpected = 0, 0, []
    mapping = topology["sumo_to_canonical"]
    lane_to_approach = {link["from_lane"]: (n["node_id"], n["approach_mapping"][link["from_edge"]])
                        for n in topology["nodes"] for link in n["sumo_links"]}
    allowed = {n["sumo_tls_id"]: [p["state"] for p in n["derived_phases"]] for n in topology["nodes"]}
    seconds = {n["node_id"]: {k: 0 for k in ("green", "yellow", "all_red")} for n in topology["nodes"]}
    signal_previous, timing_errors = {}, []
    movement_flow, movement_windows = Counter(), Counter()
    last_index = {}
    vehicle_digest, signal_digest = hashlib.sha256(), hashlib.sha256()
    backlog, queue_samples, edge_samples = [], defaultdict(list), []
    detector_hits = Counter()
    detector_lanes, stage_lengths = {}, defaultdict(list)
    bottleneck = spec.get("bottleneck")
    edge = bottleneck["edge_id"] if bottleneck else spec.get("observed_edge_id")
    stopped_seconds = 0
    with (output / "sumo-stdout.log").open("w", encoding="utf-8") as stdout, \
            gzip.open(output / "approaches.csv.gz", "wt", encoding="utf-8", newline="") as queuefile, \
            (output / "signals.csv").open("w", encoding="utf-8", newline="") as signalfile:
        queues = csv.writer(queuefile)
        queues.writerow(["time_s", "controller", "approach", "lane", "stopped_vehicles", "occupancy_percent", "vehicles"])
        signals = csv.writer(signalfile)
        signals.writerow(["start_s", "end_s", "controller", "phase_index", "state", "kind"])
        try:
            traci.start(cmd, stdout=stdout, numRetries=3)
            conn = traci.getConnection("default")
            dimensions = {tid: {"length_m": conn.vehicletype.getLength(tid),
                                "width_m": conn.vehicletype.getWidth(tid),
                                "min_gap_m": conn.vehicletype.getMinGap(tid)}
                          for tid in types}
            (output / "vehicle_dimensions.json").write_text(json.dumps(dimensions, indent=2) + "\n", encoding="utf-8")
            if set(conn.trafficlight.getIDList()) != set(mapping):
                raise ValueError("Runtime signal IDs do not match canonical mapping")
            for node in topology["nodes"]:
                tid = node["sumo_tls_id"]
                actual = conn.trafficlight.getControlledLinks(tid)
                wanted = defaultdict(set)
                for link in node["sumo_links"]:
                    wanted[link["link_index"]].add((link["from_lane"], link["to_lane"], link["via_lane"]))
                if len(actual) != node["signal_count"] or any(set(actual[i]) != wanted[i] for i in range(len(actual))):
                    raise ValueError(f"Runtime controlled-link mismatch: {tid}")
                conn.trafficlight.subscribe(tid, [tc.TL_RED_YELLOW_GREEN_STATE, tc.TL_CURRENT_PHASE])
            conn.simulation.subscribe([tc.VAR_DEPARTED_VEHICLES_IDS, tc.VAR_ARRIVED_VEHICLES_IDS,
                                       tc.VAR_COLLIDING_VEHICLES_NUMBER, tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER])
            for lane in sorted(lane_to_approach):
                conn.lane.subscribe(lane, [tc.LAST_STEP_VEHICLE_HALTING_NUMBER, tc.LAST_STEP_OCCUPANCY, tc.LAST_STEP_VEHICLE_NUMBER])
            if edge:
                conn.edge.subscribe(edge, [tc.LAST_STEP_VEHICLE_HALTING_NUMBER, tc.LAST_STEP_VEHICLE_NUMBER, tc.LAST_STEP_MEAN_SPEED])
            for detector in conn.inductionloop.getIDList():
                if f"_{spec['controller']}_" not in detector:
                    continue
                detector_lanes[detector] = conn.inductionloop.getLaneID(detector)
                detector_hits[detector] = 0
                conn.inductionloop.subscribe(detector, [tc.LAST_STEP_VEHICLE_NUMBER])
            for t in range(horizon):
                if bottleneck and t in PROTOCOL["bottleneck_window_s"]:
                    factor = PROTOCOL["bottleneck_speed_fraction"] if t == 1200 else 1
                    for lane, speed in bottleneck["lane_speeds_mps"].items():
                        conn.lane.setMaxSpeed(lane, speed*factor)
                conn.simulationStep()
                # SUMO exposes the signal applied during the step just completed.
                states = conn.trafficlight.getAllSubscriptionResults()
                for tid in sorted(mapping):
                    state = states[tid][tc.TL_RED_YELLOW_GREEN_STATE]
                    phase = states[tid][tc.TL_CURRENT_PHASE]
                    kind = signal_kind(state)
                    nid = mapping[tid]
                    if phase not in range(len(allowed[tid])) or state != allowed[tid][phase]:
                        unexpected.append([t, nid, phase, state])
                    seconds[nid][kind] += 1
                    signal_digest.update(f"{t},{nid},{phase},{state}\n".encode())
                    previous = signal_previous.get(tid)
                    if previous and (phase, state) != previous[1:]:
                        row = [previous[0], t, nid, previous[1], previous[2], signal_kind(previous[2])]
                        signals.writerow(row)
                        if row[-1] == "green":
                            stage_lengths[f"{nid}:{previous[1]}"].append(t-previous[0])
                        duration = t-previous[0]
                        expected_duration = next(n for n in topology["nodes"] if n["sumo_tls_id"] == tid)["derived_phases"][previous[1]]["duration"]
                        valid_duration = (10 <= duration <= 60) if row[-1] == "green" and spec["controller"] == "native_actuated" else duration == expected_duration
                        if phase != (previous[1]+1) % len(allowed[tid]) or not valid_duration:
                            timing_errors.append([t, nid, previous[1], phase, duration])
                    if not previous or (phase, state) != previous[1:]:
                        signal_previous[tid] = (t, phase, state)
                sim = conn.simulation.getSubscriptionResults()
                newly_departed = sim[tc.VAR_DEPARTED_VEHICLES_IDS]
                departed.update(newly_departed)
                arrived.update(sim[tc.VAR_ARRIVED_VEHICLES_IDS])
                collisions += sim[tc.VAR_COLLIDING_VEHICLES_NUMBER]
                teleports += sim[tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER]
                for vid in newly_departed:
                    conn.vehicle.subscribe(vid, [tc.VAR_SPEED, tc.VAR_ROUTE_INDEX, tc.VAR_ROAD_ID])
                vehicle_states = conn.vehicle.getAllSubscriptionResults()
                for vid, values in sorted(vehicle_states.items()):
                    speed = values[tc.VAR_SPEED]
                    stopped_seconds += speed < .1
                    index = values[tc.VAR_ROUTE_INDEX]
                    road = values[tc.VAR_ROAD_ID]
                    vehicle_digest.update(f"{t+1},{vid},{road},{index},{speed:.9f}\n".encode())
                    if not road.startswith(":"):
                        old = last_index.get(vid, 0)
                        route = routes[vid]
                        for j in range(old, index):
                            pair = (route[j], route[j+1])
                            movement_flow[pair] += 1
                            if 900 <= t < 1800:
                                movement_windows[("forward_window", *pair)] += 1
                            if 1800 <= t < 2700:
                                movement_windows[("reverse_window", *pair)] += 1
                        last_index[vid] = index
                for lane, values in conn.lane.getAllSubscriptionResults().items():
                    nid, approach = lane_to_approach[lane]
                    q, occupancy, number = (values[tc.LAST_STEP_VEHICLE_HALTING_NUMBER], values[tc.LAST_STEP_OCCUPANCY], values[tc.LAST_STEP_VEHICLE_NUMBER])
                    queues.writerow([t+1, nid, approach, lane, q, occupancy, number])
                    queue_samples[lane].append((q, occupancy))
                for detector, values in conn.inductionloop.getAllSubscriptionResults().items():
                    detector_hits[detector] += values[tc.LAST_STEP_VEHICLE_NUMBER]
                if edge:
                    values = conn.edge.getSubscriptionResults(edge)
                    edge_samples.append([t+1, values[tc.LAST_STEP_VEHICLE_HALTING_NUMBER],
                                         values[tc.LAST_STEP_VEHICLE_NUMBER], values[tc.LAST_STEP_MEAN_SPEED]])
                due = sum(d <= t+1 for d in departures.values())
                backlog.append([t+1, len(departed-arrived), due-len(departed), due-len(arrived)])
            running = set(conn.vehicle.getIDList())
            for tid, previous in sorted(signal_previous.items()):
                signals.writerow([previous[0], horizon, mapping[tid], previous[1], previous[2], signal_kind(previous[2])])
            conn.close()
            conn = None
        finally:
            if conn is not None:
                conn.close()
    elapsed = time.monotonic()-started
    accounting = vehicle_accounting(scheduled, departed, arrived, running)
    trips = ET.parse(output / "tripinfo.xml").getroot().findall("tripinfo")
    outcomes = {v.get("id"): {"status": "completed" if v.get("id") in arrived else "running",
                              "waiting_s": float(v.get("waitingTime")), "departure_delay_s": float(v.get("departDelay")),
                              "depart_s": float(v.get("depart")), "arrival_s": float(v.get("arrival")),
                              "duration_s": float(v.get("duration"))} for v in trips}
    for vid in sorted(scheduled-departed):
        outcomes[vid] = {"status": "uninserted", "waiting_s": 0, "departure_delay_s": max(0, horizon-departures[vid])}
    waits = [v["waiting_s"] for v in outcomes.values()]
    observed_inputs = set(outcomes) == scheduled and {v.get("id") for v in trips} == departed
    signal_seconds = reconcile_signals(seconds, horizon)
    warning_text = (output / "sumo-warnings.log").read_text(encoding="utf-8")
    detector_coverage = {n["node_id"]: {p["phase_id"]: any(
        lane in detector_lanes.values() for lane in {
            link["from_lane"] for link in n["sumo_links"] if p["sumo_state"][link["link_index"]] in "Gg"})
        for p in n["phases"]} for n in topology["nodes"]}
    detector_gate = (spec["controller"] != "native_actuated" or
                     (bool(detector_hits) and sum(detector_hits.values()) > 0
                      and all(all(stages.values()) for stages in detector_coverage.values())
                      and "no controlling detector" not in warning_text.lower()
                      and all(all(10 <= length <= 60 for length in lengths) for lengths in stage_lengths.values())
                      and any(length > 10 for lengths in stage_lengths.values() for length in lengths)))
    engineering = {"valid_routes_permissions_mappings_served": route_gate and not spec["audit_errors"] and observed_inputs,
                   "no_conflicting_protected_greens": not spec["audit_errors"],
                   "expected_signal_states": not unexpected,
                   "no_collisions": collisions == 0 and "collision" not in warning_text.lower(),
                   "no_teleports": teleports == 0 and "teleporting" not in warning_text.lower(),
                   "vehicle_reconciliation": accounting["accounting_gate"] and observed_inputs,
                   "signal_time_reconciliation": signal_seconds["gate"],
                   "clearance_and_stage_order": not timing_errors,
                   "actuation_detectors": detector_gate}
    metrics = {**accounting, "completion_fraction": len(arrived)/len(scheduled),
               "uninserted_fraction": accounting["uninserted"]/len(scheduled),
               "mean_stopped_wait_s_per_scheduled": sum(waits)/len(scheduled), "p95_waiting_s": percentile95(waits),
               "total_waiting_s": sum(waits), "stopped_vehicle_seconds": stopped_seconds,
               "mean_departure_delay_s": sum(v["departure_delay_s"] for v in outcomes.values())/len(scheduled),
               "collisions": collisions, "teleports": teleports, "unexpected_states": unexpected, "timing_errors": timing_errors,
               "signal_seconds": signal_seconds, "engineering_gates": engineering,
               "engineering_pass": all(engineering.values()),
               "detector_lanes": detector_lanes, "detector_hits": dict(detector_hits),
               "detector_stage_coverage": detector_coverage, "green_duration_samples_s": dict(stage_lengths),
               "queue_summary": {lane: {"mean_stopped": sum(q for q, o in xs)/len(xs), "max_stopped": max(q for q, o in xs),
                                         "mean_occupancy_percent": sum(o for q, o in xs)/len(xs)} for lane, xs in queue_samples.items()},
               "vehicle_trace_sha256": vehicle_digest.hexdigest(), "signal_trace_sha256": signal_digest.hexdigest(),
               "elapsed_wall_s": elapsed, "simulation_seconds_per_wall_second": horizon/elapsed}
    for filename, data in (("metrics.json", metrics), ("vehicle_outcomes.json", outcomes),
                           ("backlog.json", backlog), ("bottleneck_trace.json", edge_samples),
                           ("movement_flow.json", [{"from": a, "to": b, "vehicles": v} for (a, b), v in sorted(movement_flow.items())]),
                           ("movement_windows.json", [{"window": w, "from": a, "to": b, "vehicles": v} for (w, a, b), v in sorted(movement_windows.items())])):
        (output / filename).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metrics
