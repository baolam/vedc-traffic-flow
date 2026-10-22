# EdgeFlow AI — Hardware Prototype & Embedded Infrastructure (VEDC 2026)

Tài liệu thiết kế kỹ thuật, sơ đồ phần cứng và mã nguồn firmware cho **Mô hình Hành lang Sa bàn Thực tế (Tabletop Corridor 2 Nút Giao J1 - J2)** — Đội thi **31µF (VEDC 2026 - Bán kết)**.

---

## 🏗️ 1. Phân Định Vai Trò Phần Cứng (Hardware Role & Responsibility)

Hệ thống phần cứng thực tế phân tách rạch ròi giữa **Tầng Nhận Thức Thông Minh (Edge AI Perception)** và **Tầng Chấp Hành An Toàn (Safety Actuation)**:

```
+-----------------------------------------------------------------------------------------+
|                                TẦNG 1: LAPTOP / SERVER CHÍNH                            |
|                            (Chạy toàn bộ dịch vụ Docker Compose)                         |
|                                                                                         |
|  • MQTT Broker (:1883)       : Trục xương sống sự kiện trung tâm (Eclipse Mosquitto)    |
|  • Graph-Control             : Bộ não tính toán thích ứng (EdgeFlow / Max-Pressure / RL)|
|  • API Backend (:8000)       : FastAPI Control Plane & Quản lý thực nghiệm               |
|  • IOC Dashboard (:3000)     : Giao diện điều hành trực quan thời gian thực (React)     |
+--------------------------------------------+--------------------------------------------+
                                             | Mạng WiFi Cục Bộ (MQTT 1883)
                     +-----------------------+-----------------------+
                     | Telemetry                                     | ControlCommand & ACK
+--------------------v--------------------+     +--------------------v--------------------+
|       TẦNG 2: RASPBERRY PI 5 (EDGE AI)  |     |   TẦNG 3: MẠCH CHẤP HÀNH VẬT LÝ (ESP32)  |
|         (services/vision)               |     |        (src/hardware/firmware)          |
|                                         |     |                                         |
| • 📷 Camera Module 3 / USB (/dev/video0) |     | • 2x Board ESP32 NodeMCU (Nút J1 & J2)  |
| • 🧠 AI Thị Giác: YOLOv8 / OpenCV DNN   |     | • 💡 8 Cụm Đèn LED Sa bàn (24 LEDs)     |
| • 🚦 Trích xuất hàng đợi theo nhánh ROI |     | • 🛡️ Safe Clearance (Green->Yel->AllRed)|
| • 📡 Bắn Telemetry lên Laptop Broker    |     | • ⏱️ Watchdog Fallback 15s khi mất mạng |
| • 🌡️ Giám sát nhiệt độ CPU & Nghẽn nhiệt|     | • 🛑 Nút Safe-Stop (J1 GPIO16, J2 GPIO4)|
+-----------------------------------------+     +-----------------------------------------+
```

### 📌 1. Tầng 1: Laptop Server (Máy Chủ Điều Phối Trung Tâm)
- Chạy hệ thống Docker microservices: **Central MQTT Broker (:1883)**, **Graph-Control**, **API Backend (:8000)** và **IOC Dashboard (:3000)**.
- Thu nhận dữ liệu Telemetry từ Raspberry Pi, chạy thuật toán thích ứng `EdgeFlowController` và gửi lệnh `ControlCommand` đến các board ESP32.

### 📌 2. Tầng 2: Raspberry Pi 5 (Thị Giác AI Nhận Diện Sa Bàn)
- **Mã nguồn vận hành**: [`services/vision/`](file:///e:/vedc-traffic-flow/services/vision) (triển khai native trên Raspberry Pi OS hoặc Docker).
- **Nhiệm vụ chính**:
  1. **Ghi hình trực tiếp**: Kết nối với *Raspberry Pi Camera Module 3* (CSI) hoặc camera USB qua giao tiếp V4L2 (`/dev/video0`).
  2. **Thị giác AI cục bộ (Edge AI Perception)**: Chạy mô hình YOLOv8 Nano / OpenCV DNN nhận diện và theo vết mô hình xe trên sa bàn.
  3. **Trích xuất Hàng đợi & Dòng xe**: Phân bổ phương tiện vào từng vùng quan tâm (ROI) của các nhánh tiếp cận (`J1_N_IN`, `J1_S_IN`, `J2_E_IN`,...).
  4. **Phát hành Bản tin Telemetry**: Đóng gói dữ liệu hàng đợi và độ tin cậy vào bản tin chuẩn hoá `edgeflow/v1/telemetry/{node_id}` gửi về Laptop Broker.
  5. **Giám sát sức khỏe phần cứng**: Đọc nhiệt độ CPU (`/sys/class/thermal/thermal_zone0/temp`), phát hiện nguy cơ nghẽn nhiệt (*thermal throttling*) và bắn cảnh báo định kỳ lên `edgeflow/v1/health/vision`.

### 📌 3. Tầng 3: ESP32 Node 1 & Node 2 (Chấp Hành Đèn Tín Hiệu)
- **Mã nguồn vận hành**: [`src/hardware/firmware/esp32_signal_controller.ino`](file:///e:/vedc-traffic-flow/src/hardware/firmware/esp32_signal_controller.ino) (nạp vào 2 board vi điều khiển ESP32 cho ngã tư $J_1$ và $J_2$).
- **Nhiệm vụ chính**:
  1. **Lắng nghe lệnh điều khiển**: Nhận `ControlCommand` từ Laptop Server qua MQTT topic `edgeflow/v1/control/{node_id}/command`.
  2. **Thực thi chuyển pha an toàn tuyệt đối (Hardware Clearance)**: Bắt buộc đi qua chu trình $\text{GREEN} \rightarrow \text{YELLOW (3.0s)} \rightarrow \text{ALL-RED (2.0s)} \rightarrow \text{GREEN mới}$.
  3. **Phản hồi xác thực (ControlACK)**: Bắn các trạng thái `ACCEPTED`, `APPLIED`, `REJECTED`, `EXPIRED` về Laptop Server.
  4. **Tự chủ khi mất mạng (Autonomous Watchdog Fallback)**: Nếu mất kết nối với Laptop Server quá $5.0\text{s}$, tự chuyển sang chu kỳ cố định cục bộ ($15\text{s}$ xanh mỗi hướng) để duy trì giao thông.
  5. **Nút ngắt khẩn cấp (Physical Safe-Stop)**: Khi nhấn nút cơ (J1: `GPIO 16`, J2: `GPIO 4`, tiếp điểm NC, xem `HUONG_DAN_LAP_RAP.md` mục 3a), lập tức ngắt toàn bộ đèn và chuyển sang nhấp nháy đèn vàng cảnh báo nguy hiểm.

---

## 📁 Cấu Trúc Phân Hệ Hardware (`src/hardware/`)

```
src/hardware/
├── __init__.py
├── README.md                      # [Tài liệu này] Tổng quan vai trò Raspberry Pi & ESP32
├── schematic_and_pinout.md        # Sơ đồ đấu nối mạch điện, chân GPIO ESP32 và LED
└── firmware/
    └── esp32_signal_controller.ino # Mã nguồn C++/Arduino Firmware nạp vào vi điều khiển ESP32
```

> [!NOTE]
> Mã nguồn thị giác nhúng chạy trên Raspberry Pi 5 được đặt tập trung và duy trì chuẩn tại **[`services/vision/`](file:///e:/vedc-traffic-flow/services/vision)**.

---

## 📋 Bảng Dự Toán & Định Mức Thiết Bị (BOM Reference)

| Thiết bị / Linh kiện | Số lượng | Đơn giá tham khảo (VND) | Thành tiền (VND) | Vai trò trong hệ thống |
|---|---|---|---|---|
| **Raspberry Pi 5 (4GB RAM)** | 1 bộ | 4,698,000 | 4,698,000 | Chạy AI thị giác [`services/vision`](file:///e:/vedc-traffic-flow/services/vision), Broker & Coordinator |
| **Raspberry Pi Camera Module 3** | 1 cái | 864,000 | 864,000 | Camera 12MP góc rộng ghi hình sa bàn ngã tư |
| **ESP32 NodeMCU Board** | 2 cái | 190,000 | 380,000 | Vi điều khiển chấp hành đèn cho nút $J_1$ và $J_2$ |
| **Mô-đun Đèn Tín Hiệu (Đỏ/Vàng/Xanh)** | 8 cụm | 8,000 | 64,000 | 4 cụm đèn (12 bóng LED) cho mỗi ngã tư |
| **Nguồn DC 5V/3A, dây nối & Jack** | 1 bộ | 250,000 | 250,000 | Cung cấp nguồn ổn định chống sụt áp cho mạch |
| **Khung mô hình sa bàn & giá đỡ camera** | 1 bộ | 600,000 | 600,000 | Khung cố định góc nhìn camera vuông góc sa bàn |
| **Tổng cộng dự toán** | | | **6,856,000 VND** | Đúng hạn mức định mức dự toán VEDC 2026 |
