# EdgeFlow AI — Research, Tooling & Hardware Lab (`src/`)

This directory contains research algorithms, data acquisition pipelines, offline reinforcement learning training routines, spatial graph modeling, hardware prototypes, and developer utilities for **EdgeFlow AI**.

---

## 📁 Directory Structure

```
src/
├── crawler/                # Data Acquisition & ETL from Traffic Portals
│   ├── __init__.py
│   ├── hcm_traffic_crawler.py     # Grid-based Playwright crawler for HCM traffic cameras
│   ├── legacy_crawler.py          # Network interception crawler
│   ├── crawler_grid.py            # Backward-compatibility alias
│   └── crawler_v2.py              # Backward-compatibility alias
│
├── graph/                  # Spatial Graph Construction & SUMO Topology Converter
│   ├── __init__.py
│   ├── sumo_converter.py          # Parser for SUMO .net.xml -> Canonical Topology Contract
│   ├── delaunay_builder.py        # Delaunay triangulation & OSRM route builder
│   ├── camera_graph_builder.py    # BallTree nearest-neighbor graph builder
│   ├── build_camera_graph_delaunay.py # Backward-compatibility alias
│   └── build_camera_graph.py      # Backward-compatibility alias
│
├── hardware/               # Physical Hardware Prototype & Embedded Firmware
│   ├── __init__.py
│   ├── README.md                  # Hardware architecture, Raspberry Pi 5 role & BOM budget
│   ├── schematic_and_pinout.md    # Electrical schematics, GPIO pinouts & safety wiring
│   └── firmware/
│       └── esp32_signal_controller.ino # ESP32 FreeRTOS/MQTT signal actuator firmware
│
├── rl/                     # Reinforcement Learning Research & Training
│   ├── __init__.py
│   ├── policy.py                  # State feature extraction & Pure-NumPy inference engine
│   ├── traffic_env.py             # High-speed synthetic single-intersection gym environment
│   ├── train_dqn.py               # CPU / Standard DQN training pipeline
│   ├── train_gpu_dqn.py           # GPU-accelerated (CUDA/MPS) DQN training pipeline
│   ├── evaluate.py                # Policy evaluation & baseline comparison
│   └── requirements.txt           # Python dependencies for RL training
│
├── tools/                  # Developer CLI Utilities & Benchmarking
│   ├── __init__.py
│   ├── import_sumo_scenario.py    # Automated importer for RESCO & SUMO-RL benchmarks
│   ├── run_experiment_gui.py      # One-click launcher for multi-service stack with SUMO-GUI
│   └── benchmark_models.py        # Latency & throughput benchmarking for models
│
└── visualization/          # Map Rendering & Network Visualizer
    ├── __init__.py
    ├── map_visualizer.py          # Interactive Folium map generator with live queue overlay
    └── visualize_graph.py         # Backward-compatibility alias
```

---

## 🚀 Key Modules Overview

### 1. `src/crawler`
- **`hcm_traffic_crawler.py`**: Divides the Ho Chi Minh City bounding box into an $8 \times 8$ grid (64 cells) to reliably ingest camera locations, street names, and districts from the public traffic portal.

### 2. `src/graph`
- **`sumo_converter.py`**: Core translator that parses SUMO `.net.xml` network topologies, extracts traffic light logic (`tlLogic`), resolves link indices to movement pairs, and outputs compliant EdgeFlow AI Topology Contracts.
- **`delaunay_builder.py`**: Builds Delaunay spatial graphs across thousands of camera coordinates and annotates edges with real-world OSRM routing geometry.

### 3. `src/hardware`
- **`firmware/esp32_signal_controller.ino`**: Dual-core ESP32 firmware that controls 4 traffic light heads (12 LEDs) via MQTT, enforcing hardware clearance intervals ($\text{GREEN} \rightarrow \text{YELLOW} \rightarrow \text{ALL\_RED} \rightarrow \text{GREEN}$) and fallback schedules upon coordinator timeout.
- **Raspberry Pi 5 Perception Software**: Maintained directly in **[`services/vision/`](file:///e:/vedc-traffic-flow/services/vision)**.

### 4. `src/rl`
- **Train-then-Export Philosophy**: Train deep Q-networks using PyTorch GPU (`train_gpu_dqn.py`), export compact MLP weights to JSON, and serve inside production microservices (`services/graph-control`) using **zero-PyTorch pure NumPy** (`policy.py`).

### 5. `src/tools`
- **`import_sumo_scenario.py`**: Instantly downloads and configures standard academic benchmarks (RESCO `grid4x4`, `cologne8`, `arterial4x4`, `ingolstadt21`) into `contracts/topology` and `services/simulator`.
- **`run_experiment_gui.py`**: Spawns Actuator, Graph-Control, and SUMO-GUI simultaneously for visual debugging and presentation.
