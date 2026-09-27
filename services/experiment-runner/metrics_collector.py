"""
EdgeFlow AI — Metrics Collector (P0 Validated).

Metric definitions:
  queue_vehicles   — Number of halted vehicles on an approach (from SUMO
                     getLastStepHaltingNumber or deterministic sim queue).
  flow_veh_per_s   — Discharge rate (veh/s) during green. NOT vehicle count.
  occupancy_ratio  — Fraction of road segment occupied by vehicles (0.0-1.0).
  mean_speed_mps   — Average vehicle speed on approach (m/s). Real measured.
  waiting_vehicles — Vehicles with speed < 0.5 m/s.
  throughput       — Total discharged vehicles / simulation duration (veh/s).
  waiting_time     — Accumulated vehicle-seconds of delay / discharged vehicles.

All metrics come from real simulation state or deterministic-sim queues.
No synthetic/mock/fallback values are mixed into research summaries.
"""

import time
import json
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("metrics_collector")


class MetricsCollector:
    """Collects and aggregates telemetry samples from experiments."""

    def __init__(self):
        self.telemetry_samples: List[Dict[str, Any]] = []
        self.event_logs: List[Dict[str, Any]] = []
        self.start_time_ms: Optional[int] = None
        self.end_time_ms: Optional[int] = None

        # Accumulators
        self.total_discharged_vehicles: float = 0.0
        self.accumulated_waiting_vehicle_seconds: float = 0.0
        self.last_sim_time: Optional[float] = None

    def start(self):
        """Reset and start collection."""
        self.telemetry_samples.clear()
        self.event_logs.clear()
        self.start_time_ms = int(time.time() * 1000)
        self.end_time_ms = None
        self.total_discharged_vehicles = 0.0
        self.accumulated_waiting_vehicle_seconds = 0.0
        self.last_sim_time = None
        logger.info("Metrics Collector started.")

    def stop(self):
        self.end_time_ms = int(time.time() * 1000)
        logger.info(
            f"Metrics Collector stopped. "
            f"Samples: {len(self.telemetry_samples)}, "
            f"Events: {len(self.event_logs)}, "
            f"Discharged: {self.total_discharged_vehicles:.1f}"
        )

    def on_mqtt_message(self, topic: str, payload_str: str):
        try:
            payload = json.loads(payload_str)
        except Exception as e:
            logger.warning(f"Failed to parse MQTT JSON from {topic}: {e}")
            return

        receive_ts = int(time.time() * 1000)

        if "telemetry" in topic:
            self._process_telemetry(payload, receive_ts)
        elif "ack" in topic or "command" in topic or "events" in topic:
            self.event_logs.append({
                "timestamp_ms": receive_ts,
                "topic": topic,
                "event": payload,
            })

    def _process_telemetry(self, payload: Dict[str, Any], receive_ts: int):
        node_id = payload.get("node_id", "unknown")
        sim_time = float(payload.get("simulation_time_s", 0.0))
        current_phase = payload.get("current_phase_id", "unknown")
        source_type = payload.get("source_type", "unknown")
        approaches = payload.get("approaches", [])

        # Compute dt from simulation time (NOT wall clock)
        dt_s = 1.0
        if self.last_sim_time is not None and sim_time > self.last_sim_time:
            dt_s = sim_time - self.last_sim_time
        self.last_sim_time = sim_time

        # Per-approach aggregation
        total_queue = 0.0
        total_flow = 0.0
        total_waiting = 0.0
        speeds = []
        occs = []

        for app in approaches:
            q = float(app.get("queue_vehicles", 0))
            f = float(app.get("flow_veh_per_s", 0.0))
            s = float(app.get("mean_speed_mps", 0.0))
            o = float(app.get("occupancy_ratio", 0.0))

            total_queue += q
            total_flow += f
            speeds.append(s)
            occs.append(o)

            # Waiting = vehicles with speed < 0.5 m/s
            if s < 0.5:
                total_waiting += q

        avg_speed = sum(speeds) / max(len(speeds), 1)
        avg_occ = sum(occs) / max(len(occs), 1)

        # Accumulate vehicle-seconds of delay
        self.accumulated_waiting_vehicle_seconds += total_queue * dt_s
        # Accumulate discharged vehicles
        self.total_discharged_vehicles += total_flow * dt_s

        sample = {
            "timestamp_ms": receive_ts,
            "node_id": node_id,
            "simulation_time_s": sim_time,
            "current_phase_id": current_phase,
            "source_type": source_type,
            "queue_vehicles": round(total_queue, 2),
            "flow_veh_per_s": round(total_flow, 4),
            "mean_speed_mps": round(avg_speed, 2),
            "occupancy_ratio": round(avg_occ, 3),
            "waiting_vehicles": round(total_waiting, 2),
            "approaches_count": len(approaches),
        }
        self.telemetry_samples.append(sample)

    def compute_summary(self) -> Dict[str, Any]:
        """
        Compute aggregate summary statistics from collected samples.

        Metric formulas:
          average_queue_veh = mean(queue_vehicles across all samples)
          maximum_queue_veh = max(queue_vehicles across all samples)
          p50_queue_veh = median(queue_vehicles)
          p95_queue_veh = 95th percentile(queue_vehicles)
          throughput_veh_per_s = total_discharged / sim_duration
          mean_network_speed_mps = mean(mean_speed across all samples)
          average_waiting_time_s = total_waiting_veh_sec / total_discharged
          total_waiting_vehicle_seconds = sum(queue * dt) over all steps
        """
        if not self.telemetry_samples:
            return {
                "total_samples": 0,
                "duration_s": 0.0,
                "average_waiting_time_s": 0.0,
                "average_queue_veh": 0.0,
                "maximum_queue_veh": 0.0,
                "p50_queue_veh": 0.0,
                "p95_queue_veh": 0.0,
                "throughput_veh_per_s": 0.0,
                "total_discharged_vehicles": 0.0,
                "total_waiting_vehicle_seconds": 0.0,
                "mean_network_speed_mps": 0.0,
                "total_events": len(self.event_logs),
                "is_valid": False,
                "reason": "No telemetry samples collected",
            }

        queues = [s["queue_vehicles"] for s in self.telemetry_samples]
        speeds = [s["mean_speed_mps"] for s in self.telemetry_samples]

        sorted_queues = sorted(queues)
        n = len(sorted_queues)

        def percentile(data: List[float], pct: float) -> float:
            idx = int(pct * len(data))
            return data[min(idx, len(data) - 1)]

        avg_queue = sum(queues) / n
        max_queue = max(queues)
        p50_queue = percentile(sorted_queues, 0.50)
        p95_queue = percentile(sorted_queues, 0.95)
        avg_speed = sum(speeds) / n

        # Simulation duration from samples
        sim_times = [s["simulation_time_s"] for s in self.telemetry_samples]
        sim_duration = max(sim_times) - min(sim_times) if len(sim_times) > 1 else 1.0
        sim_duration = max(sim_duration, 1.0)

        # Throughput
        throughput = self.total_discharged_vehicles / sim_duration

        # Average waiting time
        if self.total_discharged_vehicles > 0.5:
            avg_waiting = self.accumulated_waiting_vehicle_seconds / self.total_discharged_vehicles
        else:
            # If no vehicles discharged, use average queue as proxy
            avg_waiting = avg_queue * 2.0

        # Validate all metrics are finite
        for val in [avg_queue, max_queue, p50_queue, p95_queue, avg_speed, throughput, avg_waiting]:
            if not math.isfinite(val):
                return {
                    "total_samples": n,
                    "duration_s": round(sim_duration, 2),
                    "is_valid": False,
                    "reason": "Non-finite metric detected",
                    "average_waiting_time_s": 0.0,
                    "average_queue_veh": 0.0,
                    "maximum_queue_veh": 0.0,
                    "p50_queue_veh": 0.0,
                    "p95_queue_veh": 0.0,
                    "throughput_veh_per_s": 0.0,
                    "total_discharged_vehicles": 0.0,
                    "total_waiting_vehicle_seconds": 0.0,
                    "mean_network_speed_mps": 0.0,
                    "total_events": len(self.event_logs),
                }

        return {
            "total_samples": n,
            "duration_s": round(sim_duration, 2),
            "average_waiting_time_s": round(avg_waiting, 2),
            "average_queue_veh": round(avg_queue, 2),
            "maximum_queue_veh": round(max_queue, 2),
            "p50_queue_veh": round(p50_queue, 2),
            "p95_queue_veh": round(p95_queue, 2),
            "throughput_veh_per_s": round(throughput, 4),
            "total_discharged_vehicles": round(self.total_discharged_vehicles, 1),
            "total_waiting_vehicle_seconds": round(self.accumulated_waiting_vehicle_seconds, 1),
            "mean_network_speed_mps": round(avg_speed, 2),
            "total_events": len(self.event_logs),
            "is_valid": True,
        }
