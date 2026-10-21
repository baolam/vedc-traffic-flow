# EdgeFlow AI — Development, Deployment & Demo Guide

Hướng dẫn chi tiết quy trình phát triển, kiểm thử cục bộ và thiết lập môi trường trình diễn thực tế theo kiến trúc **3 Tầng Phân Tán (Laptop Server $\leftrightarrow$ Raspberry Pi 5 $\leftrightarrow$ ESP32 Hardware)**.

> [!TIP]
> **Xem chi tiết các kịch bản và chế độ chạy:** [`docs/SYSTEM_RUN_MODES.md`](file:///e:/vedc-traffic-flow/docs/SYSTEM_RUN_MODES.md) | **Hướng dẫn Docker Pi 5:** [`docs/RASPBERRY_PI_DISTRIBUTED_GUIDE.md`](file:///e:/vedc-traffic-flow/docs/RASPBERRY_PI_DISTRIBUTED_GUIDE.md).

---

## 💻 1. Thiết Lập Tầng 1: Laptop Server (Chạy Docker Microservices)

Laptop đóng vai trò là **Máy Chủ Điều Phối Trung Tâm (Central Server)**:

### 1.1. Cấu hình biến môi trường
- **Windows PowerShell**:
  ```powershell
  Copy-Item .env.example .env
  ```
- **Linux / macOS**:
  ```bash
  cp .env.example .env
  ```

### 1.2. Khởi chạy toàn bộ dịch vụ trung tâm bằng Docker Compose
```bash
# Khởi chạy chế độ mô phỏng hoàn chỉnh (Broker, Control, API, Dashboard, SUMO)
docker compose up -d --build

# Xem log các dịch vụ thời gian thực
docker compose logs -f
```

### 1.3. Khởi chạy riêng lẻ bằng Python CLI (Không cần Docker)
```bash
# Terminal 1: Chạy MQTT Broker (nếu cài cục bộ mosquitto)
mosquitto -v

# Terminal 2: Chạy bộ điều khiển thích ứng (Graph-Control)
python services/graph-control/main.py

# Terminal 3: Chạy Control Plane REST API
python services/api/main.py

# Terminal 4: Mở Dashboard điều hành Web (React)
cd services/dashboard && npm start
# Truy cập giao diện tại: http://localhost:3000
```

---

## 🍓 2. Thiết Lập Tầng 2: Raspberry Pi 5 (Thị Giác AI Sa Bàn)

Raspberry Pi 5 đóng vai trò là **Edge AI Perception Node** ghi hình sa bàn mô hình xe:

### 2.1. Kết nối phần cứng
- Cắm **Raspberry Pi Camera Module 3** vào cổng CSI hoặc cắm Camera USB vào cổng USB 3.0.
- Kết nối Raspberry Pi 5 vào cùng mạng WiFi cục bộ với Laptop Server.

### 2.2. Khởi chạy tiến trình nhận diện thị giác
```bash
# Trên Raspberry Pi 5 terminal
cd services/vision

# Cài đặt thư viện phụ thuộc nhẹ
pip install -r requirements.txt

# Khởi chạy dịch vụ thị giác bắn dữ liệu về Laptop
python main.py --video 0 --mqtt-host <IP_LAPTOP_SERVER> --node-id J1
```
> [!TIP]
> Dịch vụ sẽ tự động đọc cảm biến nhiệt độ CPU của chip Broadcom BCM2712 trên Pi 5 và báo cáo trạng thái định kỳ lên topic `edgeflow/v1/health/vision`.

---

## ⚡ 3. Thiết Lập Tầng 3: ESP32 Hardware Nodes (Chấp Hành Đèn)

Hai board vi điều khiển ESP32 đóng vai trò là **Bộ Chấp Hành Tín Hiệu Đèn Giao Thông Cục Bộ**:

### 3.1. Đấu nối mạch điện
- Tham khảo sơ đồ chân chi tiết tại: [`src/hardware/schematic_and_pinout.md`](file:///e:/vedc-traffic-flow/src/hardware/schematic_and_pinout.md).
- Kết nối 4 cụm đèn (12 bóng LED) cho mỗi nút giao vào các chân GPIO 23, 22, 21 (Bắc-Nam) và 19, 18, 5 (Đông-Tây).

### 3.2. Cấu hình & Nạp Firmware
- Mở file [`src/hardware/firmware/esp32_signal_controller.ino`](file:///e:/vedc-traffic-flow/src/hardware/firmware/esp32_signal_controller.ino) trong Arduino IDE / PlatformIO.
- Đặt cấu hình `NODE_ID`:
  - **Board 1 (Ngã tư J1)**: `#define NODE_ID "J1"`
  - **Board 2 (Ngã tư J2)**: `#define NODE_ID "J2"`
- Đặt `MQTT_BROKER` trỏ về IP của Laptop Server (ví dụ: `192.168.1.100`).
- Nạp code vào ESP32 qua cổng micro-USB (NodeMCU-32S CH340). Khuyến nghị dùng PlatformIO: `cd src/hardware && pio run -e J1 -t upload` (xem `src/hardware/schematic_and_pinout.md`).

---

## 🧪 4. Quy Trình Kiểm Thử Chuẩn (Standardized Testing)

Hệ thống được trang bị bộ kiểm thử tự động toàn diện:

```bash
# 1. Kiểm thử Schema & Hợp đồng giao tiếp (Bắt buộc chạy trước khi commit)
pytest tests/unit/test_contracts.py

# 2. Kiểm thử logic máy trạng thái an toàn chuyển pha (State Machine)
pytest tests/unit/test_actuator_state_machine.py

# 3. Kiểm thử toàn bộ Unit Tests (88 tests)
pytest tests/unit

# 4. Kiểm thử tích hợp độ trễ End-to-End
pytest tests/integration/test_end_to_end_latency.py
```

---

## 📐 5. Dữ Liệu & Bản Đồ Giao Thông TP.HCM

```bash
# Xây dựng đồ thị camera Delaunay & OSRM
python src/graph/delaunay_builder.py --input data/raw/cameras_hcm_full.json --output data/processed/camera_traffic_graph_delaunay.pkl

# Xuất bản đồ tương tác Folium ra file HTML
python src/visualization/map_visualizer.py
```
Mở file `output/camera_graph_map.html` trên trình duyệt để quan sát mạng lưới camera TP.HCM.
