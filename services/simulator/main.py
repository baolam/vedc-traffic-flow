import os
import json
import time
import logging
from typing import Dict, Any

from config import settings
from simulator_contracts_helper import load_topology
from traffic_engine import TrafficEngine

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("simulator")

def main():
    topology_id = settings.edgeflow_topology
    use_sumo = settings.use_sumo
    logger.info(f"Starting EdgeFlow Simulator Service (Topology: {topology_id}, USE_SUMO: {use_sumo})...")

    try:
        topology = load_topology(topology_id)
        logger.info(f"Loaded topology '{topology_id}' with {len(topology.get('nodes', []))} nodes.")
    except Exception as e:
        logger.error(f"Failed to load topology '{topology_id}': {e}")
        raise e

    engine = TrafficEngine(topology, use_sumo=use_sumo)
    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port
    sim_interval = settings.sim_interval_s

    mqtt_client = None

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker successfully.")
            # Subscribe to Actuator ACKs to sync physical/actuated phase transitions
            client.subscribe("edgeflow/v1/control/+/ack")
        else:
            logger.warning(f"MQTT Connect failed with code {rc}")

    def on_message(client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))
            if topic.startswith("edgeflow/v1/control/") and topic.endswith("/ack"):
                node_id = payload.get("node_id")
                status = payload.get("status")
                # If signal transition was applied, update simulator phase state
                if status == "APPLIED" and node_id:
                    phase_id = payload.get("target_phase_id")
                    if not phase_id and "transitioned to phase " in payload.get("reason", ""):
                        phase_id = payload.get("reason", "").split("transitioned to phase ")[1].split()[0]
                    if phase_id:
                        engine.update_node_phase(node_id, phase_id)
                        logger.info(f"Simulator updated active phase for node {node_id} to {phase_id}")
        except Exception as e:
            logger.error(f"Error handling MQTT message on {msg.topic}: {e}")

    try:
        import paho.mqtt.client as mqtt
        try:
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="simulator-service")
        except AttributeError:
            mqtt_client = mqtt.Client(client_id="simulator-service")
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
        mqtt_client.connect_async(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.warning(f"MQTT Client setup skipped or failed: {e}. Simulator running in passive standalone mode.")

    sim_time_s = 0.0
    last_health_time = 0.0

    while True:
        loop_start = time.time()
        sim_time_s += sim_interval
        engine.step(dt_s=sim_interval)

        for node_info in topology.get("nodes", []):
            node_id = node_info["node_id"]
            try:
                telemetry = engine.generate_telemetry(node_id, sim_time_s)
                if mqtt_client and mqtt_client.is_connected():
                    pub_topic = f"edgeflow/v1/telemetry/{node_id}"
                    mqtt_client.publish(pub_topic, json.dumps(telemetry))
                    logger.debug(f"Published telemetry for {node_id} to {pub_topic}")
            except Exception as e:
                logger.error(f"Failed generating or publishing telemetry for node {node_id}: {e}")

        # Publish health check every 10 seconds
        if loop_start - last_health_time >= 10.0:
            last_health_time = loop_start
            if mqtt_client and mqtt_client.is_connected():
                health_payload = {
                    "service": "simulator",
                    "status": "HEALTHY",
                    "simulation_time_s": round(sim_time_s, 2),
                    "timestamp_ms": int(time.time() * 1000)
                }
                mqtt_client.publish("edgeflow/v1/health/simulator", json.dumps(health_payload))
                logger.info(f"Simulator Health Check - Sim Time: {sim_time_s:.1f}s")

        elapsed = time.time() - loop_start
        sleep_time = max(0.0, sim_interval - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()
