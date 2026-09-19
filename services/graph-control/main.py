import os
import json
import time
import logging
from typing import Dict, Any

from config import settings
from graph_contracts_helper import load_topology, validate_payload
from controller import MaxPressureController, FixedTimeController

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("graph-control")

def create_controller():
    controller_type = settings.edgeflow_controller.lower()
    if controller_type == "max_pressure":
        logger.info("Initializing MaxPressureController")
        return MaxPressureController()
    else:
        logger.info("Initializing FixedTimeController")
        return FixedTimeController()

def main():
    logger.info("Starting EdgeFlow Graph-Control Service...")
    topology_id = settings.edgeflow_topology
    topology = load_topology(topology_id)
    controller = create_controller()

    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker successfully.")
            client.subscribe("edgeflow/v1/telemetry/+")
        else:
            logger.warning(f"MQTT Connect failed with code {rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            validate_payload(payload, "telemetry")
            node_id = payload["node_id"]

            cmd = controller.compute_command(node_id, payload, topology)
            if not cmd:
                logger.debug(f"Node {node_id} has no traffic light phases; skipping command.")
                return

            validate_payload(cmd, "control_command")

            pub_topic = f"edgeflow/v1/control/{node_id}/command"
            client.publish(pub_topic, json.dumps(cmd))
            logger.info(f"Published ControlCommand to {pub_topic}: {cmd['target_phase_id']}")
        except Exception as e:
            logger.error(f"Error processing telemetry message: {e}")

    try:
        import paho.mqtt.client as mqtt
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="graph-control-service")
        except AttributeError:
            client = mqtt.Client(client_id="graph-control-service")
        client.on_connect = on_connect
        client.on_message = on_message
        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
        client.connect_async(mqtt_host, mqtt_port, 60)
        client.loop_start()
    except Exception as e:
        logger.warning(f"MQTT Client setup skipped or failed: {e}. Service running in passive mode.")

    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
