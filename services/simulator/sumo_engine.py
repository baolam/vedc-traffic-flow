import os
import time
import logging
from typing import Dict, Any, List

# ================================================================
# SUMO Metric Definitions (P0 TASK 5):
#
# queue_vehicles   = getLastStepHaltingNumber (vehicles speed < 0.1 m/s)
# flow_veh_per_s   = getLastStepVehicleNumber / step_interval (approx veh/s at 1s steps)
# occupancy_ratio  = getLastStepOccupancy / 100 (SUMO returns 0-100, we normalize to 0-1)
# mean_speed_mps   = getLastStepMeanSpeed (m/s, -1 if no vehicles -> default 13.89)
# ================================================================

logger = logging.getLogger("sumo_engine")

try:
    import traci
    import sumolib
    TRACI_AVAILABLE = True
except ImportError:
    traci = None
    sumolib = None
    TRACI_AVAILABLE = False


class SumoTrafficEngine:
    """
    Traffic Engine backed by real SUMO simulation via TraCI.
    """
    def __init__(self, topology: Dict[str, Any], config_path: str = None):
        if not TRACI_AVAILABLE:
            raise RuntimeError("TraCI library is not available. Install 'traci' and SUMO to use SumoTrafficEngine.")

        self.topology = topology
        if config_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            topology_id = topology.get("topology_id", "four_intersection_v1")
            candidate1 = os.path.join(base_dir, "sumo_configs", topology_id, f"{topology_id}.sumocfg")
            candidate2 = os.path.join(base_dir, "sumo_configs", f"{topology_id}.sumocfg")
            config_path = candidate1 if os.path.exists(candidate1) else candidate2

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"SUMO config file not found: {config_path}")

        self.config_path = config_path
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.traffic_light_ids: set = set()
        self.edge_ids: set = set()
        self.is_connected = False
        self._init_nodes()
        self._start_sumo()

    def _init_nodes(self):
        for node in self.topology.get("nodes", []):
            node_id = node["node_id"]
            approaches = node.get("approaches", [])
            phases = node.get("phases", [])
            self.nodes[node_id] = {
                "approaches": approaches,
                "phases": phases,
                "current_phase_id": phases[0]["phase_id"] if phases else "J1_PHASE_NS"
            }

    def _start_sumo(self):
        nod_file = self.config_path.replace(".sumocfg", ".nod.xml")
        edg_file = self.config_path.replace(".sumocfg", ".edg.xml")
        net_file = self.config_path.replace(".sumocfg", ".net.xml")
        if os.path.exists(nod_file) and os.path.exists(edg_file) and not os.path.exists(net_file):
            try:
                import subprocess
                logger.info(f"Running SUMO netconvert for {nod_file} and {edg_file}...")
                subprocess.run(["netconvert", "--node-files", nod_file, "--edge-files", edg_file, "-o", net_file, "--no-turnarounds", "true"], check=True)
            except Exception as ne:
                logger.warning(f"netconvert step skipped: {ne}")

        sumo_binary = os.getenv("SUMO_BINARY", "sumo")
        cmd = [
            sumo_binary,
            "-c", self.config_path,
            "--no-step-log", "true",
            "--waiting-time-memory", "1000"
        ]
        logger.info(f"Starting SUMO simulation with command: {' '.join(cmd)}")
        try:
            traci.start(cmd)
            self.is_connected = True
            try:
                self.traffic_light_ids = set(traci.trafficlight.getIDList())
                self.edge_ids = set(traci.edge.getIDList())
                logger.info(f"SUMO connected. Active traffic lights: {len(self.traffic_light_ids)}, active edges: {len(self.edge_ids)}")
            except Exception as e:
                logger.warning(f"Could not query TraCI trafficlight/edge IDs: {e}")
        except Exception as err:
            logger.error(f"traci.start failed: {err}")
            import subprocess
            res = subprocess.run(cmd, capture_output=True, text=True)
            logger.error(f"SUMO exit code: {res.returncode}")
            logger.error(f"SUMO stdout: {res.stdout}")
            logger.error(f"SUMO stderr: {res.stderr}")
            raise err

    def step(self, dt_s: float = 1.0):
        if not self.is_connected:
            return
        steps = max(1, int(round(dt_s)))
        for _ in range(steps):
            traci.simulationStep()

    def update_node_phase(self, node_id: str, phase_id: str):
        if node_id not in self.nodes:
            return
        self.nodes[node_id]["current_phase_id"] = phase_id
        if not self.is_connected:
            return

        if node_id not in self.traffic_light_ids:
            logger.debug(f"Node {node_id} is not a SUMO traffic light; skipping SUMO setPhase.")
            return

        # Map canonical phase_id dynamically to SUMO traffic light phase index
        phase_list = self.nodes[node_id].get("phases", [])
        matched_phase = next((p for p in phase_list if p.get("phase_id") == phase_id), None)

        if matched_phase and "sumo_phase_index" in matched_phase:
            phase_index = int(matched_phase["sumo_phase_index"])
        else:
            canonical_indices = [idx for idx, p in enumerate(phase_list) if p.get("phase_id") == phase_id]
            if canonical_indices:
                idx = canonical_indices[0]
                phase_index = idx * 2
            elif "EW" in phase_id.upper():
                phase_index = 2
            else:
                phase_index = 0

        try:
            traci.trafficlight.setPhase(node_id, phase_index)
            logger.info(f"SUMO set traffic light phase for node {node_id} to index {phase_index} ({phase_id})")
        except Exception as e:
            logger.warning(f"Could not set SUMO traffic light phase for {node_id}: {e}")

    def generate_telemetry(self, node_id: str, sim_time_s: float) -> Dict[str, Any]:
        if node_id not in self.nodes:
            raise ValueError(f"Unknown node_id: {node_id}")

        node_data = self.nodes[node_id]
        approaches_telemetry = []

        for app_id in node_data["approaches"]:
            edge_id = app_id  # approach_id corresponds directly to edge_id in SUMO net
            queue_vehicles = 0.0
            mean_speed_mps = 13.89
            occupancy_ratio = 0.0
            flow_veh_per_s = 0.0

            if self.is_connected and (not self.edge_ids or edge_id in self.edge_ids):
                try:
                    halting_vehicles = traci.edge.getLastStepHaltingNumber(edge_id)
                    speed = traci.edge.getLastStepMeanSpeed(edge_id)
                    raw_occ = traci.edge.getLastStepOccupancy(edge_id)  # May be 0-100% or 0-1
                    vehicle_count = traci.edge.getLastStepVehicleNumber(edge_id)

                    queue_vehicles = float(halting_vehicles)
                    mean_speed_mps = round(float(speed) if speed >= 0 else 13.89, 2)
                    
                    # TraCI returns occupancy as percentage 0..100% -> normalize to ratio [0.0, 1.0]
                    occupancy_ratio = round(min(1.0, max(0.0, float(raw_occ) / 100.0)), 3)
                    # Flow rate (veh/s)
                    lane0 = f"{edge_id}_0"
                    edge_len = max(1.0, float(traci.lane.getLength(lane0)) if (lane0 in traci.lane.getIDList()) else 50.0)
                    moving_veh = max(0, int(vehicle_count) - int(halting_vehicles))
                    calc_flow = (moving_veh * (float(speed) if speed >= 0 else 0.0)) / edge_len
                    flow_veh_per_s = round(float(calc_flow), 4)
                except Exception as e:
                    logger.debug(f"TraCI query fallback for edge {edge_id}: {e}")

            approaches_telemetry.append({
                "approach_id": app_id,
                "queue_vehicles": round(queue_vehicles, 1),
                "flow_veh_per_s": flow_veh_per_s,
                "mean_speed_mps": mean_speed_mps,
                "occupancy_ratio": occupancy_ratio,
                "confidence": 1.0
            })

        sim_ts = round(sim_time_s, 2)
        return {
            "node_id": node_id,
            "source_type": "simulation",
            "simulation_time_s": sim_ts,
            "timestamp_ms": int(time.time() * 1000),
            "current_phase_id": node_data["current_phase_id"],
            "approaches": approaches_telemetry
        }

    def close(self):
        if self.is_connected and traci is not None:
            try:
                traci.close()
            except Exception:
                pass
            self.is_connected = False
