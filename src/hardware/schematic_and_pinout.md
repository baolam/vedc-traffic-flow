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
| **Nút ngắt khẩn cấp (Safe-Stop)** | Nút nấm tự giữ, tiếp điểm **NC** | **J1: `GPIO 16`**, **J2: `GPIO 4`** | Pull-up trong chip; **HIGH = đang ấn** (NC hở) | - |

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
       |  GPIO 4* +--[ NC Nút Safe-Stop ]------> GND   (* J1: GPIO 16)
       |  GND     +-----------------------------> GND
       +----------+
```

---

## 🛡️ 3. Quy Chuẩn Đấu Dây & An Toàn Thiết Bị

1. **Bảo vệ chống dòng ngược & quá áp**: Dùng diode Schottky 1N5819 (sụt áp ~0,3 V) trên đường nguồn 5V vào chân 5V/VIN của ESP32 để chống cắm ngược cực, kèm cầu chì tự phục hồi (PTC) 0,5–1 A. Không dùng 1N4007: sụt ~0,8 V làm VIN chỉ còn ~4,2 V. Rút nguồn 5V ngoài khi cắm cáp micro-USB để nạp firmware.
2. **Điện trở hạn dòng cho LED**: Toàn bộ các ngõ ra điều khiển LED đều được nối qua điện trở hạn dòng $220\ \Omega$ (giới hạn dòng điện dưới $15\text{mA}$ cho mỗi chân GPIO).
3. **Cơ chế kéo chân (Pull-Up)**: Chân Safe-Stop (`GPIO 4` ở J2, `GPIO 16` ở J1, đặt bằng cờ `SAFE_STOP_GPIO` trong `platformio.ini`) sử dụng điện trở kéo lên nội bộ `INPUT_PULLUP` để chống nhiễu trường điện từ xung quanh mô hình.
4. **Module đèn mắc song song**: Module hướng Bắc và Nam dùng chung 3 chân (GPIO 23/22/21), Đông và Tây dùng chung 3 chân (GPIO 19/18/5). Module đèn có sẵn điện trở hạn dòng, dòng ~5–6 mA/LED ở 3,3 V, nên mỗi chân GPIO kéo ~12 mA. Không cần thêm trở 220 Ω hay ULN2803 khi dùng module.
5. **Nút Safe-Stop**: Nút nấm tự giữ, nối qua tiếp điểm **NC** nên nhả nút thì chân ở LOW, ấn nút thì chân lên HIGH (cờ `SAFE_STOP_PRESSED_LEVEL=HIGH`). Đứt dây cũng thành HIGH, tức tự vào dừng khẩn. Firmware đọc theo mức (có chống dội 50 ms): đang ấn thì vàng nhấp nháy và từ chối lệnh; nhả ra thì ALL_RED 2 s rồi mới xanh lại. Đổi sang tiếp điểm NO thì bỏ cờ đó. Chi tiết: `HUONG_DAN_LAP_RAP.md` mục 3a.

---

## 📈 4. Bằng Chứng Thời Gian Tín Hiệu (Output Trace)

- **Serial trace từ MCU**: Mỗi lần đầu ra đổi, firmware in một dòng `TRACE,<millis>,<node>,<ns>,<ew>,<label>` (`ns`/`ew` ∈ `R`,`Y`,`G`,`-`). Ghi lại bằng: `pio device monitor -e J1 | tee trace_J1.csv`.
- **Logic analyzer 8 kênh (PulseView)**: CH0–CH5 → GPIO 23, 22, 21, 19, 18, 5; CH6 → chân safe-stop (GPIO 4 ở J2, GPIO 16 ở J1); GND chung. Dùng để chứng minh độc lập: không có lúc nào hai hướng cùng xanh, vàng ≥ 3 s, all-red ≥ 2 s.

## 🔧 5. Build & Nạp Firmware (PlatformIO)

```bash
cd src/hardware
cp secrets.example.ini secrets.ini        # sửa WIFI_SSID / WIFI_PASS / MQTT_BROKER (git-ignored)
pio run -e J1 -t upload                   # board NodeMCU-32S (CH340, cổng micro-USB) cho nút J1
pio run -e J2 -t upload                   # board cho nút J2
pio device monitor -e J1                  # log 115200 baud
```
Không cài PlatformIO thì dùng `uvx --from platformio pio ...`. Nếu không nạp được, giữ nút BOOT khi log hiện `Connecting...`.
