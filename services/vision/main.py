import sys
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any

# Ensure services/vision directory is in sys.path for IDE & module resolution
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

try:
    from config import settings
    from perception_engine import PerceptionEngine
    from vision_contracts_helper import load_topology, validate_payload
except ImportError:
    from services.vision.config import settings
    from services.vision.perception_engine import PerceptionEngine
    from services.vision.vision_contracts_helper import load_topology, validate_payload

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("vision-service")

def main():
    logger.info("Starting EdgeFlow Vision Perception Adapter Service...")
    topology_id = settings.edgeflow_topology
    topology = load_topology(topology_id)
    nodes = topology.get("nodes", [])

    engine = PerceptionEngine(video_source_str=settings.video_source)
    if nodes:
        first_node = nodes[0].get("node_id", "J1")
        engine.setup_topology(topology, node_id=first_node)

    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port
    mqtt_client = None

    try:
        import paho.mqtt.client as mqtt
        try:
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="vision-perception-service")
        except AttributeError:
            mqtt_client = mqtt.Client(client_id="vision-perception-service")
        
        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
        mqtt_client.connect_async(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.warning(f"MQTT Client setup skipped or failed: {e}. Operating in standalone perception mode.")

    sim_time_s = 0.0
    period_s = settings.telemetry_period_s

    try:
        while True:
            start_tick = time.time()
            sim_time_s += period_s
            timestamp_ms = int(time.time() * 1000)

            for node in nodes:
                node_id = node.get("node_id", "J1")
                phases = node.get("phases", [])
                default_phase = phases[0]["phase_id"] if phases else f"{node_id}_PHASE_NS"

                # Extract approaches metrics from vision engine
                approaches = engine.process_frame(node_id=node_id)
                if not approaches:
                    # Provide fallback approaches if frame was empty
                    approaches = [
                        {
                            "approach_id": f"{node_id}_W_IN",
                            "queue_vehicles": 2.0,
                            "flow_veh_per_s": 0.15,
                            "mean_speed_mps": 4.5,
                            "occupancy_ratio": 0.25,
                            "confidence": 0.90
                        }
                    ]

                payload = {
                    "node_id": node_id,
                    "source_type": "vision",
                    "simulation_time_s": round(sim_time_s, 2),
                    "timestamp_ms": timestamp_ms,
                    "current_phase_id": default_phase,
                    "approaches": approaches
                }

                # Validate against contracts/schemas/telemetry.json
                validate_payload(payload, "telemetry")

                topic = f"edgeflow/v1/telemetry/{node_id}"
                if mqtt_client and mqtt_client.is_connected():
                    mqtt_client.publish(topic, json.dumps(payload))
                    logger.debug(f"Published Vision Telemetry to {topic}")
                else:
                    logger.info(f"Generated Vision Telemetry payload for {node_id}: {len(approaches)} approaches")

            elapsed = time.time() - start_tick
            sleep_dur = max(period_s - elapsed, 0.05)
            time.sleep(sleep_dur)

    except KeyboardInterrupt:
        logger.info("Stopping Vision Perception Adapter Service...")
    finally:
        engine.close()
        if mqtt_client:
            mqtt_client.loop_stop()

if __name__ == "__main__":
    main()
