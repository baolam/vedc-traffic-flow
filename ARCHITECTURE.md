# EdgeFlow AI - System Architecture

EdgeFlow AI demonstrates adaptive traffic-signal control using network-level traffic state $G=(V,E)$ instead of fixed timing.

---

## Logical Architecture

```
                       +-------------------+
                       |   IOC Dashboard   |
                       +---------+---------+
                                 | REST / WebSocket
                       +---------v---------+
                       |    API Backend    |
                       |  Experiments/Logs |
                       +---------+---------+
                                 | MQTT Broker
       +-------------------------+-------------------------+
       |                         |                         |
+------v------+           +------v-------+          +------v------+
|  Simulator  |----------->| Graph-Control|<---------|   Vision    |
|    SUMO     | Telemetry |  G=(V,E)     | Telemetry| YOLO/Track  |
+------^------+           | Fixed / MP   |          +-------------+
       |                  +------+-------+
       |                         | ControlCommand
       |                  +------v-------+
       +------------------|   Actuator   |
         Actuator Adapter |   Adapter    |
                          +--------------+
```

---

## Service Responsibilities & Protocols

| Service | Mechanism | Primary Responsibility |
|---|---|---|
| **MQTT Broker** | MQTT (1883) | Event backbone for Telemetry, ControlCommand, ACK, Health & Metrics |
| **API Backend** | REST / FastAPI / WebSocket | Experiment management, historical logs, state persistence (SQLite), WS live updates |
| **Graph-Control** | Python / NetworkX | Maintains global state $G_t=(V,E,X_t)$, runs Max-Pressure / Fixed-Time algorithms |
| **Simulator** | SUMO / TraCI | Digital twin, controlled traffic scenarios, ground-truth metric exporter |
| **Vision** | OpenCV / PyTorch | Video/webcam traffic perception adapter emitting canonical telemetry |
| **Actuator** | Python State Machine | Enforces safe phase timing (Green -> Yellow -> All-Red), publishes ACK |
| **Dashboard** | React / Web | Real-time traffic network visualization & benchmark comparison |

---

## MQTT Topic Tree

- Telemetry: `edgeflow/v1/telemetry/{node_id}`
- Command: `edgeflow/v1/control/{node_id}/command`
- ACK: `edgeflow/v1/control/{node_id}/ack`
- Network State: `edgeflow/v1/network/state`
- Metrics: `edgeflow/v1/metrics/network`
- Health: `edgeflow/v1/health/{service}`
- Events: `edgeflow/v1/events`
