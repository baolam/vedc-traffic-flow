"""
EdgeFlow AI - Legacy Traffic Crawler (Network Intercept Mode).
Captures raw traffic camera packets by intercepting browser network traffic.
"""

from .hcm_traffic_crawler import crawl_cameras_grid

# Provide legacy crawl_cameras_v2 function if needed
def crawl_cameras_v2():
    from .hcm_traffic_crawler import crawl_cameras_grid
    return crawl_cameras_grid(steps=8)

if __name__ == "__main__":
    crawl_cameras_v2()
