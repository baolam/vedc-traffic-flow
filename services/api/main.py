import os
import json
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Add contracts and src to sys.path safely
def _get_contracts_dir() -> Path:
    env_dir = os.getenv("CONTRACTS_DIR")
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

try:
    import contracts_sdk
except ImportError:
    import contracts.contracts_sdk as contracts_sdk

from sumo_converter import SumoNetworkConverter

app = FastAPI(
    title="EdgeFlow AI Control Plane & API",
    description="REST API serving live traffic topology, contract registries, SUMO converters, and interactive maps.",
    version="1.1.0"
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

@app.get("/")
def root():
    return {
        "service": "edgeflow-api",
        "status": "running",
        "endpoints": [
            "/health",
            "/api/v1/topologies",
            "/api/v1/topologies/{topology_id}",
            "/api/v1/topologies/convert-sumo",
            "/api/v1/cameras",
            "/api/v1/map/hcm-cameras"
        ]
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

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
    uvicorn.run(app, host="0.0.0.0", port=8000)
