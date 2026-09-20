import time
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self):
        self.telemetry_samples: List[Dict[str, Any]] = []
        self.event_logs: List[Dict[str, Any]] = []
        self.start_time_ms: Optional[int] = None
        self.end_time_ms: Optional[int] = None

    def start(self):
        self.start_time_ms = int(time.time() * 1000)
        self.telemetry_samples.clear()
        self.event_logs.clear()
        logger.info("Metrics collector started.")

    def stop(self):
        self.end_time_ms = int(time.time() * 1000)
        logger.info(f"Metrics collector stopped. Total samples: {len(self.telemetry_samples)}, events: {len(self.event_logs)}")

    def on_mqtt_message(self, topic: str, payload_str: str):
        try:
            payload = json.loads(payload_str)
        except Exception as e:
            logger.warning(f"Failed to parse MQTT JSON from topic {topic}: {e}")
            return

        receive_ts = int(time.time() * 1000)

        if "telemetry" in topic:
            self._process_telemetry(payload, receive_ts)
        elif "ack" in topic or "command" in topic or "events" in topic:
            self.event_logs.append({
                "timestamp_ms": receive_ts,
                "topic": topic,
                "event": payload
            })

    def _process_telemetry(self, payload: Dict[str, Any], receive_ts: int):
        node_id = payload.get("node_id", "unknown")
        sim_time = payload.get("simulation_time_s", 0.0)
        current_phase = payload.get("current_phase_id", "unknown")
        approaches = payload.get("approaches", [])

        total_queue = sum(app.get("queue_vehicles", 0) for app in approaches)
        total_flow = sum(app.get("flow_veh_per_s", 0.0) for app in approaches)
        avg_speed = sum(app.get("mean_speed_mps", 0.0) for app in approaches) / max(len(approaches), 1)
        avg_occ = sum(app.get("occupancy_ratio", 0.0) for app in approaches) / max(len(approaches), 1)

        # Estimate waiting vehicles (queue with speed near zero)
        waiting_vehicles = sum(
            app.get("queue_vehicles", 0)
            for app in approaches
            if app.get("mean_speed_mps", 1.0) < 0.5
        )

        sample = {
            "timestamp_ms": receive_ts,
            "node_id": node_id,
            "simulation_time_s": sim_time,
            "current_phase_id": current_phase,
            "queue_vehicles": total_queue,
            "flow_veh_per_s": round(total_flow, 4),
            "mean_speed_mps": round(avg_speed, 2),
            "occupancy_ratio": round(avg_occ, 3),
            "waiting_vehicles": waiting_vehicles,
            "approaches_count": len(approaches)
        }
        self.telemetry_samples.append(sample)

    def compute_summary(self) -> Dict[str, Any]:
        if not self.telemetry_samples:
            return {
                "total_samples": 0,
                "average_waiting_time_s": 0.0,
                "average_queue_veh": 0.0,
                "maximum_queue_veh": 0,
                "throughput_veh_per_s": 0.0,
                "stopped_vehicles": 0,
                "total_events": len(self.event_logs)
            }

        queues = [s["queue_vehicles"] for s in self.telemetry_samples]
        flows = [s["flow_veh_per_s"] for s in self.telemetry_samples]
        waiting_vehs = [s["waiting_vehicles"] for s in self.telemetry_samples]
        speeds = [s["mean_speed_mps"] for s in self.telemetry_samples]

        avg_queue = sum(queues) / len(queues)
        max_queue = max(queues) if queues else 0
        avg_flow = sum(flows) / len(flows)
        
        # Estimate average delay / waiting time based on queue and flow
        # Little's Law approximation: W = L / lambda if flow > 0
        avg_waiting_time = (avg_queue / max(avg_flow, 0.05)) if avg_flow > 0 else (avg_queue * 2.5)

        total_stopped = sum(waiting_vehs)

        duration_s = ((self.end_time_ms or int(time.time() * 1000)) - (self.start_time_ms or int(time.time() * 1000))) / 1000.0
        duration_s = max(duration_s, 1.0)

        return {
            "total_samples": len(self.telemetry_samples),
            "duration_s": round(duration_s, 2),
            "average_waiting_time_s": round(avg_waiting_time, 2),
            "average_queue_veh": round(avg_queue, 2),
            "maximum_queue_veh": max_queue,
            "throughput_veh_per_s": round(avg_flow, 4),
            "stopped_vehicles_sample_sum": total_stopped,
            "mean_network_speed_mps": round(sum(speeds) / len(speeds), 2),
            "total_events": len(self.event_logs)
        }
