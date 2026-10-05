#!/usr/bin/env python3
"""
EdgeFlow AI — Interactive Live Demo Launcher (SUMO-GUI & Docker Microservices)

This master demo runner performs the following automatic steps:
  1. Ensures Docker Microservices (MQTT Broker, FastAPI Backend, React IOC Dashboard, Graph-Control) are running.
  2. Auto-detects `sumo-gui` binary.
  3. Supports both:
     a) Canonical Network Topologies (corridor, junction, grid16, cologne)
     b) Experiments Example Scenario (`experiments/example`) with raster vehicle icons (motorcycle, car, taxi, bus, truck),
        polygon map layer, and CO2/fuel emissions reporting.
  4. Launches `sumo-gui` visual simulation window on screen.
  5. Runs real-time TraCI control loop with EdgeFlow Adaptive Controller & Safe Actuator State Machine.
  6. Displays live traffic metrics, exports `metrics.csv`, and links to the IOC Dashboard (http://localhost:3000).

Usage:
    python run_demo.py [--example] [--controller edgeflow] [--scenario directional_surge] [--duration 300] [--skip-docker]
"""

import os
import sys
import time
import shutil
import subprocess
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import csv
from typing import Dict, Any, Optional

# UTF-8 Encoding Fix for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add repo directories to sys.path
repo_root = Path(__file__).resolve().parent
for p in [
    repo_root / "contracts",
    repo_root / "services" / "experiment-runner",
    repo_root / "services" / "graph-control",
    repo_root / "services" / "actuator",
    repo_root / "services" / "simulator",
]:
    if str(p) not in sys.path and p.exists():
        sys.path.insert(0, str(p))

import contracts_sdk
from sumo_runner import generate_sumo_routes
from controller import (
    FixedTimeController, ActuatedController, MaxQueueController,
    MaxPressureController, EdgeFlowController,
)
from state_machine import ActuatorStateMachine


def print_banner(topology_id: str, scenario_id: str, controller_name: str, duration_s: int):
    print("=" * 75)
    print(" 🚥 EDGEFLOW AI — INTERACTIVE SUMO-GUI DEMO LAUNCHER")
    print("=" * 75)
    print(f" • Topology / Mode    : {topology_id}")
    print(f" • Scenario Demand    : {scenario_id}")
    print(f" • Adaptive Controller: {controller_name.upper()}")
    print(f" • Duration (seconds) : {duration_s}s")
    print(f" • React Dashboard    : http://localhost:3000")
    print(f" • FastAPI Backend    : http://localhost:8000/docs")
    print("=" * 75 + "\n")


def ensure_docker_services(skip_docker: bool = False):
    """Ensure Docker Compose microservices (MQTT, API, Dashboard, Control) are running."""
    if skip_docker:
        print("[ℹ] Skipping Docker services check (--skip-docker specified).")
        return

    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("[!] Warning: Docker CLI not found. Running in standalone local mode.")
        return

    print("[🐳] Checking Docker Microservices status...")
    try:
        r = subprocess.run([docker_bin, "compose", "ps", "--format", "json"], capture_output=True, text=True, cwd=str(repo_root))
        if "edgeflow-mqtt" in r.stdout and "edgeflow-dashboard" in r.stdout:
            print("[✓] Docker Microservices (MQTT, API, Dashboard) are already running.\n")
            return

        print("[🚀] Starting Docker Stack with 'simulation' profile...")
        cmd = [docker_bin, "compose", "--profile", "simulation", "up", "-d"]
        res = subprocess.run(cmd, cwd=str(repo_root))
        if res.returncode == 0:
            print("[✓] Docker Microservices started successfully.\n")
        else:
            print("[!] Warning: Failed to start Docker Compose. Continuing in local mode.\n")
    except Exception as err:
        print(f"[!] Warning: Docker check encountered error: {err}. Continuing locally.\n")


def find_sumo_gui_binary(custom_path: Optional[str] = None) -> str:
    """Locate sumo-gui executable."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    binary_name = "sumo-gui.exe" if sys.platform == "win32" else "sumo-gui"

    # Check PATH
    found = shutil.which("sumo-gui")
    if found:
        return found

    # Fallback paths
    fallbacks = [
        Path(r"D:\sumo\bin") / binary_name,
        Path(r"C:\Program Files (x86)\Eclipse\Sumo\bin") / binary_name,
        Path(r"C:\Program Files\Eclipse\Sumo\bin") / binary_name,
        Path("/usr/bin/sumo-gui"),
        Path("/usr/local/bin/sumo-gui"),
    ]
    for fb in fallbacks:
        if fb.exists():
            return str(fb)

    # Fallback to headless sumo if gui not found
    headless_name = "sumo.exe" if sys.platform == "win32" else "sumo"
    found_headless = shutil.which("sumo") or (Path(r"D:\sumo\bin") / headless_name)
    if found_headless and Path(found_headless).exists():
        print(f"[!] Note: 'sumo-gui' not found. Falling back to headless 'sumo': {found_headless}")
        return str(found_headless)

    raise FileNotFoundError("SUMO binary (sumo-gui / sumo) not found. Please install Eclipse SUMO.")


def setup_example_vehicle_images(exp_dir: Path, seed: int = 42) -> bool:
    """Configure vehicle raster PNG icons in experiments/example/routes.rou.xml."""
    import random

    route_file = exp_dir / "routes.rou.xml"
    if not route_file.exists():
        return False

    try:
        tree = ET.parse(route_file)
        root = tree.getroot()

        ids = {"motorcycle", "car", "taxi", "bus", "truck"}
        for e in list(root):
            if e.tag == "vType":
                root.remove(e)

        random.seed(seed)
        weights = ["motorcycle"] * 65 + ["car"] * 25 + ["taxi"] * 4 + ["bus"] * 3 + ["truck"] * 3

        count = 0
        for tag in ("vehicle", "flow"):
            for v in root.findall(tag):
                v.set("type", random.choice(weights))
                count += 1

        ET.indent(tree, space="    ")
        tree.write(route_file, encoding="UTF-8", xml_declaration=True)
        print(f"[✓] Configured vehicle raster icons (car/motorcycle/bus/taxi/truck) for {count} elements.")
        return True
    except Exception as err:
        print(f"[!] Note on vehicle image setup: {err}")
        return False


def run_example_scenario(controller_name: str, duration_s: int, seed: int, sumo_gui_bin: str):
    """Run the experiments/example scenario directly with SUMO-GUI, emissions, and raster vehicle graphics."""
    import traci

    exp_dir = repo_root / "experiments" / "example"
    sumocfg = exp_dir / "simulation.sumocfg"
    if not sumocfg.exists():
        raise FileNotFoundError(f"Example simulation config '{sumocfg}' not found.")

    # 1. Setup vehicle icons
    setup_example_vehicle_images(exp_dir, seed=seed)

    # Load topology for controller
    topology = contracts_sdk.load_topology("corridor")

    # Outputs
    trip_out = exp_dir / "tripinfo.xml"
    summary_out = exp_dir / "summary.xml"
    emission_out = exp_dir / "emission.xml"
    csv_out = exp_dir / "metrics.csv"

    # Init Controller & Actuator State Machine
    CONTROLLERS = {
        "fixed_time": lambda: FixedTimeController(cycle_time_s=30.0),
        "actuated": lambda: ActuatedController(min_green_s=10.0, max_green_s=45.0),
        "max_queue": lambda: MaxQueueController(),
        "max_pressure": lambda: MaxPressureController(),
        "edgeflow": lambda: EdgeFlowController(),
    }
    ctrl_key = controller_name.lower()
    controller = CONTROLLERS.get(ctrl_key, CONTROLLERS["edgeflow"])()
    actuator = ActuatorStateMachine(yellow_duration_s=3.0, all_red_duration_s=2.0)

    # SUMO GUI Command
    sumo_cmd = [
        sumo_gui_bin,
        "-c", str(sumocfg),
        "--start", "true",
        "--quit-on-end", "true",
        "--tripinfo-output", str(trip_out),
        "--summary-output", str(summary_out),
        "--emission-output", str(emission_out),
        "--waiting-time-memory", "1000",
        "--seed", str(seed),
    ]

    print(f"[🖥️] Launching SUMO-GUI for experiments/example scenario...")
    print(f"    Command: {' '.join(sumo_cmd)}")
    print("[ℹ] Visual SUMO-GUI window is active on screen...\n")

    traci.start(sumo_cmd)
    tl_ids = set(traci.trafficlight.getIDList())
    edge_ids = set(traci.edge.getIDList())

    # Init actuator nodes
    for node in topology.get("nodes", []):
        nid = node["node_id"]
        phases = node.get("phases", [])
        default_phase = phases[0]["phase_id"] if phases else f"{nid}_PHASE_NS"
        ns = actuator.get_or_create_node(nid, default_phase=default_phase)
        ns.phase_start_time = 0.0
        ns.state_start_time = 0.0

    step = 0
    total_queue_sum = 0.0
    samples = 0

    print("Step (s) | Active Phases                       | Mean Queue (veh)")
    print("-" * 65)

    try:
        while step < duration_s:
            traci.simulationStep()
            t = traci.simulation.getTime()
            step = int(t)

            actuator.step(now=t)
            current_phases = []
            node_queues = []

            for node in topology.get("nodes", []):
                nid = node["node_id"]
                node_state = actuator.get_or_create_node(nid)
                active_phase = node_state.current_phase_id

                approaches_data = []
                for app_id in node.get("approaches", []):
                    q = 0.0
                    if app_id in edge_ids:
                        q = float(traci.edge.getLastStepHaltingNumber(app_id))
                    approaches_data.append({"approach_id": app_id, "queue_length_veh": q})
                    node_queues.append(q)

                telemetry = {
                    "node_id": nid,
                    "timestamp": t,
                    "current_phase_id": active_phase,
                    "state": node_state.state,
                    "approaches": approaches_data,
                }

                cmd = controller.compute_command(
                    node_id=nid,
                    telemetry=telemetry,
                    topology=topology,
                    current_time_s=t,
                )
                if cmd:
                    actuator.process_command(cmd, now=t)

                if node_state.state == "GREEN" and nid in tl_ids:
                    phase_list = node.get("phases", [])
                    for pidx, p in enumerate(phase_list):
                        if p.get("phase_id") == node_state.current_phase_id:
                            try:
                                traci.trafficlight.setPhase(nid, pidx * 2)
                            except Exception:
                                pass
                            break

                current_phases.append(f"{nid}:{active_phase.split('_')[-1]}")

            mean_q = sum(node_queues) / len(node_queues) if node_queues else 0.0
            total_queue_sum += mean_q
            samples += 1

            if step % 10 == 0 or step == duration_s - 1:
                phases_str = " ".join(current_phases)
                print(f" t={step:<5} | {phases_str:<35} | {mean_q:.2f} veh")

            time.sleep(0.02)

    except traci.exceptions.FatalTraCIError:
        print("[ℹ] SUMO-GUI window closed by user.")
    except Exception as err:
        print(f"[!] Error during TraCI loop: {err}")
    finally:
        try:
            traci.close()
        except Exception:
            pass

    # Parse and compute metrics
    print("\n[📊] Calculating emission & trip performance metrics...")
    def f_val(x, default=0.0):
        try: return float(x)
        except Exception: return default

    n_trips = arrived = 0
    sum_dur = sum_w = sum_spd = sum_tl = 0.0
    if trip_out.exists():
        for e in ET.parse(trip_out).getroot().iter("tripinfo"):
            n_trips += 1
            arrived += 1
            dur = f_val(e.get("duration"))
            rlen = f_val(e.get("routeLength"))
            sum_dur += dur
            sum_w += f_val(e.get("waitingTime"))
            sum_spd += (rlen / dur) if dur > 0 else 0.0
            sum_tl += f_val(e.get("timeLoss"))

    avg_travel = sum_dur / n_trips if n_trips else 0.0
    avg_wait = sum_w / n_trips if n_trips else 0.0
    avg_spd_kmh = (sum_spd / n_trips) * 3.6 if n_trips else 0.0
    avg_timeloss = sum_tl / n_trips if n_trips else 0.0

    teleports = 0
    if summary_out.exists():
        for s in ET.parse(summary_out).getroot().iter("step"):
            teleports = int(f_val(s.get("teleports")))

    co2 = fuel = 0.0
    if emission_out.exists():
        for e in ET.parse(emission_out).getroot().iter("vehicle"):
            co2 += f_val(e.get("CO2"))
            fuel += f_val(e.get("fuel"))

    fields = [
        "vehicles_arrived", "average_travel_time_s", "average_waiting_time_s",
        "average_speed_kmh", "average_time_loss_s", "throughput_vehicles",
        "teleports", "total_co2_mg", "total_fuel_ml"
    ]
    values = [
        arrived, round(avg_travel, 3), round(avg_wait, 3), round(avg_spd_kmh, 3),
        round(avg_timeloss, 3), arrived, teleports, round(co2, 3), round(fuel, 3)
    ]

    with csv_out.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(fields)
        w.writerow(values)

    print("=" * 65)
    print(" 📊 EXPERIMENTS/EXAMPLE METRICS SUMMARY")
    print("=" * 65)
    for k, v in zip(fields, values):
        print(f" • {k:<25}: {v}")
    print("=" * 65)
    print(f"[✓] Metrics exported to: {csv_out}")
    print(f"[✓] IOC Dashboard: http://localhost:3000\n")


def run_demo_simulation(
    topology_id: str,
    scenario_id: str,
    controller_name: str,
    duration_s: int,
    seed: int,
    sumo_gui_bin: str,
):
    """Execute live TraCI simulation for standard contract topologies."""
    import traci

    topology = contracts_sdk.load_topology(topology_id)
    demo_dir = repo_root / "output" / "demo_run"
    demo_dir.mkdir(parents=True, exist_ok=True)

    route_path = str(demo_dir / "routes.rou.xml")
    generate_sumo_routes(scenario_id, seed, duration_s, route_path, topology_id)

    sumo_configs_dir = repo_root / "services" / "simulator" / "sumo_configs"
    candidates = [
        sumo_configs_dir / topology_id / f"{topology_id}.net.xml",
        sumo_configs_dir / f"{topology_id}.net.xml",
        sumo_configs_dir / "four_intersection_v1" / "four_intersection_v1.net.xml",
        sumo_configs_dir / "four_intersection_v1.net.xml",
    ]
    net_file = None
    for cand in candidates:
        if cand.exists():
            net_file = str(cand)
            break

    if not net_file:
        raise FileNotFoundError(f"SUMO network file (.net.xml) not found for topology '{topology_id}'")

    tripinfo_path = str(demo_dir / "tripinfo.xml")
    sumocfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{net_file}"/>
        <route-files value="{route_path}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{duration_s}"/>
        <step-length value="1.0"/>
    </time>
    <output>
        <tripinfo-output value="{tripinfo_path}"/>
        <tripinfo-output.write-unfinished value="true"/>
    </output>
    <processing>
        <time-to-teleport value="-1"/>
    </processing>
    <random_number>
        <seed value="{seed}"/>
    </random_number>
</configuration>"""

    sumocfg_path = str(demo_dir / "demo.sumocfg")
    with open(sumocfg_path, "w", encoding="utf-8") as f:
        f.write(sumocfg_content)

    CONTROLLERS = {
        "fixed_time": lambda: FixedTimeController(cycle_time_s=30.0),
        "actuated": lambda: ActuatedController(min_green_s=10.0, max_green_s=45.0),
        "max_queue": lambda: MaxQueueController(),
        "max_pressure": lambda: MaxPressureController(),
        "edgeflow": lambda: EdgeFlowController(),
    }
    ctrl_key = controller_name.lower()
    controller = CONTROLLERS.get(ctrl_key, CONTROLLERS["edgeflow"])()
    actuator = ActuatorStateMachine(yellow_duration_s=3.0, all_red_duration_s=2.0)

    sumo_cmd = [
        sumo_gui_bin,
        "-c", sumocfg_path,
        "--start", "true",
        "--quit-on-end", "true",
        "--waiting-time-memory", "1000",
        "--seed", str(seed),
    ]

    print(f"[🖥️] Launching SUMO-GUI Window: {' '.join(sumo_cmd)}")
    print("[ℹ] SUMO-GUI window active on screen...\n")

    traci.start(sumo_cmd)
    tl_ids = set(traci.trafficlight.getIDList())
    edge_ids = set(traci.edge.getIDList())

    for node in topology.get("nodes", []):
        nid = node["node_id"]
        phases = node.get("phases", [])
        default_phase = phases[0]["phase_id"] if phases else f"{nid}_PHASE_NS"
        ns = actuator.get_or_create_node(nid, default_phase=default_phase)
        ns.phase_start_time = 0.0
        ns.state_start_time = 0.0

    step = 0
    total_queue_sum = 0.0
    samples = 0

    print("Step (s) | Active Phases                       | Mean Queue (veh)")
    print("-" * 65)

    try:
        while step < duration_s:
            traci.simulationStep()
            t = traci.simulation.getTime()
            step = int(t)

            actuator.step(now=t)
            current_phases = []
            node_queues = []

            for node in topology.get("nodes", []):
                nid = node["node_id"]
                node_state = actuator.get_or_create_node(nid)
                active_phase = node_state.current_phase_id

                approaches_data = []
                for app_id in node.get("approaches", []):
                    q = 0.0
                    if app_id in edge_ids:
                        q = float(traci.edge.getLastStepHaltingNumber(app_id))
                    approaches_data.append({"approach_id": app_id, "queue_length_veh": q})
                    node_queues.append(q)

                telemetry = {
                    "node_id": nid,
                    "timestamp": t,
                    "current_phase_id": active_phase,
                    "state": node_state.state,
                    "approaches": approaches_data,
                }

                cmd = controller.compute_command(
                    node_id=nid,
                    telemetry=telemetry,
                    topology=topology,
                    current_time_s=t,
                )
                if cmd:
                    actuator.process_command(cmd, now=t)

                if node_state.state == "GREEN" and nid in tl_ids:
                    phase_list = node.get("phases", [])
                    for pidx, p in enumerate(phase_list):
                        if p.get("phase_id") == node_state.current_phase_id:
                            try:
                                traci.trafficlight.setPhase(nid, pidx * 2)
                            except Exception:
                                pass
                            break

                current_phases.append(f"{nid}:{active_phase.split('_')[-1]}")

            mean_q = sum(node_queues) / len(node_queues) if node_queues else 0.0
            total_queue_sum += mean_q
            samples += 1

            if step % 10 == 0 or step == duration_s - 1:
                phases_str = " ".join(current_phases)
                print(f" t={step:<5} | {phases_str:<35} | {mean_q:.2f} veh")

            time.sleep(0.02)

    except traci.exceptions.FatalTraCIError:
        print("[ℹ] SUMO-GUI window closed by user.")
    except Exception as err:
        print(f"[!] Error during TraCI loop: {err}")
    finally:
        try:
            traci.close()
        except Exception:
            pass

    avg_queue = total_queue_sum / samples if samples > 0 else 0.0

    print("\n" + "=" * 65)
    print(" 📊 SCENARIO DEMO COMPLETED SUCCESSFULLY")
    print("=" * 65)
    print(f" • Target Topology  : {topology_id}")
    print(f" • Scenario Profile : {scenario_id}")
    print(f" • Controller       : {controller_name.upper()}")
    print(f" • Mean Queue Length: {avg_queue:.2f} vehicles")
    print(f" • IOC Dashboard    : http://localhost:3000")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="EdgeFlow AI — Master SUMO-GUI Live Demo Launcher")
    parser.add_argument("--topology", type=str, default="corridor", help="Topology ID (corridor, junction, grid16, cologne)")
    parser.add_argument("--scenario", type=str, default="directional_surge", help="Scenario profile (directional_surge, balanced, example)")
    parser.add_argument("--controller", type=str, default="edgeflow", help="Controller type (edgeflow, max_pressure, actuated, fixed_time)")
    parser.add_argument("--duration", type=int, default=300, help="Demo duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--example", action="store_true", help="Run experiments/example scenario with raster vehicle graphics & emissions")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker compose initialization")

    args = parser.parse_args()

    # Determine if running example scenario
    is_example = args.example or args.scenario.lower() == "example"

    topology_id = "experiments/example" if is_example else contracts_sdk.resolve_topology_id(args.topology)
    scenario_id = "example" if is_example else args.scenario
    controller_name = args.controller
    duration_s = args.duration
    seed = args.seed

    print_banner(topology_id, scenario_id, controller_name, duration_s)

    # 1. Ensure Docker Microservices
    ensure_docker_services(skip_docker=args.skip_docker)

    # 2. Find SUMO-GUI executable
    sumo_gui_bin = find_sumo_gui_binary()

    # 3. Launch live TraCI demo with SUMO-GUI
    if is_example:
        run_example_scenario(
            controller_name=controller_name,
            duration_s=duration_s,
            seed=seed,
            sumo_gui_bin=sumo_gui_bin,
        )
    else:
        run_demo_simulation(
            topology_id=topology_id,
            scenario_id=scenario_id,
            controller_name=controller_name,
            duration_s=duration_s,
            seed=seed,
            sumo_gui_bin=sumo_gui_bin,
        )


if __name__ == "__main__":
    main()
