"""
EdgeFlow AI - Nearest Neighbor Camera Graph Builder.
Constructs spatial camera adjacency graph using BallTree nearest neighbors & OSRM routing.
"""

import json
import requests
import networkx as nx
import pickle
import numpy as np
from sklearn.neighbors import BallTree
import math
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("camera-graph-builder")

def build_camera_graph(input_file: str, output_file: str, osrm_url: str = "http://localhost:5005/route/v1/driving", k_neighbors: int = 4):
    logger.info(f"Reading camera data from {input_file}...")
    if not Path(input_file).exists():
        raise FileNotFoundError(f"Input camera file not found: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        cameras = json.load(f)

    valid_cameras = [c for c in cameras if c.get('lat') and c.get('lng')]
    logger.info(f"Total valid cameras: {len(valid_cameras)}")

    coords = np.array([[math.radians(c['lat']), math.radians(c['lng'])] for c in valid_cameras])
    
    logger.info(f"Finding nearest neighbors (k={k_neighbors})...")
    tree = BallTree(coords, metric='haversine')
    distances, indices = tree.query(coords, k=k_neighbors)

    G = nx.MultiDiGraph()

    for i, cam in enumerate(valid_cameras):
        G.add_node(cam['id'], name=cam.get('name'), lat=cam['lat'], lng=cam['lng'], status=cam.get('status'))

    logger.info("Querying OSRM for routes...")
    processed_count = 0
    total_pairs = len(valid_cameras) * (k_neighbors - 1)

    for i, neighbors_idx in enumerate(indices):
        src_cam = valid_cameras[i]
        
        for j in range(1, len(neighbors_idx)):
            dst_cam = valid_cameras[neighbors_idx[j]]
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
            
            processed_count += 1
            if processed_count % 500 == 0:
                logger.info(f"Processed {processed_count}/{total_pairs} pairs...")

    logger.info(f"Done! Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'wb') as f:
        pickle.dump(G, f)
    logger.info(f"Saved graph to: {output_file}")
    return G

def main():
    parser = argparse.ArgumentParser(description="Build camera network graph using BallTree nearest neighbors and OSRM routing.")
    parser.add_argument("--input", "-i", default="data/raw/cameras_hcm_full.json", help="Path to raw camera json dataset")
    parser.add_argument("--output", "-o", default="data/processed/camera_traffic_graph.pkl", help="Path to save output pkl graph")
    parser.add_argument("--osrm-url", default="http://localhost:5005/route/v1/driving", help="OSRM API routing server URL")
    parser.add_argument("--k-neighbors", "-k", type=int, default=4, help="Number of nearest neighbors (including self)")
    
    args = parser.parse_args()
    build_camera_graph(
        input_file=args.input,
        output_file=args.output,
        osrm_url=args.osrm_url,
        k_neighbors=args.k_neighbors
    )

if __name__ == "__main__":
    main()
