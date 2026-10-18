"""
EdgeFlow AI - shared helpers for the Raspberry Pi <-> ESP32 MQTT demo tools.

Only needs paho-mqtt and jsonschema, so it runs in the minimal Pi venv (infra/rpi/setup_pi.sh).
Topics and schemas come from contracts/ (single source of truth); nothing is redefined here.
"""

import json
import os
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

HEALTH_VISION = "vision"


@dataclass(frozen=True)
class Timing:
    """Safety timings of the ESP32 firmware (esp32_signal_controller.ino), in seconds.
    scaled() shrinks them so tests against the simulator take a second instead of a minute."""
    yellow_s: float = 3.0
    all_red_s: float = 2.0
    min_green_s: float = 5.0
    max_green_s: float = 60.0
    watchdog_s: float = 5.0
    fallback_green_s: float = 15.0
    health_period_s: float = 5.0
    keepalive_s: float = 2.0   # how often a test tool must send a command to stay under the watchdog

    @property
    def clearance_s(self) -> float:
        return self.yellow_s + self.all_red_s

    def scaled(self, factor: float) -> "Timing":
        return replace(self, **{k: v * factor for k, v in self.__dict__.items()})


def _find_contracts_dir() -> Path:
    env_dir = os.getenv("CONTRACTS_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "contracts" / "schemas").is_dir():
            return parent / "contracts"
    raise FileNotFoundError("contracts/ not found: run from the repo or set CONTRACTS_DIR")


CONTRACTS_DIR = _find_contracts_dir()
if str(CONTRACTS_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_DIR))

import contracts_sdk  # noqa: E402
import topics  # noqa: E402,F401  (re-exported: callers use mc.topics)


def now_ms() -> int:
    return int(time.time() * 1000)


def validate(payload: Dict[str, Any], schema_name: str) -> None:
    """Raise jsonschema.ValidationError when the payload breaks the contract."""
    contracts_sdk.validate_payload(payload, schema_name)


def load_node(topology_id: str, node_id: str) -> Dict[str, Any]:
    """Topology node dict (approaches, phases); a node that is not in the topology is an error."""
    nodes = {n["node_id"]: n for n in contracts_sdk.load_topology(topology_id).get("nodes", [])}
    if node_id not in nodes:
        raise ValueError(f"Node {node_id} is not in topology '{topology_id}' (has: {', '.join(sorted(nodes))})")
    return nodes[node_id]


def parse_json(payload: bytes) -> Optional[Dict[str, Any]]:
    """Decoded JSON object, or None when the bytes are not a JSON object."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def make_client(client_id: str, will: Optional[Tuple[str, str]] = None):
    """paho client that works with paho-mqtt 1.x and 2.x. will = (topic, payload) -> retained, qos 1."""
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
    except AttributeError:
        client = mqtt.Client(client_id=client_id)
    if will:
        client.will_set(will[0], will[1], qos=1, retain=True)
    return client


def connect(client, host: str, port: int, timeout_s: float = 8.0) -> None:
    """Connect and block until CONNACK; a clear error instead of a silent hang when the broker is down."""
    connected = threading.Event()
    result = {"rc": None}
    previous = client.on_connect

    def on_connect(c, userdata, flags, rc):
        result["rc"] = rc
        if previous:
            previous(c, userdata, flags, rc)
        if rc == 0:
            connected.set()

    client.on_connect = on_connect
    try:
        client.connect(host, port, 30)
    except OSError as e:
        raise ConnectionError(f"Cannot reach MQTT broker {host}:{port} ({e}). Is Mosquitto running and the "
                              "firewall open on 1883?") from e
    client.loop_start()
    if not connected.wait(timeout_s):
        client.loop_stop()
        raise ConnectionError(f"MQTT broker {host}:{port} did not accept the connection (rc={result['rc']})")


def env_host() -> str:
    return os.getenv("MQTT_HOST", "localhost")


def env_port() -> int:
    return int(os.getenv("MQTT_PORT", "1883"))
