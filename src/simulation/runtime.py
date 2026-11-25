"""One-second SUMO clock, explicit signals and complete scheduled-vehicle accounting."""
import hashlib
import importlib.metadata
import json
import os
import platform
import uuid
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from jsonschema import Draft7Validator

from contracts.contracts_sdk import load_schema
from contracts.research import ALL_RESEARCH_SCENARIOS, RESEARCH_SCENARIOS, TIMING, TOPOLOGY_ID
from contracts.scenarios import ScenarioRegistry
from src.control.actuator import ActuatorStateMachine
from src.control.research import action_mask
from .build_network import binary, write_xml

TIMELOSS_COST = os.environ.get("EDGEFLOW_TIMELOSS_COST") == "1"  # experiment: node reward matches the delay score


class InvalidRun(RuntimeError):
    """Scientific invalidity must not be retried until a favorable run appears."""
    scientifically_invalid = True


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def occupancy_ratio(percent):
    value = float(percent) / 100.0
    if not np.isfinite(value) or not -1e-9 <= value <= 1 + 1e-9:
        raise ValueError(f"Invalid SUMO occupancy: {percent}")
    return min(1., max(0., value))


def reconcile_signal_seconds(green_seconds, clearance_seconds, elapsed_s, node_ids):
    """Return network node-seconds clearing after reconciling every signal clock."""
    totals = {}
    for node_id in node_ids:
        green = sum(green_seconds[node_id].values())
        clearance = clearance_seconds[node_id]
        if green < 0 or clearance < 0 or green + clearance != elapsed_s:
            raise RuntimeError(f"Signal-time accounting does not reconcile at {node_id}")
        totals[node_id] = clearance
    if set(green_seconds) != set(node_ids) or set(clearance_seconds) != set(node_ids):
        raise RuntimeError("Signal-time accounting does not cover every canonical intersection")
    return sum(totals.values()), totals


def generate_demand(topology, scenario, seed, duration, intensity, path):
    profile = ALL_RESEARCH_SCENARIOS[scenario]
    rates = ScenarioRegistry.get_flow_rates(profile["profile"])
    rng = np.random.default_rng(seed)
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="car", accel="2.6", decel="4.5", sigma="0.5",
                  length="5", minGap="2.5", maxSpeed="13.89")
    scheduled = []
    for route in topology["routes"]:
        ET.SubElement(root, "route", id=route["route_id"], edges=" ".join(route["edges"]))
        rate = rates[f'f_{route["origin"]}_{route["axis"]}'] * intensity
        t = float(rng.exponential(1 / rate))
        while t < duration:
            scheduled.append({"depart": t, "route": route["route_id"]})
            t += float(rng.exponential(1 / rate))
    scheduled.sort(key=lambda row: (row["depart"], row["route"]))
    result = {}
    for i, row in enumerate(scheduled):
        vid = f"v{i:06d}"
        row["depart"] = round(row["depart"], 6)
        result[vid] = row
        ET.SubElement(root, "vehicle", id=vid, type="car", route=row["route"],
                      depart=str(row["depart"]), departLane="0", departSpeed="max")
    write_xml(root, path)
    return result


def validate_network(topology, network_path, generic=False):
    if generic:
        if not 2 <= len(topology["nodes"]) <= 32:
            raise ValueError("Expected 2–32 signalized junctions")
        network = ET.parse(network_path).getroot()
        programs = {t.get("id"): t for t in network.findall("tlLogic")}
        for node in topology["nodes"]:
            native = programs[node.get("sumo_tls_id",node["node_id"])]
            states = {p.get("state") for p in native.findall("phase")}
            if len(node["phases"]) < 2 or any(p["sumo_state"] not in states for p in node["phases"]):
                raise ValueError("Unaudited phase mapping")
        return
    if topology["topology_id"] != TOPOLOGY_ID:
        raise ValueError("Research runtime requires the corrected topology")
    net = ET.parse(network_path).getroot()
    connections = {(c.get("from"), c.get("to")): c for c in net.findall("connection") if c.get("tl")}
    if len(topology["routes"]) != 8 or len(topology["nodes"]) != 4:
        raise ValueError("Expected four intersections and eight boundary routes")
    for route in topology["routes"]:
        if len(route["edges"]) != 3 or any(pair not in connections for pair in zip(route["edges"], route["edges"][1:])):
            raise ValueError("Every route must cross two controlled junctions")
    for node in topology["nodes"]:
        for link in node["sumo_links"]:
            c = connections[(link["from"], link["to"])]
            if c.get("tl") != node["node_id"] or int(c.get("linkIndex")) != link["index"]:
                raise ValueError("Signal mapping does not match network")
        for phase in node["phases"]:
            state = phase["sumo_state"]
            if len(state) != len(node["sumo_links"]):
                raise ValueError("Incomplete signal mapping")
            for link in node["sumo_links"]:
                if (state[link["index"]] == "G") != (link["from"] in phase["approaches"]):
                    raise ValueError("Conflicting signal mapping")


class SumoRuntime:
    def __init__(self, topology_path, network_path, output, scenario="balanced", seed=20000,
                 demand_s=1800, drain_s=600, intensity=1.0, trace=True,
                 wait_penalty_lambda=0., benchmark_mode=False, check_every=1):
        # EDGEFLOW_LIBSUMO=1 runs SUMO in-process (no socket round-trips); one simulation per process.
        self.libsumo = os.environ.get("EDGEFLOW_LIBSUMO") == "1"
        if self.libsumo:
            import libsumo as traci
        else:
            import traci
        import traci.constants as tc
        self.tc = tc
        self.connection = None
        self._slot = None
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.trace = None
        self.topology = json.loads(Path(topology_path).read_text())
        self.benchmark_mode = benchmark_mode
        # Telemetry-schema and signal-readback checks run when time % check_every == 0 (always at t=0).
        # 1 checks every step; larger values are for training rollouts only, never for evidence runs.
        if type(check_every) is not int or check_every < 1:
            raise ValueError("check_every must be a positive integer")
        self.check_every = check_every
        validate_network(self.topology, network_path, generic=benchmark_mode)
        if (not benchmark_mode and scenario not in ALL_RESEARCH_SCENARIOS) or demand_s <= 0 or drain_s < 0 or not .01 <= intensity <= 10:
            raise ValueError("Invalid research scenario or horizon")
        if not np.isfinite(wait_penalty_lambda) or wait_penalty_lambda < 0:
            raise ValueError("wait_penalty_lambda must be finite and nonnegative")
        self.scenario, self.seed = scenario, int(seed)
        self.wait_penalty_lambda = float(wait_penalty_lambda)
        self._vmax = {}  # raw edge id -> lane 0 max speed (TIMELOSS_COST)
        self.demand_s, self.horizon = int(demand_s), int(demand_s + drain_s)
        self.edge_ids={a:n.get('sumo_edges',{}).get(a,a) for n in self.topology['nodes'] for a in n['approaches']}
        self.logical_edges={raw:canonical for canonical,raw in self.edge_ids.items()}
        self.time = 0
        routes_path = self.output / "demand.rou.xml"
        if benchmark_mode:
            from src.benchmark.demand import generate_demand as generate_suite_demand
            self.scheduled = generate_suite_demand(self.topology, scenario, seed, demand_s, intensity, routes_path)
        else:
            self.scheduled = generate_demand(self.topology, scenario, seed, demand_s, intensity, routes_path)
        self.scheduled_by_route = {app: [] for node in self.topology["nodes"] for app in node["approaches"]}
        # Due-but-undeparted vehicles, kept incrementally (insertion order == scheduled order, so sums are unchanged).
        self._due_at, self._due = {}, {}
        self._due_by_route = {app: {} for app in self.scheduled_by_route}
        for vid, row in self.scheduled.items():
            self.scheduled_by_route[row["route"]].append((vid, row))
            self._due_at.setdefault(int(np.floor(row["depart"])) + 1, []).append(vid)  # first t with depart < t
        self.departed, self.arrived = set(), set()
        self.previous_ids = {}
        self.approach_seen = {app: set() for node in self.topology["nodes"] for app in node["approaches"]}
        self.active_time_loss = {}
        self.departure_delay = {}
        self.waiting = {vid: 0. for vid in self.scheduled}
        self.active_speeds = {}
        self.approach_wait = {app: {} for n in self.topology["nodes"] for app in n["approaches"]}
        self.invalid = []
        self.actuator = ActuatorStateMachine(3, 2)
        self.last_served = {}
        self.green_seconds = {}
        self.service_gaps = {}
        self.queue_trace = []
        self.clearance_seconds = {}
        self.schema_validator = Draft7Validator(load_schema("telemetry"))
        self.metadata = {"topology_id": self.topology["topology_id"], "topology_sha256": file_hash(topology_path),
                         "network_sha256": file_hash(network_path), "demand_sha256": file_hash(routes_path),
                         "scenario": scenario, "seed": seed, "timing": TIMING, "demand_s": demand_s,
                         "drain_s": drain_s, "intensity": intensity, "provenance": "sumo_libsumo" if self.libsumo else "sumo_traci",
                         "runtime_sha256": file_hash(__file__),
                         "reward_version": "wait_tail_v1", "wait_penalty_lambda": self.wait_penalty_lambda,
                         "python": platform.python_version(), "versions": {
                             name: importlib.metadata.version(name) for name in ("eclipse-sumo", "traci", "numpy")
                             + (("libsumo",) if self.libsumo else ())}}
        (self.output / "metadata.json").write_text(json.dumps(self.metadata, indent=2))
        label = uuid.uuid4().hex
        try:
            from src.benchmark.resources import simulator_slot
            self._slot = simulator_slot()
            self._slot.__enter__()
            traci.start([binary("sumo"), "--net-file", str(Path(network_path).resolve()),
                         "--route-files", str(routes_path.resolve()), "--seed", str(seed), "--step-length", "1",
                         "--time-to-teleport", "-1", "--no-step-log", "true", "--duration-log.disable", "true",
                         "--tripinfo-output", str((self.output / "tripinfo.xml").resolve()),
                         "--tripinfo-output.write-unfinished", "true", "--tripinfo-output.write-undeparted", "true",
                         "--error-log", str((self.output / "sumo-error.log").resolve())] + (["--lateral-resolution", ".4"] if benchmark_mode else []),
                         **({} if self.libsumo else dict(label=label, verbose=False)))
            self.connection = traci if self.libsumo else traci.getConnection(label)
            for node in self.topology["nodes"]:
                for app in node["approaches"]:
                    self.connection.edge.subscribe(self.edge_ids[app], (tc.LAST_STEP_VEHICLE_ID_LIST,
                        tc.LAST_STEP_VEHICLE_HALTING_NUMBER, tc.LAST_STEP_OCCUPANCY, tc.LAST_STEP_MEAN_SPEED))
            self.trace = (self.output / "signals.jsonl").open("w") if trace else None
            for node in self.topology["nodes"]:
                nid = node["node_id"]
                self.actuator.get_or_create_node(nid, node["phases"][0]["phase_id"])
                self.last_served[nid] = {p["phase_id"]: 0 for p in node["phases"]}
                self.green_seconds[nid] = {p["phase_id"]: 0 for p in node["phases"]}
                self.clearance_seconds[nid] = 0
            self._apply_signals({})
            self.telemetry = self._telemetry({})
        except BaseException as error:
            self.fail(error)
            raise

    def fail(self, error):
        self.invalid.append(str(error))
        (self.output / "failure.json").write_text(json.dumps({"valid": False, "reasons": self.invalid}, indent=2))
        self.close()

    def _apply_signals(self, commands):
        for node in self.topology["nodes"]:
            nid = node["node_id"]
            signal = self.actuator.nodes[nid]
            phase = next(p for p in node["phases"] if p["phase_id"] == signal.current_phase_id)
            state = phase["sumo_state"]
            if signal.state == "YELLOW":
                state = state.replace("G", "y").replace("g", "y")
            elif signal.state == "ALL_RED":
                state = "r" * len(state)
            self.connection.trafficlight.setRedYellowGreenState(node.get("sumo_tls_id",nid), state)
            if not self.trace and self.time % self.check_every:
                continue  # unverified step: set above, readback skipped (never when tracing)
            actual = self.connection.trafficlight.getRedYellowGreenState(node.get("sumo_tls_id",nid))
            if actual != state:
                raise RuntimeError("SUMO did not execute the requested signal state")
            if self.trace:
                self.trace.write(json.dumps({"time_s": self.time, "node_id": nid, "command": commands.get(nid),
                                             "phase": signal.current_phase_id, "state": signal.state,
                                             "pending": signal.pending_phase_id, "expected": state, "actual": actual}) + "\n")

    def _telemetry(self, crossings):
        result = {}
        for node in self.topology["nodes"]:
            nid = node["node_id"]
            signal = self.actuator.nodes[nid]
            if signal.state == "GREEN":
                self.last_served[nid][signal.current_phase_id] = self.time
            data = {"node_id": nid, "source_type": "simulation", "simulation_time_s": self.time,
                    "timestamp_ms": self.time * 1000, "current_phase_id": signal.current_phase_id,
                    "pending_phase_id": signal.pending_phase_id, "signal_state": signal.state,
                    "elapsed_green_s": signal.elapsed_green_time(self.time),
                    "phase_service_age_s": {p: self.time-t for p, t in self.last_served[nid].items()},
                    "approaches": []}
            for app in node["approaches"]:
                edge = self.connection.edge.getSubscriptionResults(self.edge_ids[app])
                active_ids = edge[self.tc.LAST_STEP_VEHICLE_ID_LIST]
                stopped_waits = [self.approach_wait[app].get(vid, 0.) for vid in active_ids
                                 if self.active_speeds.get(vid, 1.) <= .1]
                external_ages = [self.time - self.scheduled[vid]["depart"] for vid in self._due_by_route[app]]
                data["approaches"].append({"approach_id": app, "queue_vehicles": edge[self.tc.LAST_STEP_VEHICLE_HALTING_NUMBER],
                                           "occupancy_ratio": occupancy_ratio(edge[self.tc.LAST_STEP_OCCUPANCY]),
                                           "mean_speed_mps": max(0., edge[self.tc.LAST_STEP_MEAN_SPEED]),
                                           "flow_veh_per_s": crossings.get(app, 0), "confidence": 1.0,
                                           "stopped_wait_sum_s": sum(stopped_waits),
                                           "oldest_stopped_wait_s": max(stopped_waits, default=0.),
                                           "external_due_count": len(external_ages),
                                           "external_wait_sum_s": sum(external_ages),
                                           "oldest_external_wait_s": max(external_ages, default=0.)})
            if self.time % self.check_every == 0:
                self.schema_validator.validate(data)
            result[nid] = data
        return result

    def step(self, actions):
        if self.time >= self.horizon:
            raise RuntimeError("Episode already ended")
        if set(actions) != set(self.actuator.nodes):
            raise ValueError("Actions must cover all canonical node IDs")
        commands = {}
        for node in self.topology["nodes"]:
            nid = node["node_id"]
            action = actions[nid]
            if not isinstance(action, (int, np.integer)) or not 0 <= action < len(node["phases"]):
                raise ValueError("Invalid action")
            if self.benchmark_mode:
                from src.control.phase_dqn import phase_mask
                mask = phase_mask(node, self.telemetry[nid])
            else:
                mask = action_mask(node, self.telemetry[nid])
            # The same safety envelope applies to every baseline and RL.
            applied = action if mask[action] else int(np.flatnonzero(mask)[0])
            command = {"command_id": f"{self.time}-{nid}", "node_id": nid,
                       "target_phase_id": node["phases"][applied]["phase_id"],
                       "min_green_s": 10., "max_green_s": 60., "controller": "research_runtime"}
            ack = self.actuator.process_command(command, now=self.time)
            if ack["status"] == "REJECTED":
                raise RuntimeError(ack["reason"])
            commands[nid] = {"requested_action": int(action), "applied_action": applied, "command": command, "ack": ack}
        weighted_wait_cost = 0.
        # Same cost split by approach (entry approach for vehicles still outside); other lanes are unattributed.
        self.approach_cost = cost = dict.fromkeys(self.approach_wait, 0.)
        crossing_total = {}
        interval = min(5, self.horizon-self.time)
        for _ in range(interval):
            self.actuator.step(self.time)
            # Max green is enforced on the physical clock as well as at decisions.
            for node in self.topology["nodes"]:
                signal = self.actuator.nodes[node["node_id"]]
                if signal.elapsed_green_time(self.time) >= 60:
                    alternatives=[p for p in node['phases'] if p['phase_id']!=signal.current_phase_id]
                    if self.benchmark_mode:
                        observed={a['approach_id']:a for a in self.telemetry[node['node_id']]['approaches']}
                        demanded=[p for p in alternatives if any(observed[a]['queue_vehicles']+observed[a]['external_due_count']>0 for a in p['approaches'])]
                        alternatives=demanded or alternatives
                    alternate=min(alternatives,key=lambda p:self.last_served[node['node_id']][p['phase_id']])['phase_id']
                    self.actuator.process_command({"command_id": f"max-{self.time}", "node_id": node["node_id"],
                                                   "target_phase_id": alternate, "min_green_s": 10.,
                                                   "max_green_s": 60., "controller": "safety_envelope"}, self.time)
            bottleneck = RESEARCH_SCENARIOS.get(self.scenario, {}) if not self.benchmark_mode else {}
            if self.benchmark_mode and self.scenario == "downstream_bottleneck":
                edge = self.topology["routes"][0]["edges"][-1]
                if not hasattr(self, "_original_speeds"):
                    lanes = [lane for lane in self.connection.lane.getIDList()
                             if self.connection.lane.getEdgeID(lane) == edge]
                    self._original_speeds = {lane: self.connection.lane.getMaxSpeed(lane) for lane in lanes}
                    if not self._original_speeds:
                        raise ValueError(f"Bottleneck edge has no lanes: {edge}")
                speed = 2. if self.demand_s/3 <= self.time < 2*self.demand_s/3 else None
                for lane, original in self._original_speeds.items():
                    self.connection.lane.setMaxSpeed(lane, speed if speed is not None else original)
            if "edge" in bottleneck:
                speed = bottleneck["speed_mps"] if bottleneck["begin_s"] <= self.time < bottleneck["end_s"] else 13.89
                self.connection.edge.setMaxSpeed(bottleneck["edge"], speed)
            self._apply_signals(commands if _ == 0 else {})
            for node in self.topology["nodes"]:
                signal = self.actuator.nodes[node["node_id"]]
                if signal.state == "GREEN":
                    self.green_seconds[node["node_id"]][signal.current_phase_id] += 1
                else:
                    self.clearance_seconds[node["node_id"]] += 1
            self.connection.simulationStep()
            self.time += 1
            sim, vehicles = self.connection.simulation, self.connection.vehicle
            if sim.getCollidingVehiclesNumber() or sim.getStartingTeleportNumber():
                raise InvalidRun("Collision or teleport invalidates this run")
            for vid in self._due_at.pop(self.time, ()):
                if vid in self.departed:  # left on time, never waited outside the network
                    continue
                self._due[vid] = None
                self._due_by_route[self.scheduled[vid]["route"]][vid] = None
            for vid in sim.getDepartedIDList():
                self.departed.add(vid)
                vehicles.subscribe(vid, (self.tc.VAR_SPEED, self.tc.VAR_ROAD_ID))
                if self._due.pop(vid, 0) is None:
                    del self._due_by_route[self.scheduled[vid]["route"]][vid]
            self.arrived.update(sim.getArrivedIDList())
            vehicle_data = vehicles.getAllSubscriptionResults()
            active = set(vehicle_data)
            self.active_speeds = {vid: float(data[self.tc.VAR_SPEED]) for vid, data in vehicle_data.items()}
            if self.departed != active | self.arrived or active & self.arrived:
                raise InvalidRun("Unexplained vehicle-accounting loss")
            pending = self._due
            outside = 0
            for vid in pending:
                age = self.time-self.scheduled[vid]["depart"]
                w = min(1., age) * (1. + self.wait_penalty_lambda * max(0., age) / 120.)
                outside += w
                cost[self.scheduled[vid]["route"]] += w
            weighted_wait_cost += outside
            for vid in active:
                if TIMELOSS_COST:  # experiment: per-approach cost = SUMO-style time loss, 1 - v/v_max per second
                    raw = vehicle_data[vid][self.tc.VAR_ROAD_ID]
                    road = self.logical_edges.get(raw, raw)
                    if road in self.approach_wait:
                        if raw not in self._vmax:
                            self._vmax[raw] = max(float(self.connection.lane.getMaxSpeed(f"{raw}_0")), .1)
                        cost[road] += 1. - min(vehicle_data[vid][self.tc.VAR_SPEED], self._vmax[raw]) / self._vmax[raw]
                if vehicle_data[vid][self.tc.VAR_SPEED] <= .1:
                    self.waiting[vid] += 1
                    w = 1. + self.wait_penalty_lambda * self.waiting[vid] / 120.
                    weighted_wait_cost += w
                    road = self.logical_edges.get(vehicle_data[vid][self.tc.VAR_ROAD_ID],vehicle_data[vid][self.tc.VAR_ROAD_ID])
                    if road in self.approach_wait:
                        if not TIMELOSS_COST:
                            cost[road] += w
                        ledger = self.approach_wait[road]
                        ledger[vid] = ledger.get(vid, 0) + 1
            for node in self.topology["nodes"]:
                for app in node["approaches"]:
                    ids = set(self.connection.edge.getSubscriptionResults(self.edge_ids[app])[self.tc.LAST_STEP_VEHICLE_ID_LIST])
                    self.approach_seen[app].update(ids)
                    # Removed vehicles cannot be mistaken for flow: losses/teleports fail above.
                    crossed = len(self.previous_ids.get(app, set()) - ids)
                    crossing_total[app] = crossing_total.get(app, 0) + crossed
                    self.previous_ids[app] = ids
            self.actuator.step(self.time)
            for nid, signal in self.actuator.nodes.items():
                if signal.state == "GREEN":
                    self.last_served[nid][signal.current_phase_id] = self.time
        self.telemetry = self._telemetry({k: v / interval for k, v in crossing_total.items()})
        if self.benchmark_mode:
            total=0
            for node in self.topology['nodes']:
                data=self.telemetry[node['node_id']]
                apps={a['approach_id']:a for a in data['approaches']}
                total+=sum(a['queue_vehicles']+a['external_due_count'] for a in apps.values())
                for phase in node['phases']:
                    key=phase['phase_id']
                    demanded=any(apps[a]['queue_vehicles']+apps[a]['external_due_count']>0 for a in phase['approaches'])
                    active=data['signal_state']=='GREEN' and data['current_phase_id']==key
                    current,maximum=self.service_gaps.get(key,(0,0))
                    current=current+interval if demanded and not active else 0
                    self.service_gaps[key]=(current,max(current,maximum))
            self.queue_trace.append((self.time,total))
        if self.trace:
            self.trace.flush()
        terminated = self.time >= self.demand_s and len(self.arrived) == len(self.scheduled)
        truncated = self.time >= self.horizon and not terminated
        return self.telemetry, -weighted_wait_cost / (20 * len(self.topology["nodes"]) * interval), terminated, truncated

    def finish(self):
        self.close()
        # SUMO tripinfo contains final timeLoss even for vehicles arriving in the last tick.
        trips = {t.get("id"): t for t in ET.parse(self.output / "tripinfo.xml").getroot().findall("tripinfo")}
        accrued = []
        wait = []
        for vid, row in self.scheduled.items():
            if vid in self.departed:
                if vid not in trips:
                    raise InvalidRun(f"Missing tripinfo for departed vehicle {vid}")
                trip = trips[vid]
                accrued.append(float(trip.get("timeLoss")) + float(trip.get("departDelay")))
            else:
                delay = max(0., self.time-row["depart"])
                accrued.append(delay)
                ledger = self.approach_wait[row["route"]]
                ledger[vid] = delay
        approach_waits = {app: [] for node in self.topology["nodes"] for app in node["approaches"]}
        for vid, row in self.scheduled.items():
            if vid in self.departed:
                trip = trips[vid]
                entry_wait = float(trip.get("departDelay"))
                wait.append(float(trip.get("waitingTime")) + entry_wait)
                for approach in self.approach_seen:
                    if vid in self.approach_seen[approach]:
                        local_wait = self.approach_wait[approach].get(vid, 0.)
                        if approach == row["route"]:
                            local_wait += entry_wait
                        approach_waits[approach].append(local_wait)
            else:
                entry_wait = max(0., self.time-row["depart"])
                wait.append(entry_wait)
                approach_waits[row["route"]].append(entry_wait)
        approach_p95 = {app: float(np.percentile(values, 95)) if values else 0.
                        for app, values in approach_waits.items()}
        worst_approach_wait = max((max(values, default=0.) for values in approach_waits.values()), default=0.)
        legacy_worst_approach_wait = max(
            (max(values.values(), default=0.) for values in self.approach_wait.values()), default=0.)
        clearance_total, clearance_by_node = reconcile_signal_seconds(
            self.green_seconds, self.clearance_seconds, self.time,
            [node["node_id"] for node in self.topology["nodes"]])
        result = {**self.metadata, "metrics_version": 3, "valid": not self.invalid, "failure_reasons": self.invalid,
                  "time_s": self.time, "scheduled": len(self.scheduled), "departed": len(self.departed),
                  "completed": len(self.arrived), "unfinished": len(self.departed-self.arrived),
                  "uninserted": len(self.scheduled)-len(self.departed),
                  "delay_per_scheduled_s": float(np.mean(accrued)) if accrued else 0.,
                  "p95_wait_s": float(np.percentile(wait, 95)) if wait else 0.,
                  "worst_approach_wait_s": worst_approach_wait,
                  "legacy_worst_approach_wait_s": legacy_worst_approach_wait,
                  "approach_p95_wait_s": approach_p95,
                  "max_approach_p95_wait_s": max(approach_p95.values(), default=0.),
                  "signal_green_seconds": self.green_seconds,
                  "signal_clearance_seconds": clearance_total,
                  "signal_clearance_seconds_by_node": clearance_by_node,
                  "collisions": 0, "teleports": 0, "accounting_losses": 0}
        if result["scheduled"] != result["completed"] + result["unfinished"] + result["uninserted"]:
            raise InvalidRun("Vehicle accounting does not balance")
        if self.benchmark_mode:
            result["metrics_version"] = 3
            result["signal_clearance_seconds_by_node"] = {
                nid: self.time - sum(phases.values()) for nid, phases in self.green_seconds.items()}
            result["total_signal_clearance_node_seconds"] = sum(result["signal_clearance_seconds_by_node"].values())
            result.pop("signal_clearance_seconds")
            result['maximum_demanded_service_gap_s']={key:value[1] for key,value in self.service_gaps.items()}
            result['service_gap_resolution_s']=5
            result['throughput_veh_per_s']=result['completed']/max(self.time,1)
            result['queue_backlog_trace_columns']=['time_s','stopped_plus_due_entry_vehicles']
            result['queue_backlog_trace']=self.queue_trace
            result['recovery_s']=None
            result['recovery_censored']=self.scenario in ('downstream_bottleneck','directional_reversal')
            if result['recovery_censored']:
                end=2*self.demand_s/3
                before=[q for t,q in self.queue_trace if self.demand_s/3-60<=t<self.demand_s/3]
                threshold=np.mean(before)+max(.1*np.mean(before),1.) if before else 0.
                start=None
                for t,q in self.queue_trace:
                    if t<end:
                        continue
                    start=t if q<=threshold and start is None else start
                    if q>threshold:
                        start=None
                    if start is not None and t-start>=60:
                        result['recovery_s']=start-end
                        result['recovery_censored']=False
                        break
            result["vehicle_classes"] = {}
            for kind in sorted({row["vehicle_class"] for row in self.scheduled.values()}):
                ids = [vid for vid,row in self.scheduled.items() if row["vehicle_class"] == kind]
                indices = [i for i,row in enumerate(self.scheduled.values()) if row["vehicle_class"] == kind]
                result["vehicle_classes"][kind] = dict(scheduled=len(ids), completed=sum(vid in self.arrived for vid in ids),
                    unfinished=sum(vid in self.departed-self.arrived for vid in ids),
                    uninserted=sum(vid not in self.departed for vid in ids),
                    delay_per_scheduled_s=float(np.mean([accrued[i] for i in indices])),
                    p95_wait_s=float(np.percentile([wait[i] for i in indices],95)))
        (self.output / "metrics.json").write_text(json.dumps(result, indent=2))
        return result

    def close(self):
        try:
            if self.connection is not None:
                self.connection.close()
                self.connection = None
        finally:
            if self.trace:
                self.trace.close()
                self.trace = None
            if self._slot is not None:
                self._slot.__exit__(None, None, None)
                self._slot = None
