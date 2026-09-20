import os
import sys
import time
import socket
import logging
import argparse
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_experiment_gui")

ROOT_DIR = Path(__file__).resolve().parents[2]

def is_mqtt_broker_running(host: str = "localhost", port: int = 1883) -> bool:
    """Check if MQTT broker is listening on host:port."""
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except (OSError, socket.error):
        return False

def run_gui_experiment(
    scenario: str = "directional_surge",
    controller: str = "max_pressure",
    duration: int = 60,
    seed: int = 42,
    topology: str = "four_intersection_v1",
    mqtt_host: str = "localhost",
    mqtt_port: int = 1883
):
    logger.info("=========================================================")
    logger.info("   EdgeFlow AI - Integrated SUMO-GUI Experiment Launcher ")
    logger.info("=========================================================")
    logger.info(f"Topology   : {topology}")
    logger.info(f"Scenario   : {scenario}")
    logger.info(f"Controller : {controller}")
    logger.info(f"Duration   : {duration}s")
    logger.info(f"Seed       : {seed}")
    logger.info(f"MQTT Broker: {mqtt_host}:{mqtt_port}")
    logger.info("=========================================================")

    # 1. Check MQTT Broker
    if not is_mqtt_broker_running(mqtt_host, mqtt_port):
        logger.warning(f"MQTT Broker at {mqtt_host}:{mqtt_port} is NOT reachable.")
        logger.info("Attempting to start Mosquitto MQTT Broker or continuing...")
        try:
            subprocess.Popen(["mosquitto", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
        except Exception:
            logger.warning("Could not launch 'mosquitto' executable automatically. Please ensure an MQTT Broker (Mosquitto/Docker) is running.")

    # 2. Setup environment variables for child processes
    env = os.environ.copy()
    env["USE_SUMO"] = "true"
    env["SUMO_BINARY"] = "sumo-gui"
    env["MQTT_HOST"] = mqtt_host
    env["MQTT_PORT"] = str(mqtt_port)
    env["EDGEFLOW_TOPOLOGY"] = topology
    env["EDGEFLOW_CONTROLLER"] = controller
    env["PYTHONPATH"] = str(ROOT_DIR)

    processes = []

    try:
        # 3. Launch Actuator Service
        actuator_script = ROOT_DIR / "services" / "actuator" / "main.py"
        logger.info("[1/4] Starting Actuator Service...")
        p_actuator = subprocess.Popen([sys.executable, str(actuator_script)], env=env)
        processes.append(("Actuator", p_actuator))
        time.sleep(1.0)

        # 4. Launch Graph-Control Service
        control_script = ROOT_DIR / "services" / "graph-control" / "main.py"
        logger.info("[2/4] Starting Graph-Control Service...")
        p_control = subprocess.Popen([sys.executable, str(control_script)], env=env)
        processes.append(("Graph-Control", p_control))
        time.sleep(1.0)

        # 5. Launch Simulator Service (triggers SUMO-GUI)
        sim_script = ROOT_DIR / "services" / "simulator" / "main.py"
        logger.info("[3/4] Starting Simulator Service (Opening SUMO-GUI window)...")
        p_sim = subprocess.Popen([sys.executable, str(sim_script)], env=env)
        processes.append(("Simulator (SUMO-GUI)", p_sim))
        time.sleep(2.0)

        # 6. Launch Experiment Runner
        runner_script = ROOT_DIR / "services" / "experiment-runner" / "runner.py"
        logger.info(f"[4/4] Starting Experiment Runner ({duration}s)...")
        exp_id = f"gui_{scenario}_{controller}_seed{seed}"
        cmd_runner = [
            sys.executable, str(runner_script),
            "--experiment-id", exp_id,
            "--scenario", scenario,
            "--controller", controller,
            "--duration", str(duration),
            "--seed", str(seed),
            "--topology", topology
        ]
        
        p_runner = subprocess.Popen(cmd_runner, env=env)
        processes.append(("Experiment-Runner", p_runner))

        logger.info("All services spawned successfully! SUMO-GUI window should be visible.")
        logger.info("Experiment is running. Press Ctrl+C at any time to stop all services.\n")

        # Wait for experiment runner to finish
        p_runner.wait()
        logger.info(f"Experiment {exp_id} completed successfully!")

    except KeyboardInterrupt:
        logger.info("\nTermination requested by user (Ctrl+C). Stopping services...")
    except Exception as e:
        logger.error(f"Error during execution: {e}")
    finally:
        logger.info("Cleaning up background microservice processes...")
        for name, proc in reversed(processes):
            if proc.poll() is None:
                logger.info(f"Terminating {name} (PID {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
        logger.info("All services shut down cleanly.")

def main():
    parser = argparse.ArgumentParser(description="EdgeFlow AI Unified SUMO-GUI Experiment Launcher")
    parser.add_argument("--scenario", type=str, default="directional_surge", help="Traffic scenario name")
    parser.add_argument("--controller", type=str, default="max_pressure", help="Controller type (max_pressure / fixed_time)")
    parser.add_argument("--duration", type=int, default=60, help="Simulation duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--topology", type=str, default="four_intersection_v1", help="Topology contract ID")
    parser.add_argument("--mqtt-host", type=str, default="localhost", help="MQTT broker hostname")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")

    args = parser.parse_args()

    run_gui_experiment(
        scenario=args.scenario,
        controller=args.controller,
        duration=args.duration,
        seed=args.seed,
        topology=args.topology,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port
    )

if __name__ == "__main__":
    main()
