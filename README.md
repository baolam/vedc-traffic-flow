# 🚦 EdgeFlow AI — Adaptive Traffic Signal Control System
### 🏆 Top 10 Chung Kết Toàn Quốc Cuộc Thi Thiết Kế Điện Tử Việt Nam (VEDC 2026)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](#)
[![Edge AI](https://img.shields.io/badge/Hardware-Raspberry%20Pi%205-C51A4A.svg?logo=raspberrypi&logoColor=white)](#)
[![Simulation](https://img.shields.io/badge/Simulation-Eclipse%20SUMO-339933.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🖼️ Demo & Hình Ảnh Dự Án
<div align="center">
  <img src="docs/competition/thiet_ke/3.3_kien_truc/H3.1_so_do_khoi.png" alt="EdgeFlow AI Sơ đồ khối kiến trúc" width="90%"/>
  <p><i>Kiến trúc hệ thống điều khiển giao thông phân tán EdgeFlow AI (Top 10 VEDC 2026)</i></p>
</div>

---

## 🏛️ Kiến Trúc Hệ Thống (3 Dòng)
- **1. Tầng Thu Thập & Cảm Biến:** Camera góc cao thu nhận luồng video liên tục từ các nhánh đường tại nút giao thông đô thị phức tạp.
- **2. Tầng Xử Lý & Mô Hình AI Lõi:** Edge AI (Raspberry Pi 5) đếm mật độ phương tiện thời gian thực và kích hoạt thuật toán tối ưu hóa chu kỳ đèn dựa trên đồ thị mạng lưới $G=(V, E)$.
- **3. Tầng Chấp Hành & Trực Quan Hóa:** Vi điều khiển ESP32 điều khiển cụm đèn LED thực tế và truyền trạng thái qua giao thức MQTT lên Web Dashboard theo dõi từ xa.

---

## 🚀 Cách Chạy (Quickstart)
```bash
# 1. Clone repository
git clone https://github.com/baolam/vedc-traffic-flow.git
cd vedc-traffic-flow

# 2. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

# 3. Khởi chạy kịch bản mô phỏng hoặc hệ thống demo
python run_demo.py
```

---

## 📊 Số Liệu & Benchmark (Key Metrics)
- **Hiệu quả giảm ùn tắc:** Giảm **28.4%** thời gian chờ trung bình tại nút giao so với chu kỳ đèn cố định truyền thống.
- **Tốc độ xử lý biên (Edge AI):** Đạt **25 - 30 FPS** ổn định trực tiếp trên phần cứng nhúng Raspberry Pi 5.
- **Giải thưởng kiểm chứng:** **Top 10 Chung kết Toàn quốc Cuộc thi Thiết kế Điện tử Việt Nam (VEDC 2026)**.
