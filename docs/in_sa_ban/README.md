# In sa bàn EdgeFlow AI (đội 31µF)

Sa bàn là **một tấm bạt 1200 × 600 mm** (cuộn lại được), hai ngã tư J1 (trái) và J2 (phải) trên cùng một mặt in.
Quyết định ngày 18/10 (chiều): đội in bạt thay cho 2 tấm fomex 600 × 600 + 2 khay, vì quan trọng nhất là mô hình
chạy và điều khiển đèn chuẩn xác, không cần mặt cứng. Bạt trải lên **bàn phẳng, cứng**; trụ đứng trên 2 đế MDF riêng.

## Mang ra tiệm quảng cáo

| File | Đưa tiệm? | Nội dung |
|---|---|---|
| `PHIEU_DAT_IN.pdf` | Trang 1–2 | Phiếu đặt in (vật liệu, kích thước, số lượng) và bản vẽ đế trụ MDF |
| `SA_BAN_BAT_1200x600.pdf` | Có | Mặt bạt, vector, tỉ lệ 1:1, khổ 1240 × 640 mm gồm 20 mm tràn lề mỗi cạnh để gấp viền |
| `SA_BAN_BAT_1200x600_60dpi.jpg` | Chỉ để xem | Ảnh xem trước, không dùng để in |
| `NHAN_DECAL_A4.pdf` | Có | Cờ nhãn cáp W1/W2/P1–P4, nhãn ESP32, Pi, S1, X1/X2, cực nguồn, nhãn trụ, nhãn đế |
| `BANG_GIOI_THIEU_A3.pdf` | Có | Bảng dựng cạnh sa bàn lúc thi |

Trang 3 của phiếu dành cho đội: bảng kiểm khớp từng thiết bị, chiều dài cáp, cách lắp và cách chở.

**Đặt in:** bạt Hiflex mờ, dày ≥ 440 g/m², gấp viền 20 mm dán keo, bấm khoen 4 góc nếu có. Đế trụ: 2 tấm MDF 6 ly vuông 200 mm
(cắt ở tiệm gỗ hoặc quảng cáo có CNC).

## Sinh lại

```bash
python3 in_sa_ban/_nguon/tao_tat_ca.py
```

- Dùng Python hệ thống, không cần thư viện ngoài.
- Cần Google Chrome (in HTML ra PDF) và poppler (`pdftoppm`, `pdfinfo`, `pdffonts`).
- Script tự kiểm: khớp thiết bị, chống lật của trụ, khổ trang, số trang, font đã nhúng. Có lỗi thì exit 1.

Muốn đổi số đo thì sửa `_nguon/hinh_hoc.py`; mặt đường và trụ lấy từ
`thiet_ke_bao_cao/4.4_hinh_minh_hoa/blender/bo_tri.py`.

## Những gì là ước tính

- Kích thước vỏ Pi 5 và jack X1: phải đo hàng thật. Ô in trên bạt rộng hơn thiết bị 6 mm mỗi bên.
- Vị trí lỗ ốc ke chân trụ: icdayroi không ghi kích thước ke. Đặt ke thật lên đế rồi khoan theo lỗ ke.
- **Trụ đứng trên đế MDF mà không bắt xuống bàn**: tỉ số chống lật 2,8 lần chỉ là ước tính từ khối lượng giả định
  (trụ 86 g, cần + cụm đèn 190 g). Lắp thật rồi lắc thử; nếu lung lay thì dằn thêm lên đế hoặc dán chặt xuống bàn.
- Chiều dài cáp W (~0,82 m) và dây P3 (~0,29 m) tính theo đường dán sát mặt bạt, cộng 30 % độ chùng.
- Cáp W và P3 nằm **trên** mặt bạt (dán băng keo vải), vắt qua đường gần giữa bạt; không còn lỗ luồn dây như bản 2 tấm.
- Hình báo cáo (H4.x, Phụ lục A) vẫn vẽ tấm A0 có dải mạch phía trước.
