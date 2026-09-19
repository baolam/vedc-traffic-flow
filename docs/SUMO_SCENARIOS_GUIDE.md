# Hướng Dẫn Tải & Khởi Tạo Kịch Bản Giao Thông SUMO Công Khai (SUMO Public Traffic Scenarios Guide)

Tài liệu này hướng dẫn chi tiết cách tải, chuyển đổi và chạy các kịch bản giao thông SUMO công khai (**RESCO Benchmarks**, **TAPASCologne**, **OpenStreetMap**) trên hệ thống **EdgeFlow AI**.

---

## 🚀 1. Khởi Tạo Nhanh Với Các Preset Công Khai (Quick Start Presets)

Dự án cung cấp công cụ CLI tự động `src/tools/import_sumo_scenario.py` giúp tải file mạng `.net.xml` và `.rou.xml`, tự động sinh Topology Contract JSON và cập nhật file cấu hình hệ thống `.env`.

### 🔹 Các Preset có sẵn (Available Presets):
- `grid4x4` / `resco_grid4x4`: Mạng lưới ô cờ 4x4 nút giao (16 nút giao có đèn) từ RESCO Benchmark.
- `cologne8` / `resco_cologne8`: Mạng lưới 8 nút giao trọng điểm thành phố Cologne (TAPASCologne).
- `arterial4x4` / `resco_arterial4x4`: Trục đường chính 4x4 từ RESCO.
- `ingolstadt21` / `resco_ingolstadt21`: Mạng lưới thành phố Ingolstadt 21 nút giao.
- `single_intersection`: Nút giao đơn lập 2 chiều chuẩn thử nghiệm.

### 🔹 Ví Dụ Lệnh Import:
```bash
# Import kịch bản RESCO Grid 4x4
python src/tools/import_sumo_scenario.py --preset grid4x4

# Import kịch bản Cologne8 (TAPASCologne)
python src/tools/import_sumo_scenario.py --preset cologne8

# Import kịch bản Ingolstadt21
python src/tools/import_sumo_scenario.py --preset ingolstadt21
```

---

## 🛠️ 2. Import File `.net.xml` Tùy Chỉnh (Custom SUMO Network Files)

Nếu bạn có file `.net.xml` tùy chỉnh (tải từ OpenStreetMap hoặc tạo bằng SUMO `netconvert` / `osmWebWizard.py`):

```bash
python src/tools/import_sumo_scenario.py --net /path/to/my_map.net.xml --rou /path/to/my_map.rou.xml --scenario-id my_custom_map
```

Sau khi chạy lệnh trên:
1. File Topology Contract JSON sẽ được tự động tạo tại `contracts/topology/<scenario_id>.json`.
2. File cấu hình `.sumocfg` được tạo tại `services/simulator/sumo_configs/<scenario_id>.sumocfg`.
3. Biến môi trường `EDGEFLOW_TOPOLOGY=<scenario_id>` trong file `.env` được cập nhật tự động.

---

## ⚙️ 3. Khởi Chạy Mô Phỏng Với Kịch Bản Mới (Running Simulation)

### 🔹 Khởi chạy bằng Docker Compose (Khuyên dùng):
```bash
# Đảm bảo file .env đã có EDGEFLOW_TOPOLOGY=<scenario_id> và USE_SUMO=true
docker compose --profile simulation up --build
```

### 🔹 Khởi chạy trực tiếp bằng Python local:
```powershell
# Ví dụ chạy kịch bản grid4x4 với SUMO
$env:EDGEFLOW_TOPOLOGY="grid4x4"
$env:USE_SUMO="true"

# 1. Chạy Simulator (Mô phỏng SUMO kỹ thuật số)
python services/simulator/main.py

# 2. Chạy Graph-Control (Tính toán áp lực Max-Pressure thời gian thực)
python services/graph-control/main.py
```

---

## 🧪 4. Kiểm Thử & Kiểm Tra Tính Tương Thích (Verification)

Để kiểm tra tính hợp lệ của tất cả Topology JSON contracts và SumoConverter:
```bash
python -m pytest tests/unit
```
