# Hướng dẫn lắp phần cứng nút đèn J1/J2 (bản sa bàn bạt, 21/10/2026)

Viết cho đúng linh kiện đội đã mua. Chân lấy từ `firmware/esp32_signal_controller.ino`. Bản vẽ HA.1–HA.4 trong `docs/thiet_ke/3.3_kien_truc/` vẫn đúng về chân nhưng vẽ tấm A0 và camera trên trụ (đã bỏ).

## 1. Linh kiện mỗi nút (J1 và J2 giống hệt nhau)

| Linh kiện | Số lượng | Ghi chú |
|---|---|---|
| ESP32 **Ai-Thinker NodeMCU-32 V1.3** (module ESP32-S, 38 chân, CH340, micro-USB) | 1 | J1 và J2 đã nạp firmware, đã chạy vòng kín 21/10 |
| Module đèn giao thông 4 chân **GND · R · Y · G** (in "V1224") | 4 (Bắc, Nam, Đông, Tây) | Có sẵn điện trở trên mạch, mức HIGH là sáng. **Không cần thêm trở 220 Ω hay ULN2803** |
| Cáp lên trụ (CAT5e 8 lõi, lõi đặc) | ~1,0 m | Cắm thẳng lõi vào breadboard |
| Breadboard + dây dupont | | |
| Nút dừng khẩn (tùy chọn) | 1 | Không lắp thì để trống chân 4, đèn chạy bình thường |

## 2. Chân trên board NodeMCU-32

Tất cả chân cần dùng nằm trên **một hàng**: hàng có in `GND P23 P22 TX RX P21 GND P19 P18 P5 … P4 … P2`. Nhìn từ mặt có chip, anten hướng lên trên, hàng này nằm **bên phải**. Thứ tự từ phía anten xuống:

```
1 GND · 2 P23 · 3 P22 · 4 TX · 5 RX · 6 P21 · 7 GND · 8 P19 · 9 P18 · 10 P5 · 11 P17 · 12 P16 · 13 P4 · 14 P0 · 15 P2 · …
```

Không cắm gì vào TX, RX, P0, P2 (chân nạp/khởi động).

## 3. Bảng nối dây (mỗi nút)

| Tín hiệu | Chân ESP32 | Lõi cáp (T568B, đề xuất) | Module |
|---|---|---|---|
| Bắc+Nam đỏ | **P23** | 1 cam-trắng | chân **R** của module Bắc **và** Nam |
| Bắc+Nam vàng | **P22** | 2 cam | chân **Y** của Bắc và Nam |
| Bắc+Nam xanh | **P21** | 3 xanh lá-trắng | chân **G** của Bắc và Nam |
| Đông+Tây đỏ | **P19** | 4 xanh dương | chân **R** của Đông **và** Tây |
| Đông+Tây vàng | **P18** | 5 xanh dương-trắng | chân **Y** của Đông và Tây |
| Đông+Tây xanh | **P5** | 6 xanh lá | chân **G** của Đông và Tây |
| GND | **GND** (chân 1 hoặc 7) | 7 nâu-trắng | chân **GND** của cả 4 module |
| (dự phòng) | | 8 nâu | |
| Dừng khẩn | **P4** ↔ GND | dây riêng | nhấn = nối P4 xuống GND |

- Hai module đối diện **mắc song song**: cùng chân R nối chung, Y chung, G chung. Mỗi chân GPIO kéo khoảng 12 mA, trong giới hạn.
- Ở đầu trụ, mỗi lõi tín hiệu rẽ thành 2 dây tới 2 module đối diện; lõi GND rẽ ra cả 4.
- Pi và ESP32 **không nối dây nào với nhau**, kể cả GND. Chúng chỉ nói chuyện qua Wi-Fi.

## 4. Nguồn

- Demo: cấp nguồn mỗi ESP32 qua cổng micro-USB (cục sạc 5 V hoặc laptop). Module đèn lấy điện từ chân GPIO, không cần nguồn riêng.
- Nếu dùng nguồn 5 V ngoài vào chân 5V: qua diode 1N5819 + cầu chì PTC, và **rút nguồn ngoài khi cắm USB để nạp**.

## 5. Lắp từng bước, lắp đến đâu kiểm đến đó

**Rút USB của ESP32 trước mỗi lần cắm/rút dây.** Lệnh kiểm chạy trên laptop khi Docker (`docker compose --profile hardware up -d`) đang chạy, `$PY` là Python có `paho-mqtt`, `jsonschema`, `pydantic`:

```bash
# Ai đang online, pha hiện tại, Wi-Fi
$PY src/hardware/demo/laptop_command_test.py --mqtt-host localhost status
# Đổi pha NS/EW mỗi 12 s để nhìn đèn
$PY src/hardware/demo/laptop_command_test.py --mqtt-host localhost cycle J1 --period 12
```

Muốn điều khiển tay thì tạm dừng graph-control (`docker compose stop graph-control`), xong thì `start` lại; nếu không, lệnh của graph-control sẽ chen vào.

| Bước | Lắp | Kiểm: đúng khi |
|---|---|---|
| 1 | J1: module **Bắc + Nam** vào P23/P22/P21 + GND | Pha NS: Bắc và Nam cùng xanh. Đổi pha: xanh → vàng 3 s → đỏ |
| 2 | J1: module **Đông + Tây** vào P19/P18/P5 + GND | Khi NS xanh thì EW đỏ và ngược lại; giữa hai pha có 2 s cả 4 hướng đỏ. **Không bao giờ** hai hướng cùng xanh |
| 3 | J2: lặp lại bước 1–2 | Như trên |
| 4 | Nút dừng khẩn (nếu có) | Nhấn: nút đó về đỏ hết, `status` báo `SAFE_STOP`. Nhả: chạy lại |
| 5 | Bật lại graph-control, chạy cả vòng 3 phút, chấm bằng `flow_report.py` (xem `demo/README.md`) | `RESULT: PASS`, đèn trên sa bàn khớp dashboard |

**Sai thường gặp:**

- Sáng sai màu: đổi chỗ dây R/Y/G, không sửa code.
- Không sáng gì: thiếu dây GND chung, hoặc cắm ngược module (GND vào chân tín hiệu).
- Đèn xanh Đông–Tây chớp một cái lúc ESP32 khởi động: P5 là chân strapping của ESP32. Ghi lại nếu thấy; không ảnh hưởng chạy.
