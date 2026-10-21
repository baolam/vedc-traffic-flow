# Mục lục tài liệu thiết kế, đấu nối và kế hoạch

Các thư mục dưới đây được chép vào repo ngày 21/10/2026 từ thư mục làm việc ngoài git của Hiển. Bản gốc ngoài repo vẫn giữ nguyên.

## Đấu dây phần cứng: mở file nào

| Cần gì | File |
|---|---|
| **Lắp từng bước theo linh kiện đã mua (bắt đầu ở đây)** | [`src/hardware/HUONG_DAN_LAP_RAP.md`](../src/hardware/HUONG_DAN_LAP_RAP.md) |
| Bảng chân GPIO của ESP32 (khớp firmware) | [`src/hardware/schematic_and_pinout.md`](../src/hardware/schematic_and_pinout.md) |
| Đấu nối tổng thể toàn hệ thống | [`thiet_ke/3.3_kien_truc/HA.1_tong_the_bo_tri_dau_noi.png`](thiet_ke/3.3_kien_truc/HA.1_tong_the_bo_tri_dau_noi.png) |
| Nguyên lý một nút đèn (J1 và J2 đấu giống nhau) | [`thiet_ke/3.3_kien_truc/HA.2_nguyen_ly_nut_chap_hanh.png`](thiet_ke/3.3_kien_truc/HA.2_nguyen_ly_nut_chap_hanh.png) |
| Đấu nối khối AI (Raspberry Pi 5) | [`thiet_ke/3.3_kien_truc/HA.3_dau_noi_khoi_AI_bien.png`](thiet_ke/3.3_kien_truc/HA.3_dau_noi_khoi_AI_bien.png) |
| Đi dây từ breadboard lên trụ | [`thiet_ke/3.3_kien_truc/HA.4_di_day_len_tru.png`](thiet_ke/3.3_kien_truc/HA.4_di_day_len_tru.png) |
| Giải thích 4 tờ bản vẽ + bảng cáp | [`thiet_ke/3.3_kien_truc/noi_dung_phu_luc_A.md`](thiet_ke/3.3_kien_truc/noi_dung_phu_luc_A.md) |
| Danh sách linh kiện | [`thiet_ke/3.4_linh_kien/bang_linh_kien.csv`](thiet_ke/3.4_linh_kien/bang_linh_kien.csv) |
| Nạp ESP32 khi cổng USB hay rớt | [`src/hardware/flash_retry.sh`](../src/hardware/flash_retry.sh) |

Tóm tắt chân (mỗi nút J1/J2, theo `esp32_signal_controller.ino`):

- Bắc + Nam (2 module mắc song song): Đỏ GPIO 23, Vàng GPIO 22, Xanh GPIO 21.
- Đông + Tây (2 module mắc song song): Đỏ GPIO 19, Vàng GPIO 18, Xanh GPIO 5.
- Nút dừng khẩn: GPIO 4 nối GND khi nhấn (INPUT_PULLUP, active-LOW). LED trạng thái: GPIO 2 (trên board).
- GND của module đèn nối chung GND của ESP32. Rút USB trước khi cắm/rút dây.

**Lưu ý, bản vẽ chưa cập nhật hết:**

- HA.1–HA.4 và H3.x vẫn vẽ **tấm A0 và camera trên trụ**. Sa bàn thật từ 18/10 là **1 tấm bạt 1200 × 600 mm**, trụ đứng trên đế MDF, và demo bán kết **không lắp camera** (Pi đọc file video). Chân GPIO trên bản vẽ vẫn đúng.
- Bảng chân trong `schematic_and_pinout.md` có cột "220 Ω", nhưng mục 4 cùng file ghi module đèn đã có sẵn trở: dùng module thì không cần thêm trở.

## Thư mục

| Thư mục | Nội dung |
|---|---|
| [`thiet_ke/`](thiet_ke/) | Hình và bản vẽ báo cáo: 3.3 kiến trúc + phụ lục A (file `.drawio` là nguồn, PNG/SVG là bản xuất), 3.4 linh kiện, 4.4 hình minh họa Blender, video demo + nhãn + ROI, script sinh hình (`_scripts/`), ghi chú lịch sử (`_ghi_chu/`). Xem [`thiet_ke/README.md`](thiet_ke/README.md) |
| [`in_sa_ban/`](in_sa_ban/) | File in sa bàn bạt 1200 × 600, phiếu đặt in, decal, bảng giới thiệu A3. Sinh lại: `python3 docs/in_sa_ban/_nguon/tao_tat_ca.py` |
| [`ke_hoach/`](ke_hoach/) | `KE_HOACH_DEPLOY.md` (kế hoạch và nhật ký deploy Pi/ESP32/laptop, các lỗi F1–F33, G1–G7), `KE_HOACH_TOI_NAY.md`, danh sách mua sắm còn thiếu |
| [`ho_so/`](ho_so/) | Revised Development Plan (2) 22/09 (nguồn đúng về phạm vi), phương án phần cứng 29/07, Team Setup Guide |
| [`bang_chung/2026-10-21/`](bang_chung/2026-10-21/) | Vòng kín trên phần cứng thật (Pi + 2 ESP32): `run_report.txt` PASS 16/16. Log MQTT gốc `run_pi_esp32_that.log` bị `.gitignore` bỏ qua (`*.log`), muốn commit phải `git add -f` |

## Cố ý không đưa vào repo

- Báo giá `BG_*.pdf`: có CCCD, SĐT, địa chỉ.
- Báo cáo bán kết `3._bao_cao_...docx`, `BAO_CAO_BAN_KET_...docx`: có MSSV, email, SĐT của cả 4 thành viên.
- `CLAUDE.md` ngoài repo: có mật khẩu Pi và Wi-Fi.
- `yolo11n_sa_ban_best.pt`: `.gitignore` bỏ qua `*.pt`; model dùng chạy là các file ONNX trong `models/` (gửi lên Pi bằng `sync_to_pi.sh`).
- `video_demo_150s.mp4` đã có ở `data/demo_video/`, không chép trùng.
