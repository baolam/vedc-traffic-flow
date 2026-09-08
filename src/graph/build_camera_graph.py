import json
import requests
import networkx as nx
import pickle
import numpy as np
from sklearn.neighbors import BallTree
import math
import time

def main():
    # Cấu hình OSRM. Bạn có thể đổi port nếu docker của bạn dùng port khác
    OSRM_URL = "http://localhost:5005/route/v1/driving"
    K_NEIGHBORS = 4  # Số lượng node lân cận cần nối (tính cả chính nó nên thực tế là 3)

    print("Reading camera data...")
    with open('data/raw/cameras_hcm_full.json', 'r', encoding='utf-8') as f:
        cameras = json.load(f)

    # Lọc các camera có tọa độ hợp lệ
    valid_cameras = [c for c in cameras if c.get('lat') and c.get('lng')]
    print(f"Total valid cameras: {len(valid_cameras)}")

    # Chuẩn bị dữ liệu tọa độ (đổi sang radians) cho BallTree tính Haversine distance
    coords = np.array([[math.radians(c['lat']), math.radians(c['lng'])] for c in valid_cameras])
    
    print("Finding nearest neighbors...")
    tree = BallTree(coords, metric='haversine')
    distances, indices = tree.query(coords, k=K_NEIGHBORS)

    # Khởi tạo đồ thị có hướng, cho phép đa cạnh (MultiDiGraph)
    G = nx.MultiDiGraph()

    print("Adding nodes to graph...")
    for i, cam in enumerate(valid_cameras):
        G.add_node(cam['id'], name=cam.get('name'), lat=cam['lat'], lng=cam['lng'], status=cam.get('status'))

    print("Querying OSRM for routes...")
    processed_count = 0
    total_pairs = len(valid_cameras) * (K_NEIGHBORS - 1)

    for i, neighbors_idx in enumerate(indices):
        src_cam = valid_cameras[i]
        
        # neighbors_idx[0] luôn là chính nó, nên duyệt từ 1
        for j in range(1, len(neighbors_idx)):
            dst_cam = valid_cameras[neighbors_idx[j]]
            
            # Chuỗi tọa độ cho OSRM (định dạng: lng,lat;lng,lat)
            coords_str = f"{src_cam['lng']},{src_cam['lat']};{dst_cam['lng']},{dst_cam['lat']}"
            url = f"{OSRM_URL}/{coords_str}?alternatives=true&geometries=geojson&overview=full"
            
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('code') == 'Ok':
                        routes = data.get('routes', [])
                        # Nếu có nhiều đường đi (alternatives), sẽ add nhiều cạnh
                        for route in routes:
                            distance = route.get('distance')
                            duration = route.get('duration')
                            geometry = route.get('geometry')  # GeoJSON định dạng LineString
                            
                            # Thêm cạnh vào đồ thị
                            G.add_edge(src_cam['id'], dst_cam['id'], 
                                       distance=distance, 
                                       duration=duration, 
                                       geometry=geometry)
                else:
                    print(f"OSRM Error: HTTP {resp.status_code}")
            except Exception as e:
                # Nếu OSRM không phản hồi hoặc lỗi, có thể bỏ qua hoặc in ra
                pass
            
            processed_count += 1
            if processed_count % 500 == 0:
                print(f"Processed {processed_count}/{total_pairs} pairs...")

    print(f"Done! Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    # Lưu đồ thị dưới dạng pickle để giữ nguyên NetworkX object
    output_file = 'data/processed/camera_traffic_graph.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(G, f)
    print(f"Đã lưu đồ thị vào file: {output_file}")
    
    # Bạn có thể load lại bằng:
    # with open('camera_traffic_graph.pkl', 'rb') as f:
    #     G_loaded = pickle.load(f)

if __name__ == "__main__":
    main()
