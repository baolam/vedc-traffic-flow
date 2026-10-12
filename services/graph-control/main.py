import os
import json
import time
import logging
from typing import Dict, Any

from config import settings
from graph_contracts_helper import load_topology, validate_payload, topics
from controller import (
    MaxPressureController, FixedTimeController, ActuatedController,
    MaxQueueController, EdgeFlowController, PressLightRLController,
    FlowTheoryController
)

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("graph-control")

def create_controller():
    from src.control.factory import create_controller as build_controller
    name = settings.edgeflow_controller.lower()
    aliases = {"flow": "flow_theory", "ctm": "flow_theory", "flow_rl": "presslight_rl",
               "presslight": "presslight_rl", "rl_ppo": "presslight_rl"}
    return build_controller(aliases.get(name, name), model_path=settings.rl_model_path or None)


def main():
    logger.info("Starting EdgeFlow Graph-Control Service...")
    topology_id = settings.edgeflow_topology
    topology = load_topology(topology_id)
    controller = create_controller()

    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port
    network_state: Dict[str, Any] = {}

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker successfully.")
            client.subscribe(topics.TELEMETRY_SUB_PATTERN)
        else:
            logger.warning(f"MQTT Connect failed with code {rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            validate_payload(payload, "telemetry")
            node_id = payload["node_id"]
            network_state[node_id] = payload

            cmd = controller.compute_command(
                node_id=node_id, 
                telemetry=payload, 
                topology=topology,
                network_state=network_state
            )
            if not cmd:
                logger.debug(f"Node {node_id} has no traffic light phases; skipping command.")
                return

            validate_payload(cmd, "control_command")

            pub_topic = topics.get_command_topic(node_id)
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
