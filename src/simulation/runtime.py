"""One-second SUMO clock, explicit signals and complete scheduled-vehicle accounting."""
import hashlib
import importlib.metadata
import json
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


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def occupancy_ratio(percent):
    value = float(percent) / 100.0
    if not np.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"Invalid SUMO occupancy: {percent}")
    return value


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


def validate_network(topology, network_path):
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
                 wait_penalty_lambda=0.):
        import traci
        import traci.constants as tc
        self.tc = tc
        self.connection = None
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.trace = None
        self.topology = json.loads(Path(topology_path).read_text())
        validate_network(self.topology, network_path)
        if scenario not in ALL_RESEARCH_SCENARIOS or demand_s <= 0 or drain_s < 0 or not .01 <= intensity <= 10:
            raise ValueError("Invalid research scenario or horizon")
        if not np.isfinite(wait_penalty_lambda) or wait_penalty_lambda < 0:
            raise ValueError("wait_penalty_lambda must be finite and nonnegative")
        self.scenario, self.seed = scenario, int(seed)
        self.wait_penalty_lambda = float(wait_penalty_lambda)
        self.demand_s, self.horizon = int(demand_s), int(demand_s + drain_s)
        self.time = 0
        routes_path = self.output / "demand.rou.xml"
        self.scheduled = generate_demand(self.topology, scenario, seed, demand_s, intensity, routes_path)
        self.scheduled_by_route = {app: [] for node in self.topology["nodes"] for app in node["approaches"]}
        for vid, row in self.scheduled.items():
            self.scheduled_by_route[row["route"]].append((vid, row))
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
        self.clearance_seconds = {}
        self.schema_validator = Draft7Validator(load_schema("telemetry"))
        self.metadata = {"topology_id": TOPOLOGY_ID, "topology_sha256": file_hash(topology_path),
                         "network_sha256": file_hash(network_path), "demand_sha256": file_hash(routes_path),
                         "scenario": scenario, "seed": seed, "timing": TIMING, "demand_s": demand_s,
                         "drain_s": drain_s, "intensity": intensity, "provenance": "sumo_traci",
                         "runtime_sha256": file_hash(__file__),
                         "reward_version": "wait_tail_v1", "wait_penalty_lambda": self.wait_penalty_lambda,
                         "python": platform.python_version(), "versions": {
                             name: importlib.metadata.version(name) for name in ("eclipse-sumo", "traci", "numpy")}}
        (self.output / "metadata.json").write_text(json.dumps(self.metadata, indent=2))
        label = uuid.uuid4().hex
        try:
            traci.start([binary("sumo"), "--net-file", str(Path(network_path).resolve()),
                         "--route-files", str(routes_path.resolve()), "--seed", str(seed), "--step-length", "1",
                         "--time-to-teleport", "-1", "--no-step-log", "true", "--duration-log.disable", "true",
                         "--tripinfo-output", str((self.output / "tripinfo.xml").resolve()),
                         "--tripinfo-output.write-unfinished", "true", "--tripinfo-output.write-undeparted", "true",
                         "--error-log", str((self.output / "sumo-error.log").resolve())], label=label, verbose=False)
            self.connection = traci.getConnection(label)
            for node in self.topology["nodes"]:
                for app in node["approaches"]:
                    self.connection.edge.subscribe(app, (tc.LAST_STEP_VEHICLE_ID_LIST,
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
                state = state.replace("G", "y")
            elif signal.state == "ALL_RED":
                state = "r" * len(state)
            self.connection.trafficlight.setRedYellowGreenState(nid, state)
            actual = self.connection.trafficlight.getRedYellowGreenState(nid)
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
                edge = self.connection.edge.getSubscriptionResults(app)
                active_ids = edge[self.tc.LAST_STEP_VEHICLE_ID_LIST]
                stopped_waits = [self.approach_wait[app].get(vid, 0.) for vid in active_ids
                                 if self.active_speeds.get(vid, 1.) <= .1]
                external_ages = [self.time - row["depart"] for vid, row in self.scheduled_by_route[app]
                                 if row["depart"] < self.time and vid not in self.departed]
                data["approaches"].append({"approach_id": app, "queue_vehicles": edge[self.tc.LAST_STEP_VEHICLE_HALTING_NUMBER],
                                           "occupancy_ratio": occupancy_ratio(edge[self.tc.LAST_STEP_OCCUPANCY]),
                                           "mean_speed_mps": max(0., edge[self.tc.LAST_STEP_MEAN_SPEED]),
                                           "flow_veh_per_s": crossings.get(app, 0), "confidence": 1.0,
                                           "stopped_wait_sum_s": sum(stopped_waits),
                                           "oldest_stopped_wait_s": max(stopped_waits, default=0.),
                                           "external_due_count": len(external_ages),
                                           "external_wait_sum_s": sum(external_ages),
                                           "oldest_external_wait_s": max(external_ages, default=0.)})
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
            if not isinstance(action, (int, np.integer)) or not 0 <= action < 2:
                raise ValueError("Invalid action")
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
        crossing_total = {}
        interval = min(5, self.horizon-self.time)
        for _ in range(interval):
            self.actuator.step(self.time)
            # Max green is enforced on the physical clock as well as at decisions.
            for node in self.topology["nodes"]:
                signal = self.actuator.nodes[node["node_id"]]
                if signal.elapsed_green_time(self.time) >= 60:
                    alternate = next(p["phase_id"] for p in node["phases"] if p["phase_id"] != signal.current_phase_id)
                    self.actuator.process_command({"command_id": f"max-{self.time}", "node_id": node["node_id"],
                                                   "target_phase_id": alternate, "min_green_s": 10.,
                                                   "max_green_s": 60., "controller": "safety_envelope"}, self.time)
            bottleneck = RESEARCH_SCENARIOS.get(self.scenario, {})
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
                raise RuntimeError("Collision or teleport invalidates this run")
            for vid in sim.getDepartedIDList():
                self.departed.add(vid)
                vehicles.subscribe(vid, (self.tc.VAR_SPEED, self.tc.VAR_ROAD_ID))
            self.arrived.update(sim.getArrivedIDList())
            vehicle_data = vehicles.getAllSubscriptionResults()
            active = set(vehicle_data)
            self.active_speeds = {vid: float(data[self.tc.VAR_SPEED]) for vid, data in vehicle_data.items()}
            if self.departed != active | self.arrived or active & self.arrived:
                raise RuntimeError("Unexplained vehicle-accounting loss")
            pending = [vid for vid, row in self.scheduled.items() if row["depart"] < self.time and vid not in self.departed]
            weighted_wait_cost += sum(min(1., self.time-self.scheduled[vid]["depart"])
                                      * (1. + self.wait_penalty_lambda
                                         * max(0., self.time-self.scheduled[vid]["depart"]) / 120.)
                                      for vid in pending)
            for vid in active:
                if vehicle_data[vid][self.tc.VAR_SPEED] <= .1:
                    self.waiting[vid] += 1
                    weighted_wait_cost += 1. + self.wait_penalty_lambda * self.waiting[vid] / 120.
                    road = vehicle_data[vid][self.tc.VAR_ROAD_ID]
                    if road in self.approach_wait:
                        ledger = self.approach_wait[road]
                        ledger[vid] = ledger.get(vid, 0) + 1
            for node in self.topology["nodes"]:
                for app in node["approaches"]:
                    ids = set(self.connection.edge.getSubscriptionResults(app)[self.tc.LAST_STEP_VEHICLE_ID_LIST])
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
        if self.trace:
            self.trace.flush()
        terminated = self.time >= self.demand_s and len(self.arrived) == len(self.scheduled)
        truncated = self.time >= self.horizon and not terminated
        return self.telemetry, -weighted_wait_cost / (20 * 4 * 5), terminated, truncated

    def finish(self):
        self.close()
        # SUMO tripinfo contains final timeLoss even for vehicles arriving in the last tick.
        trips = {t.get("id"): t for t in ET.parse(self.output / "tripinfo.xml").getroot().findall("tripinfo")}
        accrued = []
        wait = []
        for vid, row in self.scheduled.items():
            if vid in self.departed:
                if vid not in trips:
                    raise RuntimeError(f"Missing tripinfo for departed vehicle {vid}")
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
            raise RuntimeError("Vehicle accounting does not balance")
        (self.output / "metrics.json").write_text(json.dumps(result, indent=2))
        return result

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.trace:
            self.trace.close()
            self.trace = None
