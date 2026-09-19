import json
import requests
import networkx as nx
import pickle
import numpy as np
from scipy.spatial import Delaunay
import math
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build-camera-graph-delaunay")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def build_delaunay_graph(input_file: str, output_file: str, osrm_url: str = "http://localhost:5005/route/v1/driving", max_distance_km: float = 3.0):
    logger.info(f"Reading camera data from {input_file}...")
    if not Path(input_file).exists():
        raise FileNotFoundError(f"Input camera file not found: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        cameras = json.load(f)

    valid_cameras = [c for c in cameras if c.get('lat') and c.get('lng')]
    logger.info(f"Total valid cameras: {len(valid_cameras)}")

    coords = np.array([[c['lat'], c['lng']] for c in valid_cameras])
    
    logger.info("Computing Delaunay Triangulation...")
    tri = Delaunay(coords)

    unique_edges = set()
    for simplex in tri.simplices:
        edges = [
            tuple(sorted((simplex[0], simplex[1]))),
            tuple(sorted((simplex[1], simplex[2]))),
            tuple(sorted((simplex[2], simplex[0])))
        ]
        unique_edges.update(edges)

    logger.info(f"Generated {len(unique_edges)} candidate edges from Delaunay.")

    G = nx.MultiDiGraph()
    for i, cam in enumerate(valid_cameras):
        G.add_node(cam['id'], name=cam.get('name'), lat=cam['lat'], lng=cam['lng'], status=cam.get('status'))

    logger.info("Filtering long edges and querying OSRM...")
    processed_count = 0
    total_edges = len(unique_edges)
    
    for idx_u, idx_v in unique_edges:
        processed_count += 1
        cam_u = valid_cameras[idx_u]
        cam_v = valid_cameras[idx_v]
        
        dist_km = haversine(cam_u['lat'], cam_u['lng'], cam_v['lat'], cam_v['lng'])
        if dist_km > max_distance_km:
            continue

        directions = [(cam_u, cam_v), (cam_v, cam_u)]
        
        for src_cam, dst_cam in directions:
            coords_str = f"{src_cam['lng']},{src_cam['lat']};{dst_cam['lng']},{dst_cam['lat']}"
            url = f"{osrm_url}/{coords_str}?alternatives=true&geometries=geojson&overview=full"
            
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('code') == 'Ok':
                        routes = data.get('routes', [])
                        for route in routes:
                            distance = route.get('distance')
                            duration = route.get('duration')
                            geometry = route.get('geometry')
                            
                            G.add_edge(src_cam['id'], dst_cam['id'], 
                                       distance=distance, 
                                       duration=duration, 
                                       geometry=geometry)
            except Exception:
                pass
        
        if processed_count % 500 == 0:
            logger.info(f"Processed {processed_count}/{total_edges} candidate edges...")

    logger.info(f"Done! Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'wb') as f:
        pickle.dump(G, f)
    logger.info(f"Saved graph to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Build camera network graph using Delaunay triangulation and OSRM routing.")
    parser.add_argument("--input", "-i", default="data/raw/cameras_hcm_full.json", help="Path to raw camera json dataset")
    parser.add_argument("--output", "-o", default="data/processed/camera_traffic_graph_delaunay.pkl", help="Path to save output pkl graph")
    parser.add_argument("--osrm-url", default="http://localhost:5005/route/v1/driving", help="OSRM API routing server URL")
    parser.add_argument("--max-distance-km", type=float, default=3.0, help="Maximum straight-line distance filter in km")
    
    args = parser.parse_args()
    build_delaunay_graph(
        input_file=args.input,
        output_file=args.output,
        osrm_url=args.osrm_url,
        max_distance_km=args.max_distance_km
    )

if __name__ == "__main__":
    main()
