# Kế hoạch: Bản vẽ mạch (Phụ lục A)

> Spec: `2026-10-11-ban-ve-mach-design.md` (cùng thư mục). Hiển bảo "làm luôn" nên làm ngay trong phiên, không dừng chờ duyệt kế hoạch. Không commit, vì thư mục này nằm ngoài git.

**Mục tiêu:** 3 trang draw.io (A.1 nguyên lý nút chấp hành, A.2 đấu nối khối AI biên, A.3 đi dây lên trụ), xuất ra PNG/SVG, rồi đưa vào bản Word nháp dưới dạng Phụ lục A.

**Ràng buộc chung**

- Số chân lấy theo `esp32_signal_controller.ino`. Bảng chân trong script phải khớp 8 hằng `PIN_*` của firmware, lệch thì `exit 1`.
- Thứ tự chân NodeMCU-32S theo trang linh kiện LCSC/Flux: chân 1–19 ở hàng trái (3.3V … 5V), chân 20–38 ở hàng phải đánh số từ dưới lên (CLK … GND).
- Stencil draw.io đã thử render được:
  - `resistors.resistor_1` (trở kiểu IEC);
  - `diodes.schottky_diode`;
  - `opto_electronics.led_2`;
  - `miscellaneous.fuse_2`;
  - `electro-mechanical.pushbutton_make`;
  - `signal_sources.signal_ground`;
  - `signal_sources.vdd`;
  - `radio.aerial_-_antenna_1`.
- Không ghi tên hay thông tin cá nhân của thành viên. Dùng dấu phẩy thập phân kiểu Việt. Không dùng ký tự "∥", viết "song song".
- Không ghi đè file `.drawio` đã có, trừ khi chạy với `--ghi-de`.

**Lỗi dễ gặp nhất**

1. Script ghi đè bản `.drawio` mà đội đã sửa.
2. Số chân trên hình lệch firmware sau khi đội sửa code.
3. Edge trỏ tới id không tồn tại: draw.io vẫn mở, nhưng dây bị mất.
4. Chữ tiếng Việt tràn khỏi khối khi xuất PNG.
5. Bảng màu lõi cáp bị hiểu là đã lắp thật.

## Task 1: Script sinh `.drawio`

**File:** tạo `_scripts/tao_drawio_ban_ve_mach.py` (dùng `drawio_lib.py`, không sửa thư viện).

- [ ] `doc_chan_firmware(path) -> dict[str, int]` đọc `const int PIN_X = N;`. `kiem_chan()` so với `CHAN` và báo lỗi khi lệch.
- [ ] `page_a1()`, `page_a2()`, `page_a3()`, mỗi hàm trả về một `Page`. `main()` nhận `--out` và `--ghi-de`.
- [ ] `kiem_xml(path)`: mọi `source`/`target` đều tồn tại, các trang parse được.
- [ ] Chạy với `--out` ra thư mục tạm. Sửa tạm một chân trong `CHAN`: script phải `exit 1`.

## Task 2: Xuất hình và rà bằng mắt

**File:** tạo `_scripts/xuat_hinh_ban_ve_mach.sh`.

- [ ] Xuất 3 trang ra `HA.1_nguyen_ly_nut_chap_hanh`, `HA.2_dau_noi_khoi_AI_bien`, `HA.3_di_day_len_tru` (PNG 2x có nhúng sơ đồ, và SVG).
- [ ] Mở từng PNG kiểm tràn chữ, đè đường, dấu tiếng Việt. Sửa lại cho tới khi sạch.

## Task 3: Chữ trong báo cáo và file Word

**File:**

- tạo `3.3_kien_truc/noi_dung_phu_luc_A.md`;
- sửa `3.3_kien_truc/noi_dung_3.3.md` (một câu sau H3.2);
- sửa `_scripts/tao_docx.py` (thêm file phụ lục vào danh sách, cập nhật dòng ghi chú);
- sửa `README.md`.

- [ ] Chạy `python3 _scripts/tao_docx.py` không lỗi. Kiểm tra file Word có "Phụ lục A" và 3 hình.
