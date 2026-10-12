"""
EdgeFlow AI — Canonical MQTT Topics & Channels Contract.

Single Source of Truth for all MQTT topics used across services:
- Telemetry streams
- Control commands & acknowledgments
- Health heartbeats & diagnostics
"""

# Base prefixes
PREFIX_V1 = "edgeflow/v1"

# Telemetry
TELEMETRY_PUB_PATTERN = f"{PREFIX_V1}/telemetry/{{node_id}}"
TELEMETRY_SUB_PATTERN = f"{PREFIX_V1}/telemetry/+"

# Control Commands (Graph-Control -> Actuator)
COMMAND_PUB_PATTERN = f"{PREFIX_V1}/control/{{node_id}}/command"
COMMAND_SUB_PATTERN = f"{PREFIX_V1}/control/+/command"

# Control ACKs (Actuator -> Simulator/System)
ACK_PUB_PATTERN = f"{PREFIX_V1}/control/{{node_id}}/ack"
ACK_SUB_PATTERN = f"{PREFIX_V1}/control/+/ack"

# Health & Diagnostics
HEALTH_PUB_PATTERN = f"{PREFIX_V1}/health/{{service_name}}"
HEALTH_SUB_PATTERN = f"{PREFIX_V1}/health/+"

# Wildcard all EdgeFlow topics
ALL_EDGEFLOW_SUB = f"{PREFIX_V1}/#"


def get_telemetry_topic(node_id: str) -> str:
    return TELEMETRY_PUB_PATTERN.format(node_id=node_id)


def get_command_topic(node_id: str) -> str:
    return COMMAND_PUB_PATTERN.format(node_id=node_id)


def get_ack_topic(node_id: str) -> str:
    return ACK_PUB_PATTERN.format(node_id=node_id)


def get_health_topic(service_name: str) -> str:
    return HEALTH_PUB_PATTERN.format(service_name=service_name)
