"""Canonical MQTT routing; publishers/subscribers share these definitions."""
import os
import socket
import uuid

TELEMETRY_FILTER = "edgeflow/v1/telemetry/+"
ACK_FILTER = "edgeflow/v1/control/+/ack"
HEALTH_FILTER = "edgeflow/v1/health/+"


def topic(kind, node_id):
    if not node_id or any(c in node_id for c in "/+#"):
        raise ValueError("Invalid MQTT node_id")
    if kind in ("command", "ack"):
        return f"edgeflow/v1/control/{node_id}/{kind}"
    if kind in ("telemetry", "health"):
        return f"edgeflow/v1/{kind}/{node_id}"
    raise ValueError("Unknown message kind")


def client_id(role):
    return f"{role}-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
