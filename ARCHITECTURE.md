# EdgeFlow AI — System Architecture (3-Tier Distributed System)

EdgeFlow AI demonstrates real-time adaptive traffic-signal control on a network-level graph $G_t=(V,E,X_t)$ using a **3-tier distributed architecture**:
1. **Central Server (Laptop)**: Hosts the Dockerized microservices stack, MQTT broker, adaptive control algorithms, and IOC Dashboard.
2. **Edge AI Perception (Raspberry Pi 5)**: Ingests camera feeds from the physical tabletop corridor, performs YOLO vehicle detection, and emits canonical Telemetry.
3. **Hardware Safety Actuators (ESP32)**: Enforces physical clearance timing and controls traffic light LEDs on the physical corridor.

---

## 🏗️ Logical Architecture & Hardware Mapping

```text
+-----------------------------------------------------------------------------------------+
|                                TIER 1: LAPTOP / CENTRAL SERVER                          |
|                                                                                         |
|      +---------------------+                                 +---------------------+    |
|      |   IOC Dashboard     |                                 | Experiment Runner / |    |
|      |  (React - Port 3000)|                                 | SUMO Digital Twin   |    |
|      +----------+----------+                                 +----------+----------+    |
|                 | REST / WebSocket                                      |               |
|      +----------v----------+                                            |               |
|      |    API Backend      |                                            |               |
|      |  (FastAPI - :8000)  |                                            |               |
|      +----------+----------+                                            |               |
|                 |                                                       |               |
|  +--------------v-------------------------------------------------------v------------+  |
|  |                   Central MQTT Event Backbone (Mosquitto - Port 1883)             |  |
|  +--------------+-------------------------------------+-----------------+------------+  |
|                 | Telemetry                           | ControlCommand  |               |
|      +----------v----------+                          |                 |               |
|      |   Graph-Control     |--------------------------+                 |               |
|      |  (EdgeFlow Engine)  |                                            |               |
|      +---------------------+                                            |               |
+-------------------------------------------------------------------------+---------------+
                                          | Local Network (WiFi / MQTT 1883)
                  +-----------------------+-----------------------+
                  | Telemetry                                     | ControlCommand & ACK
+-----------------v-----------------------+     +-----------------v-----------------------+
|    TIER 2: RASPBERRY PI 5 (EDGE AI)     |     |   TIER 3: PHYSICAL ACTUATORS (ESP32)    |
|           (services/vision)             |     |        (src/hardware/firmware)          |
|                                         |     |                                         |
| • Camera Module 3 / USB (/dev/video0)   |     | • ESP32 Node 1 (J1) & ESP32 Node 2 (J2) |
| • YOLOv8 / OpenCV DNN Detection Engine  |     | • 8 Signal Heads (24 Physical LEDs)     |
| • ROI Manager (Approach Queue Count)    |     | • Mandatory Clearance:                  |
| • CPU Thermal & Throttling Diagnostics  |     |   GREEN -> YELLOW (3s) -> ALL_RED (2s)  |
| • Publishes edgeflow/v1/telemetry/{id}  |     | • Autonomous 15s Watchdog Fallback      |
+-----------------------------------------+     +-----------------------------------------+
```

---

## 📦 Service Responsibilities & Deployment Targets

| Service / Node | Deployment Target | Protocol / Port | Primary Responsibility |
|---|---|---|---|
| **MQTT Broker** | Laptop (Server) | MQTT (1883) | Central event backbone for Telemetry, ControlCommand, ControlACK, Health, and State events. |
| **API Backend** | Laptop (Server) | REST / FastAPI (8000) | System control plane, topology catalog, experiment registry, and WebSocket live feed. |
| **Graph-Control** | Laptop (Server) | Python / MQTT | Maintains network graph $G_t$, executes EdgeFlow / Max-Pressure / RL algorithms, and emits ControlCommand. |
| **Dashboard** | Laptop (Client UI) | React (3000) | Real-time traffic IOC dashboard displaying live intersection states, video feeds, and metrics. |
| **Simulator** | Laptop (Server) | SUMO / TraCI | Digital Twin microscopic simulation engine used for high-volume benchmark research. |
| **Vision Service** | **Raspberry Pi 5** | OpenCV / YOLO / MQTT | **Edge AI Perception Service** extracting vehicle queues from physical tabletop corridor cameras. |
| **Actuator Firmware** | **2x ESP32 Boards** | C++ / FreeRTOS / MQTT | **Physical Signal Actuators** enforcing safe hardware clearance on LED heads and local failsafe. |

---

## 📡 MQTT Topic Tree

- **Telemetry (Perception $\rightarrow$ Controller)**: `edgeflow/v1/telemetry/{node_id}`
- **Control Command (Controller $\rightarrow$ Actuator)**: `edgeflow/v1/control/{node_id}/command`
- **Control ACK (Actuator $\rightarrow$ System)**: `edgeflow/v1/control/{node_id}/ack`
- **Network State (Global Graph Snapshot)**: `edgeflow/v1/network/state`
- **Metrics (Aggregated Throughput & Queue)**: `edgeflow/v1/metrics/network`
- **Health Heartbeat (Diagnostic Telemetry)**: `edgeflow/v1/health/{service_or_node_id}`
- **System Events (State Changes & Incidents)**: `edgeflow/v1/events`
