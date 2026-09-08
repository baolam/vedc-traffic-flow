import pickle
import folium

def main():
    print("Loading graph...")
    with open('data/processed/camera_traffic_graph_delaunay.pkl', 'rb') as f:
        G = pickle.load(f)

    print(f"Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    nodes_data = G.nodes(data=True)
    lats = [data['lat'] for node, data in nodes_data if 'lat' in data]
    lngs = [data['lng'] for node, data in nodes_data if 'lng' in data]

    center_lat = sum(lats) / len(lats)
    center_lng = sum(lngs) / len(lngs)

    print("Generating map...")
    # Tạo bản đồ trung tâm tại HCM với nền Google Maps
    m = folium.Map(
        location=[center_lat, center_lng], 
        zoom_start=12, 
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google'
    )

    # Vẽ đường đi (Edges)
    for u, v, key, data in G.edges(data=True, keys=True):
        geometry = data.get('geometry')
        if geometry and geometry.get('type') == 'LineString':
            coords = geometry.get('coordinates', [])
            # Folium nhận vào (lat, lon) thay vì (lon, lat) của GeoJSON
            folium_coords = [(lat, lon) for lon, lat in coords]
            
            folium.PolyLine(
                locations=folium_coords,
                color='blue',
                weight=2,
                opacity=0.4
            ).add_to(m)

    # Vẽ các camera (Nodes)
    for node, data in nodes_data:
        if 'lat' in data and 'lng' in data:
            folium.CircleMarker(
                location=(data['lat'], data['lng']),
                radius=4,
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=1,
                popup=data.get('name', str(node))
            ).add_to(m)

    output_file = 'output/camera_graph_map.html'
    m.save(output_file)
    print(f"Done! Open {output_file} in your browser to view the map.")

if __name__ == "__main__":
    main()
