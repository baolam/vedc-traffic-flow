"""Canonical MQTT routing compatibility shim, delegating to contracts.topics.
This preserves backwards compatibility for any module importing from contracts.protocol.
"""
from contracts.topics import (
    TELEMETRY_FILTER,
    ACK_FILTER,
    COMMAND_FILTER,
    HEALTH_FILTER,
    topic,
    client_id,
)

__all__ = [
    "TELEMETRY_FILTER",
    "ACK_FILTER",
    "COMMAND_FILTER",
    "HEALTH_FILTER",
    "topic",
    "client_id",
]
