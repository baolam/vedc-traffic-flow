"""
Backward-compatibility alias for src.visualization.map_visualizer
"""

from .map_visualizer import generate_camera_map, load_graph_data, main

if __name__ == "__main__":
    main()
