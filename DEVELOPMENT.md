# Development & Setup Guide (Hướng Dẫn Phát Triển & Chuẩn Hoá)

## Quick Start (Docker Environment)

### 1. Copy local configuration
- **Bash / Linux / macOS**:
  ```bash
  cp .env.example .env
  ```
- **Windows PowerShell**:
  ```powershell
  Copy-Item .env.example .env
  ```

### 2. Start the Simulation Stack
Run Docker Compose directly (no `make` required):
```bash
docker compose --profile simulation up --build
```
*(To run in background mode, add `-d`: `docker compose --profile simulation up -d --build`)*

### 3. Verify Service Health & View Logs
- **Check container status**:
  ```bash
  docker compose ps
  ```
- **Tail logs**:
  ```bash
  docker compose logs -f
  ```

### 4. Stop Services
```bash
docker compose down
```

---

## 🛠️ Microservice Configuration (`pydantic-settings`)

Mọi Microservice trong hệ thống (`graph-control`, `actuator`, `simulator`, `api`) đều đọc biến môi trường tập trung thông qua `pydantic-settings` tại file `config.py` của từng service:
- Đọc tự động từ `.env` hoặc hệ thống.
- Ép kiểu dữ liệu an toàn & giá trị mặc định chuẩn.
- Dễ dàng thay đổi thuật toán controller (`EDGEFLOW_CONTROLLER=max_pressure` hoặc `fixed_time`) hay topology (`EDGEFLOW_TOPOLOGY=four_intersection_v1`).

---

## 🧪 Standardized Testing Commands

Chạy kiểm thử nhanh chóng bằng `pytest` hoặc `make`:

- **Chạy toàn bộ hợp đồng & kiểm thử (Khuyên dùng)**:
  ```bash
  make check-all
  ```
- **Contract tests**:
  ```bash
  python -m pytest tests/unit/test_contracts.py
  ```
- **Unit tests**:
  ```bash
  python -m pytest tests/unit
  ```
- **Integration tests**:
  ```bash
  python -m pytest tests/integration
  ```
- **Dọn dẹp cache test**:
  ```bash
  make clean
  ```

---

## 📐 Graph & Data Pipeline Execution

Các script trong `src/graph/` được chuẩn hoá giao diện dòng lệnh (`argparse` CLI):

```bash
# Xây dựng đồ thị camera theo thuật toán BallTree
python src/graph/build_camera_graph.py --input data/raw/cameras_hcm_full.json --output data/processed/camera_traffic_graph.pkl

# Xây dựng đồ thị camera theo tam giác hoá Delaunay
python src/graph/build_camera_graph_delaunay.py --input data/raw/cameras_hcm_full.json --output data/processed/camera_traffic_graph_delaunay.pkl

# Chuyển đổi file SUMO network .net.xml sang JSON Topology contract
python src/graph/sumo_converter.py --input path/to/net.xml --output contracts/topology/custom_topo.json --topology-id custom_topo_v1
```

---

## Local Development Requirements

- Docker & Docker Compose v2 (Docker Desktop for Windows/macOS)
- Python 3.9+
- Git
