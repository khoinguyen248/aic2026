# TRAKE — cách hiện thực (cho team đọc/sửa code)

> Mục tiêu file này: giúp người **chưa từng đụng vào code TRAKE** đọc xong là biết code nằm ở đâu,
> chạy theo thứ tự nào, muốn sửa/thêm gì thì sửa ở đúng hàm nào. Không đi sâu công thức toán —
> cần công thức chi tiết thì đọc thẳng code trong `trake_service.py` (đã có comment tại chỗ khó hiểu).

## 1. Sơ đồ tổng quan — ai gọi ai

```
Client (frontend/Postman)
   │  POST /search/trake  {events: [...], language: true}
   ▼
search_routes.py            -> chỉ khai báo route, gọi thẳng qua controller
   ▼
trake_controller.py         -> đọc request, dịch VI->EN nếu cần, load model, gọi service
   ▼
trake_service.run_trake()   -> hàm "nhạc trưởng", gọi lần lượt 4 bước bên dưới
   │
   ├─ 1. select_video_dp()        -> chọn video đúng nhất
   ├─ 2. allocate_video_slots()   -> chia slot nộp bài cho video hạng 1/hạng 2
   ├─ 3. locate_events_exact()    -> định vị thô từng event trong video đã chọn
   ├─ 4. refine_event_fine()      -> (nếu có video gốc) tinh chỉnh xuống frame gốc
   │        └─ rerank khoảnh khắc: thuật toán (mặc định) hoặc Qwen (khi tie + đã bật)
   └─ 5. build_cartesian_submissions() -> ghép thành nhiều phương án nộp, xếp hạng
   ▼
Trả JSON: {mode, video_candidates, submissions}
```

## 2. File nào làm việc gì

| File | Vai trò |
|---|---|
| [`app/routes/search_routes.py`](backendAIC2025/app/routes/search_routes.py) | Khai báo route `POST /search/trake`, không chứa logic |
| [`app/controllers/trake_controller.py`](backendAIC2025/app/controllers/trake_controller.py) | Nhận request HTTP, validate input, gọi model + service, trả JSON |
| [`app/controllers/search_controller.py`](backendAIC2025/app/controllers/search_controller.py) | Có hàm `ensure_models()` — load CLIP/FAISS **1 lần duy nhất** (singleton), TRAKE dùng lại chung, không load riêng |
| [`app/services/trake_service.py`](backendAIC2025/app/services/trake_service.py) | **Toàn bộ thuật toán nằm ở đây** — file duy nhất cần đọc nếu muốn hiểu/sửa logic TRAKE |
| [`app/config.py`](backendAIC2025/app/config.py) | Các biến cấu hình TRAKE đọc từ `.env` (bật/tắt tinh chỉnh, đường dẫn video, bật/tắt Qwen rerank, ...) |

## 3. Đi từng bước trong `trake_service.py`

### Bước 0 — biến câu chữ thành vector

```python
event_vecs = encode_texts(events_text, clip_bundle, device)
```
Mỗi câu mô tả event → 1 vector số (CLIP text encoder). Có `event_vecs[0]` cho event 1,
`event_vecs[1]` cho event 2, v.v. Toàn bộ so khớp phía sau đều là **so vector với vector** bằng
tích vô hướng (càng cao càng giống nhau).

### Bước 1 — `select_video_dp()`: tìm đúng video

Cách làm đơn giản hoá:
1. Với mỗi event, tìm top-150 keyframe giống nhất **trong toàn bộ kho** (không phân biệt video).
2. Gom các keyframe đó theo video (`L`, `V`).
3. Video nào **có mặt đủ trong top-150 của TẤT CẢ event** mới được xét tiếp (video thiếu 1 event
   coi như chưa đủ bằng chứng, bỏ qua).
4. Với mỗi video còn lại, tính "đường đi tốt nhất" qua các event **theo đúng thứ tự thời gian**
   (event sau phải xảy ra sau event trước — không được đảo ngược). Hàm phụ trách việc này là
   `_dp_align()` — nếu tò mò cách nó chọn đường đi tối ưu, đọc comment trong hàm.
5. Video có tổng điểm đường đi cao nhất → được chọn.

Nếu không video nào đủ dữ liệu (bước 3 loại hết) → tự động thử lại với top-450, rồi top-1350
(tăng dần x3, tối đa 3 lần) trước khi báo lỗi "không tìm được video".

### Bước 2 — `allocate_video_slots()`: có nên tin tuyệt đối vào video hạng 1 không?

Đề cho nộp tối đa 100 phương án. Nếu video hạng 1 và hạng 2 điểm số sít sao (không chắc chắn),
dồn hết 100 phương án cho hạng 1 là mạo hiểm. Hàm này chia:
- Nếu hạng 1 "rất tự tin" (vượt ngưỡng `TRAKE_VIDEO_CONFIDENCE_THRESHOLD`, mặc định 0.8) → dồn hết
  100 slot cho hạng 1.
- Nếu không chắc → chia sẻ, ví dụ 80 slot cho hạng 1, 20 slot cho hạng 2.

### Bước 3 — `locate_events_exact()`: định vị thô từng event trong video đã chọn

Lấy toàn bộ keyframe của đúng video đó (không lẫn video khác), so từng event với từng keyframe,
chọn khớp nhất — **nhưng bắt buộc keyframe của event sau phải đứng sau keyframe của event trước**
(nếu không, code sẽ tự nới lỏng ràng buộc để tránh trả về rỗng). Hàm trả về **top-3 ứng viên** mỗi
event (không chỉ 1), để dùng cho bước ghép tổ hợp ở bước 5.

### Bước 4 — `refine_event_fine()`: tinh chỉnh xuống frame gốc (CHỈ CHẠY NẾU CÓ VIDEO GỐC)

Đây là bước duy nhất cần **file video thật** (không chỉ keyframe). Với vị trí thô tìm được ở
Bước 3, mở video gốc, đọc khoảng 30 frame xung quanh (±15 frame), so từng frame với event bằng
CLIP → có 1 đường cong điểm số theo thời gian. Việc "có chạy bước này hay không" được quyết định
tự động — xem mục 4 (Case 1/2).

**Rerank khoảnh khắc (chọn đúng frame trong số các frame gần giống nhau):**
1. **Mặc định — thuật toán, miễn phí, luôn chạy** (`pick_semantic_frame_algorithmic()`): thay vì
   chỉ lấy điểm cao nhất (argmax), tìm **đỉnh rõ rệt** trên đường cong điểm số (peak/prominence,
   dùng `scipy.signal.find_peaks`) — tách được "khoảnh khắc" thật ra khỏi một dải nhiều frame gần
   giống hệt nhau mà CLIP không phân biệt nổi. Nếu không tìm được đỉnh nào (hoặc thiếu scipy),
   tự rơi về argmax thường — không bao giờ tệ hơn cách cũ.
2. **Tuỳ chọn — Qwen2.5-VL (chạy LOCAL), chỉ gọi khi thật sự cần**: nếu 2 ứng viên đầu (sau bước
   1) vẫn **tie sít sao** (chênh lệch điểm < `TRAKE_RERANK_TIE_MARGIN`, mặc định 0.03) **và** đã bật
   `TRAKE_QWEN_RERANK_ENABLED=true` → đưa các frame đang tie kèm mô tả event cho Qwen chọn đúng
   khoảnh khắc ngữ nghĩa. Qwen được **load local qua transformers và giữ ấm trên GPU** (spec mục
   13), **quantize 4bit/8bit** để giảm VRAM/RAM cho model 7B/72B — **không dùng API bên ngoài**.
   Nếu load/inference lỗi (thiếu GPU, thiếu thư viện, ...) → **tự fallback về kết quả thuật toán**,
   không bao giờ làm hỏng kết quả.

Cơ chế bật/tắt Qwen **giống hệt kiểu Case 1/2** đã làm cho tier 3 — tự động theo cấu hình, không
cần sửa code khi đổi máy.

### Bước 5 — `build_cartesian_submissions()`: ghép thành nhiều phương án nộp

Mỗi event đang có vài ứng viên (top-3). Thay vì chỉ ghép ứng viên #1 của từng event thành 1 phương
án duy nhất, hàm này **ghép mọi tổ hợp có thể** (event1-ứng viên nào × event2-ứng viên nào × ...),
loại tổ hợp nào không đúng thứ tự thời gian, xếp hạng theo độ tin cậy, lấy tối đa 100 (hoặc số
slot được chia ở Bước 2). Lý do làm vậy: đề chấm điểm theo "trúng ở bất kỳ phương án nào trong 100
phương án nộp", nên nộp nhiều phương án hợp lý tăng khả năng trúng hơn hẳn chỉ nộp 1 phương án.

## 4. Case 1 (đủ video gốc) / Case 2 (không có) — điểm quyết định nằm ở đâu trong code

```python
def tier3_globally_ready():
    if not Config.TRAKE_TIER3_ENABLED:
        return False, "..."
    if not Config.VIDEO_ROOT or not os.path.isdir(Config.VIDEO_ROOT):
        return False, "..."
    ...
    return True, "tier 3 sẵn sàng"
```

Hàm này được gọi 1 lần trong `run_trake()`. Nếu trả `False` → toàn bộ Bước 4 (tinh chỉnh) bị bỏ
qua, code dùng thẳng kết quả thô của Bước 3 làm ứng viên cho Bước 5. Muốn bật Case 1, chỉ cần set
2 biến trong `.env`:

```env
TRAKE_TIER3_ENABLED=true
VIDEO_ROOT=E:\aic2026_videos
```

Không set (hoặc set nhưng USB chưa gắn) → tự rơi về Case 2, không cần sửa code, không crash.

**Rerank Qwen cũng có công tắc riêng tương tự** (`qwen_rerank_ready()`), độc lập với Case 1/2.
Qwen chạy **local** (load qua transformers, giữ ấm trên GPU, quantize để tiết kiệm RAM/VRAM),
**không dùng API**:

```env
TRAKE_QWEN_RERANK_ENABLED=true
QWEN_MODEL_PATH=Qwen/Qwen2.5-VL-7B-Instruct
QWEN_QUANTIZATION=4bit          # 4bit | 8bit | none
QWEN_DEVICE_MAP=auto
QWEN_MAX_NEW_TOKENS=10
```

- `QWEN_QUANTIZATION=4bit` (mặc định): model 7B chạy vừa ~6–8GB VRAM nhờ bitsandbytes. `8bit` nếu
  VRAM dư; `none` nếu bạn trỏ `QWEN_MODEL_PATH` tới bản **đã prequant AWQ/GPTQ**.
- Cần cài thêm (chỉ khi bật Qwen, cần GPU): `accelerate`, `bitsandbytes` (cho 4bit/8bit),
  và `qwen-vl-utils` — đã liệt kê dạng comment trong `requirements.txt`.
- Model load **lazy 1 lần** ở lần rerank đầu tiên rồi giữ ấm; nếu load lỗi (không GPU / thiếu thư
  viện) → tự tắt Qwen và dùng thuật toán, không crash. Không bật → luôn chỉ dùng thuật toán.

## 5. Muốn thêm/sửa gì thì sửa ở đâu

| Muốn làm | Sửa ở |
|---|---|
| Đổi số lượng ứng viên video xét (hiện tại top-2) | `Config.TRAKE_TOP_VIDEOS` trong `.env` |
| Đổi bán kính quét tinh chỉnh (hiện tại ±15 frame) | `Config.TRAKE_TIER3_RADIUS` |
| Đổi ngưỡng coi là "tie" để gọi Qwen | `Config.TRAKE_RERANK_TIE_MARGIN` |
| Đổi prompt gửi Qwen | `qwen_rerank_candidates()` trong `trake_service.py` |
| Đổi cách load/quantize Qwen | `_load_qwen()` trong `trake_service.py` + các biến `QWEN_*` trong `.env` |
| Thêm leg BEiT-3 hoặc jina-clip-v2 cho TRAKE (hiện chỉ dùng CLIP) | Viết thêm `encode_texts_beit3()`/`encode_images_beit3()` tương tự `encode_texts()`/`encode_images()` trong `trake_service.py`, rồi cho `run_trake()` nhận thêm 1 `model_bundle` |
| Đổi công thức chọn video (Bước 1) | `_dp_align()` + `select_video_dp()` |
| Đổi cách sinh tổ hợp nộp (Bước 5) | `build_cartesian_submissions()` + `nms_candidates()` |
| Test nhanh logic mà không cần Mongo/model thật | `_dp_align`, `build_cartesian_submissions`, `pick_semantic_frame_algorithmic`, `qwen_rerank_ready`, `qwen_rerank_candidates` đều là hàm thuần (pure function hoặc tự fallback an toàn) — gọi trực tiếp với dữ liệu giả lập được, không cần Flask/DB/model thật |

## 6. Dùng API nhanh (để test tay)

```
POST /search/trake
{ "events": ["mô tả event 1", "mô tả event 2", "..."], "language": true }
```

Trả về `submissions`: danh sách `{video_id, frame_ids}` đã xếp hạng sẵn, lấy từ đầu danh sách để
nộp bài. Response còn có `qwen_rerank_globally_ready`, `qwen_rerank_reason`,
`qwen_rerank_used_events` để biết Qwen có thực sự được gọi lần nào không.

Cần `SEARCH_ENABLED=true` và chạy backend ngoài Docker (`python run.py`) vì Docker hiện chưa cài
torch/faiss/opencv/scipy.
