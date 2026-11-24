# Auto-label YOLO (chuẩn bị dữ liệu fine-tune)

Gán nhãn tự động (pre-label) cho video giao thông thật trong
`services/vision/input_videos/*.mp4` để làm dữ liệu khởi đầu cho fine-tune model YOLO —
dùng detector COCO sẵn có của project để đề xuất box+class, rồi dùng SAM (MobileSAM qua
`ultralytics`) để tinh chỉnh box cho sát vật thể hơn. Đây là nhãn **mẫu/khởi điểm**, không phải
ground truth cuối cùng — luôn duyệt `dataset/review/*.jpg` trước khi tin dùng để train.

Hoàn toàn tách biệt với `services/vision` runtime (chỉ đọc lại code của nó, không sửa gì ngoài
1 thay đổi thuần-cộng-thêm đã làm sẵn trong `services/vision/vision/detector.py` để lộ
`last_class_ids`) và không đụng `services/vision/requirements.txt` (vốn phải nhẹ cho Raspberry
Pi) — dependency của pipeline này nằm riêng trong `requirements.txt` ở đây.

## Cài đặt

```bash
uv pip install -r experiments/auto-label-yolo/requirements.txt
```

CPU-only (không cần CUDA). Chạy mọi lệnh dưới đây từ **gốc repo** — checkpoint SAM sẽ tự tải về
thư mục hiện tại (`mobile_sam.pt`, ~40MB, chỉ tải lần đầu; đã nằm trong `.gitignore` gốc).

## Chạy từng bước (nên thử trên 1 video, giới hạn frame trước)

```bash
# a) Trích frame (mặc định 1 frame/giây, bỏ frame gần giống nhau)
python experiments/auto-label-yolo/extract_frames.py \
    --videos services/vision/input_videos/1.mp4 \
    --out experiments/auto-label-yolo/dataset \
    --max-frames-per-video 20   # bỏ flag này khi chạy thật

# b) Đề xuất box + lớp (car/motorcycle/bus/truck) bằng YOLOv8n COCO đã có trong repo
python experiments/auto-label-yolo/propose_boxes.py \
    --images experiments/auto-label-yolo/dataset/images \
    --model services/vision/models/yolov8n.onnx \
    --out experiments/auto-label-yolo/dataset/proposals.json

# c) Tinh chỉnh box bằng SAM (prompt = box ở bước b)
python experiments/auto-label-yolo/refine_with_sam.py \
    --images experiments/auto-label-yolo/dataset/images \
    --proposals experiments/auto-label-yolo/dataset/proposals.json \
    --out experiments/auto-label-yolo/dataset/proposals_refined.json

# d) Ghi nhãn YOLO chuẩn + ảnh review + manifest/data.yaml
python experiments/auto-label-yolo/export_dataset.py \
    --dataset-dir experiments/auto-label-yolo/dataset

# e) (tùy chọn) Xuất thêm 1 bản annotations_coco.json chuẩn COCO, để mở được bằng các
#    tool gán nhãn tay hỗ trợ COCO (không chỉ tool hỗ trợ YOLO) -- xem mục "Gán nhãn tay" dưới.
python experiments/auto-label-yolo/export_coco.py \
    --dataset-dir experiments/auto-label-yolo/dataset
```

Sau đó duyệt `dataset/review/*.jpg` (box + tên lớp vẽ sẵn) trước khi tin dùng. Khi hài lòng,
chạy lại bước (a) với toàn bộ 5 video (`--videos services/vision/input_videos/*.mp4`), bỏ
`--max-frames-per-video`, rồi lặp lại b→c→d. Bước (c) chạy trên CPU là bước chậm nhất với khối
lượng lớn — có thể dùng `--limit N` ở bước b/c để chạy theo lô, hoặc chạy nền/qua đêm cho full
batch (~27 phút video, 1 frame/giây ≈ 1600 frame trước khi lọc trùng).

## Kết quả

```
dataset/
  images/          # frame gốc đã trích
  labels/          # nhãn YOLO: "<class_id> <cx> <cy> <w> <h>" (chuẩn hoá 0-1), rỗng nếu không có xe
  review/           # ảnh gốc + box/label vẽ đè, để duyệt mắt
  classes.txt        # car / motorcycle / bus / truck (thứ tự = class_id)
  data.yaml          # config kiểu Ultralytics (path/train/val/nc/names)
  manifest.json       # provenance: model + sha256, tham số từng bước, số liệu cuối
  annotations_coco.json  # (sau khi chạy bước e) cùng dữ liệu, chuẩn COCO (categories 1-indexed)
```

## Định dạng nhãn có chuẩn COCO không?

`labels/*.txt` là format **YOLO** (class_id đếm từ 0, box chuẩn hoá 0-1) -- đây là format gốc
để train YOLO, **không phải** JSON COCO, nhưng class origin vẫn là COCO: model đề xuất box ở
bước (b) là YOLOv8n huấn luyện trên COCO, chỉ lọc lại 4 lớp phương tiện (COCO id 2/3/5/7 ->
YOLO id 0/1/2/3 qua `common.COCO_TO_YOLO_CLASS`).

Đã kiểm tra format trên toàn bộ dataset hiện có (1646 ảnh, 14272 box): mỗi ảnh có đúng 1 file
`.txt` tương ứng, mọi dòng đủ 5 trường, class_id trong [0,3], toạ độ trong [0,1] -- không có
dòng lỗi.

Nếu cần JSON COCO thật (để mở bằng tool chỉ hỗ trợ COCO, hoặc chia sẻ với pipeline khác), chạy
bước (e) `export_coco.py` ở trên -- script đọc lại đúng `labels/*.txt` đã ghi (không phải state
giữa các bước) để sinh `annotations_coco.json` (`images`/`annotations`/`categories`, bbox
`[x,y,w,h]` pixel tuyệt đối, `category_id` 1-indexed đúng chuẩn COCO). Đã validate: bbox không
vượt biên ảnh, mọi `category_id` tham chiếu đúng category.

## Gán nhãn tay / sửa nhãn thủ công bằng AutoLabelImg

Repo chưa có tool GUI gán nhãn nào cài sẵn. "AutoLabelImg" gốc
([ofeksadlo/AutoLabelImg](https://github.com/ofeksadlo/AutoLabelImg)) là bản rất cũ (Python
3.7.7, nhắm Darknet YOLOv3/v4) nên dùng fork **[T-SW/AutoLabelImg](https://github.com/T-SW/AutoLabelImg)**
(dựa trên `labelImg`, auto-detect bằng YOLOv8) -- khớp đúng họ model YOLOv8 pipeline này đang
dùng (`services/vision/models/yolov8n.onnx` cũng export từ YOLOv8n).

Đã đọc trực tiếp source code của fork này (`libs/yolo_io.py`, `autolabelImg.py`, README) để kiểm
tra tương thích thật, không đoán -- vài điểm khác với suy đoán ban đầu, **1 điểm thực sự không
tương thích** cần sửa trước khi mở dataset:

- **Entry point thật là `autolabelImg.py`**, không phải `labelImg.py` như README của repo đó ghi
  (file đó không tồn tại ở root -- README gốc tự mâu thuẫn).
- **`classes.txt` phải nằm cùng thư mục với các file `.txt` nhãn** (tức `dataset/labels/
  classes.txt`), **không phải `dataset/classes.txt`** như `export_dataset.py` đang ghi -- đây là
  điểm không tương thích thật, phải copy file qua trước khi mở.
- `requirements.txt` của repo đó **thiếu `ultralytics`** (code có `from ultralytics import YOLO`
  nhưng package không nằm trong `requirements.txt`) -- phải cài tay.
- Weight chỉ nhận **`.pt`** (`models/*.pt`, mặc định `models/yolov8n.pt`) -- không đọc được
  `.onnx`, nên vẫn cần lấy `yolov8n.pt` như dự tính, không dùng `.onnx` của pipeline này được.
- Config auto-detect (`default.yaml`) **tự sinh khi chạy lần đầu** (không có sẵn trong repo) với
  mặc định `classes: [2, 5, 7]` -- **thiếu motorcycle (id COCO 3)** so với 4 lớp pipeline này
  dùng, phải tự thêm `3` vào sau lần chạy đầu.
- Repo còn 1 file riêng `data/predefined_classes.txt` (danh sách lớp gợi ý khi gõ tay) --
  README gốc ghi rõ nguyên nhân crash thường gặp là file này **không khớp** với `classes.txt`
  của dataset, nên phải sửa cho khớp y hệt `classes.txt` (car/motorcycle/bus/truck, đúng thứ tự).

Cài ở **venv riêng**, Python **3.8** (README gốc cảnh báo Python 3.10+ dễ crash do định dạng dữ
liệu vẽ box không tương thích -- không liên quan/không nên trộn với venv của pipeline này hay
của `services/vision`):

```bash
uv venv --python 3.8 .venv-autolabelimg
.venv-autolabelimg\Scripts\activate   # Windows; .venv-autolabelimg/bin/activate trên macOS/Linux
git clone https://github.com/T-SW/AutoLabelImg.git
cd AutoLabelImg
uv pip install pyqt5 lxml torch ultralytics
uv pip install -r requirements.txt
pyrcc5 -o libs/resources.py resources.qrc
```

Lấy sẵn weight `yolov8n.pt` (cùng gốc COCO với `yolov8n.onnx` đang dùng ở bước (b), chỉ khác
định dạng export) bỏ vào `models/yolov8n.pt` của AutoLabelImg -- có thể lấy qua
`python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"` (tự tải về) rồi copy file sang.
Chạy `python autolabelImg.py` 1 lần để nó tự sinh `./default.yaml`, sửa `classes: [2, 3, 5, 7]`
(thêm motorcycle) và `model: models/yolov8n.pt`, rồi sửa `data/predefined_classes.txt` thành
đúng 4 dòng `car`/`motorcycle`/`bus`/`truck` (khớp thứ tự `classes.txt`).

**Trước khi mở dataset**: copy `dataset/classes.txt` thành `dataset/labels/classes.txt` (giữ
bản gốc ở `dataset/classes.txt` làm backup, vì save dir cần `classes.txt` nằm ngay trong
`labels/`, và tool sẽ **ghi đè `classes.txt` mỗi lần save**).

Trong GUI, mở thư mục `dataset/images`, đặt save dir trùng `dataset/labels`, bật định dạng lưu
YOLO (nút toggle PascalVOC/YOLO/CreateML -- ưu tiên đọc PascalXML > YOLO > CreateML nếu có nhiều
file cùng tên, ta không có `.xml` nên không bị nhầm). Vì `dataset/labels/*.txt` đã đúng format
YOLO, mỗi ảnh mở lên sẽ tự hiện box auto-label có sẵn (không cần import gì thêm). Phím tắt auto
detect 1 ảnh: `Ctrl+P`; auto-label theo lô (ảnh hiện tại+sau / toàn bộ / theo khoảng index): `Ctrl+M`
-- dùng được để chạy lại YOLOv8 cho các ảnh còn thiếu box (vd 9 ảnh zero-box) mà không cần làm
từng ảnh. Nhãn ghi đè trực tiếp vào `dataset/labels/*.txt` -- đây sẽ là nhãn cuối cùng dùng để
fine-tune.

**Đã kiểm chứng id không bị xáo trộn khi sửa tay** -- không chỉ đọc code mà đã chạy thật
`YOLOWriter`/`YoloReader` gốc của fork này trên 2 file nhãn thật (`5_003480.txt` 23 box,
`3_008700.txt` 20 box), mô phỏng sửa tay (dịch box + đổi nhãn 1 box, kiểu `motorcycle -> bus`),
rồi đọc lại file vừa lưu: id đổi đúng theo tên lớp mới, `classes.txt`/`label_hist` không bị
xáo trộn thứ tự giữa các ảnh. Lý do: app chỉ nạp `label_hist` **1 lần lúc mở** (từ
`data/predefined_classes.txt`), dùng chung cho mọi lần save, không dựng lại theo từng ảnh --
nên id chỉ ổn định đúng car=0/motorcycle=1/bus=2/truck=3 **nếu** `data/predefined_classes.txt`
đã được set đúng 4 dòng này theo đúng thứ tự *trước khi mở app lần đầu* (bước ở trên). Vẫn nên
thử sửa+lưu 1-2 ảnh đầu rồi mở lại `.txt` xem qua cho chắc, nhưng đây giờ là bước xác nhận cuối,
không còn là rủi ro chưa rõ.

**Đừng chạy lại `export_dataset.py` (bước d) sau khi đã sửa tay**: nó ghi `labels/` từ
`proposals_refined.json` (bản auto-label cũ), nên sẽ **xoá mất nhãn vừa sửa tay**. Chỉ cần chạy
lại `export_coco.py` (bước e) nếu muốn JSON COCO khớp bản đã sửa -- script đó đọc thẳng
`dataset/labels/*.txt` hiện tại (không qua `proposals_refined.json`) nên an toàn với nhãn đã
sửa tay.

`data.yaml` hiện đặt `train`/`val` cùng trỏ `images/` (placeholder 1-split) — trước khi fine-tune
thật nên tách train/val theo `video_id` (không tách theo frame liền kề, tránh rò rỉ dữ liệu gần
giống nhau giữa 2 tập), cùng tinh thần `capture_dataset.py` đã ghi trong docstring của nó.

## Xem lại kết quả dưới dạng video

Ghép các ảnh `review/*.jpg` (đã có box/nhãn) trở lại thành video .mp4 theo từng video gốc, để
xem lướt thay vì mở từng ảnh:

```bash
python experiments/auto-label-yolo/make_preview_video.py \
    --dataset-dir experiments/auto-label-yolo/dataset \
    --video-id all --fps 5
```

Ghi ra `dataset/preview/<video_id>.mp4` (mỗi video gốc 1 file, có caption góc trên trái ghi
video id + mốc thời gian gốc). Mỗi frame trong review đại diện 1 giây video gốc (do lấy mẫu
1 frame/giây), nên `--fps` chỉ là tốc độ phát lại (xem lướt nhanh), không phải thời gian thực —
`--fps 5` nghĩa là 5 giây video gốc được chiếu trong 1 giây. Dùng `--video-id 1` (thay vì `all`)
để chỉ xuất 1 video nếu muốn kiểm nhanh.

## Lưu ý

- Nhãn đa lớp (4 lớp) khác với quy ước 1 lớp "vehicle" của model sa bàn hiện tại
  (`yolo11n_sa_ban.onnx`, xem `docs/competition/ke_hoach/KE_HOACH_DEPLOY.md`) — bộ dữ liệu này
  nhắm tới video giao thông thật ngoài đường, không phải sa bàn thu nhỏ.
- `--sam-model` đổi được sang `FastSAM-s.pt`/`sam_b.pt` nếu muốn thử biến thể khác (mặc định
  `mobile_sam.pt` để chạy được trên CPU).
- Nhãn tự động không hoàn hảo (nhất là xe nhỏ/xa, ngược sáng) — luôn coi là điểm khởi đầu để sửa
  tay, không phải ground truth.
