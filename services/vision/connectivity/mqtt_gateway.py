"""
EdgeFlow AI - Open connection to the broader system (MQTT).
-------------------------------------------------------------
Consolidates everything the vision service needs to talk to the central MQTT broker: client
construction, Last-Will-and-Testament (LWT) so a dead/disconnected process is never mistaken
for a healthy one, subscribing to ESP32 device health (feeding PhaseTracker), and publishing
canonical Telemetry/Health payloads. If the broker is unreachable at startup, `connect()`
degrades gracefully to a log-only "standalone edge perception mode" rather than failing -- the
Supervisor keeps running the vision pipeline either way.
"""

import json
import logging
import threading
from typing import Any, Dict, Optional

try:
    from vision_contracts_helper import validate_payload, topics
except ImportError:
    from services.vision.vision_contracts_helper import validate_payload, topics

from .phase_tracker import PhaseTracker

logger = logging.getLogger("vision-mqtt-gateway")


class MqttGateway:
    """One instance per service process. `health_request` is set from the MQTT network thread
    on every (re)connect (so a fresh HEALTHY message overwrites any stale retained OFFLINE left
    by a prior will-triggered drop) and is meant to be polled/cleared by the Supervisor's single
    main-loop thread, exactly like the `health_request` Event main.py used to own directly."""

    def __init__(self, settings, phase_tracker: PhaseTracker, health_topic: str):
        self._settings = settings
        self._phase_tracker = phase_tracker
        self._health_topic = health_topic
        self._offline_payload = json.dumps({"service": "vision", "status": "OFFLINE"})
        self.health_request = threading.Event()
        self._client = None  # stays None in standalone mode

    def connect(self) -> None:
        """Best-effort: any failure here (missing paho, broker unreachable, ...) is logged as a
        warning and leaves self._client None, so the caller's publish_* calls simply no-op."""
        try:
            import paho.mqtt.client as mqtt

            client_id = self._settings.mqtt_client_id or topics.client_id("vision")
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
            except AttributeError:
                client = mqtt.Client(client_id=client_id)

            client.on_connect = self._on_connect
            client.on_message = self._on_message
            self._set_offline_will(client)

            logger.info(f"Connecting to MQTT broker at {self._settings.mqtt_host}:{self._settings.mqtt_port}...")
            client.connect_async(self._settings.mqtt_host, self._settings.mqtt_port,
                                 self._settings.mqtt_keepalive_s)
            client.loop_start()
            self._client = client
        except Exception as e:
            logger.warning(f"MQTT client connection skipped ({e}). Operating in standalone edge perception mode.")
            self._client = None

    def _set_offline_will(self, client) -> None:
        """The broker publishes this retained OFFLINE when the service dies or drops off the
        network, so a stale retained HEALTHY never outlives the process."""
        client.will_set(self._health_topic, self._offline_payload, qos=1, retain=True)

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            logger.info(f"Connected to MQTT Broker successfully at "
                        f"{self._settings.mqtt_host}:{self._settings.mqtt_port}")
            for topic in self._phase_tracker.topics:
                client.subscribe(topic)
            self.health_request.set()  # replaces a retained OFFLINE left by the will after a drop
        else:
            logger.warning(f"MQTT connection failed with return code {rc}")

    def _on_message(self, client, userdata, msg) -> None:
        self._phase_tracker.update(msg.topic, msg.payload)

    @property
    def is_connected(self) -> bool:
        return bool(self._client is not None and self._client.is_connected())

    def _publish(self, topic: str, payload: Dict[str, Any], qos: int, retain: bool) -> bool:
        """Shared publish path: returns True iff actually sent. Never raises on a down broker --
        callers fall back to log-only reporting when this returns False."""
        if not self.is_connected:
            return False
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)
        return True

    def publish_telemetry(self, node_id: str, payload: Dict[str, Any]) -> bool:
        validate_payload(payload, "telemetry")
        topic = topics.get_telemetry_topic(node_id)
        sent = self._publish(topic, payload, qos=self._settings.mqtt_qos_telemetry, retain=False)
        if sent:
            logger.debug(f"Published Vision Telemetry to {topic} "
                        f"({len(payload['approaches'])} approaches)")
        return sent

    def publish_health(self, payload: Dict[str, Any]) -> bool:
        validate_payload(payload, "health")
        return self._publish(self._health_topic, payload,
                             qos=self._settings.mqtt_qos_health, retain=True)

    def publish_signal_fault(self, node_id: str, payload: Dict[str, Any], category: Optional[str] = None) -> bool:
        validate_payload(payload, "signal_fault_event")
        cat = category or payload.get("category", "camera")
        topic = topics.get_signal_fault_topic(node_id, category=cat)
        sent = self._publish(topic, payload, qos=1, retain=False)
        if sent:
            logger.warning(f"Published Signal Fault [{payload.get('fault_code')}] to {topic}: {payload.get('reason')}")
        return sent

    def disconnect(self) -> None:
        """Explicit OFFLINE announce before disconnecting: a clean DISCONNECT suppresses the
        LWT, so the retained health topic would otherwise keep showing HEALTHY after a planned
        stop. This always uses qos=1/retain=True regardless of settings.mqtt_qos_health, since
        shutdown behavior must stay deterministic."""
        if self._client is None:
            return
        if self._client.is_connected():
            info = self._client.publish(self._health_topic, self._offline_payload, qos=1, retain=True)
            try:
                info.wait_for_publish(timeout=2.0)
            except TypeError:
                pass  # paho-mqtt < 2.0 has no timeout argument; do not risk blocking shutdown
            except (RuntimeError, ValueError) as e:
                logger.warning(f"OFFLINE health not confirmed: {e}")
        self._client.disconnect()
        self._client.loop_stop()
