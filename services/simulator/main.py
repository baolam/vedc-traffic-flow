import os
import time

print(f"Starting EdgeFlow SUMO Simulator Service (Topology: {os.getenv('EDGEFLOW_TOPOLOGY', 'four_intersection_v1')})...")

if __name__ == "__main__":
    while True:
        time.sleep(10)
