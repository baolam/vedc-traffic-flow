#!/usr/bin/env python3
"""
EdgeFlow AI — Canonical Live Demo Launcher (SUMO-GUI & Docker Microservices)

This master demo runner performs the following automatic steps:
  1. Ensures Docker Microservices (MQTT Broker, FastAPI Backend, React IOC Dashboard, Graph-Control) are running.
  2. Auto-detects `sumo-gui` binary executable.
  3. Executes canonical project topologies & scenarios:
     • realworld_demo (Canonical 29-junction urban city graph with raster vehicle icons, polygon map, and emissions)
     • corridor (4-intersection linear corridor)
     • grid16 (4x4 16-intersection grid network)
     • cologne (TAPAS Cologne city graph)
     • junction (3-way / single intersection)
  4. Launches visual `sumo-gui` window on screen.
  5. Runs real-time TraCI control loop with EdgeFlow Adaptive Controller & Safe Actuator State Machine.
  6. Displays live traffic metrics, exports `metrics.csv`, and links to the React IOC Dashboard (http://localhost:3000).

Usage:
    python run_demo.py [--topology realworld_demo] [--scenario realworld_demo] [--controller edgeflow] [--duration 300] [--skip-docker]
"""

import os
import sys
import time
import json
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
import topics
from sumo_runner import generate_sumo_routes
from controller import (
    FixedTimeController, ActuatedController, MaxQueueController,
    MaxPressureController, EdgeFlowController, PressLightRLController, FlowTheoryController,
)
from state_machine import ActuatorStateMachine
from runtime_guards import ManualOverrideHold

import struct


def _png_dimensions(path: Path) -> Optional[tuple]:
    """Reads (width, height) straight out of a PNG's IHDR chunk -- no Pillow dependency."""
    try:
        with open(path, "rb") as f:
            head = f.read(26)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        width, height = struct.unpack(">II", head[16:24])
        return width, height
    except Exception:
        return None


def print_banner(topology_id: str, scenario_id: str, controller_name: str, duration_s: int,
                  hardware: bool = False, mqtt_host: str = "", mqtt_port: int = 1883):
    print("=" * 75)
    print(" 🚥 EDGEFLOW AI — CANONICAL SUMO-GUI LIVE DEMO")
    print("=" * 75)
    print(f" • Topology Contract  : {topology_id}")
    print(f" • Scenario Profile   : {scenario_id}")
    print(f" • Adaptive Controller: {controller_name.upper()}")
    print(f" • Duration (seconds) : {duration_s}s")
    print(f" • React Dashboard    : http://localhost:3000")
    print(f" • FastAPI Backend    : http://localhost:8000/docs")
    if hardware:
        print(f" • Hardware Mirror    : ENABLED — ControlCommand mirrored to real ESP32 via MQTT {mqtt_host}:{mqtt_port}")
        print(f"                        (ESP32 is actuator-only: it executes the command and ACKs/health back;")
        print(f"                        the decision stays local to this controller, same as SimulationActuator)")
        print(f"                        (Docker Compose uses the 'hardware' profile and the virtual 'actuator'")
        print(f"                        container is stopped automatically -- it would otherwise double-ACK the ESP32.")
        print(f"                        With --skip-docker, stop it yourself first: `docker compose stop actuator`.)")
    else:
        print(f" • Hardware Mirror    : disabled (pass --hardware to mirror commands to real ESP32 boards)")
    print("=" * 75 + "\n")


def ensure_docker_services(skip_docker: bool = False, hardware: bool = False):
    """Ensure Docker Compose microservices (MQTT, API, Dashboard, Control) are running."""
    if skip_docker:
        print("[ℹ] Skipping Docker services check (--skip-docker specified).")
        return

    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("[!] Warning: Docker CLI not found. Running in standalone local mode.")
        return

    # --hardware uses the 'hardware' compose profile (mqtt, api, graph-control, dashboard) instead of
    # 'simulation': the latter also brings up the virtual 'actuator' container, which would answer
    # the very same mirrored ControlCommand as the real ESP32 -- two ACKs (one fabricated, one real)
    # for one command_id, which is exactly the confusing duplicate-ACK log this was built to prevent.
    profile = "hardware" if hardware else "simulation"
    print(f"[🐳] Checking Docker Microservices status (profile: {profile})...")
    try:
        r = subprocess.run([docker_bin, "compose", "ps", "--format", "json"], capture_output=True, text=True, cwd=str(repo_root))
        already_up = "edgeflow-mqtt" in r.stdout and "edgeflow-dashboard" in r.stdout
        if already_up:
            print("[✓] Docker Microservices (MQTT, API, Dashboard) are already running.\n")
        else:
            print(f"[🚀] Starting Docker Stack with '{profile}' profile...")
            cmd = [docker_bin, "compose", "--profile", profile, "up", "-d"]
            res = subprocess.run(cmd, cwd=str(repo_root))
            if res.returncode == 0:
                print("[✓] Docker Microservices started successfully.\n")
            else:
                print("[!] Warning: Failed to start Docker Compose. Continuing in local mode.\n")

        if hardware:
            # The api container's background MQTT listener can be left in a broken/stale state by a
            # prior run (see the NOTE above `if __name__ == "__main__"` in services/api/main.py) --
            # when that happens it silently stops ingesting ESP32 health/heartbeat/LWT messages, so
            # unplugging the board never flips the dashboard to Offline/HEARTBEAT_LOST. Recreating the
            # container here guarantees a clean listener for every hardware run, at the cost of a few
            # seconds; the file is bind-mounted so this never requires an image rebuild.
            print("[🔁] Hardware mode: recreating 'api' container for a clean MQTT listener "
                  "(prevents a stale listener from silently dropping ESP32 Offline/heartbeat updates)...")
            subprocess.run([docker_bin, "compose", "--profile", profile, "up", "-d", "--force-recreate", "api"], cwd=str(repo_root))

        if hardware and "edgeflow-actuator" in r.stdout:
            print("[⚡] Hardware mode: stopping the virtual 'actuator' container (it was running from a "
                  "previous 'simulation'/'vision' run and would double-ACK the real ESP32)...")
            subprocess.run([docker_bin, "compose", "stop", "actuator"], cwd=str(repo_root))
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


def run_demo_simulation(
    topology_id: str,
    scenario_id: str,
    controller_name: str,
    duration_s: int,
    seed: int,
    sumo_gui_bin: str,
    delay_ms: int = 0,
    hardware: bool = False,
    mqtt_host: str = "localhost",
    mqtt_port: int = 1883,
):
    """Execute live TraCI simulation for canonical topologies."""
    import traci

    resolved_topo = contracts_sdk.resolve_topology_id(topology_id)
    topology = contracts_sdk.load_topology(resolved_topo)

    output_dir = repo_root / "output" / "demo_run"
    output_dir.mkdir(parents=True, exist_ok=True)

    sumo_configs_dir = repo_root / "services" / "simulator" / "sumo_configs"
    topo_config_dir = sumo_configs_dir / resolved_topo

    # Output files
    trip_out = output_dir / "tripinfo.xml"
    summary_out = output_dir / "summary.xml"
    emission_out = output_dir / "emission.xml"
    csv_out = output_dir / "metrics.csv"

    # Ensure gui-settings.xml is copied/present in output_dir
    src_gui_settings = topo_config_dir / "gui-settings.xml" if topo_config_dir.exists() else (sumo_configs_dir / "gui-settings.xml")
    gui_settings_path = output_dir / "gui-settings.xml"
    if src_gui_settings.exists():
        shutil.copy(src_gui_settings, gui_settings_path)
        # Copy any decal/background images referenced by gui-settings.xml (relative paths
        # resolve against the copy's own directory, not the original scenario folder).
        for img in src_gui_settings.parent.glob("*.jpg"):
            shutil.copy(img, output_dir / img.name)
        for img in src_gui_settings.parent.glob("*.png"):
            shutil.copy(img, output_dir / img.name)
    else:
        gui_settings_path = sumo_configs_dir / "gui-settings.xml"

    # Handle hcm_corridor real-world topology natively
    if resolved_topo == "hcm_corridor" and topo_config_dir.exists():
        sumocfg_path = topo_config_dir / "hcm_corridor.sumocfg"
    else:
        # Standard route generation for synthetic corridors/grids
        route_path = str(output_dir / "routes.rou.xml")
        generate_sumo_routes(scenario_id, seed, duration_s, route_path, resolved_topo)

        candidates = [
            topo_config_dir / f"{resolved_topo}.net.xml",
            sumo_configs_dir / f"{resolved_topo}.net.xml",
            sumo_configs_dir / "four_intersection_v1" / "four_intersection_v1.net.xml",
            sumo_configs_dir / "four_intersection_v1.net.xml",
        ]
        net_file = None
        for cand in candidates:
            if cand.exists():
                net_file = str(cand)
                break

        if not net_file:
            raise FileNotFoundError(f"SUMO network file (.net.xml) not found for topology '{resolved_topo}'")

        sumocfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{net_file}"/>
        <route-files value="{route_path}"/>
    </input>
    <gui_only>
        <gui-settings-file value="{gui_settings_path}"/>
    </gui_only>
    <time>
        <begin value="0"/>
        <end value="{duration_s}"/>
        <step-length value="1.0"/>
    </time>
    <output>
        <tripinfo-output value="{trip_out}"/>
        <tripinfo-output.write-unfinished value="true"/>
    </output>
    <processing>
        <time-to-teleport value="-1"/>
    </processing>
    <random_number>
        <seed value="{seed}"/>
    </random_number>
</configuration>"""

        sumocfg_path = output_dir / "demo.sumocfg"
        with open(sumocfg_path, "w", encoding="utf-8") as f:
            f.write(sumocfg_content)

    # Init Controller & Actuator State Machine
    CONTROLLERS = {
        "fixed_time": lambda: FixedTimeController(cycle_time_s=30.0),
        "actuated": lambda: ActuatedController(min_green_s=10.0, max_green_s=45.0),
        "max_queue": lambda: MaxQueueController(),
        "max_pressure": lambda: MaxPressureController(),
        "edgeflow": lambda: EdgeFlowController(),
        "presslight_rl": lambda: PressLightRLController(),
        "rl": lambda: PressLightRLController(),
        "flow_theory": lambda: FlowTheoryController(),
        "ctm": lambda: FlowTheoryController(),
    }
    ctrl_key = controller_name.lower()
    controller = CONTROLLERS.get(ctrl_key, CONTROLLERS.get("max_pressure", CONTROLLERS["edgeflow"]))()
    actuator = ActuatorStateMachine(yellow_duration_s=3.0, all_red_duration_s=2.0)

    # Dashboard "Force Priority" phase override (POST /api/v1/control/override) is published straight
    # to MQTT by the API, same shared OVERRIDE_ID_PREFIX/hold logic as services/graph-control uses for
    # the real deployment. Reused here so a click on the dashboard shows up on the SUMO-GUI light too,
    # not only on the real ESP32 -- without this, run_demo.py's own controller would just overwrite the
    # override on the very next tick and the simulated light would never match what was requested.
    override_hold_s = float(os.environ.get("MANUAL_OVERRIDE_HOLD_S", "15"))
    override_hold = ManualOverrideHold(hold_s=override_hold_s)

    # Hardware mirror: ESP32 boards are actuator-only (no sensors, no decisions). The SAME
    # ControlCommand already applied above to the local ActuatorStateMachine (which drives the
    # SUMO-GUI light) is also published to the real board over MQTT; it runs its own safety
    # clearance (yellow/all-red/min/max-green) and reports ControlACK/health back on its own.
    # This loop never reads that ACK/health back to decide anything -- it is status-only, consumed
    # by services/api's existing MQTT listener for the dashboard.
    hw_mqtt_client = None
    hw_connected = {"value": False}
    # Per-node real Safe-Stop state, read from the ESP32's OWN health/{node} message (never from
    # telemetry or any decision logic). This is a pure backoff signal -- "is it worth sending a
    # command at all" -- not a control input: it never touches `controller`/`actuator`/the SUMO
    # phase. Without it, every keepalive resend while the button is held gets REJECTED "Safe-stop is
    # engaged", flooding the ACK log for no reason (the board already told us not to bother).
    hw_safe_stop: Dict[str, bool] = {}
    if hardware:
        try:
            import paho.mqtt.client as mqtt
            try:
                hw_mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"run_demo-hw-mirror-{os.getpid()}")
            except AttributeError:
                hw_mqtt_client = mqtt.Client(client_id=f"run_demo-hw-mirror-{os.getpid()}")

            def _on_hw_connect(client, userdata, flags, rc):
                hw_connected["value"] = (rc == 0)
                if rc == 0:
                    print(f"[⚡] Hardware mirror: connected to MQTT broker {mqtt_host}:{mqtt_port}")
                    client.subscribe(topics.HEALTH_SUB_PATTERN)
                    # Dashboard "Force Priority" override publishes straight to this same command
                    # topic; seeing it here is how run_demo.py's own SUMO-GUI light learns about it.
                    client.subscribe(topics.COMMAND_SUB_PATTERN)
                else:
                    print(f"[!] Hardware mirror: MQTT connect failed (rc={rc})")

            def _on_hw_disconnect(client, userdata, rc):
                hw_connected["value"] = False
                print("[!] Hardware mirror: MQTT connection lost, retrying...")

            def _on_hw_message(client, userdata, msg):
                try:
                    payload = json.loads(msg.payload.decode("utf-8"))
                except Exception:
                    return
                nid = payload.get("node_id")
                if not nid:
                    return

                if msg.topic.endswith("/command"):
                    # Our own mirrored commands (fresh uuid4) and hold re-sends (HOLD_ID_PREFIX) come
                    # back through this same subscription too; observe_command() ignores anything
                    # whose command_id isn't a dashboard override (OVERRIDE_ID_PREFIX), so only a real
                    # "Force Priority" click starts a hold here.
                    if override_hold.observe_command(payload):
                        print(f"[🎛️] Hardware mirror: dashboard override for {nid} -> "
                              f"{payload.get('target_phase_id')} -- holding the SUMO-GUI light in sync "
                              f"with it for up to {override_hold_s:.0f}s.")
                    return

                is_stopped = bool(payload.get("safe_stop")) or payload.get("status") == "SAFE_STOP"
                was_stopped = hw_safe_stop.get(nid, False)
                hw_safe_stop[nid] = is_stopped
                if is_stopped and not was_stopped:
                    print(f"[🛑] Hardware mirror: {nid} reports SAFE_STOP -- pausing ControlCommand to this node until released.")
                elif was_stopped and not is_stopped:
                    print(f"[⚡] Hardware mirror: {nid} SAFE_STOP released -- resuming ControlCommand mirror.")

            hw_mqtt_client.on_connect = _on_hw_connect
            hw_mqtt_client.on_disconnect = _on_hw_disconnect
            hw_mqtt_client.on_message = _on_hw_message
            hw_mqtt_client.connect_async(mqtt_host, mqtt_port, keepalive=30)
            hw_mqtt_client.loop_start()
            hw_node_ids = [n["node_id"] for n in topology.get("nodes", [])]
            print(f"[⚡] Hardware-mirrored nodes (every ESP32 actuator for this topology): {', '.join(hw_node_ids)}")
        except Exception as exc:
            print(f"[!] Hardware mirror requested but MQTT client init failed: {exc}")
            hw_mqtt_client = None

    # Per-node throttling for the hardware mirror publish: send immediately on a phase change,
    # otherwise at most once/second as a keepalive (well under the ESP32's 5s watchdog timeout).
    last_hw_publish_s: Dict[str, float] = {}
    last_hw_target: Dict[str, str] = {}

    # Sync active topology and controller to Dashboard API
    try:
        import urllib.request
        sync_req = urllib.request.Request(
            "http://localhost:8000/api/v1/control/policy",
            data=json.dumps({"controller": ctrl_key, "topology_id": topology_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(sync_req, timeout=1.0) as _:
            pass
        print(f"[✓] Dashboard synchronized with topology '{topology_id}' and controller '{ctrl_key}'.")
    except Exception as exc:
        print(f"[ℹ] Dashboard sync notice (API might be offline): {exc}")

    # SUMO GUI Command with gui-settings & visual delay
    sumo_cmd = [
        sumo_gui_bin,
        "-c", str(sumocfg_path),
        "--gui-settings-file", str(gui_settings_path),
        "--start", "true",
        "--quit-on-end", "true",
        "--delay", str(delay_ms),
        "--tripinfo-output", str(trip_out),
        "--summary-output", str(summary_out),
        "--emission-output", str(emission_out),
        "--waiting-time-memory", "1000",
        "--seed", str(seed),
    ]

    print(f"[🖥️] Launching SUMO-GUI Window...")
    print(f"    Command: {' '.join(sumo_cmd)}")
    print("[ℹ] Visual SUMO-GUI window active on screen...\n")

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

    import queue
    import threading
    import http.client

    telemetry_queue = queue.Queue(maxsize=3000)

    def _telemetry_worker():
        conn = None
        while True:
            try:
                item = telemetry_queue.get(timeout=0.5)
                if item is None:
                    break
                endpoint, payload = item
                try:
                    if conn is None:
                        conn = http.client.HTTPConnection("localhost", 8000, timeout=0.5)
                    body = json.dumps(payload)
                    conn.request("POST", f"/api/v1/{endpoint}", body=body, headers={"Content-Type": "application/json"})
                    resp = conn.getresponse()
                    resp.read()
                except Exception:
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass
                    conn = None
                    try:
                        import urllib.request
                        req = urllib.request.Request(
                            f"http://localhost:8000/api/v1/{endpoint}",
                            data=json.dumps(payload).encode("utf-8"),
                            headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=0.2) as _:
                            pass
                    except Exception:
                        pass
                finally:
                    telemetry_queue.task_done()
            except queue.Empty:
                continue

    t_worker = threading.Thread(target=_telemetry_worker, daemon=True)
    t_worker.start()

    step = 0
    total_queue_sum = 0.0
    samples = 0

    # Periodic SUMO-GUI snapshot for the dashboard's per-node "Edge Vision Perception Canvas":
    # a read-only screenshot of the SAME view the operator is already watching (never changes
    # its zoom/offset/boundary -- so the live SUMO-GUI window on screen is never disturbed).
    # Each node's pixel position is computed from the view's own boundary so the dashboard can
    # crop/zoom to one intersection client-side, no Pillow/video-encoding dependency needed here.
    SNAPSHOT_INTERVAL_S = 2.0
    snapshot_dir = repo_root / "output" / "sumo_snapshots"
    last_snapshot_wall_s = 0.0
    snapshot_due_next_step = False
    pending_boundary = None
    snapshot_png_path = snapshot_dir / f"{topology_id}.png"
    snapshot_meta_path = snapshot_dir / f"{topology_id}_meta.json"

    # Reverse view sync: the dashboard can ask the live sumo-gui window to pan/zoom to a node
    # (POST /api/v1/vision/sumo-focus writes this request file). Unlike the read-only snapshot
    # above, this DOES move the operator's actual camera -- only happens on an explicit request.
    FOCUS_CHECK_INTERVAL_S = 1.0
    FOCUS_RADIUS_M = 80.0
    focus_request_path = snapshot_dir / f"{topology_id}_focus_request.json"
    last_focus_check_wall_s = 0.0
    last_applied_focus_ms = 0

    print("Step (s) | Active Phases                       | Mean Queue (veh)")
    print("-" * 65)

    try:
        while step < duration_s:
            traci.simulationStep()
            t = traci.simulation.getTime()
            step = int(t)

            now_wall_s = time.time()
            if now_wall_s - last_snapshot_wall_s >= SNAPSHOT_INTERVAL_S:
                try:
                    snapshot_dir.mkdir(parents=True, exist_ok=True)
                    pending_boundary = traci.gui.getBoundary(traci.gui.DEFAULT_VIEW)
                    traci.gui.screenshot(traci.gui.DEFAULT_VIEW, str(snapshot_png_path))
                    last_snapshot_wall_s = now_wall_s
                    snapshot_due_next_step = True
                except Exception:
                    pass
            elif snapshot_due_next_step:
                # screenshot() writes its file on the NEXT simulationStep -- that has now
                # happened, so the PNG should be on disk.
                snapshot_due_next_step = False
                try:
                    dims = _png_dimensions(snapshot_png_path)
                    if dims and pending_boundary:
                        img_w, img_h = dims
                        (xmin, ymin), (xmax, ymax) = pending_boundary
                        span_x = max(1e-6, xmax - xmin)
                        span_y = max(1e-6, ymax - ymin)
                        nodes_px = {}
                        for node in topology.get("nodes", []):
                            nid = node["node_id"]
                            try:
                                wx, wy = traci.junction.getPosition(nid)
                                nodes_px[nid] = {
                                    "x": round((wx - xmin) / span_x * img_w, 1),
                                    "y": round(img_h - (wy - ymin) / span_y * img_h, 1),
                                }
                            except Exception:
                                continue
                        snapshot_meta_path.write_text(json.dumps({
                            "topology_id": topology_id,
                            "timestamp_ms": int(time.time() * 1000),
                            "image_width": img_w,
                            "image_height": img_h,
                            "boundary": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
                            "nodes": nodes_px,
                        }), encoding="utf-8")
                except Exception:
                    pass

            if now_wall_s - last_focus_check_wall_s >= FOCUS_CHECK_INTERVAL_S:
                last_focus_check_wall_s = now_wall_s
                try:
                    if focus_request_path.is_file():
                        req = json.loads(focus_request_path.read_text(encoding="utf-8"))
                        req_ms = req.get("requested_ms") or 0
                        req_node = req.get("node_id")
                        if req_node and req_ms and req_ms != last_applied_focus_ms:
                            cx, cy = traci.junction.getPosition(req_node)
                            traci.gui.setBoundary(
                                traci.gui.DEFAULT_VIEW,
                                cx - FOCUS_RADIUS_M, cy - FOCUS_RADIUS_M,
                                cx + FOCUS_RADIUS_M, cy + FOCUS_RADIUS_M,
                            )
                            last_applied_focus_ms = req_ms
                            logger_print = f"[🎯] sumo-gui camera focused on node '{req_node}' (dashboard request)"
                            print(logger_print)
                except Exception:
                    pass

            actuator.step(now=t)
            current_phases = []
            node_queues = []
            step_telemetries = []

            for node in topology.get("nodes", []):
                nid = node["node_id"]
                node_state = actuator.get_or_create_node(nid)
                active_phase = node_state.current_phase_id

                canonical_approaches = []
                for app_id in node.get("approaches", []):
                    q = 0.0
                    veh_count = 0
                    spd = 13.89
                    if app_id in edge_ids:
                        try:
                            q = float(traci.edge.getLastStepHaltingNumber(app_id))
                            veh_count = int(traci.edge.getLastStepVehicleNumber(app_id))
                            spd = max(0.1, float(traci.edge.getLastStepMeanSpeed(app_id)))
                        except Exception:
                            pass
                    flow = round(max(0.15 * q, veh_count * 0.25), 2)
                    canonical_approaches.append({
                        "approach_id": app_id,
                        "queue_vehicles": round(q, 1),
                        "flow_veh_per_s": flow,
                        "mean_speed_mps": round(spd, 2),
                        "occupancy_ratio": round(min(max(q, veh_count) / 20.0, 1.0), 2),
                        "confidence": 1.0
                    })
                    node_queues.append(q)

                telemetry = {
                    "node_id": nid,
                    "topology_id": topology_id,
                    "source_type": "simulation",
                    "simulation_time_s": t,
                    "timestamp_ms": int(time.time() * 1000),
                    "current_phase_id": active_phase,
                    "status": "ONLINE",
                    "approaches": canonical_approaches,
                    "hardware_mirror": hardware,
                    "hardware_mqtt_connected": bool(hardware and hw_mqtt_client is not None and hw_connected["value"]),
                }
                step_telemetries.append(telemetry)

                override_cmd = override_hold.command_for(nid, active_phase) if hardware else None
                cmd = override_cmd or controller.compute_command(
                    node_id=nid,
                    telemetry=telemetry,
                    topology=topology,
                    current_time_s=t,
                )
                if cmd and hw_mqtt_client is not None and hw_connected["value"] and not hw_safe_stop.get(nid):
                    target = cmd.get("target_phase_id")
                    changed = last_hw_target.get(nid) != target
                    if changed or (now_wall_s - last_hw_publish_s.get(nid, -999.0)) >= 1.0:
                        try:
                            hw_mqtt_client.publish(topics.get_command_topic(nid), json.dumps(cmd), qos=0)
                            last_hw_publish_s[nid] = now_wall_s
                            last_hw_target[nid] = target
                        except Exception:
                            pass
                if cmd:
                    ack = actuator.process_command(cmd, now=t)
                    # Only record control ACK on actual phase transition to avoid flooding HTTP queue
                    if ack and getattr(node_state, "state_start_time", -1.0) == t:
                        try:
                            # ack is already a plain ControlACK dict (command_id, node_id, status,
                            # reason, ...) from ActuatorStateMachine._ack() -- use it as-is. The old
                            # `getattr(ack, "status", ...)` here never worked on a dict (getattr reads
                            # object attributes, not keys), so every local ACK silently reported the
                            # fallback "APPLIED"/"Phase command executed." regardless of what actually
                            # happened (REJECTED/EXPIRED reasons were swallowed).
                            ack_payload = dict(ack) if isinstance(ack, dict) else (
                                ack.to_dict() if hasattr(ack, "to_dict") else {
                                    "command_id": f"cmd-{nid}-{t}",
                                    "node_id": nid,
                                    "status": "APPLIED",
                                    "reason": "Phase command executed.",
                                    "timestamp_ms": int(time.time() * 1000)
                                }
                            )
                            telemetry_queue.put_nowait(("control_ack", ack_payload))
                        except queue.Full:
                            pass

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

            # Send high-speed batch telemetry of all nodes to Dashboard API
            if step_telemetries:
                try:
                    telemetry_queue.put_nowait(("telemetry", step_telemetries))
                except queue.Full:
                    pass

            mean_q = sum(node_queues) / len(node_queues) if node_queues else 0.0
            total_queue_sum += mean_q
            samples += 1

            if step % 10 == 0 or step == duration_s - 1:
                phases_str = " ".join(current_phases[:4])
                if len(current_phases) > 4:
                    phases_str += f" (+{len(current_phases)-4} nodes)"
                print(f" t={step:<5} | {phases_str:<35} | {mean_q:.2f} veh")

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            else:
                # 20ms pace yields CPU for smooth WebSocket streaming to React Dashboard (~50 fps)
                time.sleep(0.02)

    except traci.exceptions.FatalTraCIError:
        print("[ℹ] SUMO-GUI window closed by user.")
    except Exception as err:
        print(f"[!] Error during TraCI loop: {err}")
    finally:
        try:
            # Drain telemetry queue to ensure all steps are sent to the Dashboard
            telemetry_queue.join()
        except Exception:
            pass
        try:
            traci.close()
        except Exception:
            pass
        if hw_mqtt_client is not None:
            try:
                hw_mqtt_client.loop_stop()
                hw_mqtt_client.disconnect()
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
    print(" 📊 SCENARIO DEMO COMPLETED SUCCESSFULLY")
    print("=" * 65)
    for k, v in zip(fields, values):
        print(f" • {k:<25}: {v}")
    print("=" * 65)
    print(f"[✓] Metrics exported to: {csv_out}")
    print(f"[✓] IOC Dashboard: http://localhost:3000\n")


def main():
    parser = argparse.ArgumentParser(description="EdgeFlow AI — Canonical SUMO-GUI Live Demo Launcher")
    parser.add_argument("--topology", type=str, default="hcm_corridor", help="Topology ID (hcm_corridor, corridor, junction, grid16, cologne)")
    parser.add_argument("--scenario", type=str, default="hcm_corridor", help="Scenario profile (hcm_corridor, directional_surge, balanced)")
    parser.add_argument("--controller", type=str, default="max_pressure", help="Controller type (max_pressure, actuated, fixed_time, flow_theory)")
    parser.add_argument("--duration", type=int, default=300, help="Demo duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--delay", type=int, default=0, help="SUMO-GUI step delay in milliseconds (0 for max speed / instant, 20 for fast/smooth, 100 for slow)")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker compose initialization")
    parser.add_argument("--hardware", action="store_true",
                         help="Mirror every ControlCommand to real ESP32 actuator boards over MQTT "
                              "(e.g. tabletop_j1_j2_v1 J1/J2). ESP32 is actuator-only: it executes the "
                              "command and safety timing itself; this process remains the sole decision brain.")
    parser.add_argument("--mqtt-host", type=str, default=os.environ.get("MQTT_HOST", "localhost"),
                         help="MQTT broker host for --hardware (default: $MQTT_HOST or localhost)")
    parser.add_argument("--mqtt-port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")),
                         help="MQTT broker port for --hardware (default: $MQTT_PORT or 1883)")

    args = parser.parse_args()

    topology_id = contracts_sdk.resolve_topology_id(args.topology)
    scenario_id = args.scenario
    controller_name = args.controller
    duration_s = args.duration
    seed = args.seed
    delay_ms = args.delay

    print_banner(topology_id, scenario_id, controller_name, duration_s,
                 hardware=args.hardware, mqtt_host=args.mqtt_host, mqtt_port=args.mqtt_port)

    # 1. Ensure Docker Microservices
    ensure_docker_services(skip_docker=args.skip_docker, hardware=args.hardware)

    # 2. Find SUMO-GUI executable
    sumo_gui_bin = find_sumo_gui_binary()

    # 3. Launch live TraCI demo with SUMO-GUI
    run_demo_simulation(
        topology_id=topology_id,
        scenario_id=scenario_id,
        controller_name=controller_name,
        duration_s=duration_s,
        seed=seed,
        sumo_gui_bin=sumo_gui_bin,
        delay_ms=delay_ms,
        hardware=args.hardware,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
    )


if __name__ == "__main__":
    main()
