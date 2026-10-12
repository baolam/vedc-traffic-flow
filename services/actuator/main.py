"""
EdgeFlow AI — Standalone Actuator Microservice.

Consumes ControlCommand messages from MQTT, enforces clearance transitions
(Yellow -> All-Red -> Green) and safety envelopes via ActuatorStateMachine,
and broadcasts canonical ControlACK messages.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

# Setup paths for contracts and src
CURR_DIR = Path(__file__).resolve().parent
REPO_ROOT = next((p for p in [CURR_DIR, *CURR_DIR.parents] if (p / "src" / "control").is_dir()), CURR_DIR.parent.parent)

for p in [REPO_ROOT / "contracts", REPO_ROOT]:
    if str(p) not in sys.path and p.exists():
        sys.path.insert(0, str(p))

try:
    import contracts_sdk
    import topics
except ImportError:
    from contracts import contracts_sdk, topics

from config import settings
from src.control.actuator import ActuatorStateMachine

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [actuator] %(message)s"
)
logger = logging.getLogger("actuator")


def main():
    logger.info("Starting EdgeFlow Standalone Actuator Service...")

    actuator = ActuatorStateMachine(
        yellow_duration_s=settings.yellow_duration_s,
        all_red_duration_s=settings.all_red_duration_s
    )

    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port

    mqtt_client = None

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Actuator connected to MQTT Broker successfully.")
            client.subscribe(topics.COMMAND_SUB_PATTERN)
            logger.info(f"Subscribed to {topics.COMMAND_SUB_PATTERN}")
        else:
            logger.warning(f"MQTT connect failed with rc={rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            now = time.time()
            contracts_sdk.validate_payload(payload, "control_command")
            node_id = payload["node_id"]

            ack = actuator.process_command(payload, now=now)
            contracts_sdk.validate_payload(ack, "control_ack")

            ack_topic = topics.get_ack_topic(node_id)
            client.publish(ack_topic, json.dumps(ack))
            logger.info(f"Command for [{node_id}] -> ACK Status: {ack['status']} ({ack.get('reason', '')})")
        except Exception as e:
            logger.error(f"Error handling ControlCommand on {msg.topic}: {e}")

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
        logger.warning(f"MQTT setup failed: {e}. Running in passive standalone mode.")

    last_step_time = time.time()
    last_health_time = time.time()

    while True:
        now = time.time()
        # Step clearance clock
        step_result = actuator.step(now=now)
        for applied_event in step_result.get("applied_events", []):
            node_id = applied_event["node_id"]
            phase_id = applied_event["phase_id"]
            cmd_id = applied_event.get("command_id", f"cmd-{int(now * 1000)}")

            applied_ack = {
                "command_id": cmd_id,
                "node_id": node_id,
                "target_phase_id": phase_id,
                "status": "APPLIED",
                "timestamp_ms": int(now * 1000),
                "reason": f"Clearance complete. Switched to GREEN on {phase_id}"
            }
            try:
                contracts_sdk.validate_payload(applied_ack, "control_ack")
            except Exception as ve:
                logger.warning(f"ControlACK validation warning: {ve}")

            if mqtt_client and mqtt_client.is_connected():
                ack_topic = topics.get_ack_topic(node_id)
                mqtt_client.publish(ack_topic, json.dumps(applied_ack))
                logger.info(f"Clearance transition complete -> Published APPLIED ACK for [{node_id}] -> {phase_id}")

        # Periodic health check
        if now - last_health_time >= 10.0:
            last_health_time = now
            if mqtt_client and mqtt_client.is_connected():
                health_payload = {
                    "service": "actuator",
                    "status": "HEALTHY",
                    "active_nodes": list(actuator.nodes.keys()),
                    "timestamp_ms": int(now * 1000)
                }
                health_topic = topics.get_health_topic("actuator")
                mqtt_client.publish(health_topic, json.dumps(health_payload))

        time.sleep(0.1)


if __name__ == "__main__":
    main()
