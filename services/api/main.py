import os
import json
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

curr_dir = Path(__file__).resolve().parent
if str(curr_dir) not in sys.path:
    sys.path.insert(0, str(curr_dir))

try:
    from config import settings
except ImportError:
    from services.api.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("api-service")

# Add contracts and src to sys.path safely
def _get_contracts_dir() -> Path:
    env_dir = settings.contracts_dir or os.getenv("CONTRACTS_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    if Path("/contracts").exists():
        return Path("/contracts")
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "contracts").is_dir():
            return p / "contracts"
        if (p / "contracts_sdk.py").is_file():
            return p
    return Path("/contracts")

contracts_dir = _get_contracts_dir()
if str(contracts_dir) not in sys.path:
    sys.path.insert(0, str(contracts_dir))

def _get_src_graph_dir() -> Path:
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "src" / "graph").is_dir():
            return p / "src" / "graph"
    return curr / "src" / "graph"

src_graph_dir = _get_src_graph_dir()
if str(src_graph_dir) not in sys.path:
    sys.path.insert(0, str(src_graph_dir))

def _get_artifacts_dir() -> Path:
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "artifacts").is_dir():
            return p / "artifacts"
    return curr / "artifacts"

artifacts_dir = _get_artifacts_dir()

try:
    import contracts_sdk
except ImportError:
    import contracts.contracts_sdk as contracts_sdk

try:
    from sumo_converter import SumoNetworkConverter
except ImportError:
    try:
        from src.graph.sumo_converter import SumoNetworkConverter
    except ImportError:
        SumoNetworkConverter = None

app = FastAPI(
    title="EdgeFlow AI Control Plane & API",
    description="REST API serving live traffic topology, telemetry snapshots, experiment registries, and control policy management.",
    version="1.2.0"
)

# Enable CORS for React Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOPOLOGY_FILE = contracts_sdk.CONTRACTS_DIR / "topology" / "hcm_realworld_v1.json"

def _get_map_html_file() -> Path:
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "output" / "camera_graph_map.html").exists():
            return p / "output" / "camera_graph_map.html"
    return curr / "output" / "camera_graph_map.html"

MAP_HTML_FILE = _get_map_html_file()

# In-memory Live State Store
LIVE_STATE: Dict[str, Any] = {
    "active_topology_id": "four_intersection_v1",
    "active_controller": "edgeflow",
    "last_updated_ms": int(time.time() * 1000),
    "source_mode": "simulation",
    "nodes": {}
}

class PolicyChangeRequest(BaseModel):
    controller: str
    topology_id: Optional[str] = None

DASHBOARD_HTML_FILE = Path(__file__).resolve().parent / "templates" / "dashboard.html"

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """
    Serves the standalone, rich Web Dashboard (Zero React / Zero Docker required).
    """
    if DASHBOARD_HTML_FILE.exists():
        with open(DASHBOARD_HTML_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse("<h2>EdgeFlow AI Dashboard Initializing...</h2>")

@app.get("/api")
def api_root():
    return {
        "service": "edgeflow-api",
        "status": "running",
        "version": "1.2.0",
        "dashboard_ui": "/dashboard",
        "endpoints": [
            "/health",
            "/api/v1/network/state",
            "/api/v1/control/policy",
            "/api/v1/experiments",
            "/api/v1/scenarios",
            "/api/v1/topologies",
            "/api/v1/topologies/{topology_id}",
            "/api/v1/topologies/convert-sumo",
            "/api/v1/cameras",
            "/api/v1/map/hcm-cameras"
        ]
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp_ms": int(time.time() * 1000),
        "active_controller": LIVE_STATE["active_controller"],
        "active_topology": LIVE_STATE["active_topology_id"]
    }

@app.get("/api/v1/network/state")
def get_network_state():
    """
    Returns the real-time live traffic network telemetry and phase states.
    If no live nodes are registered yet, loads topology structure with zero queues.
    """
    try:
        topo = contracts_sdk.load_topology(LIVE_STATE["active_topology_id"])
        nodes_info = []
        for n in topo.get("nodes", []):
            nid = n["node_id"]
            node_live = LIVE_STATE["nodes"].get(nid)
            if node_live:
                nodes_info.append(node_live)
            else:
                # Default clean state reflecting topology without fake data
                phases = n.get("phases", [])
                nodes_info.append({
                    "node_id": nid,
                    "name": n.get("name", nid),
                    "current_phase_id": phases[0]["phase_id"] if phases else f"{nid}_PHASE_NS",
                    "source_type": LIVE_STATE["source_mode"],
                    "status": "ONLINE",
                    "approaches": [
                        {
                            "approach_id": app_id,
                            "queue_vehicles": 0.0,
                            "flow_veh_per_s": 0.0,
                            "mean_speed_mps": 13.89,
                            "occupancy_ratio": 0.0,
                            "confidence": 1.0
                        }
                        for app_id in n.get("approaches", [])
                    ]
                })

        return {
            "topology_id": LIVE_STATE["active_topology_id"],
            "controller": LIVE_STATE["active_controller"],
            "source_mode": LIVE_STATE["source_mode"],
            "last_updated_ms": LIVE_STATE["last_updated_ms"],
            "total_nodes": len(nodes_info),
            "nodes": nodes_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed retrieving network state: {str(e)}")

@app.post("/api/v1/control/policy")
def set_control_policy(req: PolicyChangeRequest):
    """
    Updates the active traffic control policy (fixed_time, max_queue, max_pressure, edgeflow).
    """
    valid_controllers = ["fixed_time", "max_queue", "max_pressure", "edgeflow", "presslight_rl", "rl", "rl_ppo"]
    req_ctrl = req.controller.lower()
    if req_ctrl not in valid_controllers:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid controller: {req_ctrl}. Valid options: {valid_controllers}"
        )

    LIVE_STATE["active_controller"] = req_ctrl
    if req.topology_id:
        LIVE_STATE["active_topology_id"] = req.topology_id
    LIVE_STATE["last_updated_ms"] = int(time.time() * 1000)

    logger.info(f"Control policy updated to: {req_ctrl} (Topology: {LIVE_STATE['active_topology_id']})")
    return {
        "status": "SUCCESS",
        "active_controller": LIVE_STATE["active_controller"],
        "active_topology_id": LIVE_STATE["active_topology_id"],
        "timestamp_ms": LIVE_STATE["last_updated_ms"]
    }

@app.get("/api/v1/experiments")
def list_experiments():
    """
    Scans the artifacts directory and returns metadata summaries of completed experiment runs.
    """
    if not artifacts_dir.exists():
        return {"total_experiments": 0, "experiments": []}

    exps = []
    for exp_folder in sorted(artifacts_dir.iterdir()):
        if exp_folder.is_dir():
            summary_file = exp_folder / "summary.json"
            manifest_file = exp_folder / "manifest.yaml"
            if summary_file.exists():
                try:
                    with open(summary_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    exps.append({
                        "experiment_id": exp_folder.name,
                        "has_manifest": manifest_file.exists(),
                        "is_valid": data.get("is_valid", True),
                        "valid_for_research": data.get("valid_for_research", True),
                        "average_waiting_time_s": data.get("average_waiting_time_s", 0.0),
                        "average_queue_veh": data.get("average_queue_veh", 0.0),
                        "throughput_veh_per_s": data.get("throughput_veh_per_s", 0.0),
                        "duration_s": data.get("duration_s", 0.0),
                        "summary": data
                    })
                except Exception as e:
                    logger.debug(f"Could not read {summary_file}: {e}")

    return {
        "total_experiments": len(exps),
        "experiments": exps
    }

@app.get("/api/v1/experiments/{experiment_id}")
def get_experiment_detail(experiment_id: str):
    """
    Returns full artifacts and summary for a single experiment ID.
    """
    exp_folder = artifacts_dir / experiment_id
    if not exp_folder.exists() or not exp_folder.is_dir():
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found in artifacts.")

    summary_file = exp_folder / "summary.json"
    env_file = exp_folder / "environment.json"

    result = {"experiment_id": experiment_id}
    if summary_file.exists():
        with open(summary_file, "r", encoding="utf-8") as f:
            result["summary"] = json.load(f)
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            result["environment"] = json.load(f)

    return result

@app.get("/api/v1/scenarios")
def list_scenarios():
    """Returns list of all available simulation scenarios and SUMO configs with contract metadata."""
    available_ids = contracts_sdk.list_topologies()
    sumo_config_dir = Path(__file__).resolve().parent.parent / "simulator" / "sumo_configs"
    
    scenarios = []
    for tid in available_ids:
        has_sumo = False
        if sumo_config_dir.exists():
            sumo_file = sumo_config_dir / f"{tid}.sumocfg"
            has_sumo = sumo_file.exists()
        
        try:
            summary = contracts_sdk.get_topology_summary(tid)
            scenarios.append({
                "scenario_id": tid,
                "topology_id": tid,
                "name": tid.replace("_", " ").title(),
                "has_sumo_config": has_sumo,
                "total_nodes": summary.get("total_nodes", 0),
                "total_edges": summary.get("total_edges", 0),
                "total_phases": summary.get("total_phases", 0),
            })
        except Exception as e:
            scenarios.append({
                "scenario_id": tid,
                "topology_id": tid,
                "name": tid,
                "has_sumo_config": has_sumo,
                "error": str(e)
            })
    
    return {
        "total_scenarios": len(scenarios),
        "scenarios": scenarios
    }

@app.get("/api/v1/topologies")
def list_topologies():
    """Returns list of all registered topology contract IDs with metadata summaries."""
    available_ids = contracts_sdk.list_topologies()
    summaries = []
    for tid in available_ids:
        try:
            summaries.append(contracts_sdk.get_topology_summary(tid))
        except Exception as e:
            summaries.append({"topology_id": tid, "error": str(e)})
    return {
        "total_topologies": len(available_ids),
        "topologies": summaries
    }

@app.get("/api/v1/topologies/{topology_id}")
def get_topology_contract(topology_id: str):
    """Returns full canonical JSON contract for a given topology_id."""
    try:
        topology = contracts_sdk.load_topology(topology_id)
        return topology
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Topology contract '{topology_id}' not found.")

@app.post("/api/v1/topologies/convert-sumo")
def convert_sumo_xml(xml_content: str = Body(..., media_type="text/xml"), topology_id: str = "sumo_converted_v1"):
    """Parses SUMO .net.xml payload and returns canonical topology contract JSON with explicit phase approaches."""
    try:
        topology = SumoNetworkConverter.parse_net_xml(xml_content, topology_id=topology_id)
        return topology
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed converting SUMO XML: {str(e)}")

@app.get("/api/v1/cameras")
def get_hcm_cameras():
    """
    Returns list of all HCM geographic camera nodes with metadata and coordinates.
    """
    if not os.path.exists(TOPOLOGY_FILE):
        raise HTTPException(status_code=404, detail="HCM Topology Contract not found.")
    
    with open(TOPOLOGY_FILE, "r", encoding="utf-8") as f:
        topology = json.load(f)
    
    nodes = topology.get("nodes", [])
    return {
        "topology_id": topology.get("topology_id", "hcm_realworld_v1"),
        "total_cameras": len(nodes),
        "total_edges": len(topology.get("edges", [])),
        "cameras": [
            {
                "node_id": n["node_id"],
                "name": n.get("name"),
                "lat": n.get("lat"),
                "lng": n.get("lng"),
                "status": n.get("status", "Online")
            }
            for n in nodes
        ]
    }

@app.get("/api/v1/map/hcm-cameras", response_class=HTMLResponse)
def get_hcm_camera_map():
    """
    Serves the interactive Folium Dark Mode map for HCM SUMO Geo camera network.
    """
    if not os.path.exists(MAP_HTML_FILE):
        raise HTTPException(status_code=404, detail="HCM Camera Map HTML not generated yet.")
    
    with open(MAP_HTML_FILE, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
