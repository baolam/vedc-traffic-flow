"""
Crawler Package for EdgeFlow AI.
Extracts camera metadata and geographic coordinates from Ho Chi Minh City traffic systems.
"""

from .hcm_traffic_crawler import crawl_cameras_grid

__all__ = ["crawl_cameras_grid"]
