# Sơ Đồ Nguyên Lý Mạch & Bảng Gán Chân GPIO (Schematic & Pinout)

Tài liệu thiết kế chi tiết mạch điều khiển chấp hành tín hiệu giao thông 2 nút giao (J1 & J2) sử dụng vi điều khiển **ESP32 NodeMCU**.

---

## 🔌 1. Bảng Gán Chân GPIO Cho Nút Giao (ESP32 Pinout Mapping)

Mỗi nút giao ngã tư gồm 4 hướng tiếp cận (**Bắc - N, Nam - S, Đông - E, Tây - W**).
- Pha Bắc - Nam (NS): Đèn Bắc và Nam đồng pha.
- Pha Đông - Tây (EW): Đèn Đông và Tây đồng pha.

### 🔹 Bảng Chân GPIO Điều Khiển Đèn Tín Hiệu (Mỗi nút giao J1 / J2)

| Hướng tiếp cận | Màu đèn | Chân GPIO ESP32 | Mức logic kích hoạt | Điện trở hạn dòng |
|---|---|---|---|---|
| **Bắc & Nam (NS)** | 🔴 Đỏ (Red) | `GPIO 23` | HIGH (3.3V / 5V) | 220 Ω |
| **Bắc & Nam (NS)** | 🟡 Vàng (Yellow) | `GPIO 22` | HIGH (3.3V / 5V) | 220 Ω |
| **Bắc & Nam (NS)** | 🟢 Xanh (Green) | `GPIO 21` | HIGH (3.3V / 5V) | 220 Ω |
| **Đông & Tây (EW)** | 🔴 Đỏ (Red) | `GPIO 19` | HIGH (3.3V / 5V) | 220 Ω |
| **Đông & Tây (EW)** | 🟡 Vàng (Yellow) | `GPIO 18` | HIGH (3.3V / 5V) | 220 Ω |
| **Đông & Tây (EW)** | 🟢 Xanh (Green) | `GPIO 5` | HIGH (3.3V / 5V) | 220 Ω |
| **Chẩn đoán / Trạng thái** | 🔵 LED Status | `GPIO 2` (Onboard) | Nhấp nháy theo nhịp | - |
| **Nút ngắt khẩn cấp (Safe-Stop)** | Nút nhấn cơ | `GPIO 4` | Pull-up (Active LOW) | 10 kΩ |

---

## ⚡ 2. Sơ Đồ Khối Nguyên Lý Điện (Circuit Block Diagram)

```
       +5V Power Supply (DC Jack)
             |
             +--------+--------------------------+
             |        |                          |
       +-----v----+   |                 +--------v-------+
       | ESP32    |   |                 | Transistor /   |
       | NodeMCU  |   |                 | ULN2803 Driver |
       |          |   |                 +--------+-------+
       |  GPIO 23 +---+--[ 220Ω ]----------------> [ LED Đỏ NS ]
       |  GPIO 22 +---+--[ 220Ω ]----------------> [ LED Vàng NS ]
       |  GPIO 21 +---+--[ 220Ω ]----------------> [ LED Xanh NS ]
       |  GPIO 19 +---+--[ 220Ω ]----------------> [ LED Đỏ EW ]
       |  GPIO 18 +---+--[ 220Ω ]----------------> [ LED Vàng EW ]
       |  GPIO 5  +---+--[ 220Ω ]----------------> [ LED Xanh EW ]
       |          |
       |  GPIO 4  +------[ Nút Safe-Stop ]-----> GND
       |  GND     +-----------------------------> GND
       +----------+
```

---

## 🛡️ 3. Quy Chuẩn Đấu Dây & An Toàn Thiết Bị

1. **Bảo vệ chống dòng ngược & quá áp**: Sử dụng diode chỉnh lưu 1N4007 trên đường nguồn 5V vào board ESP32 để chống cắm ngược cực.
2. **Điện trở hạn dòng cho LED**: Toàn bộ các ngõ ra điều khiển LED đều được nối qua điện trở hạn dòng $220\ \Omega$ (giới hạn dòng điện dưới $15\text{mA}$ cho mỗi chân GPIO).
3. **Cơ chế kéo chân (Pull-Up)**: Chân Safe-Stop (`GPIO 4`) sử dụng điện trở kéo lên nội bộ `INPUT_PULLUP` để chống nhiễu trường điện từ xung quanh mô hình.
