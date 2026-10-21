# Spec: Bản vẽ mạch EdgeFlow AI (Phụ lục A)

Ngày 11/10/2026. Hiển duyệt thiết kế trong chat cùng ngày. Folder `thiet_ke_bao_cao/` nằm ngoài git nên không commit.

## Mục tiêu

- Phần thuyết trình bán kết có mục "Bản vẽ mạch". Mục 3.3 của báo cáo cho phép chèn kiến trúc phần cứng.
- H3.2 hiện là sơ đồ khối có ghi số chân, chưa phải bản vẽ mạch.
- Cần 3 tờ bản vẽ **thể hiện**, không phải bản để gia công. Không làm PCB (Hiển chốt).

**Đạt khi:**

- Có PNG/SVG đưa thẳng vào báo cáo và slide.
- Có file `.drawio` để đội sửa.
- Mọi số chân trên hình khớp firmware.

## Công cụ và file

- Chỉ dùng draw.io (Hiển chọn). Dùng lại `_scripts/drawio_lib.py`; được thêm style ký hiệu điện vào đó, nhưng không đổi hàm có sẵn.

| File mới | Vai trò |
| --- | --- |
| `_scripts/tao_drawio_ban_ve_mach.py` | Sinh `3.3_kien_truc/EdgeFlow_ban_ve_mach.drawio` gồm 3 trang. Đọc `PIN_*` trong firmware; số chân trên hình khác code thì dừng |
| `_scripts/xuat_hinh_ban_ve_mach.sh` | Xuất `HA.1_nguyen_ly_nut_chap_hanh`, `HA.2_dau_noi_khoi_AI_bien`, `HA.3_di_day_len_tru` ra `.png` (2x, có nhúng sơ đồ) và `.svg` trong `3.3_kien_truc/` |
| `3.3_kien_truc/noi_dung_phu_luc_A.md` | Chữ của Phụ lục A, thêm ghi chú cho đội ở cuối |

**Không đụng** vào `EdgeFlow_3.3_kien_truc.drawio` hay `tao_drawio_3_3.py`. Vì cùng nỗi lo ghi đè, script mới **từ chối ghi đè** file `.drawio` đã tồn tại, trừ khi có cờ `--ghi-de`.

**Sửa nhỏ:**

- `noi_dung_3.3.md`: thêm một câu sau đoạn H3.2, dẫn tới Phụ lục A.
- `tao_docx.py`: thêm Phụ lục A vào file Word.
- `README.md`: thêm mục bản vẽ mạch.

## Nguồn sự thật

- Chân GPIO, mức logic, kéo lên nội: `vedc-traffic-flow/src/hardware/firmware/esp32_signal_controller.ino`.
- Nguồn, linh kiện, số lượng: H3.2 và `3.4_linh_kien/bang_linh_kien.csv`. Bảo vệ nguồn dùng **chung một bộ** PTC + 1N5819 cho cả 2 nút, giống H3.2.
- Kích thước trụ: `4.4_hinh_minh_hoa/blender/bo_tri.py`. Các số là đề xuất, không phải số đo:
  - ống kính cao 400 mm;
  - cần camera cao 432 mm;
  - cần đèn cao 160 mm;
  - tâm cụm đèn cao 112 mm;
  - cần vươn 141 mm;
  - cáp CSI ~0,78 m.
- `schematic_and_pinout.md` mục 1–2 **sai** (trở 220 Ω, ULN2803, kéo lên 10 kΩ), nên không dùng. Chỉ dùng mục 3–4.

## Nội dung 3 tờ

Mọi tờ: khổ ngang, cùng bảng màu `TIER` và `FLOW` với H3.x. Mỗi tờ có khung tên gồm:

- dự án EdgeFlow AI, đội 31µF, VEDC 2026;
- số tờ và tên tờ;
- ngày;
- dòng nguồn ("bám firmware …", hoặc "kích thước đề xuất").

Không ghi tên hay thông tin cá nhân của thành viên.

### Hình A.1: Sơ đồ nguyên lý nút chấp hành J1 (J2 giống hệt)

- **Nguồn:** adapter 5 V/4 A → jack DC 5.5×2.1 → PTC 0,5–1 A → 1N5819 → domino +5V → chân 5V/VIN của U1. Có nhánh "→ VIN nút J2". GND chung giữa 2 nút.
- **U1 ESP32 NodeMCU-32S:** đủ 38 chân, theo thứ tự vật lý của hai hàng. Chân dùng tới tô đậm, chân không dùng ghi mờ. Ghi chú trên khối:
  - LED trạng thái trên board (GPIO 2);
  - cổng micro-USB/CH340 để nạp firmware.
- **Ngõ ra:**
  - GPIO 23/22/21 → net `NS_R`, `NS_Y`, `NS_G` → module Bắc **và** module Nam (song song);
  - GPIO 19/18/5 → `EW_R`, `EW_Y`, `EW_G` → module Đông **và** module Tây.
  - Mỗi module vẽ 3 LED, mỗi LED nối tiếp một trở ghi "có sẵn trên module", không ghi giá trị. Chân GND của module nối GND.
- **SW1 safe-stop:** nút tự giữ, thường mở, nối GPIO 4 xuống GND. Ghi chú "INPUT_PULLUP nội, nhấn = LOW = dừng an toàn".
- **J_LA:** header logic analyzer (tùy chọn): CH0–CH5 → 6 net đèn, CH6 → GPIO 4, GND.
- **Ghi chú ngắn:**
  - dòng ước tính ~6 mA/LED ở 3,3 V, tức ~12 mA mỗi chân;
  - rút 5 V ngoài khi nạp qua micro-USB;
  - cáp W1 giữa breadboard và cụm đèn, xem Hình A.3.

### Hình A.2: Sơ đồ đấu nối khối AI biên

- Ổ 220 V → nguồn USB-C PD 5,1 V/5 A (27 W) → cổng USB-C của Pi 5.
- Cổng CAM/DISP 0 → cáp FPC 22→15 pin dài 1 m → Camera Module 3 Wide trên trụ J1. Cổng CAM/DISP 1 → camera trên trụ J2.
- Các khối phụ: quạt 5 V (cổng FAN hoặc chân 5V/GND, tùy loại tản nhiệt), thẻ microSD 64 GB, Wi-Fi 2.4 GHz → router.
- Ghi rõ:
  - Pi và ESP32 **không nối dây**, chỉ nói chuyện qua Wi-Fi/MQTT, và là hai miền nguồn riêng, không chung GND;
  - đọc 2 camera trên 1 Pi "đang phát triển", cùng cách ghi với H3.1.

### Hình A.3: Sơ đồ đi dây lên trụ (1 nút)

- **Trái:** 2 breadboard 830 lỗ ghép lại, U1 cắm bắc cầu giữa hai tấm, thanh nguồn từ domino, SW1, các lõi cáp W1 cắm vào breadboard. Vẽ giản lược, không theo đúng từng lỗ.
- **Giữa:** mặt đứng của trụ, ghi kích thước đề xuất. Cáp W1 đi dưới mặt sa bàn → lên trụ → dọc cần đèn → tới cụm đèn. Cáp FPC của camera vẽ nét đứt, đi lên cần trên.
- **Phải:**
  - **Cụm đèn 4 mặt nhìn từ trên:** mặt quay về phía xe tới. Module Bắc quay lên Bắc, các module khác tương tự (theo `FACE_YAW`).
  - **Bảng lõi W1 (CAT5e, T568B), đề xuất:**

    | Lõi | Màu | Tín hiệu |
    | --- | --- | --- |
    | 1 | cam-trắng | NS_R |
    | 2 | cam | NS_Y |
    | 3 | xanh lá-trắng | NS_G |
    | 4 | xanh dương | EW_R |
    | 5 | xanh dương-trắng | EW_Y |
    | 6 | xanh lá | EW_G |
    | 7 | nâu-trắng | GND |
    | 8 | nâu | dự phòng |

  - **Điểm rẽ nhánh ở đầu cần (đề xuất):** mỗi lõi tín hiệu hàn ra 2 dây dupont cái, bọc co nhiệt, cắm vào 2 module đối diện. Lõi GND rẽ ra 4 module.

## Chữ trong báo cáo

- `noi_dung_3.3.md`, sau đoạn H3.2: "Sơ đồ nguyên lý và cách đi dây chi tiết ở Phụ lục A (Hình A.1–A.3)."
- `noi_dung_phu_luc_A.md`: mỗi hình một đoạn ngắn kèm chú thích hình. Ghi rõ những gì là **đề xuất**: màu lõi cáp, điểm rẽ nhánh, kích thước trụ.

## Kiểm tra

1. Script so 8 hằng `PIN_*` với bảng chân dùng để vẽ, lệch thì `exit 1`. Kiểm bằng cách sửa tạm một chân trong bảng: script phải báo lỗi.
2. Kiểm XML: mỗi trang parse được, id không trùng (`drawio_lib` đã chặn trùng id), mọi `source`/`target` của edge đều trỏ tới id có thật.
3. Xuất PNG bằng draw.io CLI rồi mở từng trang xem: không tràn chữ, không đè đường, chữ tiếng Việt hiển thị đúng.
4. `tao_docx.py` chạy không lỗi, file Word có Phụ lục A với 3 hình.

## Ngoài phạm vi (chỉ báo lại cho Hiển)

- `schematic_and_pinout.md` mục 1–2 lệch code. File nằm trong repo chung, đội quyết có sửa không.
- GPIO 5 là chân strapping, nên đèn xanh Đông–Tây có thể nháy lúc ESP32 khởi động. Phải kiểm trên mạch thật. Ghi vào phần ghi chú cho đội, không đưa lên hình.
- H3.2, bảng 3.4 và các render 4.4 không sửa.

## Sửa đổi 11/10/2026 tối: vẽ lại, thêm tờ tổng thể

Hiển xem bản 3 tờ và nhận xét: chưa có hình thiết kế tổng, các tờ còn xấu. Đã vẽ lại cả bộ. File `.drawio` lúc đó trùng từng byte với bản script sinh, tức chưa ai sửa tay. Bản cũ lưu ở `_ghi_chu/ban_ve_mach_truoc_ve_lai_2026-10-11/`.

- **Thêm tờ A.1 "Sơ đồ bố trí và đấu nối tổng thể"**, nên các tờ cũ A.1–A.3 thành A.2–A.4. Tên file PNG đổi theo (`HA.1_tong_the_bo_tri_dau_noi`, `HA.2_nguyen_ly_nut_chap_hanh`, `HA.3_dau_noi_khoi_AI_bien`, `HA.4_di_day_len_tru`).
  - Mặt bằng sa bàn vẽ theo tỷ lệ từ `bo_tri.py`.
  - Có bảng cáp: C1–C2 camera, W1–W2 lên trụ, P1–P4 nguồn, L1–L3 Wi-Fi.
  - Có danh mục tờ.
- **Hệ thống hình chung:**
  - mọi tờ cùng khổ 1600 × 1131 (tỉ lệ A3);
  - khung đôi có lưới ô 1–8 × A–F;
  - khung tên mới gồm tên bản vẽ, tờ "A.n · n/4", ngày, tỷ lệ, nguồn số liệu, trạng thái;
  - nhãn hình đánh số, khối ghi chú đánh số, ô ký hiệu, bảng có hàng tiêu đề in nhỏ;
  - bảng màu dùng chung: nguồn cam, CAT5e tím, FPC xanh dương, Wi-Fi nâu vàng, tín hiệu R/Y/G.
- **A.2:** trục rẽ nhánh xếp lại để dây từ U1 không cắt trục nào; còn 6 chỗ giao trong nhóm, vẽ cung vượt. GND của module quay về breadboard qua lõi 7. Bảng tín hiệu thay cho bảng X3 cũ.
- **A.3:** board Pi 5 vẽ theo tỷ lệ theo bản vẽ cơ khí RP-008347-DS-1 (tải từ pip.raspberrypi.com). Nhãn CAM/DISP 0/1 đọc từ ảnh sản phẩm chính thức: đầu nối gần HDMI là 1, gần Ethernet là 0.
- **A.4:**
  - ESP32 quay anten sang trái; lõi W1 cắm thẳng vào cột của chân GPIO (đề xuất mới);
  - mặt đứng trụ có đường kích thước kiểu bản vẽ kỹ thuật;
  - chi tiết rẽ nhánh vẽ cả lõi 1 và lõi 7.
- `tao_docx.py`: ảnh phụ lục 24 cm thay vì 25 cm, để ảnh tỉ lệ A3 cùng chú thích vừa trang A4 ngang.
