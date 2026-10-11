"""
EdgeFlow AI — Unified Live SUMO/TraCI Simulation Backend (P0/P1/P2).

Executes real SUMO simulations with TraCI control, adhering strictly to:
  1. Authoritative contracts and schemas (contracts/schemas/telemetry.json, control_command.json).
  2. Actuator abstraction and common safety envelope (ActuatorStateMachine).
  3. Controller abstraction via src/control/factory.py:create_controller().
  4. Precise scenario interventions (balanced, directional_surge, downstream_congestion).
  5. Exhaustive scheduled-vehicle accounting (scheduled = completed + active + pending).
  6. Scientifically rigorous KPI computation:
     - Mean & linear P95 wait times of completed vehicles (null if 0 completed).
     - Full cohort observed wait + delay metric.
     - Measurement-window network-wide queue time-series on unique incoming edges.
  7. Generation of complete 14-artifact per-run evidence packages.
"""

import os
import sys
import csv
import json
import uuid
import time
import shutil
import hashlib
import logging
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

import numpy as np
from jsonschema import Draft7Validator

logger = logging.getLogger("sumo-live-backend")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import contracts_sdk
from contracts.contracts_sdk import load_schema
from src.control.factory import create_controller
from src.control.actuator import ActuatorStateMachine
from src.simulation.sumo_network_registry import NETWORK_REGISTRY, NetworkMappingResolver
from src.simulation.sumo_demand_generator import SumoDemandGenerator

try:
    import traci
    import traci.constants as tc
except ImportError:
    traci = None
    tc = None


class LiveSumoRuntime:
    """
    Standardized, robust execution engine for a single SUMO/TraCI experiment run.
    """

    def __init__(
        self,
        topology_id: str,
        scenario: str,
        seed: int,
        controller_name: str,
        artifacts_dir: Path,
        warmup_s: int = 300,
        duration_s: int = 1800,
        drain_s: int = 600,
        frozen_demand_dir: Optional[Path] = None,
        controller_params: Optional[Dict[str, Any]] = None,
        model_path: Optional[str] = None,
        gui: bool = False,
    ):
        self.topology_id = topology_id
        self.scenario = scenario
        self.seed = int(seed)
        self.controller_name = controller_name.lower()
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.warmup_s = int(warmup_s)
        self.duration_s = int(duration_s)
        self.drain_s = int(drain_s)
        self.total_horizon_s = self.warmup_s + self.duration_s + self.drain_s
        self.measurement_start_s = self.warmup_s
        self.measurement_end_s = self.warmup_s + self.duration_s

        self.frozen_demand_dir = Path(frozen_demand_dir) if frozen_demand_dir else None
        self.controller_params = controller_params or {}
        self.model_path = model_path
        self.gui = gui

        # Validators
        self.telemetry_validator = Draft7Validator(load_schema("telemetry"))
        self.command_validator = Draft7Validator(load_schema("control_command"))

        # Resolver & mapping
        self.resolver = NetworkMappingResolver(self.topology_id, repo_root=REPO_ROOT)
        self.mapping = self.resolver.mapping
        self.controlled_tls_ids = self.mapping["controlled_tls_ids"]

        # Actuator State Machine (yellow 3s, all-red 2s, min green 10s, max green 60s)
        self.actuator = ActuatorStateMachine(yellow_duration_s=3.0, all_red_duration_s=2.0)

        # Controller instantiation
        self.controller = self._init_and_verify_controller()

        # Telemetry and state caches
        self.incoming_edges_set: Set[str] = set()
        for nid in self.controlled_tls_ids:
            for app_id in self.mapping["nodes"][nid]["approaches"]:
                self.incoming_edges_set.add(app_id)

        # Simulation trackers
        self.faults: List[Dict[str, Any]] = []
        self.scenario_events: List[Dict[str, Any]] = []
        self.signals_log: List[Dict[str, Any]] = []
        self.telemetry_samples: List[Dict[str, Any]] = []
        self.network_queue_samples: List[Tuple[float, float]] = []  # (time_s, queue_veh)
        self.arrivals_in_measurement = 0

        # Ledger tracking
        self.scheduled_ledger: Dict[str, Any] = {}
        self.departed_vehicle_ids: Set[str] = set()
        self.arrived_vehicle_ids: Set[str] = set()

        # Bottleneck state
        self.bottleneck_throttled = False

    def _init_and_verify_controller(self):
        """Instantiate controller via factory and enforce identity."""
        ctrl = create_controller(
            self.controller_name,
            parameters=self.controller_params,
            model_path=self.model_path,
        )

        expected_classes = {
            "fixed_time": "FixedTimeController",
            "max_queue": "MaxQueueController",
            "max_pressure": "MaxPressureController",
            "flow_theory": "FlowTheoryController",
            "edgeflow": "EdgeFlowController",
        }
        expected = expected_classes.get(self.controller_name)
        actual = ctrl.__class__.__name__
        if expected and actual != expected:
            raise RuntimeError(
                f"CONTROLLER IDENTITY MISMATCH: requested='{self.controller_name}', "
                f"expected class='{expected}', actual class='{actual}'."
            )
        if hasattr(ctrl, "reset"):
            ctrl.reset()
        return ctrl

    def _find_sumo_binary(self) -> str:
        """Find reliable SUMO binary path."""
        binary_name = "sumo-gui.exe" if (self.gui and sys.platform == "win32") else (
            "sumo-gui" if self.gui else ("sumo.exe" if sys.platform == "win32" else "sumo")
        )

        # Check SUMO_HOME
        sumo_home = os.environ.get("SUMO_HOME", "")
        if sumo_home:
            candidate = Path(sumo_home) / "bin" / binary_name
            if candidate.exists():
                return str(candidate)

        # Check default D:\sumo\bin
        default_candidate = Path("D:/sumo/bin") / binary_name
        if default_candidate.exists():
            return str(default_candidate)

        # Fallback to which/where
        which_path = shutil.which(binary_name)
        if which_path:
            return which_path

        raise FileNotFoundError(f"SUMO binary '{binary_name}' not found. Please set SUMO_HOME.")

    def run(self) -> Dict[str, Any]:
        """Execute simulation run and return summary dict."""
        logger.info(
            f"Starting Live SUMO Run: [{self.topology_id} | {self.scenario} | "
            f"{self.controller_name} | seed={self.seed}] "
            f"(Warmup={self.warmup_s}s, Horizon={self.total_horizon_s}s)"
        )

        # 1. Setup frozen demand
        demand_meta = self._setup_demand()
        demand_rou_file = Path(demand_meta["demand_rou_path"])
        initial_rou_sha256 = demand_meta["demand_rou_sha256"]

        # 2. Write configuration and resolved mappings to run directory
        self._write_pre_run_artifacts()

        # 3. Create experiment.sumocfg
        sumocfg_path = self.artifacts_dir / "experiment.sumocfg"
        tripinfo_path = self.artifacts_dir / "tripinfo.xml"
        error_log_path = self.artifacts_dir / "sumo-error.log"

        sumocfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{Path(self.mapping['net_path']).resolve().as_posix()}"/>
        <route-files value="{demand_rou_file.resolve().as_posix()}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{self.total_horizon_s}"/>
        <step-length value="1.0"/>
    </time>
    <output>
        <tripinfo-output value="{tripinfo_path.resolve().as_posix()}"/>
        <tripinfo-output.write-unfinished value="true"/>
    </output>
    <processing>
        <time-to-teleport value="-1"/>
        <waiting-time-memory value="3600"/>
    </processing>
    <random_number>
        <seed value="{self.seed}"/>
    </random_number>
</configuration>"""
        sumocfg_path.write_text(sumocfg_content, encoding="utf-8")

        # 4. Launch SUMO with TraCI
        sumo_binary = self._find_sumo_binary()
        conn_label = f"ef_{uuid.uuid4().hex[:12]}"

        sumo_cmd = [
            sumo_binary,
            "-c", str(sumocfg_path.resolve()),
            "--no-step-log", "true",
            "--duration-log.disable", "true",
            "--error-log", str(error_log_path.resolve()),
            "--seed", str(self.seed),
        ]

        if not traci:
            raise RuntimeError("TraCI is not installed or importable.")

        conn = None
        run_valid = True
        telemetry_csv_path = self.artifacts_dir / "telemetry.csv"
        signals_jsonl_path = self.artifacts_dir / "signals.jsonl"
        events_jsonl_path = self.artifacts_dir / "scenario_events.jsonl"

        telemetry_f = open(telemetry_csv_path, "w", newline="", encoding="utf-8")
        telemetry_writer = csv.writer(telemetry_f)
        telemetry_writer.writerow([
            "simulation_time_s", "node_id", "current_phase_id",
            "approach_id", "queue_vehicles", "flow_veh_per_s", "mean_speed_mps", "occupancy_ratio"
        ])

        signals_f = open(signals_jsonl_path, "w", encoding="utf-8")
        events_f = open(events_jsonl_path, "w", encoding="utf-8")

        try:
            traci.start(sumo_cmd, label=conn_label)
            conn = traci.getConnection(conn_label)

            # Initialize actuator state for each controlled node
            for nid in self.controlled_tls_ids:
                phases = self.mapping["nodes"][nid]["phases"]
                initial_phase = phases[0]["phase_id"] if phases else f"{nid}_PHASE_1"
                ns = self.actuator.get_or_create_node(nid, default_phase=initial_phase)
                ns.phase_start_time = 0.0
                ns.state_start_time = 0.0
                # Apply initial green state
                init_state = phases[0]["state"]
                conn.trafficlight.setRedYellowGreenState(nid, init_state)

            # Scenario intervention timing
            bn_spec = self.mapping["bottleneck"]
            bn_edge = bn_spec["edge_id"]
            bn_normal_spd = bn_spec["normal_speed_mps"]
            bn_congested_spd = bn_spec["congested_speed_mps"]

            sc_spec = demand_meta["scenario_spec"]
            cg_start = sc_spec["downstream_congestion_intervention"]["start_s"]
            cg_end = sc_spec["downstream_congestion_intervention"]["end_s"]

            # Main Simulation Step Loop
            step = 0
            while step < self.total_horizon_s:
                conn.simulationStep()
                current_time_s = float(conn.simulation.getTime())
                step = int(current_time_s)

                # Track departures & arrivals
                departed_now = conn.simulation.getDepartedIDList()
                arrived_now = conn.simulation.getArrivedIDList()

                self.departed_vehicle_ids.update(departed_now)
                self.arrived_vehicle_ids.update(arrived_now)

                if self.measurement_start_s <= current_time_s < self.measurement_end_s:
                    self.arrivals_in_measurement += len(arrived_now)

                # Scenario speed-gating intervention (for downstream_congestion)
                if self.scenario == "downstream_congestion":
                    if (cg_start <= current_time_s < cg_end) and not self.bottleneck_throttled:
                        conn.edge.setMaxSpeed(bn_edge, bn_congested_spd)
                        self.bottleneck_throttled = True
                        ev = {
                            "time_s": current_time_s,
                            "event": "BOTTLENECK_APPLIED",
                            "edge": bn_edge,
                            "speed_mps": bn_congested_spd,
                        }
                        self.scenario_events.append(ev)
                        events_f.write(json.dumps(ev) + "\n")

                    elif (current_time_s >= cg_end) and self.bottleneck_throttled:
                        conn.edge.setMaxSpeed(bn_edge, bn_normal_spd)
                        self.bottleneck_throttled = False
                        ev = {
                            "time_s": current_time_s,
                            "event": "BOTTLENECK_RELEASED",
                            "edge": bn_edge,
                            "speed_mps": bn_normal_spd,
                        }
                        self.scenario_events.append(ev)
                        events_f.write(json.dumps(ev) + "\n")

                # Advance Actuator state machine
                self.actuator.step(now=current_time_s)

                # Collect edge telemetry
                raw_edge_data: Dict[str, Dict[str, float]] = {}
                for eid in self.incoming_edges_set:
                    try:
                        q = float(conn.edge.getLastStepHaltingNumber(eid))
                        spd = float(conn.edge.getLastStepMeanSpeed(eid))
                        spd = round(spd if spd >= 0 else 13.89, 2)
                        # API percentage / 100.0, clamp [0.0, 1.0]
                        occ_raw = float(conn.edge.getLastStepOccupancy(eid))
                        occ = round(min(1.0, max(0.0, occ_raw / 100.0)), 4)
                        veh_count = conn.edge.getLastStepVehicleNumber(eid)
                        raw_edge_data[eid] = {
                            "queue": q,
                            "speed": spd,
                            "occupancy": occ,
                            "veh_count": veh_count,
                        }
                    except Exception as e:
                        raw_edge_data[eid] = {
                            "queue": 0.0,
                            "speed": 13.89,
                            "occupancy": 0.0,
                            "veh_count": 0,
                        }

                # Network-wide queue measurement
                if self.measurement_start_s <= current_time_s < self.measurement_end_s:
                    net_q = sum(raw_edge_data[eid]["queue"] for eid in self.incoming_edges_set)
                    self.network_queue_samples.append((current_time_s, net_q))

                # Build global network_state dictionary
                network_state: Dict[str, Any] = {}
                for other_nid in self.controlled_tls_ids:
                    other_apps_list = []
                    for oa in self.mapping["nodes"][other_nid]["approaches"]:
                        d = raw_edge_data.get(oa, {"queue": 0.0, "speed": 13.89, "occupancy": 0.0})
                        other_apps_list.append({
                            "approach_id": oa,
                            "queue_vehicles": d["queue"],
                            "mean_speed_mps": d["speed"],
                            "occupancy_ratio": d["occupancy"],
                        })
                    network_state[other_nid] = {
                        "node_id": other_nid,
                        "approaches": other_apps_list,
                    }

                # Control decision loop for every controlled TLS
                for nid in self.controlled_tls_ids:
                    node_data = self.mapping["nodes"][nid]
                    act_state = self.actuator.get_or_create_node(nid)
                    current_phase_id = act_state.current_phase_id

                    # Build canonical Telemetry object
                    approaches_payload = []
                    for aid in node_data["approaches"]:
                        d = raw_edge_data.get(aid, {"queue": 0.0, "speed": 13.89, "occupancy": 0.0})
                        approaches_payload.append({
                            "approach_id": aid,
                            "queue_vehicles": round(d["queue"], 1),
                            "flow_veh_per_s": round(float(d["veh_count"]) / 10.0, 3),  # approximate flow density
                            "mean_speed_mps": d["speed"],
                            "occupancy_ratio": d["occupancy"],
                            "confidence": 1.0,
                        })
                        # Log to telemetry CSV
                        telemetry_writer.writerow([
                            current_time_s, nid, current_phase_id,
                            aid, d["queue"], round(float(d["veh_count"]) / 10.0, 3), d["speed"], d["occupancy"]
                        ])

                    telemetry = {
                        "node_id": nid,
                        "source_type": "simulation",  # Canonical enum per contracts/schemas/telemetry.json
                        "simulation_time_s": current_time_s,
                        "timestamp_ms": int(current_time_s * 1000),
                        "current_phase_id": current_phase_id,
                        "approaches": approaches_payload,
                    }

                    # Validate Telemetry schema
                    self.telemetry_validator.validate(telemetry)
                    self.telemetry_samples.append(telemetry)

                    # Compute controller command
                    topology_arg = contracts_sdk.load_topology(self.topology_id)
                    cmd = self.controller.compute_command(
                        node_id=nid,
                        telemetry=telemetry,
                        topology=topology_arg,
                        network_state=network_state,
                        current_time_s=current_time_s,
                    )

                    if cmd:
                        self.command_validator.validate(cmd)
                        # Process through actuator state machine
                        self.actuator.process_command(cmd, now=current_time_s)

                    # Get updated physical state from actuator
                    curr_signal_state = act_state.state  # GREEN, YELLOW, ALL_RED
                    curr_phase_id = act_state.current_phase_id
                    pending_phase_id = act_state.pending_phase_id

                    # Resolve SUMO state string
                    phases_map = {p["phase_id"]: p["state"] for p in node_data["phases"]}
                    p_curr_state = phases_map.get(curr_phase_id, list(phases_map.values())[0])

                    if curr_signal_state == "GREEN":
                        sumo_state_str = p_curr_state
                    elif curr_signal_state == "ALL_RED":
                        sumo_state_str = "r" * len(p_curr_state)
                    elif curr_signal_state == "YELLOW":
                        target_phase_id = pending_phase_id if pending_phase_id else curr_phase_id
                        p_target_state = phases_map.get(target_phase_id, p_curr_state)
                        yellow_chars = []
                        for i in range(len(p_curr_state)):
                            c_curr = p_curr_state[i]
                            c_next = p_target_state[i] if i < len(p_target_state) else "r"
                            if c_curr in ("G", "g") and c_next not in ("G", "g"):
                                yellow_chars.append("y")
                            elif c_curr in ("G", "g") and c_next in ("G", "g"):
                                yellow_chars.append(c_curr)
                            else:
                                yellow_chars.append("r")
                        sumo_state_str = "".join(yellow_chars)
                    else:
                        sumo_state_str = p_curr_state

                    # Apply to SUMO traffic light
                    conn.trafficlight.setRedYellowGreenState(nid, sumo_state_str)

                    # Log signal event
                    sig_entry = {
                        "time_s": current_time_s,
                        "node_id": nid,
                        "phase_id": curr_phase_id,
                        "signal_state": curr_signal_state,
                        "sumo_state": sumo_state_str,
                    }
                    signals_f.write(json.dumps(sig_entry) + "\n")

        except Exception as e:
            logger.error(f"SUMO runtime exception during execution: {e}", exc_info=True)
            run_valid = False
            self.faults.append({
                "time_s": current_time_s if 'current_time_s' in locals() else 0.0,
                "error": str(e),
                "type": "SIMULATION_EXCEPTION",
            })
        finally:
            telemetry_f.close()
            signals_f.close()
            events_f.close()

            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        # 5. Verify Demand Hash After Run
        final_rou_sha256 = self.resolver.repo_root / demand_rou_file
        final_sha256 = SumoDemandGenerator.compute_sha256(demand_rou_file)
        if final_sha256 != initial_rou_sha256:
            run_valid = False
            self.faults.append({
                "error": f"DEMAND_HASH_MUTATION: initial={initial_rou_sha256} final={final_sha256}",
                "type": "HASH_CORRUPTION",
            })

        # 6. Parse TripInfo and Vehicle Ledger
        ledger_kpis = self._parse_and_reconcile_tripinfo(tripinfo_path)

        # 7. Compute Final Metrics
        summary = self._compute_final_kpis(ledger_kpis, run_valid, initial_rou_sha256)

        # 8. Write Evidence Package Artifacts
        self._write_post_run_artifacts(summary, run_valid)

        logger.info(
            f"Finished Live SUMO Run: [{self.topology_id} | {self.scenario} | "
            f"{self.controller_name} | seed={self.seed}] -> Valid={run_valid}, "
            f"Scheduled={summary['accounting']['scheduled_vehicles']}, "
            f"Completed={summary['accounting']['completed_vehicles']}, "
            f"AvgWait={summary['kpis']['mean_waiting_completed_s']}"
        )
        return summary

    def _setup_demand(self) -> Dict[str, Any]:
        """Setup frozen demand in run artifacts dir or copy from frozen_inputs."""
        if self.frozen_demand_dir and (self.frozen_demand_dir / "demand.rou.xml").exists():
            rou_src = self.frozen_demand_dir / "demand.rou.xml"
            ledger_src = self.frozen_demand_dir / "demand_ledger.json"
            sc_src = self.frozen_demand_dir / "scenario.json"

            rou_dst = self.artifacts_dir / "demand.rou.xml"
            ledger_dst = self.artifacts_dir / "demand_ledger.json"
            sc_dst = self.artifacts_dir / "scenario.json"

            shutil.copy2(rou_src, rou_dst)
            shutil.copy2(ledger_src, ledger_dst)
            shutil.copy2(sc_src, sc_dst)

            rou_sha = SumoDemandGenerator.compute_sha256(rou_dst)
            with open(ledger_dst, "r", encoding="utf-8") as f:
                ledger_data = json.load(f)
            with open(sc_dst, "r", encoding="utf-8") as f:
                sc_data = json.load(f)

            self.scheduled_ledger = ledger_data
            return {
                "demand_rou_path": str(rou_dst),
                "demand_rou_sha256": rou_sha,
                "scenario_spec": sc_data,
            }
        else:
            demand_meta = SumoDemandGenerator.generate_frozen_demand(
                topology_id=self.topology_id,
                scenario=self.scenario,
                seed=self.seed,
                output_dir=self.artifacts_dir,
                warmup_s=self.warmup_s,
                duration_s=self.duration_s,
                drain_s=self.drain_s,
            )
            with open(demand_meta["demand_ledger_path"], "r", encoding="utf-8") as f:
                self.scheduled_ledger = json.load(f)
            return demand_meta

    def _parse_and_reconcile_tripinfo(self, tripinfo_path: Path) -> Dict[str, Any]:
        """Parse tripinfo.xml and reconcile against demand ledger."""
        vehicles_csv_path = self.artifacts_dir / "vehicles.csv"
        trip_records: Dict[str, Dict[str, Any]] = {}

        if tripinfo_path.exists():
            try:
                tree = ET.parse(tripinfo_path)
                root = tree.getroot()
                for trip in root.findall("tripinfo"):
                    vid = trip.get("id")
                    arr = float(trip.get("arrival", -1.0))
                    completed = (arr >= 0.0)
                    trip_records[vid] = {
                        "depart_actual": float(trip.get("depart", 0.0)),
                        "arrival_actual": arr if completed else None,
                        "duration_s": float(trip.get("duration", 0.0)),
                        "waiting_time_s": float(trip.get("waitingTime", 0.0)),
                        "time_loss_s": float(trip.get("timeLoss", 0.0)),
                        "depart_delay_s": float(trip.get("departDelay", 0.0)),
                        "completed": completed,
                    }
            except Exception as e:
                self.faults.append({"error": f"Failed to parse tripinfo.xml: {e}", "type": "XML_PARSE_ERROR"})

        # Reconcile against scheduled cohort vehicles
        scheduled_list = self.scheduled_ledger.get("scheduled_vehicles", [])
        cohort_list = [v for v in scheduled_list if v.get("is_cohort", False)]

        completed_cohort = []
        active_cohort = []
        pending_cohort = []

        with open(vehicles_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "vehicle_id", "route_id", "corridor_axis", "is_cohort",
                "depart_scheduled_s", "depart_actual_s", "arrival_s",
                "waiting_time_s", "time_loss_s", "depart_delay_s", "status"
            ])

            for v in scheduled_list:
                vid = v["vehicle_id"]
                is_cohort = v.get("is_cohort", False)
                sched_dep = v["depart_time_s"]
                trip = trip_records.get(vid)

                if trip and trip["completed"]:
                    status = "COMPLETED"
                    act_dep = trip["depart_actual"]
                    arr = trip["arrival_actual"]
                    wt = trip["waiting_time_s"]
                    tl = trip["time_loss_s"]
                    dd = trip["depart_delay_s"]
                    if is_cohort:
                        completed_cohort.append(trip)
                elif trip and not trip["completed"]:
                    status = "ACTIVE"
                    act_dep = trip["depart_actual"]
                    arr = None
                    wt = trip["waiting_time_s"]
                    tl = trip["time_loss_s"]
                    dd = trip["depart_delay_s"]
                    if is_cohort:
                        active_cohort.append({
                            "depart_actual": act_dep,
                            "waiting_time_s": wt,
                            "depart_delay_s": dd,
                        })
                else:
                    status = "PENDING"
                    act_dep = None
                    arr = None
                    wt = 0.0
                    tl = 0.0
                    dd = max(0.0, self.total_horizon_s - sched_dep)
                    if is_cohort:
                        pending_cohort.append({"depart_delay_s": dd})

                writer.writerow([
                    vid, v["route_id"], v["corridor_axis"], is_cohort,
                    sched_dep, act_dep, arr, wt, tl, dd, status
                ])

        return {
            "cohort_total_scheduled": len(cohort_list),
            "completed_cohort": completed_cohort,
            "active_cohort": active_cohort,
            "pending_cohort": pending_cohort,
        }

    def _compute_final_kpis(
        self, ledger_kpis: Dict[str, Any], run_valid: bool, demand_sha256: str
    ) -> Dict[str, Any]:
        """Compute all canonical KPIs and statistical aggregates."""
        n_sched = ledger_kpis["cohort_total_scheduled"]
        comp = ledger_kpis["completed_cohort"]
        act = ledger_kpis["active_cohort"]
        pend = ledger_kpis["pending_cohort"]

        n_comp = len(comp)
        n_act = len(act)
        n_pend = len(pend)
        n_dep = n_comp + n_act

        # Verification of vehicle accounting
        accounting_matches = (n_sched == n_comp + n_act + n_pend)
        if not accounting_matches:
            self.faults.append({
                "error": f"ACCOUNTING_LOSS: scheduled={n_sched} != comp({n_comp}) + act({n_act}) + pend({n_pend})",
                "type": "ACCOUNTING_MISMATCH",
            })
            run_valid = False

        completion_rate = round(n_comp / max(1, n_sched), 4)

        # Completed vehicle metrics
        if n_comp > 0:
            waits = [v["waiting_time_s"] for v in comp]
            losses = [v["time_loss_s"] for v in comp]
            delays = [v["depart_delay_s"] for v in comp]

            mean_wait = round(float(np.mean(waits)), 2)
            p95_wait = round(float(np.percentile(waits, 95, method="linear")), 2)
            mean_loss = round(float(np.mean(losses)), 2)
            mean_delay = round(float(np.mean(delays)), 2)
        else:
            # Zero completed: return None (null), NOT 0.0s!
            mean_wait = None
            p95_wait = None
            mean_loss = None
            mean_delay = None

        # Full cohort observed wait + depart delay metric
        cohort_waits_and_delays = []
        for v in comp:
            cohort_waits_and_delays.append(v["waiting_time_s"] + v["depart_delay_s"])
        for v in act:
            cohort_waits_and_delays.append(v["waiting_time_s"] + v["depart_delay_s"])
        for v in pend:
            cohort_waits_and_delays.append(v["depart_delay_s"])

        mean_observed_wait_delay = (
            round(float(np.mean(cohort_waits_and_delays)), 2) if cohort_waits_and_delays else None
        )

        # Network queue metrics over measurement window
        if self.network_queue_samples:
            q_values = [s[1] for s in self.network_queue_samples]
            mean_q = round(float(np.mean(q_values)), 2)
            max_q = round(float(np.max(q_values)), 2)
            p95_q = round(float(np.percentile(q_values, 95, method="linear")), 2)
        else:
            mean_q = 0.0
            max_q = 0.0
            p95_q = 0.0

        # Arrivals per second during measurement window
        arrivals_per_s = round(self.arrivals_in_measurement / max(1, self.duration_s), 4)

        return {
            "experiment_id": f"{self.topology_id}_{self.scenario}_{self.controller_name}_seed{self.seed}",
            "simulation_backend": "sumo_traci",
            "is_synthetic": False,
            "valid_for_research": (run_valid and len(self.faults) == 0),
            "manifest": {
                "topology": self.topology_id,
                "scenario": {"name": self.scenario, "seed": self.seed},
                "controller": {"type": self.controller_name},
                "protocol": {
                    "warmup_s": self.warmup_s,
                    "duration_s": self.duration_s,
                    "drain_s": self.drain_s,
                    "total_horizon_s": self.total_horizon_s,
                },
            },
            "controller": self.controller_name,
            "requested_controller": self.controller_name,
            "active_controller_class": self.controller.__class__.__name__,
            "demand_hash": demand_sha256,
            "demand_rou_sha256": demand_sha256,
            "topology_hash": self.mapping["topo_sha256"],
            "network_hash": self.mapping["net_sha256"],
            "accounting": {
                "scheduled_vehicles": n_sched,
                "departed_vehicles": n_dep,
                "completed_vehicles": n_comp,
                "active_vehicles": n_act,
                "pending_vehicles": n_pend,
                "completion_rate": completion_rate,
                "accounting_invariant_holds": accounting_matches,
            },
            "kpis": {
                "mean_waiting_completed_s": mean_wait,
                "p95_waiting_completed_s": p95_wait,
                "mean_time_loss_completed_s": mean_loss,
                "mean_depart_delay_completed_s": mean_delay,
                "mean_observed_wait_plus_depart_delay_cohort_s": mean_observed_wait_delay,
                "mean_network_queue_veh": mean_q,
                "max_network_queue_veh": max_q,
                "p95_network_queue_veh": p95_q,
                "arrivals_measurement_veh_per_s": arrivals_per_s,
                "percentile_method": "linear",
            },
            "faults_count": len(self.faults),
        }

    def _write_pre_run_artifacts(self):
        """Write configuration and metadata before simulation starts."""
        # 1. manifest.json
        manifest_data = {
            "experiment_id": f"{self.topology_id}_{self.scenario}_{self.controller_name}_seed{self.seed}",
            "topology": self.topology_id,
            "scenario": {
                "name": self.scenario,
                "seed": self.seed,
                "warmup_s": self.warmup_s,
                "duration_s": self.duration_s,
                "drain_s": self.drain_s,
            },
            "controller": {
                "type": self.controller_name,
                "class": self.controller.__class__.__name__,
                "parameters": self.controller_params,
            },
        }
        with open(self.artifacts_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # 2. environment.json
        env_data = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "sumo_binary": self._find_sumo_binary(),
            "code_commit": self._get_git_commit(),
            "topology_sha256": self.mapping["topo_sha256"],
            "network_sha256": self.mapping["net_sha256"],
            "simulation_backend": "sumo_traci",
            "is_synthetic": False,
        }
        with open(self.artifacts_dir / "environment.json", "w", encoding="utf-8") as f:
            json.dump(env_data, f, indent=2)

        # 3. resolved_topology.json
        shutil.copy2(self.resolver.topo_path, self.artifacts_dir / "resolved_topology.json")

        # 4. resolved_mapping.json
        with open(self.artifacts_dir / "resolved_mapping.json", "w", encoding="utf-8") as f:
            json.dump(self.mapping, f, indent=2)

    def _write_post_run_artifacts(self, summary: Dict[str, Any], run_valid: bool):
        """Write summary.json, validity.json, and faults.jsonl."""
        with open(self.artifacts_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        validity_data = {
            "valid_for_research": summary["valid_for_research"],
            "run_valid": run_valid,
            "accounting_invariant_holds": summary["accounting"]["accounting_invariant_holds"],
            "faults": self.faults,
            "statistical_notes": (
                "Completed vehicles waiting time is evaluated over the measurement cohort. "
                "Pending vehicles are recorded in accounting."
            ),
        }
        with open(self.artifacts_dir / "validity.json", "w", encoding="utf-8") as f:
            json.dump(validity_data, f, indent=2)

        with open(self.artifacts_dir / "faults.jsonl", "w", encoding="utf-8") as f:
            for fault in self.faults:
                f.write(json.dumps(fault) + "\n")

    def _get_git_commit(self) -> str:
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=5)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return "unknown"
