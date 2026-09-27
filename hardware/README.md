# EdgeFlow AI - Hardware Prototype & Embedded Infrastructure (VEDC 2026)

Tài liệu hướng dẫn và mã nguồn triển khai mô hình phần cứng nhúng thực tế cho **Đội 31µF (VEDC 2026 - Bán kết)**.

---

## 🏗️ 1. Tổng Quan Kiến Trúc Mô Hình Phần Cứng

Mô hình thực tế triển khai một hành lang giao thông gồm **2 Nút Giao Thông Cục Bộ (Intersection Corridor)** được điều khiển bởi 2 board vi điều khiển ESP32 độc lập kết nối qua mạng cục bộ (WiFi / MQTT) với 1 bộ điều phối trung tâm (Raspberry Pi 5):

```
                        +------------------------------------+
                        |       Raspberry Pi 5 (Edge AI)     |
                        | - Camera Ingestion & YOLO Inference|
                        | - Local MQTT Broker (:1883)        |
                        | - Graph-Control / Coordinator      |
                        +-----------------+------------------+
                                          | Local Network (MQTT)
                    +---------------------+---------------------+
                    |                                           |
         +----------v----------+                     +----------v----------+
         | ESP32 Signal Node 1 |                     | ESP32 Signal Node 2 |
         | (Nút giao J1)       |                     | (Nút giao J2)       |
         | - 4 Cụm LED (12 LEDs|                     | - 4 Cụm LED (12 LEDs|
         | - Local Safe Timing |                     | - Local Safe Timing |
         | - Hardware Watchdog |                     | - Hardware Watchdog |
         | - Fallback Schedule |                     | - Fallback Schedule |
         +---------------------+                     +---------------------+
```

---

## 📋 2. Bảng Dự Toán & Định Mức Thiết Bị (BOM Reference)

| Thiết bị / Linh kiện | Số lượng | Đơn giá tham khảo (VND) | Thành tiền (VND) | Ghi chú kỹ thuật |
|---|---|---|---|---|
| **Raspberry Pi 5 (4GB RAM)** | 1 bộ | 4,698,000 | 4,698,000 | Chạy AI thị giác YOLO & Broker điều phối |
| **Raspberry Pi Camera Module 3** | 1 cái | 864,000 | 864,000 | Cảm biến 12MP, góc rộng, Auto-focus |
| **ESP32 NodeMCU Board** | 2 cái | 190,000 | 380,000 | Vi điều khiển chấp hành tín hiệu đèn cục bộ |
| **Mô-đun Đèn Tín Hiệu (3 màu: Đỏ/Vàng/Xanh)** | 8 cụm | 8,000 | 64,000 | 4 cụm cho mỗi nút giao (12V/5V với điện trở 220Ω) |
| **Dây nối, nguồn hạ thế 5V/3A & Jack nguồn** | 1 bộ | 250,000 | 250,000 | Cung cấp nguồn ổn định và chống sụt áp |
| **Khung mô hình sa bàn & giá đỡ camera** | 1 bộ | 600,000 | 600,000 | Khung nhôm/mica cố định góc nhìn camera |
| **Tổng cộng dự toán** | | | **6,856,000 VND** | Phù hợp với hạn mức dự toán VEDC 2026 |

---

## 🛡️ 3. Cơ Chế An Toàn & Dự Phòng Cục Bộ (Failsafe & Fallback)

1. **Bảo vệ thời gian chuyển pha an toàn (Hardware Clearance Time)**:
   - Tuyệt đối không bao giờ chuyển trực tiếp Xanh hướng này sang Xanh hướng khác.
   - Bắt buộc thực thi chu kỳ: $\text{GREEN} \rightarrow \text{YELLOW (3.0s)} \rightarrow \text{ALL-RED (2.0s)} \rightarrow \text{GREEN (mới)}$.
2. **Cơ chế tự chủ khi mất kết nối (Loss-of-Coordinator Local Fallback)**:
   - Nếu mất kết nối MQTT hoặc không nhận được lệnh từ Pi trong quá 5.0 giây, ESP32 tự động kích hoạt **Local Fallback Fixed-Time Schedule** (chu kỳ xanh 15s cho mỗi hướng) để duy trì giao thông thông suốt.
   - Khi mạng khôi phục, tự động chuyển về chế độ thích ứng (Adaptive Mode).
3. **Nút ngắt khẩn cấp (Safe-Stop)**:
   - Ngắt nguồn cấp đèn tín hiệu và chuyển toàn bộ sang nhấp nháy đèn vàng cảnh báo khi có sự cố.
