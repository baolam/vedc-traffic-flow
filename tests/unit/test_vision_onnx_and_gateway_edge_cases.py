import time
import pytest
import numpy as np
from pathlib import Path
from contracts.contracts_sdk import load_topology, validate_payload
from contracts.topics import topic
from src.control.gateway import ControlGateway
from src.control.controllers import FixedTimeController
from services.vision.config import settings
from services.vision.detector import VehicleDetector


class TestRealYOLOv8nONNX:
    def test_model_file_exists_and_sha256(self):
        model_path = Path(settings.detection_model_path)
        assert model_path.is_file(), f"Model file not found at {model_path}"
        assert model_path.stat().st_size > 10_000_000, "ONNX model file is suspiciously small"

    def test_detector_inference_on_synthetic_frame(self):
        detector = VehicleDetector(
            model_path=settings.detection_model_path,
            conf_threshold=0.25,
            input_size=640
        )
        assert detector.backend == "opencv_dnn"
        assert detector.model_sha256 is not None

        # Create synthetic 3-channel BGR image
        frame = np.full((480, 640, 3), 120, dtype=np.uint8)
        # Draw a synthetic rectangle simulating a vehicle
        frame[150:250, 200:350] = (40, 40, 200)

        boxes, latency_ms = detector.detect(frame)
        assert isinstance(boxes, list)
        assert isinstance(latency_ms, float)
        assert latency_ms > 0

        # Check timings recorded
        assert "preprocess_ms" in detector.last_timings
        assert "inference_ms" in detector.last_timings
        assert "postprocess_ms" in detector.last_timings
        assert "total_ms" in detector.last_timings



class TestControlGatewayEdgeCases:
    @pytest.fixture
    def setup_gateway(self):
        topology = load_topology("tabletop_j1_j2_v1")
        controller = FixedTimeController(cycle_time_s=60.0)
        gw = ControlGateway(
            controller=controller,
            topology=topology,
            controller_id="coord-alpha",
            state_max_age_ms=3000,
            command_ttl_ms=4000
        )
        return gw, topology

    def _sample_telemetry(self, node_id, timestamp_ms, phase_id="J1_PHASE_NS", confidence=0.85):
        return {
            "node_id": node_id,
            "source_type": "vision",
            "timestamp_ms": timestamp_ms,
            "current_phase_id": phase_id,
            "approaches": [
                {"approach_id": f"{node_id}_N_IN", "queue_vehicles": 2.0, "confidence": confidence,
                 "flow_veh_per_s": 0.1, "mean_speed_mps": 4.0, "occupancy_ratio": 0.1},
                {"approach_id": f"{node_id}_S_IN", "queue_vehicles": 1.0, "confidence": confidence,
                 "flow_veh_per_s": 0.1, "mean_speed_mps": 4.0, "occupancy_ratio": 0.05},
                {"approach_id": f"{node_id}_E_IN", "queue_vehicles": 0.0, "confidence": confidence,
                 "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0},
                {"approach_id": f"{node_id}_W_IN", "queue_vehicles": 3.0, "confidence": confidence,
                 "flow_veh_per_s": 0.2, "mean_speed_mps": 3.5, "occupancy_ratio": 0.12},
            ]
        }

    def _healthy_actuator(self, node_id, timestamp_ms, phase="J1_PHASE_NS"):
        return {
            "service": "esp32_actuator",
            "node_id": node_id,
            "status": "HEALTHY",
            "current_phase": phase,
            "clearance": "GREEN",
            "safe_stop": False,
            "timestamp_ms": timestamp_ms
        }

    def test_reject_topic_mismatch(self, setup_gateway):
        gw, _ = setup_gateway
        now_ms = 100000
        telemetry = self._sample_telemetry("J1", now_ms)
        # Pass a mismatched topic (e.g. topic for J2 when payload is for J1)
        with pytest.raises(ValueError, match="Topic/payload node mismatch"):
            gw.decision(telemetry, now_ms=now_ms, mqtt_topic=topic("telemetry", "J2"))

    def test_reject_expired_telemetry(self, setup_gateway):
        gw, _ = setup_gateway
        now_ms = 100000
        gw.ingest_health(self._healthy_actuator("J1", now_ms), now_ms)
        gw.ingest_health(self._healthy_actuator("J2", now_ms, "J2_PHASE_NS"), now_ms)

        # Telemetry is older than state_max_age_ms (3000ms)
        old_stamp = now_ms - 5000
        telemetry = self._sample_telemetry("J1", old_stamp)
        assert gw.decision(telemetry, now_ms=now_ms) is None

    def test_reject_future_telemetry(self, setup_gateway):
        gw, _ = setup_gateway
        now_ms = 100000
        # Telemetry from far future (> now_ms + 1000)
        future_stamp = now_ms + 2500
        telemetry = self._sample_telemetry("J1", future_stamp)
        assert gw.decision(telemetry, now_ms=now_ms) is None

    def test_reject_out_of_order_telemetry(self, setup_gateway):
        gw, _ = setup_gateway
        now_ms = 100000
        gw.ingest_health(self._healthy_actuator("J1", now_ms), now_ms)
        gw.ingest_health(self._healthy_actuator("J2", now_ms, "J2_PHASE_NS"), now_ms)

        gw.decision(self._sample_telemetry("J2", now_ms, "J2_PHASE_NS"), now_ms)
        # Advance J1 to timestamp 100000
        gw.decision(self._sample_telemetry("J1", now_ms), now_ms)

        # Arriving packet with earlier timestamp 99000
        assert gw.decision(self._sample_telemetry("J1", 99000), now_ms=now_ms) is None

    def test_reject_all_zero_confidence(self, setup_gateway):
        gw, _ = setup_gateway
        now_ms = 100000
        gw.ingest_health(self._healthy_actuator("J1", now_ms), now_ms)
        gw.ingest_health(self._healthy_actuator("J2", now_ms, "J2_PHASE_NS"), now_ms)
        gw.decision(self._sample_telemetry("J2", now_ms, "J2_PHASE_NS"), now_ms)

        zero_conf_telem = self._sample_telemetry("J1", now_ms, confidence=0.0)
        assert gw.decision(zero_conf_telem, now_ms=now_ms) is None

    def test_actuator_safe_stop_evicts_cache(self, setup_gateway):
        gw, _ = setup_gateway
        now_ms = 100000
        # J1 is healthy and cached
        gw.ingest_health(self._healthy_actuator("J1", now_ms), now_ms)
        assert "J1" in gw.health

        # Emergency safe stop triggered on J1
        safe_stop_payload = {
            "service": "esp32_actuator",
            "node_id": "J1",
            "status": "FALLBACK_AUTONOMOUS",
            "safe_stop": True,
            "clearance": "RED",
            "timestamp_ms": now_ms + 100
        }
        gw.ingest_health(safe_stop_payload, now_ms + 100)
        assert "J1" not in gw.state

    def test_valid_command_structure_and_ttl(self, setup_gateway):
        gw, _ = setup_gateway
        now_ms = 100000
        gw.ingest_health(self._healthy_actuator("J1", now_ms, "J1_PHASE_NS"), now_ms)
        gw.ingest_health(self._healthy_actuator("J2", now_ms, "J2_PHASE_NS"), now_ms)

        gw.decision(self._sample_telemetry("J2", now_ms, "J2_PHASE_NS"), now_ms)
        cmd = gw.decision(self._sample_telemetry("J1", now_ms, "J1_PHASE_NS"), now_ms)

        assert cmd is not None
        assert cmd["node_id"] == "J1"
        assert cmd["controller_id"] == "coord-alpha"
        assert cmd["timestamp_ms"] == now_ms
        assert cmd["expires_at_ms"] == now_ms + 4000  # ttl = 4000
        validate_payload(cmd, "control_command")
