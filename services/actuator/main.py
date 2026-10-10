"""
EdgeFlow AI - Signal Actuator Service.
Enforces safe signal clearance transitions (GREEN -> YELLOW -> ALL_RED -> GREEN)
and publishes authoritative ControlACK responses to MQTT.
"""

import os
import json
import time
import logging
from typing import Dict, Any

from config import settings
from actuator_contracts_helper import validate_payload
from state_machine import ActuatorStateMachine

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [Actuator] %(message)s"
)
logger = logging.getLogger("actuator")


def main():
    logger.info("=========================================================")
    logger.info("       Starting EdgeFlow Signal Actuator Service        ")
    logger.info("=========================================================")
    
    state_machine = ActuatorStateMachine(
        yellow_duration_s=getattr(settings, "yellow_duration_s", 3.0),
        all_red_duration_s=getattr(settings, "all_red_duration_s", 2.0)
    )

    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port
    mqtt_client = None

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT Broker at {mqtt_host}:{mqtt_port}")
            client.subscribe("edgeflow/v1/control/+/command")
            logger.info("Subscribed to control commands: edgeflow/v1/control/+/command")
        else:
            logger.warning(f"MQTT Connect failed with return code {rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            validate_payload(payload, "control_command")
            node_id = payload["node_id"]
            now_s = time.time()

            ack = state_machine.process_command(payload, now=now_s)
            validate_payload(ack, "control_ack")

            pub_topic = f"edgeflow/v1/control/{node_id}/ack"
            client.publish(pub_topic, json.dumps(ack))
            logger.info(f"Published ControlACK [{node_id}] -> status: {ack['status']} | {ack.get('reason', '')}")
        except Exception as e:
            logger.error(f"Error processing ControlCommand: {e}")

    try:
        import paho.mqtt.client as mqtt
        try:
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="actuator-service")
        except AttributeError:
            mqtt_client = mqtt.Client(client_id="actuator-service")
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
        mqtt_client.connect_async(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.warning(f"MQTT Client setup skipped or failed: {e}. Service running in passive mode.")

    try:
        while True:
            # Advance internal clearance clock and emit completion ACKs
            now_s = time.time()
            step_result = state_machine.step(now=now_s)
            applied_events = step_result.get("applied_events", [])
            for evt in applied_events:
                node_id = evt["node_id"]
                applied_ack = {
                    "command_id": "auto_clearance",
                    "node_id": node_id,
                    "target_phase_id": evt["phase_id"],
                    "status": "APPLIED",
                    "timestamp_ms": int(now_s * 1000),
                    "reason": f"Physical clearance transition complete. Phase {evt['phase_id']} is now GREEN."
                }
                if mqtt_client and mqtt_client.is_connected():
                    pub_topic = f"edgeflow/v1/control/{node_id}/ack"
                    mqtt_client.publish(pub_topic, json.dumps(applied_ack))
                    logger.info(f"Transition Complete [{node_id}] -> GREEN on {evt['phase_id']}")

            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Stopping Actuator Service...")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()


if __name__ == "__main__":
    main()
