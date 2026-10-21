# EdgeFlow AI: danh sách mua sắm còn thiếu (VEDC 2026, đội 31µF)

> **18/10/2026 (chiều):** danh sách hiện hành là `MUA_SAM_CON_THIEU_2026-10-16.xlsx`. Sa bàn là 1 tấm bạt
> 1200 × 600 mm cuộn được (không còn 2 tấm fomex, khay, tấm A0 hay giá treo camera); file in và phiếu đặt ở `in_sa_ban/`.
> Mục 9 và dòng "Tiệm quảng cáo" bên dưới đã sửa theo; phần còn lại giữ nguyên làm lịch sử.

Cập nhật 04/10/2026. File này nằm ngoài git. Căn cứ:

- Revised Development Plan (2), bản 22/09. Đây là bản kế hoạch có hiệu lực.
- Hai báo giá ngày 19/09: Bảo Anh (2.521.000đ) và HSHOP (570.000đ).
- Bảng dự toán 7.288.000đ.
- Thiết kế phần cứng thực tế trong repo `vedc-traffic-flow`: [src/hardware/](vedc-traffic-flow/src/hardware/), firmware ESP32 và `services/vision`.
- Phiên trao đổi trên claude.ai.
- Đồ đã có sẵn: Raspberry Pi 5 và nguồn.

> **Việc gấp:** cả hai báo giá chỉ có hiệu lực 5 ngày nên đã hết hạn từ 24/09. Theo plan, giai đoạn 29/09–04/10 phải đi dây xong 2 nút đèn và chạy liên tục 30 phút trên phần cứng thật. Tức là hôm nay đã chạm mốc. Cần xin báo giá lại và đặt hàng **trong hôm nay hoặc ngày mai**. Giao hàng trong TP.HCM mất 2–3 ngày.

---

## 0. Khác biệt với lần trao đổi trên claude.ai (đọc trước)

Repo đã có firmware và sơ đồ chân thật, nên vài khuyến nghị cũ phải đổi theo:

| Điểm | Trên claude.ai | Theo repo (dùng cái này) | Hệ quả khi mua |
|---|---|---|---|
| Số chân GPIO cho đèn | 12 chân mỗi nút, mỗi hướng riêng | **6 chân mỗi nút**: Bắc+Nam chung 3 chân (GPIO 23/22/21), Đông+Tây chung 3 chân (GPIO 19/18/5) | Mỗi chân nuôi 2 module mắc song song, khoảng 12 mA ở 3,3 V. Vẫn an toàn |
| Nút safe-stop | GPIO 33 | **GPIO 4**, INPUT_PULLUP, nối xuống GND | Firmware đọc theo mức: giữ = dừng. Nên mua **nút nhấn tự giữ** |
| Logic analyzer | 8 kênh không đủ cho 12 tín hiệu | 6 tín hiệu đèn + 1 safe-stop = **7 kênh**, đủ cho 1 nút | Loại 8 kênh là vừa |
| Cổng USB của ESP32 | Không rõ | NodeMCU-32S Ai-Thinker CH340 dùng **micro-USB** (HSHOP xác nhận). Tài liệu repo ghi "Type-C" là sai | Mua cáp micro-USB **loại truyền dữ liệu** |
| Mạng | Router mini | Firmware mặc định trỏ tới AP của Pi (`EdgeFlow_Local_AP`, 192.168.4.1). Trong khi đó `.env.rpi` lại trỏ broker về laptop 192.168.1.100 | Dùng router riêng, và cấu hình lại SSID/broker trong `secrets.ini` (xem KE_HOACH_DEPLOY.md) |

---

## 1. Hai báo giá cũ: cần đặt lại và sửa số lượng

| # | Món (báo giá) | SL hiện tại | Đánh giá | Đề xuất |
|---|---|---|---|---|
| BA-1 | Thẻ microSD ACER 64GB | 1 | ✅ Đủ | Giữ |
| BA-2 | Vỏ ABS Pi 5, 35×91×62 mm | 1 | ⚠️ | Giữ, nhưng **hỏi shop**: vỏ có đóng được khi đã gắn tản nhiệt kèm quạt không, và có khe cho cáp camera đi ra không |
| BA-3 | Tản nhiệt nhôm kèm quạt 5V | 1 | ✅ | Giữ |
| BA-4 | Cáp micro HDMI 1,5 m | 1 | ✅ | Giữ. Chỉ cần khi cắm màn hình để debug |
| BA-5 | Camera Module 3 **Wide** SC0874 | 1 | ✅ | Giữ. Bản Wide 120° phủ được 2 ngã tư. **Không kèm cáp dùng được cho Pi 5** (xem mục 2) |
| BA-6 | Cảm biến IR LM393 | **12** | 🔻 Dư | **Giảm còn 0–4.** Plan chỉ dùng IR để chẩn đoán, và repo hiện không có dòng code nào đọc IR. Giảm xuống 4 tiết kiệm ~120k, bỏ hẳn tiết kiệm ~180k |
| BA-7 | Relay 1 kênh opto 5V | 1 | ⚪ Tùy chọn | Firmware không dùng relay. Plan cũng ghi relay 1 kênh "không chứng minh tương thích tủ đèn". Bỏ được. Nếu giữ thì thêm 1 transistor S8050 + trở 1k để kích bằng 3,3 V |
| BA-8 | Adapter 5V/4A, đầu DC 5.5×2.1 | 1 | ⚠️ | Giữ, **chỉ dùng cấp nguồn cho 2 ESP32 và đèn**, không cắm được vào Pi 5 (Pi dùng USB-C). Cần thêm đầu chuyển (mục 2) |
| BA-9 | Breadboard 830 lỗ | 1 | ❌ Thiếu | Tăng lên 4, hoặc mua thêm 3 ở mục 2 |
| BA-10..12 | Dây dẹt 40P 20 cm M-M / M-F / F-F | 3 | ✅ | Giữ. Dây 20 cm ngắn so với khoảng cách trên sa bàn A0, nên thêm dây 30 cm (mục 2) |
| HS-1 | ESP32 NodeMCU-32S CH340 | 3 | ✅ | Giữ: 2 con dùng, 1 con dự phòng. Giá web HSHOP hôm nay là **175k** (báo giá cũ 190k), nên xin báo giá lại sẽ rẻ hơn |

---

## 2. Danh sách mua thêm

### 2.1 Bắt buộc (thiếu thì không chạy được demo)

| # | Món | SL | Ước tính | Lý do và lưu ý khi mua |
|---|---|---|---|---|
| 1 | **Cáp camera Pi 5: 22 pin 0,5 mm sang 15 pin 1 mm** | 2 (1× 500 mm + 1× 300 mm) | 150–230k | Pi 5 dùng cổng camera 22 pin loại nhỏ, còn cáp đi kèm Camera Module 3 là loại 15–15 nên không cắm được. Nếu gắn Pi lên giá treo, ngay cạnh camera, thì sợi 300 mm là đủ. Sợi 500 mm cho phép đặt Pi thấp hơn và đồng thời làm dự phòng. Link HSHOP cũ đã báo 404, nên tìm ở raspberrypi.vn, mlab, pivietnam hoặc Shopee (Waveshare/Adafruit). Kiểm tra đúng chữ "Pi 5" và "22-pin to 15-pin" |
| 2 | **Mạch LED đèn giao thông** (đỏ/vàng/xanh, có sẵn trở, 4 chân R-Y-G-GND) | 10 (8 dùng + 2 dự phòng) | 80–150k | Chưa có trong báo giá nào. 2 nút × 4 hướng = 8 cụm. Link trong dự toán đã 404, Nshop hết hàng. Hỏi Bảo Anh/HSHOP khi xin báo giá lại, hoặc tìm trên Shopee với từ khóa "module đèn giao thông LED 5V". Phương án dự phòng: tự làm bằng LED 5 mm R/Y/G + trở 220 Ω (~50k cho 8 cụm) |
| 3 | **Cáp micro-USB truyền dữ liệu** | 3 | 60–90k | Để nạp firmware và xem log. Loại chỉ sạc sẽ không nhận được cổng COM. macOS bản mới đã có sẵn driver CH340 |
| 4 | **Breadboard 830 lỗ** | 3 (tổng thành 4) | ~100k | NodeMCU-32S rộng 25,4 mm nên cắm lên 1 board gần như không còn lỗ trống. Mỗi nút cắm ESP32 bắc cầu qua 2 board |
| 5 | **Jack DC cái 5.5×2.1 mm ra domino** | 2 (1 + 1 dự phòng) | 10–20k | Để lấy 5V từ adapter BA-8 ra đường nguồn chung của 2 nút |
| 6 | **Nút nhấn tự giữ** (2 hoặc 6 chân), dùng làm safe-stop | 3 | 10–15k | Firmware đọc GPIO 4 theo mức: nhấn giữ thì đèn chuyển vàng nhấp nháy. Nút tự giữ không bắt người demo phải đè tay liên tục. (Tùy chọn cho chung kết: nút dừng khẩn nấm đỏ 22 mm, ~40k/cái) |
| 7 | **Dây dupont 40P dài 30 cm**: 1 bộ F-F + 1 bộ M-F | 2 bộ | ~60k | Module đèn có header đực. Dây 20 cm không đủ đi từ ESP32 tới các góc ngã tư trên sa bàn A0 |
| 8 | **Router Wi-Fi mini, có băng 2.4 GHz** | 1 | 250–350k | ESP32 chỉ có Wi-Fi 2.4 GHz. Cần mạng LAN riêng cho MQTT và có thể đặt DHCP reservation, tắt AP/client isolation. Không nên để Pi hay điện thoại phát Wi-Fi: khi demo "mất coordinator", cả mạng sẽ sập theo |
| 9 | **Bộ sa bàn** (sửa 18/10 chiều): 1 tấm bạt Hiflex mờ 1200 × 600 mm gấp viền + 2 đế trụ MDF 6 ly 200 × 200 mm + băng keo vải. Xe 1:64 chỉ "nếu cần"; không còn giá treo camera (demo dùng video từ 17/10) | 1 bạt + 2 đế | ước tính 150–300k, hỏi tiệm | Tiệm quảng cáo (bạt), tiệm gỗ hoặc CNC (đế), mang `in_sa_ban/PHIEU_DAT_IN.pdf` |

**Cộng phần bắt buộc: khoảng 1,29–1,6 triệu.**

### 2.2 Nên có (cần cho tiêu chí đo đạc của plan và giảm rủi ro khi demo)

| # | Món | SL | Ước tính | Lý do |
|---|---|---|---|---|
| 10 | Logic analyzer USB 8 kênh 24 MHz (dùng PulseView) | 1 | 150–250k | Plan yêu cầu "MCU or logic-analyzer output traces" để chứng minh có đủ vàng 3 s, all-red 2 s và không bao giờ có 2 hướng cùng xanh. 7 kênh là đủ cho 1 nút. Firmware trên nhánh `deploy/hardware-prep` đã có thêm log `TRACE` qua serial làm bằng chứng phía MCU. LA là bằng chứng độc lập, giám khảo tin hơn |
| 11 | Đèn LED chiếu sa bàn, loại không nhấp nháy | 1 | 100–200k | Tránh flicker do đèn hội trường và giữ ánh sáng ổn định giữa lúc thu dữ liệu và lúc thi |
| 12 | Diode Schottky 1N5819 ×5 + cầu chì tự phục hồi PTC 0,5–1 A ×4 | 1 bộ | ~20k | Plan yêu cầu "protected low-voltage power". Đừng dùng 1N4007 như ghi trong `schematic_and_pinout.md`: sụt áp ~0,8 V làm VIN của ESP32 chỉ còn ~4,2 V |
| 13 | Nhãn dán cáp, ống co nhiệt, dây rút | 1 bộ | ~50k | Plan yêu cầu "cable labels" |
| 14 | Cáp mạng LAN 1–2 m | 1 | 20–40k | Cắm Pi thẳng vào router. Ở hội trường đông thiết bị, dây ổn định hơn Wi-Fi |

**Cộng phần nên có: khoảng 0,34–0,56 triệu.**

### 2.3 Chỉ mua nếu cần (kiểm tra trước)

| Món | Điều kiện | Ước tính |
|---|---|---|
| Nguồn Raspberry Pi chính hãng 27 W (5V/5A, USB-C PD) | Nếu nguồn đang có **không** phải 5V/5A. Kiểm tra bằng `vcgencmd get_throttled` khi chạy YOLO: kết quả phải là `0x0` | ~388k |
| Đầu đọc thẻ microSD USB | Nếu Mac không có khe SD để ghi Raspberry Pi OS | 30–50k |
| Transistor S8050 + trở 1k | Nếu giữ relay BA-7 | ~5k |
| Ổ cắm điện nối dài ≥ 4 lỗ | Bàn demo cần cắm nguồn Pi, adapter 5V, router, laptop và đèn | 60–120k |

---

## 3. Ngân sách

| Khoản | Số tiền |
|---|---|
| 2 báo giá cũ (chưa sửa) | 3.091.000đ |
| Giảm IR 12 → 4 (hoặc → 0) | −120k (−180k) |
| Bỏ relay (tùy chọn) | −23k |
| Mua thêm, bắt buộc | +1,29–1,6 triệu |
| Mua thêm, nên có | +0,34–0,56 triệu |
| **Tổng ước tính** | **≈ 4,6–5,1 triệu** (chưa tính mục 2.3) |

Vẫn dưới trần 8,5 triệu mà plan đề xuất. Mọi giá ở mục 2 là ước tính, phải xin báo giá thật.

---

## 4. Kiểm tra tương thích phần cứng

| Kết nối | Trạng thái | Xử lý |
|---|---|---|
| Camera Module 3 ↔ Pi 5 | ❌ Cáp kèm theo không vừa | Mục 1 (cáp 22→15) |
| Camera Module 3 ↔ phần mềm | ❌ `cv2.VideoCapture(0)` không đọc được camera CSI trên Pi 5 | Đã sửa trên nhánh `deploy/hardware-prep`: `VIDEO_SOURCE=picamera` dùng Picamera2, khóa `LensPosition`, chống nhấp nháy 50 Hz |
| Adapter 5V/4A ↔ Pi 5 | ❌ Đầu jack tròn, Pi dùng USB-C | Pi dùng nguồn USB-C riêng. Adapter chỉ cấp cho ESP32 |
| Adapter 5V ↔ ESP32 | ✅ qua jack→domino → chân 5V/VIN | Nối GND chung. **Rút nguồn 5V ngoài khi đang cắm USB nạp firmware**, hoặc đặt diode Schottky trên đường 5V |
| ESP32 GPIO 3,3 V ↔ module đèn | ✅ | Module có sẵn trở, ~5–6 mA/LED ở 3,3 V. 2 module chung 1 chân ≈ 12 mA, dưới mức 20 mA. Cùng lúc chỉ sáng 4 LED mỗi nút |
| ESP32 ↔ router | ⚠️ | Router phải phát 2.4 GHz, WPA2, tắt client isolation. Đặt IP cố định cho máy chạy broker |
| Cảm biến IR ↔ ESP32 (nếu giữ) | ⚠️ | Cấp 3,3 V cho IR, **không** cấp 5 V. Chân OUT ở mức 5 V sẽ làm hỏng GPIO |
| Relay opto 5V ↔ ESP32 (nếu giữ) | ⚠️ | Mức 3,3 V có thể không nhả được relay. Kích qua S8050 + 1k |
| Logic analyzer ↔ ESP32 | ✅ | Ngưỡng 3,3 V phù hợp. Nối GND chung. CH0–CH5 vào GPIO 23/22/21/19/18/5, CH6 vào GPIO 4 |
| Vỏ ABS ↔ tản nhiệt + cáp camera | ❓ | Hỏi shop (BA-2) |

---

## 5. Checklist đặt hàng

- [ ] Xin báo giá lại ở Bảo Anh: sửa IR 12 → 4 (hoặc 0), cân nhắc bỏ relay, breadboard 1 → 4, gộp thêm module đèn ×10, cáp micro-USB ×3, jack DC ×2, nút tự giữ ×3, dây 30 cm, diode/PTC (nếu shop có)
- [ ] Xin báo giá lại ở HSHOP: ESP32 ×3 (giá web 175k), hỏi kèm cáp camera Pi 5 và module đèn
- [ ] Chốt nơi mua cáp camera Pi 5 (500 mm + 300 mm). **Đây là món chặn toàn bộ phần thị giác**
- [ ] Router 2.4 GHz
- [ ] Logic analyzer 8 kênh
- [ ] Tiệm quảng cáo: 1 tấm bạt 1200 × 600 + 2 đế MDF 200 × 200 + tờ nhãn A4 + bảng A3, theo `in_sa_ban/PHIEU_DAT_IN.pdf` (sửa 18/10 chiều)
- [ ] Kiểm tra nguồn Pi đang có có phải 27 W không, và Mac có khe SD không
- [ ] Hỏi shop về vỏ ABS (khe cáp camera, độ cao khi có tản nhiệt)
- [ ] Lưu hóa đơn và báo giá vào `VEDC/` để quyết toán (BTC hỗ trợ 2 triệu nếu có sản phẩm trình bày tại bán kết)
