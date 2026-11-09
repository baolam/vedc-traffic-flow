# Hướng dẫn lắp phần cứng nút đèn J1–J5 (sa bàn bạt 5 nút, cập nhật 09/11/2026)

Viết cho bộ linh kiện chung kết: 5 nút, mỗi nút một ESP32-DevKitC-32U. Chân lấy từ `firmware/esp32_signal_controller.ino` và `platformio.ini`. Bản bán kết (2 nút, NodeMCU-32S, J1 hàn nút khẩn vào P16) nằm trong lịch sử git của file này.

Bản vẽ HA.1–HA.4 trong `docs/thiet_ke/3.3_kien_truc/` vẫn đúng về chân GPIO. Riêng phần cơ khí trong đó đã cũ: bản vẽ còn tấm A0, trụ và camera trên trụ.

## 1. Linh kiện mỗi nút (J1–J5 giống hệt nhau)

| Linh kiện | Số lượng | Ghi chú |
|---|---|---|
| **ESP32-DevKitC-32U** (module WROOM-32U, ăng-ten ngoài đầu IPEX, 38 chân) | 1 | Thay NodeMCU-32S của bán kết, cả J1 và J2 cũng đổi. Firmware build cho `board = esp32dev` |
| Đế ra chân 38P cho board trên | 1 | Cắm dây vào cọc của đế, không cần breadboard |
| Ăng-ten FPC dán, đầu IPEX | 1 | Cắm vào board **trước khi** cấp nguồn. Dán phẳng xuống bạt cạnh board |
| Module đèn giao thông 4 chân **GND · R · Y · G** (in "V1224") | 4 (Bắc, Nam, Đông, Tây) | Có sẵn điện trở trên mạch, mức HIGH là sáng. **Không cần thêm trở 220 Ω hay ULN2803**. Dán thẳng xuống bạt bằng băng keo 2 mặt, không còn trụ |
| Dây nối board → 4 module | | Dán băng keo sát mặt bạt |
| Nút dừng khẩn (nút nấm đỏ tự giữ, xoay để nhả) | 1 | Nối vào tiếp điểm **NC**. Thiếu nút thì board luôn ở dừng khẩn: xem mục 3a |
| Cáp USB từ hub có nguồn riêng | 1 | Chỉ cấp nguồn + xem log + nạp code. Kiểu đầu cáp theo cổng USB thật trên board (xem tận mắt trước khi mua) |

## 2. Chân trên board DevKitC

Tất cả chân cần dùng nằm trên **một hàng 19 chân**. Đặt board mặt có module hướng lên, đầu module (phía đầu IPEX) hướng ra xa người. Hàng đó nằm **bên phải**. Thứ tự từ phía module xuống:

```
1 GND · 2 IO23 · 3 IO22 · 4 TX · 5 RX · 6 IO21 · 7 GND · 8 IO19 · 9 IO18 · 10 IO5 · 11 IO17 · 12 IO16 · 13 IO4 · 14 IO0 · 15 IO2 · …
```

Thứ tự này giống hệt NodeMCU-32S của bán kết. Thứ tự lấy theo sơ đồ chân DevKitC V4 của Espressif, **chưa đối chiếu trên board thật của đội**. Khi board về, so với chữ in trên đế ra chân.

Không cắm gì vào TX, RX, IO0, IO2 (chân nạp/khởi động).

**Đếm theo chữ in cạnh chân, không đếm lỗ.** Giữa IO22 và IO21 có TX, RX. Giữa IO21 và IO19 có một chân GND. Ngày 22/10 J1 cắm dây chân 21 vào RX, nên cả chuỗi phía sau lệch một chân: hai module sáng đỏ và xanh cùng lúc, không đổi theo pha.

## 3. Bảng nối dây (mỗi nút)

| Tín hiệu | Chân ESP32 | Module |
|---|---|---|
| Bắc+Nam đỏ | **IO23** | chân **R** của module Bắc **và** Nam |
| Bắc+Nam vàng | **IO22** | chân **Y** của Bắc và Nam |
| Bắc+Nam xanh | **IO21** | chân **G** của Bắc và Nam |
| Đông+Tây đỏ | **IO19** | chân **R** của Đông **và** Tây |
| Đông+Tây vàng | **IO18** | chân **Y** của Đông và Tây |
| Đông+Tây xanh | **IO5** | chân **G** của Đông và Tây |
| GND | **GND** (chân 1 hoặc 7) | chân **GND** của cả 4 module |
| Dừng khẩn | **IO4** ↔ GND | qua tiếp điểm **NC** của nút (xem 3a) |

- Hai module đối diện **mắc song song**: R nối chung với R, Y chung với Y, G chung với G. Mỗi chân GPIO kéo khoảng 12 mA, trong giới hạn.
- Pi và ESP32 **không nối dây tín hiệu nào với nhau**. Chúng chỉ nói chuyện qua Wi-Fi/MQTT.
- DevKitC **không có LED người dùng ở GPIO 2** như NodeMCU. Muốn biết trạng thái thì xem log serial hoặc dashboard.

### 3a. Nút dừng khẩn

| Nút | Chân | Tiếp điểm | Cờ build trong `platformio.ini` |
|---|---|---|---|
| J1–J5 | **IO4** | NC | `[env]`: `-D SAFE_STOP_PRESSED_LEVEL=HIGH` (chung cho mọi nút) |

- Nút nấm đỏ thường có tiếp điểm **NC** (block đỏ, số 1–2) và **NO** (block xanh lá, số 3–4). Với NC: nhả nút thì mạch đóng, chân về GND (LOW), đèn chạy. Ấn nút thì mạch hở, chân lên HIGH nhờ điện trở kéo lên trong chip, firmware vào dừng khẩn.
- NC an toàn hơn: **đứt dây nút cũng tự vào dừng khẩn**. Hệ quả là board không gắn nút sẽ luôn ở dừng khẩn. Muốn chạy không có nút thì nối tắt IO4 xuống GND.
- Đổi một nút sang NO thì phải bỏ cờ `SAFE_STOP_PRESSED_LEVEL=HIGH` khỏi env của nút đó. Hàn nút vào chân khác IO4 thì thêm `-D SAFE_STOP_GPIO=<chân>` vào env của nút đó. Sửa xong phải nạp lại board.
- Kiểm nhanh: ấn nút thì `status` phải báo `SAFE_STOP`. Nhả nút thì phải về `HEALTHY` hoặc `FALLBACK_AUTONOMOUS`.

## 4. Nguồn

- Mỗi ESP32 lấy nguồn qua cáp USB từ **một hub USB có nguồn riêng** đặt ở mép trước sa bàn. Pi 5 dùng adapter riêng. Module đèn lấy điện từ chân GPIO, không cần nguồn riêng.
- Đã cấp qua USB thì **không nối thêm dây 5 V chung** giữa các board, chỉ nối GND nếu cần. Hai nguồn 5 V chập nhau là nghi phạm chính khiến USB rớt liên tục lúc nạp code ngày 22/10.
- Firmware bật Wi-Fi lệch nhau theo nút (J1 ở 0 ms, J2 ở 400 ms, …) để 5 board không cùng hút dòng đỉnh lúc khởi động. Nếu hub vẫn rớt thì build thêm `-D WIFI_TX_POWER=WIFI_POWER_11dBm`. Dòng thật của 5 board trên một hub **chưa đo**.

## 5. Đèn làm gì (để biết lúc lắp thấy gì là đúng)

| Lúc | Đèn |
|---|---|
| Vừa cấp nguồn hoặc reset | **Vàng nhấp nháy** cả 4 hướng 4 s → vàng đứng 3 s → đỏ hết 2 s → Bắc–Nam xanh |
| Chạy bình thường | Xanh → vàng 3 s → đỏ hết 2 s → hướng kia xanh. Xanh tối thiểu 5 s, tối đa 60 s |
| Mất lệnh từ laptop quá 5 s | Tự chạy chu kỳ dự phòng: mỗi pha xanh 15 s |
| Ấn nút khẩn | Vàng nhấp nháy cả 4 hướng, mọi lệnh bị từ chối |
| Nhả nút khẩn | Vàng đứng 3 s → đỏ hết 2 s → xanh lại pha cũ |
| Firmware thấy 2 hướng cùng xanh, hoặc đọc ngược chân ra sai | Đỏ hết ngay, rồi vàng nhấp nháy 10 s, rồi về như trên. Tắt phần đọc ngược bằng `-D OUTPUT_READBACK=0` nếu module làm nó báo nhầm |

## 6. Lắp từng bước, lắp đến đâu kiểm đến đó

**Rút USB của ESP32 trước mỗi lần cắm/rút dây.** Lệnh kiểm chạy trên laptop khi Docker (`docker compose --profile hardware up -d`) đang chạy. `$PY` là Python có `paho-mqtt`, `jsonschema`, `pydantic`. Topology 5 nút: đặt `EDGEFLOW_TOPOLOGY=tabletop_5nut_v1` trong `.env` laptop trước khi `up`.

```bash
# Ai đang online, pha hiện tại, Wi-Fi
$PY src/hardware/demo/laptop_command_test.py --mqtt-host localhost status
# Đổi pha NS/EW mỗi 12 s để nhìn đèn
$PY src/hardware/demo/laptop_command_test.py --mqtt-host localhost cycle J1 --period 12
```

Muốn điều khiển tay thì tạm dừng graph-control (`docker compose stop graph-control`), xong thì `start` lại. Nếu không, lệnh của graph-control sẽ chen vào.

| Bước | Lắp | Kiểm: đúng khi |
|---|---|---|
| 1 | Nạp board: `bash src/hardware/set_network.sh "<SSID>" "<pass>"` rồi `pio run -e J1 -t upload` | Log serial có `[FLASH] Enter flashing yellow (startup)`, rồi kết nối MQTT |
| 2 | J1: module **Bắc + Nam** vào IO23/IO22/IO21 + GND | Pha NS: Bắc và Nam cùng xanh. Đổi pha: xanh → vàng 3 s → đỏ |
| 3 | J1: module **Đông + Tây** vào IO19/IO18/IO5 + GND | Khi NS xanh thì EW đỏ và ngược lại. Giữa hai pha có 2 s cả 4 hướng đỏ. **Không bao giờ** hai hướng cùng xanh |
| 4 | Nút dừng khẩn J1 (mục 3a) | Như dòng "Ấn/Nhả nút khẩn" ở mục 5, `status` báo `SAFE_STOP`, lệnh bị `REJECTED: Safe-stop is engaged` |
| 5 | J2, J3, J4, J5: lặp lại bước 1–4, mỗi lần một nút | Như trên |
| 6 | Bật lại graph-control, chạy cả vòng 3 phút, chấm bằng `flow_report.py` (xem `demo/README.md`) | `RESULT: PASS`, đèn trên sa bàn khớp dashboard |

**Sai thường gặp:**

- Sáng sai màu: đổi chỗ dây R/Y/G, không sửa code.
- Không sáng gì: thiếu dây GND chung, hoặc cắm ngược module (GND vào chân tín hiệu).
- Một module sáng 2 màu cùng lúc hoặc không đổi theo pha: dây lệch chân (xem mục 2). Dò bằng cách bật từng chân một (firmware kiểm chân) và xem module nào sáng.
- Nút ấn mà không có gì xảy ra: dây nút không ở IO4, hoặc 2 dây nằm trên 2 block tiếp điểm khác nhau.
- Nhả nút thì vàng nhấp nháy, ấn thì chạy: nút nối NC mà firmware đang đọc kiểu NO, hoặc ngược lại (mục 3a).
- Board không lên mạng: chưa cắm ăng-ten IPEX (bản 32U không có ăng-ten in trên mạch), hoặc mạng 5 GHz (ESP32 chỉ 2.4 GHz; iPhone bật "Maximize Compatibility").
- Đèn xanh Đông–Tây chớp một cái lúc ESP32 khởi động: IO5 là chân strapping của ESP32. Ghi lại nếu thấy, không ảnh hưởng chạy.
