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
from runtime_guards import BlindNodeGate, ManualOverrideHold, PolicyFollower

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("graph-control")

POLICY_POLL_S = 2.0


def create_controller(name=None):
    from src.control.factory import create_controller as build_controller
    name = (name or settings.edgeflow_controller).lower()
    aliases = {"flow": "flow_theory", "ctm": "flow_theory", "flow_rl": "presslight_rl",
               "presslight": "presslight_rl", "rl_ppo": "presslight_rl"}
    return build_controller(aliases.get(name, name), model_path=settings.rl_model_path or None)


def main():
    logger.info("Starting EdgeFlow Graph-Control Service...")
    topology_id = settings.edgeflow_topology
    topology = load_topology(topology_id)
    # Swapped by the policy follower (main thread) and read by the MQTT thread: one reference assignment
    active = {"controller": create_controller()}
    logger.info(f"Topology: {topology_id} | controller: {settings.edgeflow_controller}")
    gate = BlindNodeGate()
    hold = ManualOverrideHold(settings.manual_override_hold_s)

    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port
    network_state: Dict[str, Any] = {}

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker successfully.")
            client.subscribe(topics.TELEMETRY_SUB_PATTERN)
            # Dashboard overrides are published by the API straight to the ESP32; seeing them here pauses the controller
            client.subscribe(topics.COMMAND_SUB_PATTERN)
        else:
            logger.warning(f"MQTT Connect failed with code {rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if msg.topic.endswith("/command"):
                hold.observe_command(payload)  # our own commands are ignored by their command_id
                return
            validate_payload(payload, "telemetry")
            node_id = payload["node_id"]
            # No observation -> no command: the ESP32 runs its own fallback instead of obeying zeros (G1)
            admitted = gate.admit(node_id, payload, network_state)
            if admitted:
                network_state[node_id] = payload

            # An operator override outranks both the controller and the blind gate, for a bounded time
            cmd = hold.command_for(node_id, payload.get("current_phase_id"))
            if cmd is None:
                if not admitted:
                    return
                cmd = active["controller"].compute_command(
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
            logger.error(f"Error processing {msg.topic} message: {e}")

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

    # Dashboard "Apply Policy" -> API -> here (HTTP poll). Unset = keep EDGEFLOW_CONTROLLER for the whole run.
    follower = None
    if settings.control_policy_url:
        follower = PolicyFollower(settings.control_policy_url, settings.edgeflow_controller, create_controller)
        logger.info(f"Following the controller policy at {settings.control_policy_url}")

    while True:
        time.sleep(POLICY_POLL_S if follower else 10)
        if follower:
            new_controller = follower.poll_once()
            if new_controller is not None:
                active["controller"] = new_controller

if __name__ == "__main__":
    main()
