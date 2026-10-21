# Thiết kế cho báo cáo bán kết: mục 3.3, 3.4 (linh kiện), 4.4, Phụ lục A (bản vẽ mạch)

Folder này **nằm ngoài git** `vedc-traffic-flow`. Tạo ngày 10/10/2026, bám code trên `main` + phần chưa commit của Hiển. Ngày 11/10 đổi giá treo camera chữ L thành 2 trụ giao thông (xem cuối file).

```
thiet_ke_bao_cao/
├── EdgeFlow_ban_nhap_muc_3.3_3.4_4.4.docx   ← bản nháp Word: chữ + hình + bảng, copy vào mẫu báo cáo
├── 3.3_kien_truc/
│   ├── EdgeFlow_3.3_kien_truc.drawio        ← BẢN GỐC, 4 trang = 4 hình, mở bằng draw.io để sửa
│   ├── H3.1_so_do_khoi.png / .svg
│   ├── H3.2_phan_cung_dau_noi.png / .svg
│   ├── H3.3_kien_truc_phan_mem.png / .svg
│   ├── H3.4_may_trang_thai_an_toan.png / .svg
│   ├── noi_dung_3.3.md                      ← chữ mục 3.3 (+ ghi chú cho đội ở cuối)
│   ├── EdgeFlow_ban_ve_mach.drawio          ← BẢN GỐC bản vẽ mạch, 4 trang = Hình A.1–A.4
│   ├── HA.1_tong_the_bo_tri_dau_noi.png / .svg
│   ├── HA.2_nguyen_ly_nut_chap_hanh.png / .svg
│   ├── HA.3_dau_noi_khoi_AI_bien.png / .svg
│   ├── HA.4_di_day_len_tru.png / .svg
│   └── noi_dung_phu_luc_A.md                ← chữ Phụ lục A (+ ghi chú cho đội ở cuối)
├── 3.4_linh_kien/
│   ├── H3.5_linh_kien_chinh.png             ← render 9 linh kiện chính, đúng tỉ lệ
│   ├── bang_linh_kien.csv                   ← bảng 26 dòng (mở bằng Excel/Google Sheets)
│   └── noi_dung_3.4_linh_kien.md
├── 4.4_hinh_minh_hoa/
│   ├── renders/H4.1 … H4.6_*.png            ← hình cuối, đã chú thích
│   ├── renders/raw/                         ← render gốc chưa chú thích
│   ├── blender/                             ← script dựng cảnh, texture, file .blend
│   └── noi_dung_4.4.md
├── _ghi_chu/                                ← tin nhắn yêu cầu của đội, bản .drawio trước khi đổi sang trụ
└── _scripts/                                ← script sinh .drawio, chú thích ảnh, tạo .docx
```

## Sửa sơ đồ 3.3 (draw.io)

- Mở `3.3_kien_truc/EdgeFlow_3.3_kien_truc.drawio` bằng một trong các cách sau. Mọi khối đều kéo thả và sửa chữ được.
  - **draw.io desktop** (đã cài trên máy Hiển).
  - **app.diagrams.net** trên trình duyệt.
  - Extension "Draw.io Integration" của VS Code.
- **Cả đội cùng sửa:** đưa file `.drawio` lên Google Drive rồi mở bằng app.diagrams.net. diagrams.net hỗ trợ nhiều người sửa cùng lúc trên file Drive.
- File PNG có nhúng sơ đồ: kéo file PNG vào draw.io vẫn sửa tiếp được.
- Sửa xong, xuất lại PNG/SVG: `bash _scripts/xuat_hinh_3_3.sh`.
- ⚠️ **Đừng chạy lại `_scripts/tao_drawio_3_3.py` sau khi đội đã sửa.** Script đó ghi đè file `.drawio` bằng bản gốc. (Ngày 11/10 đã chạy lại một lần, sau khi kiểm file trong máy trùng từng byte với bản script sinh ra, tức chưa ai sửa. Bản cũ lưu ở `_ghi_chu/`. Nếu đội đã sửa một bản trên Drive thì chỉ cần chép lại các chữ về 2 camera và cụm đèn 4 mặt.)

## Bản vẽ mạch: Phụ lục A (draw.io, 11/10)

Mục thuyết trình "Bản vẽ mạch" cần sơ đồ nguyên lý thật, H3.2 chỉ là sơ đồ khối. Bốn tờ, cùng khung bản vẽ kỹ thuật (lưới ô 1–8 × A–F, khung tên ở góc dưới phải):

- **A.1 tổng thể:** mặt bằng sa bàn vẽ theo tỷ lệ từ `bo_tri.py` (2 ngã tư, 2 trụ, tủ Pi, dải mạch phía trước), đường đi của mọi cáp, bảng cáp (C1–C2 camera, W1–W2 lên trụ, P1–P4 nguồn, L1–L3 Wi-Fi), danh mục tờ.
- **A.2 nguyên lý nút chấp hành:** nguồn X1 → F1 → D1 → X2, U1 NodeMCU-32S đủ 38 chân, cáp W1 vẽ thành dải, 4 module H1–H4 (Bắc song song Nam, Đông song song Tây), S1 safe-stop, bảng tín hiệu (net, GPIO, chân, lõi W1, kênh logic analyzer X3).
- **A.3 khối AI biên:** Pi 5 vẽ theo tỷ lệ, cổng theo bản vẽ cơ khí chính thức (RP-008347-DS-1), 2 camera qua CAM/DISP 0/1, nguồn 27 W, quạt, Wi-Fi, bảng thông số.
- **A.4 đi dây lên trụ:** breadboard, mặt đứng trụ có đường kích thước (số từ `bo_tri.py`), cụm đèn 4 mặt, bảng lõi cáp W1 theo T568B, chi tiết rẽ nhánh. Màu lõi, cách rẽ nhánh và kích thước trụ là **đề xuất**.

Sửa trực tiếp `3.3_kien_truc/EdgeFlow_ban_ve_mach.drawio` bằng draw.io, rồi xuất lại: `bash _scripts/xuat_hinh_ban_ve_mach.sh`.

- `_scripts/tao_drawio_ban_ve_mach.py` sinh file `.drawio`. Mỗi tờ một module (`to_a1_tong_the.py` … `to_a4_tru.py`), phần dùng chung (bảng màu, khung tờ, khung tên, ký hiệu) ở `ban_ve_mach_chung.py`.
  - Script đọc các hằng `PIN_*` trong firmware và dừng nếu số chân trên hình lệch code.
  - Script **không ghi đè** file `.drawio` đã có, trừ khi chạy với `--ghi-de`.
- Dây trên hình là đường tự do: kéo ký hiệu thì phải kéo dây theo.
- Trong file Word, phụ lục nằm ở một section khổ ngang (ảnh rộng 24 cm).
- Spec và kế hoạch: `_ghi_chu/2026-10-11-ban-ve-mach-*.md`. Bản 3 tờ trước khi vẽ lại: `_ghi_chu/ban_ve_mach_truoc_ve_lai_2026-10-11/`.

## Dựng lại render Blender (4.4 và H3.5)

Bố trí sa bàn (kích thước, vị trí ngã tư, vị trí và độ cao trụ, camera, cụm đèn, Pi, ROI, xe) nằm hết trong `4.4_hinh_minh_hoa/blender/bo_tri.py`. Đổi số ở đó rồi chạy:

```bash
cd 4.4_hinh_minh_hoa/blender
python3 tao_texture.py                                         # decal A0, breadboard, màn hình dashboard
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b -P dung_canh.py -- --views hero,pole,closeup,cam_J1,cam_J2,top,front --samples 128   # ~4 phút trên M1 Pro
$B -b -P linh_kien_scene.py -- --samples 128                                   # ~1 phút
cd ../.. && python3 _scripts/chu_thich_render.py               # chú thích, ROI, kích thước
python3 _scripts/tao_docx.py                                   # dựng lại file Word từ các noi_dung_*.md
```

- Muốn thử nhanh thì thêm `--samples 16 --percent 40`.
- Muốn chỉnh trực tiếp trong Blender thì mở `blender/sa_ban_edgeflow.blend`. File có sẵn các camera `cam_hero`, `cam_pole`, `cam_closeup`, `cam_J1`, `cam_J2`, `cam_top`, `cam_front`.

## Những điều phải giữ đúng

- **Render không phải ảnh chụp.** Mỗi ảnh có dòng "Render 3D minh họa" ở góc, và chú thích trong `.docx` cũng ghi rõ điều này. Mục 4.4 nằm trong phần "Kết quả đạt được", nên ngay khi có ảnh chụp sa bàn hoặc mạch thật, hãy thêm ảnh thật vào.
- Hình 4.4 chỉ vẽ ROI, **không** vẽ khung phát hiện xe, vì chưa có kết quả phát hiện trên ảnh sa bàn thật.
- Hình 3.3 vẽ cho **triển khai thực tế** (góp ý của Bảo Lâm, 11/10): không nhắc laptop, sa bàn là một khu vực giao thông bất kỳ, Pi dùng Wi-Fi. Chi tiết trong ghi chú cuối `noi_dung_3.3.md`.
- Những chỗ code chưa làm, hình vẫn ghi rõ:
  - Đọc 2 camera trên 1 Pi: H3.1 ghi "đang phát triển".
  - Graph-Control chưa đọc topic ack: footnote bảng topic H3.3.
  - (API theo dõi MQTT đã có trên `origin/main` từ 11/10, nên hình đã đổi sang nét liền.)
- Các số đo của sa bàn (ống kính 400 mm, cụm đèn 112 mm, 560 mm, đường 120 mm, dải mạch 200 mm) và trụ nhôm 20 × 20 là **phương án đề xuất**. Sa bàn thật khác thì sửa `bo_tri.py` rồi dựng lại.
- Bảng linh kiện lấy số lượng theo `MUA_SAM_CON_THIEU.md` (04/10). Đội cần kiểm lại món nào đã mua và lắp thật.

## Đổi sang 2 trụ giao thông (11/10)

Hiển yêu cầu ngày 10/10. Công Thịnh nói rõ thêm (ảnh chụp tin nhắn: `_ghi_chu/yeu_cau_tru_giao_thong_Cong_Thinh_2026-10-10.png`): thu nhỏ giá chữ L, gắn thêm đèn, thành 1 trụ giao thông cho mỗi ngã tư. Lý do: hạ tầng thật không có một camera khổng lồ quan sát toàn mạng.

Hiển chốt ngày 11/10:
- Cụm đèn 4 mặt trên trụ **thay cho** 4 cột module đèn nhỏ. Vẫn 8 module, giữ nguyên GPIO và cách mắc song song.
- **1 Pi + 2 camera**, dùng 2 cổng CSI (CAM0 → J1, CAM1 → J2). Pi đặt ven đường giữa hai trụ.

Bố trí (`bo_tri.py`):
- Trụ J1 ở góc Đông-Bắc, trụ J2 ở góc Tây-Bắc, cách tâm ngã tư 100 mm mỗi trục. Cần vươn chéo 141 mm tới tâm ngã tư.
- Ống kính cao 400 mm, nhìn thẳng xuống, cạnh dài khung hình dọc theo cần. Cụm đèn treo ở tâm ngã tư, tâm cao 112 mm.
- ROI dài 200 mm (khoảng 2 xe); trên đoạn nối thì dừng ở giữa đoạn (182 mm). Ống kính phải cao tối thiểu 382 mm mới thấy trọn 4 ROI, chọn 400 mm.
- Cáp CSI đi dọc mặt sa bàn → rãnh trụ → lưng cần, dài ~0,77 m mỗi bên → dùng cáp 1 m.

Việc **còn phải làm ngoài folder này** (chưa sửa code):
- **Code vision chưa đọc được 2 camera.** `video_source.py` gọi `Picamera2()` không có `camera_num`, nên chỉ mở camera 0. `main.py` dùng `client_id` MQTT cố định và topic health cố định `edgeflow/v1/health/vision`, nên hai tiến trình vision (mỗi camera một tiến trình với `VISION_NODE_IDS=J1` hoặc `J2`) sẽ đá nhau khỏi broker. Phải sửa trước khi demo. Hình H3.1 đã ghi "đang phát triển".
- Plan (2) chốt phạm vi "1 Pi + 1 camera", nên đây là thay đổi phạm vi, cần cả đội đồng ý.
- Mua sắm (`MUA_SAM_CON_THIEU.md` chưa cập nhật):
  - thêm 1 Camera Module 3 Wide;
  - cáp 22 → 15 pin đổi từ 300 + 500 mm sang 2 sợi 1 m (loại này ít phổ biến, phải thử ảnh có ổn định không);
  - 2 sợi cáp 8 lõi ~1,2 m lên trụ;
  - nhôm định hình 20 × 20 cho 2 trụ.
- Pi chạy YOLO cho 2 luồng nên FPS mỗi luồng sẽ giảm. Đo lại bằng `benchmark.py`.
- ROI thật vẽ riêng cho từng camera bằng `roi_calibrate.py`. Khung hình xoay 45° theo cần, nên các đường đi chéo trong ảnh.
