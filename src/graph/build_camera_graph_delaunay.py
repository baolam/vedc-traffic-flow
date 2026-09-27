"""
Backward-compatibility alias for src.graph.delaunay_builder
"""

from .delaunay_builder import build_delaunay_graph, haversine, main

if __name__ == "__main__":
    main()
