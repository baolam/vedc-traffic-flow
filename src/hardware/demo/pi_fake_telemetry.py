"""
EdgeFlow AI - fake vision telemetry from the Raspberry Pi (MQTT demo / test tool).

Publishes schema-valid telemetry for the chosen nodes with a scripted traffic scenario, so the
laptop (graph-control, dashboard) and the ESP32 can be tested before the camera and YOLO model are
ready. It does NOT replace services/vision: the data is invented and says so in the retained health
message (`"mode": "FAKE_DATA"`). It refuses to start while a real vision service is HEALTHY.

  python src/hardware/demo/pi_fake_telemetry.py --mqtt-host 192.168.1.100 --scenario ns_heavy
  python src/hardware/demo/pi_fake_telemetry.py --dry-run --duration 3        # no broker needed

Like the real service, current_phase_id follows the phase each ESP32 reports on
edgeflow/v1/health/{node}; until a fresh report exists it uses the node's first phase.
"""

import argparse
import json
import logging
import os
import random
import signal
import sys
import threading
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also with `python -I` or another cwd
import mqtt_common as mc  # noqa: E402

logger = logging.getLogger("pi-fake-telemetry")

SCENARIOS = ("ns_heavy", "ew_heavy", "balanced", "alternate", "ramp", "camera_lost")
ALTERNATE_PERIOD_S = 60.0      # alternate: heavy side flips every minute
RAMP_PERIOD_S = 120.0          # ramp: NS queue grows from 0 to RAMP_MAX over this time, then restarts
RAMP_MAX_VEHICLES = 15.0
HEAVY_QUEUE, LIGHT_QUEUE, BALANCED_QUEUE = 12.0, 2.0, 6.0
OCCUPANCY_PER_VEHICLE = 0.05   # share of the lane area one queued vehicle covers
PHASE_STALE_S = 15.0           # same freshness rule as the real vision service (ESP32 reports every 5 s)
CONFLICT_STATUSES = ("STARTING", "HEALTHY", "DEGRADED")
OFFLINE_PAYLOAD = json.dumps({"service": "vision", "status": "OFFLINE", "mode": "FAKE_DATA"})


def approach_axis(approach_id: str) -> str:
    """'NS' for ..._N_IN / ..._S_IN, 'EW' for ..._E_IN / ..._W_IN."""
    direction = approach_id.rsplit("_", 2)[-2] if approach_id.count("_") >= 2 else ""
    if direction in ("N", "S"):
        return "NS"
    if direction in ("E", "W"):
        return "EW"
    raise ValueError(f"Cannot tell the direction of approach '{approach_id}'")


def target_queue(scenario: str, axis: str, elapsed_s: float) -> float:
    """Noise-free queue (vehicles) the scenario wants on one axis at a time since start."""
    if scenario == "ns_heavy":
        return HEAVY_QUEUE if axis == "NS" else LIGHT_QUEUE
    if scenario == "ew_heavy":
        return HEAVY_QUEUE if axis == "EW" else LIGHT_QUEUE
    if scenario == "balanced":
        return BALANCED_QUEUE
    if scenario == "alternate":
        ns_turn = int(elapsed_s // ALTERNATE_PERIOD_S) % 2 == 0
        return HEAVY_QUEUE if (axis == "NS") == ns_turn else LIGHT_QUEUE
    if scenario == "ramp":
        if axis == "EW":
            return LIGHT_QUEUE
        return RAMP_MAX_VEHICLES * ((elapsed_s % RAMP_PERIOD_S) / RAMP_PERIOD_S)
    if scenario == "camera_lost":
        return 0.0
    raise ValueError(f"Unknown scenario '{scenario}' (choose from {', '.join(SCENARIOS)})")


def approach_metrics(approach_id: str, queue: float, confidence: float) -> Dict[str, Any]:
    """Same derived figures as services/vision/metrics_extractor.py, so downstream sees familiar values."""
    occupancy = min(max(queue * OCCUPANCY_PER_VEHICLE, 0.0), 1.0)
    return {
        "approach_id": approach_id,
        "queue_vehicles": float(queue),
        "flow_veh_per_s": round(queue * 0.08, 4),
        "mean_speed_mps": round(min(max(2.5 * (1.0 - occupancy * 0.8), 0.5), 15.0), 2),
        "occupancy_ratio": round(occupancy, 4),
        "confidence": confidence,
    }


def build_fake_telemetry(node: Dict[str, Any], scenario: str, elapsed_s: float, timestamp_ms: int,
                         current_phase_id: Optional[str] = None,
                         rng: Optional[random.Random] = None) -> Dict[str, Any]:
    """One schema-valid telemetry message. camera_lost mimics a dead camera: zero queue, zero confidence."""
    rng = rng or random.Random()
    node_id = node["node_id"]
    lost = scenario == "camera_lost"
    approaches = []
    for approach_id in node["approaches"]:
        queue = target_queue(scenario, approach_axis(approach_id), elapsed_s)
        if not lost:
            queue = max(0.0, round(queue + rng.uniform(-1.0, 1.0)))  # whole vehicles, +-1 jitter
        approaches.append(approach_metrics(approach_id, queue, 0.0 if lost else 1.0))
    phases = node.get("phases", [])
    return {
        "node_id": node_id,
        "source_type": "vision",
        "simulation_time_s": round(elapsed_s, 2),
        "timestamp_ms": timestamp_ms,
        "current_phase_id": current_phase_id or (phases[0]["phase_id"] if phases else f"{node_id}_PHASE_NS"),
        "approaches": approaches,
    }


def build_health(scenario: str, nodes: List[str], timestamp_ms: int, status: str = "HEALTHY") -> Dict[str, Any]:
    return {"service": "vision", "status": status, "mode": "FAKE_DATA", "device": "pi_fake_telemetry",
            "scenario": scenario, "active_nodes": nodes, "timestamp_ms": timestamp_ms}


@dataclass
class PhaseObservation:
    phase_id: str
    seen_at: float


class FakePi:
    """Builds the messages of one publish period; knows nothing about MQTT, so it is easy to test."""

    def __init__(self, nodes: List[Dict[str, Any]], scenario: str, seed: Optional[int] = None):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario '{scenario}' (choose from {', '.join(SCENARIOS)})")
        self.nodes = nodes
        self.scenario = scenario
        self.rng = random.Random(seed)
        self.phases: Dict[str, PhaseObservation] = {}

    @property
    def node_ids(self) -> List[str]:
        return [n["node_id"] for n in self.nodes]

    def observe_health(self, topic: str, payload: bytes, now_s: float) -> None:
        """Remember the phase an ESP32 reports on edgeflow/v1/health/{node}."""
        data = mc.parse_json(payload)
        if not data or data.get("service") != "esp32_actuator":
            return
        node_id, phase = data.get("node_id"), data.get("current_phase")
        if node_id in self.node_ids and isinstance(phase, str) and phase:
            self.phases[node_id] = PhaseObservation(phase, now_s)

    def phase_for(self, node_id: str, now_s: float) -> Tuple[Optional[str], str]:
        """(phase_id, source): the ESP32's phase while fresh, else (None, 'default')."""
        seen = self.phases.get(node_id)
        if seen and now_s - seen.seen_at <= PHASE_STALE_S:
            return seen.phase_id, "esp32_health"
        return None, "default"

    def tick(self, elapsed_s: float, now_s: float, timestamp_ms: int) -> List[Tuple[str, Dict[str, Any]]]:
        """[(topic, payload)] for every node; each payload is validated against the contract."""
        messages = []
        for node in self.nodes:
            phase_id, _ = self.phase_for(node["node_id"], now_s)
            payload = build_fake_telemetry(node, self.scenario, elapsed_s, timestamp_ms, phase_id, self.rng)
            mc.validate(payload, "telemetry")
            messages.append((mc.topics.get_telemetry_topic(node["node_id"]), payload))
        return messages


def real_vision_is_running(client, wait_s: float = 1.5) -> Optional[Dict[str, Any]]:
    """The retained vision health if a real (non-fake) service looks alive, else None."""
    seen: Dict[str, Any] = {}
    done = threading.Event()
    topic = mc.topics.get_health_topic(mc.HEALTH_VISION)

    def on_message(c, userdata, msg):
        data = mc.parse_json(msg.payload)
        if data is not None:
            seen.update(data)
        done.set()

    previous = client.on_message
    client.on_message = on_message
    client.subscribe(topic)
    done.wait(wait_s)
    client.unsubscribe(topic)
    client.on_message = previous
    if seen.get("status") in CONFLICT_STATUSES and seen.get("mode") != "FAKE_DATA":
        return seen
    return None


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publish scripted fake vision telemetry over MQTT")
    p.add_argument("--mqtt-host", default=mc.env_host(), help="broker (env MQTT_HOST, default localhost)")
    p.add_argument("--mqtt-port", type=int, default=mc.env_port(), help="env MQTT_PORT, default 1883")
    p.add_argument("--nodes", default="J1,J2", help="comma-separated node ids (default J1,J2)")
    p.add_argument("--topology", default=os.getenv("EDGEFLOW_TOPOLOGY", "four_intersection_v1"))
    p.add_argument("--scenario", choices=SCENARIOS, default="balanced")
    p.add_argument("--period", type=float, default=1.0, help="seconds between messages (default 1.0)")
    p.add_argument("--duration", type=float, default=0.0, help="stop after N seconds (0 = until Ctrl+C)")
    p.add_argument("--seed", type=int, default=None, help="fix the jitter for repeatable runs")
    p.add_argument("--force", action="store_true", help="publish even if a real vision service is HEALTHY")
    p.add_argument("--dry-run", action="store_true", help="print the messages, do not connect to a broker")
    return p.parse_args(argv)


def run(args: argparse.Namespace, stop: Optional[threading.Event] = None) -> int:
    stop = stop or threading.Event()
    node_ids = [n.strip() for n in args.nodes.split(",") if n.strip()]
    if not node_ids or args.period <= 0:
        logger.error("Need at least one node and a positive --period")
        return 2
    fake = FakePi([mc.load_node(args.topology, n) for n in node_ids], args.scenario, args.seed)

    client = None
    if not args.dry_run:
        health_topic = mc.topics.get_health_topic(mc.HEALTH_VISION)
        # One client id per node set: two fake sources (e.g. J1 camera_lost, J2 normal) must not kick each other
        client = mc.make_client(f"pi-fake-telemetry-{'-'.join(node_ids)}", will=(health_topic, OFFLINE_PAYLOAD))
        client.on_message = lambda c, u, msg: fake.observe_health(msg.topic, msg.payload, time.monotonic())
        try:
            mc.connect(client, args.mqtt_host, args.mqtt_port)
        except ConnectionError as e:
            logger.error(str(e))
            return 1
        real = real_vision_is_running(client)
        if real and not args.force:
            client.loop_stop()
            logger.error("A real vision service is publishing (health %s, device %s): refusing to mix fake data "
                         "into its stream. Stop it, or pass --force.", real.get("status"), real.get("device"))
            return 3
        for node_id in node_ids:  # phase each ESP32 shows, same source as the real service
            client.subscribe(mc.topics.get_health_topic(node_id))
        logger.info("Connected to %s:%s, publishing FAKE telemetry for %s, scenario '%s', every %.1fs",
                    args.mqtt_host, args.mqtt_port, ",".join(node_ids), args.scenario, args.period)

    started = time.monotonic()
    next_tick = started
    try:
        while not stop.is_set():
            elapsed = time.monotonic() - started
            if args.duration and elapsed > args.duration:
                break
            messages = fake.tick(elapsed, time.monotonic(), mc.now_ms())
            for topic, payload in messages:
                total_queue = sum(a["queue_vehicles"] for a in payload["approaches"])
                _, source = fake.phase_for(payload["node_id"], time.monotonic())
                line = (f"[{payload['node_id']}] phase {payload['current_phase_id']} ({source}) | "
                        f"queue {total_queue:.0f} veh | conf {payload['approaches'][0]['confidence']}")
                if client:
                    client.publish(topic, json.dumps(payload))
                    logger.info("-> %s | %s", topic, line)
                else:
                    print(json.dumps(payload))
            if client:
                client.publish(mc.topics.get_health_topic(mc.HEALTH_VISION),
                               json.dumps(build_health(args.scenario, node_ids, mc.now_ms())), qos=1, retain=True)
            next_tick += args.period
            stop.wait(max(next_tick - time.monotonic(), 0.0))
    finally:
        if client:
            # A clean DISCONNECT suppresses the will, so announce OFFLINE explicitly
            info = client.publish(mc.topics.get_health_topic(mc.HEALTH_VISION), OFFLINE_PAYLOAD, qos=1, retain=True)
            try:
                info.wait_for_publish(timeout=2.0)
            except (TypeError, RuntimeError, ValueError):
                pass
            client.disconnect()
            client.loop_stop()
        logger.info("Stopped.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [fake-pi] %(message)s")
    args = parse_args(argv)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    return run(args, stop)


if __name__ == "__main__":
    sys.exit(main())
