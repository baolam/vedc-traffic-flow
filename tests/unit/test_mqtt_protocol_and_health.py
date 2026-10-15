import pytest
import jsonschema
from contracts.contracts_sdk import load_schema, validate_payload, load_topology
import contracts.topics as topics
import contracts.protocol as protocol


class TestMQTTTopicsAndProtocol:
    def test_topic_valid_kinds(self):
        assert topics.topic("telemetry", "J1") == "edgeflow/v1/telemetry/J1"
        assert topics.topic("command", "J1") == "edgeflow/v1/control/J1/command"
        assert topics.topic("ack", "J1") == "edgeflow/v1/control/J1/ack"
        assert topics.topic("health", "vision") == "edgeflow/v1/health/vision"

    def test_topic_invalid_kind(self):
        with pytest.raises(ValueError, match="Unknown message kind"):
            topics.topic("invalid_kind", "J1")

    def test_topic_invalid_node_ids(self):
        # Empty or None
        with pytest.raises(ValueError, match="Invalid MQTT node_id"):
            topics.topic("telemetry", "")
        with pytest.raises(ValueError, match="Invalid MQTT node_id"):
            topics.topic("telemetry", None)

        # Illegal MQTT wildcard characters in node_id
        for illegal in ("node/1", "node+1", "node#1"):
            with pytest.raises(ValueError, match="Invalid MQTT node_id"):
                topics.topic("telemetry", illegal)

    def test_client_id_generation(self):
        cid1 = topics.client_id("gateway")
        cid2 = topics.client_id("gateway")
        assert cid1.startswith("gateway-")
        assert cid2.startswith("gateway-")
        # Ensure UUID suffix guarantees uniqueness
        assert cid1 != cid2

    def test_protocol_shim_equivalence(self):
        assert protocol.TELEMETRY_FILTER == topics.TELEMETRY_FILTER
        assert protocol.ACK_FILTER == topics.ACK_FILTER
        assert protocol.COMMAND_FILTER == topics.COMMAND_FILTER
        assert protocol.HEALTH_FILTER == topics.HEALTH_FILTER
        assert protocol.topic("telemetry", "J1") == topics.topic("telemetry", "J1")
        assert protocol.client_id("test").startswith("test-")


class TestHealthSchema:
    def test_valid_health_payloads(self):
        # Actuator health
        actuator_health = {
            "service": "esp32_actuator",
            "status": "HEALTHY",
            "node_id": "J1",
            "current_phase": "J1_PHASE_NS",
            "clearance": "GREEN",
            "safe_stop": False,
            "timestamp_ms": 1700000000000
        }
        validate_payload(actuator_health, "health")

        # Vision service health
        vision_health = {
            "service": "vision",
            "status": "HEALTHY",
            "device": "raspberry_pi_5",
            "cpu_temp_c": 48.5,
            "backend": "opencv_dnn",
            "active_nodes": ["J1", "J2"],
            "model_sha256": "7529cf4f3ef9858d",
            "timestamp_ms": 1700000000000
        }
        validate_payload(vision_health, "health")

    def test_invalid_health_payload_missing_required(self):
        # Missing 'status'
        with pytest.raises(jsonschema.ValidationError):
            validate_payload({"service": "vision"}, "health")

        # Missing 'service'
        with pytest.raises(jsonschema.ValidationError):
            validate_payload({"status": "HEALTHY"}, "health")

    def test_health_schema_structure(self):
        schema = load_schema("health")
        assert schema["title"] == "Health"
        assert "service" in schema["properties"]
        assert "status" in schema["properties"]
        assert set(schema["required"]) == {"service", "status"}


class TestTabletopTopologyContract:
    def test_tabletop_aliases_load(self):
        topo_canonical = load_topology("tabletop_j1_j2_v1")
        topo_alias1 = load_topology("tabletop")
        topo_alias2 = load_topology("tabletop_v1")

        assert topo_canonical["topology_id"] == "tabletop_j1_j2_v1"
        assert topo_alias1["topology_id"] == "tabletop_j1_j2_v1"
        assert topo_alias2["topology_id"] == "tabletop_j1_j2_v1"

    def test_tabletop_graph_invariants(self):
        topo = load_topology("tabletop")
        node_ids = {n["node_id"] for n in topo["nodes"]}
        assert node_ids == {"J1", "J2"}

        # Edge checks
        edges = topo["edges"]
        assert any(e["edge_id"] == "E_J1_J2_EB" and e["source"] == "J1" and e["target"] == "J2" for e in edges)
        assert any(e["edge_id"] == "E_J2_J1_WB" and e["source"] == "J2" and e["target"] == "J1" for e in edges)

        # Cross-node movement checks: J1 East-West movement connects to J2 West In
        j1 = next(n for n in topo["nodes"] if n["node_id"] == "J1")
        ew_phase = next(p for p in j1["phases"] if p["phase_id"] == "J1_PHASE_EW")
        inter_move = next(m for m in ew_phase["movements"] if m.get("to_node") == "J2")
        assert inter_move["to_edge"] == "E_J1_J2_EB"
        assert inter_move["to_approach"] == "J2_W_IN"
