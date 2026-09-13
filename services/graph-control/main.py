import os
import time

print(f"Starting EdgeFlow Graph-Control Service (Controller: {os.getenv('EDGEFLOW_CONTROLLER', 'fixed_time')})...")

if __name__ == "__main__":
    while True:
        time.sleep(10)
