"""
Backward-compatibility alias for src.crawler.hcm_traffic_crawler
"""

from .hcm_traffic_crawler import crawl_cameras_grid, crawl_cameras_grid as crawl_cameras_grid_v3

if __name__ == "__main__":
    crawl_cameras_grid()
