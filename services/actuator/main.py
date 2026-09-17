import os
import json
import time
import logging

from actuator_contracts_helper import validate_payload
from state_machine import ActuatorStateMachine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("actuator")

def main():
    logger.info("Starting EdgeFlow Signal Actuator Service...")
    state_machine = ActuatorStateMachine()

    mqtt_host = os.getenv("MQTT_HOST", "mqtt")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker successfully.")
            client.subscribe("edgeflow/v1/control/+/command")
        else:
            logger.warning(f"MQTT Connect failed with code {rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            validate_payload(payload, "control_command")
            node_id = payload["node_id"]

            ack = state_machine.process_command(payload)
            validate_payload(ack, "control_ack")

            pub_topic = f"edgeflow/v1/control/{node_id}/ack"
            client.publish(pub_topic, json.dumps(ack))
            logger.info(f"Published ControlACK to {pub_topic}: status={ack['status']}, reason={ack['reason']}")
        except Exception as e:
            logger.error(f"Error processing ControlCommand message: {e}")

    try:
        import paho.mqtt.client as mqtt
        client = mqtt.Client(client_id="actuator-service")
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
