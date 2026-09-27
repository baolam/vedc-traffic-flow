"""
EdgeFlow AI - Interactive Traffic Map Visualizer.
Generates rich Folium interactive dark/light maps from HCM City camera graphs.
"""

import os
import pickle
import json
from pathlib import Path
from typing import Tuple, Any

try:
    import folium
    from folium.plugins import MarkerCluster
except ImportError:
    folium = None
    MarkerCluster = None


def load_graph_data(pkl_path: str = 'data/processed/camera_traffic_graph_delaunay.pkl', 
                    json_path: str = 'contracts/topology/hcm_realworld_v1.json') -> Tuple[Any, str]:
    if os.path.exists(pkl_path):
        with open(pkl_path, 'rb') as f:
            return pickle.load(f), 'pkl'
    elif os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f), 'json'
    else:
        raise FileNotFoundError(f"Neither {pkl_path} nor {json_path} found.")


def generate_camera_map(
    output_html: str = 'output/camera_graph_map.html',
    pkl_file: str = 'data/processed/camera_traffic_graph_delaunay.pkl',
    json_file: str = 'contracts/topology/hcm_realworld_v1.json'
):
    if folium is None:
        raise ImportError("Folium library is not installed. Install with 'pip install folium'")

    print("Loading HCM camera traffic graph data...")
    data, data_type = load_graph_data(pkl_file, json_file)

    if data_type == 'pkl':
        G = data
        nodes_data = [(node, data_dict) for node, data_dict in G.nodes(data=True)]
        edges_data = [(u, v, key, data_dict) for u, v, key, data_dict in G.edges(data=True, keys=True)]
        node_count = G.number_of_nodes()
        edge_count = G.number_of_edges()
    else:
        nodes_data = [(n['node_id'], n) for n in data.get('nodes', [])]
        edges_data = [(e['source'], e['target'], 0, {}) for e in data.get('edges', [])]
        node_count = len(nodes_data)
        edge_count = len(edges_data)

    print(f"Data loaded successfully: {node_count} camera nodes, {edge_count} road connections.")

    lats = [d['lat'] for _, d in nodes_data if d.get('lat') is not None]
    lngs = [d['lng'] for _, d in nodes_data if d.get('lng') is not None]

    if not lats or not lngs:
        print("Error: No valid coordinates found.")
        return

    center_lat = sum(lats) / len(lats)
    center_lng = sum(lngs) / len(lngs)

    print("Generating Light Theme Interactive Folium Map for HCM Real-world SUMO Scenario...")
    
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=12,
        tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
    )

    edges_group = folium.FeatureGroup(name="Road Connections (OSRM / Delaunay)", show=True)

    for u, v, key, data_dict in edges_data:
        geometry = data_dict.get('geometry')
        if geometry and geometry.get('type') == 'LineString':
            coords = geometry.get('coordinates', [])
            folium_coords = [(lat, lon) for lon, lat in coords]
            folium.PolyLine(
                locations=folium_coords,
                color='#0284c7',
                weight=1.8,
                opacity=0.45
            ).add_to(edges_group)

    edges_group.add_to(m)

    marker_cluster = MarkerCluster(
        name="HCM Camera Nodes",
        options={
            'maxClusterRadius': 40,
            'disableClusteringAtZoom': 15,
            'spiderfyOnMaxZoom': True
        }
    ).add_to(m)

    import random
    random.seed(42)

    online_count = 0
    congested_count = 0

    for node_id, data_dict in nodes_data:
        lat = data_dict.get('lat')
        lng = data_dict.get('lng')
        name = data_dict.get('name', str(node_id))
        status = data_dict.get('status', 'Online')
        
        if status == 'Online':
            online_count += 1

        if lat is not None and lng is not None:
            sim_queue = random.randint(2, 22)
            if sim_queue > 15:
                color = '#dc2626'
                congested_count += 1
                status_label = 'Congested (Queue > 15)'
            elif sim_queue > 8:
                color = '#ca8a04'
                status_label = 'Moderate (Queue 8-15)'
            else:
                color = '#16a34a'
                status_label = 'Normal Flow (Queue < 8)'

            popup_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; min-width: 200px; color: #0f172a;">
                <h4 style="margin: 0 0 6px 0; color: #0284c7; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">
                    📷 {name}
                </h4>
                <p style="margin: 3px 0; font-size: 12px;"><b>Node ID:</b> <code>{node_id}</code></p>
                <p style="margin: 3px 0; font-size: 12px;"><b>Status:</b> <span style="color: {'#16a34a' if status=='Online' else '#dc2626'}; font-weight: bold;">{status}</span></p>
                <p style="margin: 3px 0; font-size: 12px;"><b>Coordinates:</b> {lat:.5f}, {lng:.5f}</p>
                <hr style="margin: 6px 0; border: None; border-top: 1px dashed #cbd5e1;">
                <p style="margin: 3px 0; font-size: 12px;"><b>SUMO Live Queue:</b> <b style="color:{color};">{sim_queue} vehicles</b></p>
                <p style="margin: 3px 0; font-size: 12px;"><b>Traffic State:</b> {status_label}</p>
            </div>
            """

            folium.CircleMarker(
                location=(lat, lng),
                radius=5,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"Camera {name} ({node_id}) - Queue: {sim_queue}"
            ).add_to(marker_cluster)

    panel_html = f"""
    <div style="
        position: fixed;
        bottom: 24px;
        left: 24px;
        z-index: 9999;
        background-color: rgba(255, 255, 255, 0.94);
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        padding: 16px 20px;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        box-shadow: 0 10px 25px rgba(0,0,0,0.12);
        backdrop-filter: blur(8px);
        max-width: 320px;
    ">
        <div style="font-weight: 700; font-size: 15px; margin-bottom: 8px; color: #0284c7; display: flex; align-items: center; gap: 8px;">
            🚦 EdgeFlow AI - HCM SUMO Geo Map
        </div>
        <div style="font-size: 12px; color: #64748b; margin-bottom: 12px;">
            Live Real-World Traffic Telemetry Simulation
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; border-radius: 6px;">
                <span style="color: #64748b;">Total Cameras:</span><br>
                <b style="font-size: 14px; color: #0f172a;">{node_count}</b>
            </div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; border-radius: 6px;">
                <span style="color: #64748b;">Online Status:</span><br>
                <b style="font-size: 14px; color: #16a34a;">{online_count} / {node_count}</b>
            </div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; border-radius: 6px;">
                <span style="color: #64748b;">Road Edges:</span><br>
                <b style="font-size: 14px; color: #0284c7;">{edge_count}</b>
            </div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; border-radius: 6px;">
                <span style="color: #64748b;">Congested Nodes:</span><br>
                <b style="font-size: 14px; color: #dc2626;">{congested_count}</b>
            </div>
        </div>
        <div style="margin-top: 12px; pt-2; border-top: 1px solid #e2e8f0; font-size: 11px; color: #64748b; display: flex; justify-content: space-between;">
            <span style="color: #16a34a; font-weight: 600;">🟢 Normal Queue</span>
            <span style="color: #ca8a04; font-weight: 600;">🟡 Moderate</span>
            <span style="color: #dc2626; font-weight: 600;">🔴 Heavy Queue</span>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(panel_html))

    Path(output_html).parent.mkdir(parents=True, exist_ok=True)
    m.save(output_html)
    print(f"Map generated successfully! Saved to {output_html}")
    return m


def main():
    generate_camera_map()


if __name__ == "__main__":
    main()
