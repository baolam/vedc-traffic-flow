# Hướng dẫn lắp phần cứng nút đèn J1/J2 (bản sa bàn bạt, cập nhật 23/10/2026)

Viết cho đúng linh kiện đội đã mua. Chân lấy từ `firmware/esp32_signal_controller.ino`. Bản vẽ HA.1–HA.4 trong `docs/thiet_ke/3.3_kien_truc/` vẫn đúng về chân nhưng vẽ tấm A0 và camera trên trụ (đã bỏ).

## 1. Linh kiện mỗi nút (J1 và J2 giống hệt nhau)

| Linh kiện | Số lượng | Ghi chú |
|---|---|---|
| ESP32 **Ai-Thinker NodeMCU-32 V1.3** (module ESP32-S, 38 chân, CH340, micro-USB) | 1 | J1 và J2 đã nạp firmware, đã chạy vòng kín 21/10 |
| Module đèn giao thông 4 chân **GND · R · Y · G** (in "V1224") | 4 (Bắc, Nam, Đông, Tây) | Có sẵn điện trở trên mạch, mức HIGH là sáng. **Không cần thêm trở 220 Ω hay ULN2803** |
| Cáp lên trụ (CAT5e 8 lõi, lõi đặc) | ~1,0 m | Cắm thẳng lõi vào breadboard |
| Breadboard + dây dupont | | |
| Nút dừng khẩn (nút nấm đỏ tự giữ, xoay để nhả) | 1 | Đang nối vào tiếp điểm **NC** (thường đóng). Không lắp nút thì firmware hiện tại sẽ báo dừng khẩn: xem mục 3a |

## 2. Chân trên board NodeMCU-32

Tất cả chân cần dùng nằm trên **một hàng**: hàng có in `GND P23 P22 TX RX P21 GND P19 P18 P5 … P4 … P2`. Nhìn từ mặt có chip, anten hướng lên trên, hàng này nằm **bên phải**. Thứ tự từ phía anten xuống:

```
1 GND · 2 P23 · 3 P22 · 4 TX · 5 RX · 6 P21 · 7 GND · 8 P19 · 9 P18 · 10 P5 · 11 P17 · 12 P16 · 13 P4 · 14 P0 · 15 P2 · …
```

Không cắm gì vào TX, RX, P0, P2 (chân nạp/khởi động).

**Đếm theo chữ in cạnh chân, không đếm lỗ.** Giữa P22 và P21 có TX, RX; giữa P21 và P19 có một chân GND. Ngày 22/10 J1 cắm dây P21 vào RX nên cả chuỗi phía sau lệch một chân: hai module sáng đỏ và xanh cùng lúc, không đổi theo pha.

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
| Dừng khẩn | **J1: P16**, **J2: P4** ↔ GND | dây riêng | qua tiếp điểm **NC** của nút (xem 3a) |

- Hai module đối diện **mắc song song**: cùng chân R nối chung, Y chung, G chung. Mỗi chân GPIO kéo khoảng 12 mA, trong giới hạn.
- Ở đầu trụ, mỗi lõi tín hiệu rẽ thành 2 dây tới 2 module đối diện; lõi GND rẽ ra cả 4.
- Pi và ESP32 **không nối dây tín hiệu nào với nhau**. Chúng chỉ nói chuyện qua Wi-Fi/MQTT. Cáp USB từ Pi sang ESP32 (từ 22/10) chỉ để cấp nguồn, xem log và nạp code.

### 3a. Nút dừng khẩn: chân và kiểu tiếp điểm (22/10)

| Nút | Chân | Tiếp điểm | Cờ build trong `platformio.ini` |
|---|---|---|---|
| J1 | **P16** (đã hàn vào đây thay vì P4) | NC | `[env:J1]`: `-D SAFE_STOP_GPIO=16` |
| J2 | **P4** | NC | (mặc định chân 4) |
| Cả hai | | | `[env]`: `-D SAFE_STOP_PRESSED_LEVEL=HIGH` |

- Nút nấm đỏ thường có tiếp điểm **NC** (block đỏ, số 1–2) và **NO** (block xanh lá, số 3–4). Cả hai nút đang nối NC: nhả nút thì mạch đóng, chân về GND (LOW), đèn chạy; ấn nút thì mạch hở, chân lên HIGH qua điện trở kéo lên trong chip, firmware vào dừng khẩn.
- NC an toàn hơn: **đứt dây nút cũng tự vào dừng khẩn**. Hệ quả: board không gắn nút sẽ luôn ở dừng khẩn. Muốn chạy không có nút thì nối tắt chân nút xuống GND, hoặc bỏ cờ `SAFE_STOP_PRESSED_LEVEL=HIGH` rồi nạp lại.
- Đổi nút sang tiếp điểm NO thì bỏ cờ `SAFE_STOP_PRESSED_LEVEL=HIGH`. Hàn lại J1 sang P4 thì bỏ cờ `SAFE_STOP_GPIO=16`. Sửa xong phải nạp lại board.
- Kiểm nhanh: ấn nút, `status` phải báo `SAFE_STOP`; nhả nút, phải về `HEALTHY` hoặc `FALLBACK_AUTONOMOUS`.

## 4. Nguồn

- Demo: cấp nguồn mỗi ESP32 qua cổng micro-USB. Từ 22/10 cắm cả hai vào **cổng USB của Pi 5**. Pi cần adapter 5 V 5 A (27 W) để cổng USB cấp đủ dòng. Module đèn lấy điện từ chân GPIO, không cần nguồn riêng.
- Đã cấp qua USB thì **không nối thêm dây 5 V chung** giữa hai board, chỉ nối GND nếu cần. Hai nguồn 5 V chập nhau là nghi phạm chính khiến USB rớt liên tục lúc nạp code ngày 22/10.
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
| 4 | Nút dừng khẩn (mục 3a) | Nhấn: cả 4 hướng **vàng nhấp nháy**, `status` báo `SAFE_STOP`, mọi lệnh bị `REJECTED: Safe-stop is engaged`. Xoay nhả: đỏ hết 2 s rồi xanh lại |
| 5 | Bật lại graph-control, chạy cả vòng 3 phút, chấm bằng `flow_report.py` (xem `demo/README.md`) | `RESULT: PASS`, đèn trên sa bàn khớp dashboard |

**Sai thường gặp:**

- Sáng sai màu: đổi chỗ dây R/Y/G, không sửa code.
- Không sáng gì: thiếu dây GND chung, hoặc cắm ngược module (GND vào chân tín hiệu).
- Một module sáng 2 màu cùng lúc hoặc không đổi theo pha: dây lệch chân (xem mục 2). Dò bằng cách bật từng chân một (firmware kiểm chân) và xem module nào sáng.
- Nút ấn mà không có gì xảy ra: dây nút không ở đúng chân (J1 là P16), hoặc 2 dây nằm trên 2 block tiếp điểm khác nhau.
- Nhả nút thì vàng nhấp nháy, ấn thì chạy: nút nối NC mà firmware đang đọc kiểu NO, hoặc ngược lại (mục 3a).
- Đèn xanh Đông–Tây chớp một cái lúc ESP32 khởi động: P5 là chân strapping của ESP32. Ghi lại nếu thấy; không ảnh hưởng chạy.
