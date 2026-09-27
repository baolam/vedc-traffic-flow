# EdgeFlow AI — Microservices Ecosystem (`services/`)

This directory contains the production microservices forming the **EdgeFlow AI** distributed traffic signal control system.

---

## 🏛️ Services Architecture

| Service Directory | Core Technology | Primary Responsibility | Deployment Target |
|---|---|---|---|
| **[`actuator/`](file:///e:/vedc-traffic-flow/services/actuator)** | Python State Machine | Enforces non-negotiable physical clearance ($\text{GREEN} \rightarrow \text{YELLOW} \rightarrow \text{ALL\_RED} \rightarrow \text{GREEN}$) and validates command expiry. | Docker / Local Runtime |
| **[`api/`](file:///e:/vedc-traffic-flow/services/api)** | FastAPI / REST / WebSockets | Central control plane for live network telemetry, policy switching, experiment index, and topology conversion. | Docker / Cloud / Edge Server |
| **[`dashboard/`](file:///e:/vedc-traffic-flow/services/dashboard)** | React 18 / Lucide Icons / Chart.js | Real-time traffic IOC dashboard displaying live intersection states, queues, and performance metrics. | Web Browser / Nginx Container |
| **[`experiment-runner/`](file:///e:/vedc-traffic-flow/services/experiment-runner)** | Python Orchestration | Automated benchmark runner for SUMO simulation experiments under strict scientific reproducibility standards. | Research PC / Benchmarking Node |
| **[`graph-control/`](file:///e:/vedc-traffic-flow/services/graph-control)** | Python / NetworkX / NumPy | Graph-level adaptive traffic signal controller (Fixed-Time, Actuated, Max-Queue, Max-Pressure, EdgeFlow, PressLight RL). | Coordinator / Edge Server |
| **[`simulator/`](file:///e:/vedc-traffic-flow/services/simulator)** | Eclipse SUMO / TraCI | Digital Twin microscopic simulation engine executing synthetic traffic scenarios and emitting ground-truth telemetry. | Simulation Host |
| **[`vision/`](file:///e:/vedc-traffic-flow/services/vision)** | OpenCV / YOLO / Picamera | **Raspberry Pi 5 Edge Perception Service** extracting vehicle queues and flow from live camera feeds on tabletop corridors. | **Raspberry Pi 5 (Native / Docker)** |

---

## 🔄 Inter-Service Communication

All inter-service messaging occurs through the **MQTT Event Backbone** on port `1883`:

- **Telemetry**: `edgeflow/v1/telemetry/{node_id}`
- **Control Command**: `edgeflow/v1/control/{node_id}/command`
- **Control ACK**: `edgeflow/v1/control/{node_id}/ack`
- **Network State**: `edgeflow/v1/network/state`
- **Health Heartbeat**: `edgeflow/v1/health/{service}`
- **Live Events**: `edgeflow/v1/events`
