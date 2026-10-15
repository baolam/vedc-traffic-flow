"""Transport-independent single-coordinator gate. No global lease/takeover claims.

Static ownership is checked on every decision; deployments must run exactly one
coordinator for the supplied demo profile. Duplicate deployments on other hosts
are not arbitrated by MQTT: distributed mode is intentionally disabled.
"""
import copy
from contracts.contracts_sdk import validate_payload
from contracts.protocol import topic


class ControlGateway:
    def __init__(self, controller, topology, controller_id="demo-central",
                 owned_node_ids=None, owners=None, state_max_age_ms=3000, command_ttl_ms=3000):
        self.controller, self.topology = controller, topology
        self.controller_id = controller_id
        nodes = {n["node_id"] for n in topology["nodes"]}
        self.owned = set(owned_node_ids if owned_node_ids is not None else nodes)
        if not self.owned <= nodes:
            raise ValueError("Owned nodes outside topology")
        self.owners = owners or {n: controller_id for n in nodes}
        if any(self.owners.get(n) != controller_id for n in self.owned):
            raise ValueError("Ownership conflict")
        self.max_age, self.ttl = state_max_age_ms, command_ttl_ms
        self.state, self.received, self.health, self.health_received = {}, {}, {}, {}

    def ingest_health(self, payload, now_ms):
        validate_payload(payload, "health")
        node = payload["node_id"]
        self.health[node] = copy.deepcopy(payload)
        self.health_received[node] = now_ms
        if payload.get("service") == "esp32_actuator" and (
                payload.get("status") not in ("HEALTHY", "FALLBACK_AUTONOMOUS")
                or payload.get("safe_stop") or payload.get("clearance") != "GREEN"):
            # A protected/clearing receiver must not remain an apparently
            # available neighbor in a previously cached camera observation.
            self.state.pop(node, None)
            self.received.pop(node, None)

    def decision(self, payload, now_ms, mqtt_topic=None):
        validate_payload(payload, "telemetry")
        node = payload["node_id"]
        if mqtt_topic is not None and mqtt_topic != topic("telemetry", node):
            raise ValueError("Topic/payload node mismatch")
        spec = next((n for n in self.topology["nodes"] if n["node_id"] == node), None)
        if spec is None or {a["approach_id"] for a in payload["approaches"]} != set(spec["approaches"]):
            raise ValueError("Node/approaches do not match topology")
        stamp = payload.get("timestamp_ms", now_ms)
        if stamp > now_ms + 1000 or now_ms - stamp > self.max_age:
            return None
        if stamp < self.state.get(node, {}).get("timestamp_ms", -1):
            return None
        payload = copy.deepcopy(payload)
        device = self.health.get(node, {})
        if device.get("service") == "esp32_actuator" and (
                device.get("status") not in ("HEALTHY", "FALLBACK_AUTONOMOUS")
                or device.get("safe_stop") or device.get("clearance") != "GREEN"):
            return None
        if payload.get("source_type") == "vision":
            # A camera cannot observe the actuator phase. Use recent ESP32 health.
            health = self.health.get(node, {})
            if (now_ms - self.health_received.get(node, -self.max_age * 10) > 6000
                    or health.get("service") != "esp32_actuator"
                    or health.get("status") not in ("HEALTHY", "FALLBACK_AUTONOMOUS")
                    or health.get("clearance") != "GREEN"):
                return None
            payload["current_phase_id"] = health.get("current_phase", health.get("current_phase_id"))
            payload.pop("simulation_time_s", None)
        if payload["current_phase_id"] not in {p["phase_id"] for p in spec["phases"]}:
            return None
        self.state[node], self.received[node] = payload, now_ms
        if node not in self.owned or self.owners.get(node) != self.controller_id:
            return None
        if payload["approaches"] and all(a.get("confidence", 1) <= 0 for a in payload["approaches"]):
            return None
        fresh = {n: p for n, p in self.state.items() if now_ms - self.received[n] <= self.max_age}
        fresh = {n: p for n, p in fresh.items() if p.get("source_type") != "vision"
                 or now_ms - self.health_received.get(n, -60000) <= 6000}
        # Missing downstream state must not be interpreted as an empty road.
        neighbors = {m.get("to_node") for p in spec["phases"] for m in p.get("movements", []) if m.get("to_node")}
        if not neighbors <= fresh.keys():
            return None
        cmd = self.controller.compute_command(node_id=node, telemetry=payload,
                                              topology=self.topology, network_state=fresh)
        if cmd:
            cmd.update(timestamp_ms=now_ms, expires_at_ms=now_ms + self.ttl,
                       controller_id=self.controller_id)
            validate_payload(cmd, "control_command")
        return cmd
