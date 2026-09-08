import json
import requests
import networkx as nx
import pickle
import numpy as np
from scipy.spatial import Delaunay
import math
import time

def haversine(lat1, lon1, lat2, lon2):
    # Tính khoảng cách giữa 2 tọa độ (đơn vị: km)
    R = 6371.0 # Bán kính trái đất
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def main():
    OSRM_URL = "http://localhost:5005/route/v1/driving"
    MAX_DISTANCE_KM = 3.0  # Loại bỏ các node cách nhau quá 3km

    print("Reading camera data...")
    with open('data/raw/cameras_hcm_full.json', 'r', encoding='utf-8') as f:
        cameras = json.load(f)

    # Lọc các camera hợp lệ
    valid_cameras = [c for c in cameras if c.get('lat') and c.get('lng')]
    print(f"Total valid cameras: {len(valid_cameras)}")

    # Tạo mảng tọa độ (lat, lng)
    coords = np.array([[c['lat'], c['lng']] for c in valid_cameras])
    
    print("Computing Delaunay Triangulation...")
    tri = Delaunay(coords)

    # Trích xuất các cạnh (edges) từ các lưới tam giác (simplices)
    unique_edges = set()
    for simplex in tri.simplices:
        # Một tam giác có 3 đỉnh, tạo ra 3 cạnh
        # Sắp xếp index để tránh bị trùng lặp (1,2) và (2,1)
        edges = [
            tuple(sorted((simplex[0], simplex[1]))),
            tuple(sorted((simplex[1], simplex[2]))),
            tuple(sorted((simplex[2], simplex[0])))
        ]
        unique_edges.update(edges)

    print(f"Generated {len(unique_edges)} candidate edges from Delaunay.")

    # Khởi tạo đồ thị có hướng (MultiDiGraph)
    G = nx.MultiDiGraph()
    for i, cam in enumerate(valid_cameras):
        G.add_node(cam['id'], name=cam.get('name'), lat=cam['lat'], lng=cam['lng'], status=cam.get('status'))

    print("Filtering long edges and querying OSRM...")
    processed_count = 0
    total_edges = len(unique_edges)
    
    # Do giao thông có tính chất chiều đi và chiều về (đường 1 chiều), ta sẽ query cả 2 chiều
    for idx_u, idx_v in unique_edges:
        processed_count += 1
        
        cam_u = valid_cameras[idx_u]
        cam_v = valid_cameras[idx_v]
        
        # Kiểm tra khoảng cách chim bay
        dist_km = haversine(cam_u['lat'], cam_u['lng'], cam_v['lat'], cam_v['lng'])
        if dist_km > MAX_DISTANCE_KM:
            continue # Bỏ qua các cạnh quá dài

        # Query cả chiều U -> V và V -> U
        directions = [
            (cam_u, cam_v),
            (cam_v, cam_u)
        ]
        
        for src_cam, dst_cam in directions:
            coords_str = f"{src_cam['lng']},{src_cam['lat']};{dst_cam['lng']},{dst_cam['lat']}"
            url = f"{OSRM_URL}/{coords_str}?alternatives=true&geometries=geojson&overview=full"
            
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
                            
                            # Thêm cạnh vào đồ thị
                            G.add_edge(src_cam['id'], dst_cam['id'], 
                                       distance=distance, 
                                       duration=duration, 
                                       geometry=geometry)
            except Exception as e:
                pass
        
        if processed_count % 500 == 0:
            print(f"Processed {processed_count}/{total_edges} candidate edges...")

    print(f"Done! Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    output_file = 'data/processed/camera_traffic_graph_delaunay.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(G, f)

if __name__ == "__main__":
    main()
