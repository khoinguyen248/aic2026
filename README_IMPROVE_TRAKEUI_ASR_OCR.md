# Cải tiến: TRAKE UI + ASR search + OCR search

> Tổng hợp toàn bộ thay đổi trong đợt này và cách cấu hình để chạy. Đọc kèm:
> [README_TRAKE.md](README_TRAKE.md) (pipeline TRAKE), `AIC2026_IMPROVEMENT_SPEC (1).md` (§8 OCR, §9 ASR, §10.3 TRAKE).

---

## 1. Tóm tắt những gì đã làm

1. **TRAKE 3 tầng + rerank** — tìm chuỗi sự kiện theo thời gian, tự sinh tối đa 100 tổ hợp frame.
   - Tầng 1 chọn video (DP alignment), tầng 2 định vị thô, tầng 3 tinh chỉnh frame gốc (nếu có video).
   - Rerank khoảnh khắc: **thuật toán** (peak-detection, luôn chạy) + **Qwen2.5-VL local** (khi 2 ứng viên tie).
2. **TRAKE UI** — panel nhập N event → list tổ hợp → bấm 1 tổ hợp để xem frame verify (ảnh decode từ video).
3. **ASR search** — tìm theo **nội dung lời nói** (collection `asr_segments`). 2 mode: độc lập / gộp vào search chính.
4. **OCR search** — tìm theo **chữ trên màn hình** (`ocr_text` trong `frames`). 2 mode như ASR.
5. **Dọn UI** — bỏ object search cũ (palette, drop area, object fillin, AND/OR, "Text indicator", select temporal-fuzzy). UI toàn bộ **tiếng Anh**.

---

## 2. File thêm / sửa / xoá

### Backend (`backendAIC2025/`)
| File | Thay đổi |
|---|---|
| `app/services/trake_service.py` | **MỚI** — toàn bộ thuật toán TRAKE (DP, tinh chỉnh, Cartesian, rerank thuật toán + Qwen local) |
| `app/controllers/trake_controller.py` | **MỚI** — `trake_search()` + `trake_frame()` (decode frame verify) |
| `app/controllers/asr_controller.py` | **MỚI** — `asr_search()` (độc lập) + `asr_boost_idxset()` (merge) |
| `app/controllers/ocr_controller.py` | **MỚI** — `ocr_search()` (độc lập) + `ocr_boost_idxset()` (merge) |
| `app/controllers/search_controller.py` | thêm `ensure_models()`; nhận param `asr`/`ocr` (merge boost) |
| `app/models/eeiot_model.py` | thêm `get_asr_collection()` → `asr_segments` |
| `app/routes/search_routes.py` | thêm route `/trake`, `/frame`, `/asr`, `/ocr` |
| `app/config.py` | thêm các key TRAKE + Qwen (mục 4) |
| `app/models/search_model.py` | **fix bảo mật**: bỏ Gemini API key hard-code + đường dẫn checkpoint cá nhân → đọc từ `Config` |
| `requirements.txt` | thêm (comment) dep optional cho Qwen local: `accelerate`, `bitsandbytes`, `qwen-vl-utils` |

### Frontend (`frontend-final/vite-project/src/`)
| File | Thay đổi |
|---|---|
| `TrakePanel.jsx` | **MỚI** — panel TRAKE (nhập N event → tổ hợp → verify frame) |
| `AsrResults.jsx` | **MỚI** — hiển thị kết quả ASR độc lập |
| `api.js` | thêm `trakeSearch`, `asrSearch`, `ocrSearch`, `frameUrl` |
| `Jobs.jsx` | bỏ object search; thêm block ASR + OCR (toggle 2 mode); nối TrakePanel; UI tiếng Anh |
| `ItemPalette.jsx`, `DropArea.jsx` | **XOÁ** (dead code sau khi bỏ object search) |

### Data / config
| File | Thay đổi |
|---|---|
| `.env.example` | thêm các key TRAKE + Qwen |

---

## 3. Endpoint mới

| Method | Route | Ý nghĩa | Body / Query |
|---|---|---|---|
| POST | `/search/trake` | TRAKE search | `{ "events": ["...","..."], "language": true }` |
| GET | `/search/frame` | Decode 1 frame gốc để verify | `?L=30&V=068&frame_id=1007` |
| POST | `/search/asr` | ASR độc lập (nội dung lời nói) | `{ "query": "chủ tịch công bố", "k": 50 }` |
| POST | `/search/ocr` | OCR độc lập (chữ trên màn hình) | `{ "query": "TEAM A", "k": 100 }` |
| POST | `/search/collection` | Search chính (đã có) — **thêm** param merge | `{ ..., "asr": "...", "ocr": "..." }` |

> `asr`/`ocr` trong `/search/collection` = mode "gộp": đẩy frame khớp lời nói/chữ lên đầu kết quả.

---

## 4. Cấu hình `.env`

**ASR/OCR không cần env mới** — chỉ cần bật Mongo và có data (mục 5). Các key dưới đây là của **TRAKE**:

```env
# ===== TRAKE tầng 3 (tinh chỉnh frame gốc) — chỉ bật khi máy có video (vd USB) =====
TRAKE_TIER3_ENABLED=false          # true = chạy 3 tầng; false = tự động 2 tầng
VIDEO_ROOT=                        # thư mục chứa video gốc. VD Windows: E:\aic2026_videos | WSL: /mnt/e/aic2026_videos

TRAKE_TOP_M=150                    # top-M ứng viên/mỗi event ở tầng 1
TRAKE_TOP_VIDEOS=2                 # số video ứng viên xét
TRAKE_MAX_COMBOS=100               # tối đa tổ hợp nộp (đề cho 100)
TRAKE_TIER3_RADIUS=15              # bán kính quét frame gốc quanh vị trí thô (±15)
TRAKE_TIER3_STRIDE=1               # bước quét (1 = mọi frame)
TRAKE_VIDEO_CONFIDENCE_THRESHOLD=0.8   # dưới ngưỡng này thì chia slot cho video hạng 2

# ===== Rerank khoảnh khắc tầng 3 =====
TRAKE_RERANK_TIE_MARGIN=0.03       # 2 ứng viên chênh < mức này = "tie" -> mới gọi Qwen
TRAKE_QWEN_RERANK_ENABLED=false    # true = bật Qwen local (cần GPU); false = chỉ thuật toán
QWEN_MODEL_PATH=Qwen/Qwen2.5-VL-7B-Instruct   # HF id hoặc thư mục local; có thể trỏ bản AWQ/GPTQ
QWEN_QUANTIZATION=4bit             # 4bit | 8bit | none  (4bit ~6-8GB VRAM cho 7B)
QWEN_DEVICE_MAP=auto               # auto | cuda | cpu
QWEN_MAX_NEW_TOKENS=10

# ===== Bật search + Mongo (cần cho MỌI search kể cả ASR/OCR) =====
SEARCH_ENABLED=true
MONGO_ENABLED=true
MONGO_URI2=mongodb://localhost:27017/aic2026   # DB chứa collection frames + asr_segments
```

### 2 CASE của TRAKE (tự động, không sửa code)

| | Case 1 — có video (3 tầng) | Case 2 — không video (2 tầng) |
|---|---|---|
| Bật bằng | `TRAKE_TIER3_ENABLED=true` + `VIDEO_ROOT` trỏ đúng | để mặc định (false/rỗng) |
| Tinh chỉnh frame gốc | có | tự bỏ qua (dừng ở keyframe) |
| Rerank | Qwen (nếu `TRAKE_QWEN_RERANK_ENABLED=true`) + thuật toán | **thuật toán** (peak-detection) |
| Verify ảnh trong UI | decode đúng frame từ video | fallback placeholder (dùng link YouTube + ±10) |

Response TRAKE trả `"mode"` (`case1_full`/`case2_coarse`), `"tier"` (3/2), `"rerank_method"` (`qwen`/`algorithm`) để biết đang chạy gì.

---

## 5. Data cần có trong MongoDB

Backend dùng **1 DB** (theo `MONGO_URI2`) với 2 collection:

### `frames` — keyframe (đã có, dùng cho KIS/QA/OCR/TRAKE)
Mỗi doc = 1 keyframe:
```json
{"idx": 315264, "video_id": "L30_V079", "L": "30", "V": "079", "frame_id": 2, "fps": 25.0,
 "frame_stamp": 0.08, "path": "Keyframes/L30_V079/000002.webp", "video_url": "https://youtube.com/watch?v=...",
 "objects": [], "detection": [], "ocr_text": ""}
```
- OCR search dùng field **`ocr_text`**.
- Nên có index `(video_id, frame_id)` để merge boost nhanh; index `idx` unique.

### `asr_segments` — đoạn lời nói (MỚI, cho ASR)
Mỗi doc = 1 đoạn ASR (từ `metadata_asr_clean/<video_id>.json`):
```json
{"id": 3106800000, "video_id": "L30_V068", "t_start": 0.0, "t_end": 20.0,
 "frame_start": 0, "frame_end": 500, "text": "rảo bước trên con đường thơ mộng..."}
```
- ASR search dùng field **`text`**; merge dùng `frame_start/end` để chiếu về keyframe.

### Full-text search
- ASR/OCR ưu tiên **Atlas Search index** tên `default` (fuzzy). Không có index → **tự fallback regex** (vẫn chạy, chậm hơn).
- Nếu dùng Mongo Atlas Local (`mongodb/mongodb-atlas-local`), tạo Atlas Search index `default` trên `frames.ocr_text` và `asr_segments.text`.

---

## 6. Cách chạy & test

### Backend (ngoài Docker — vì cần torch/faiss/opencv nặng)
```bash
cd backendAIC2025
pip install -r requirements.txt        # cần thêm torch/faiss/opencv-python
# (tuỳ chọn Qwen local) pip install accelerate bitsandbytes qwen-vl-utils
python run.py                          # cần .env có SEARCH_ENABLED=true + Mongo
```

### Frontend
```bash
cd frontend-final/vite-project
npm install
npm run dev                            # http://localhost:5173
```

### Test nhanh endpoint (khi backend chạy)
```bash
# TRAKE
curl -X POST localhost:5000/search/trake -H "Content-Type: application/json" \
  -d '{"events":["vận động viên giậm nhảy","bay qua xà","tiếp đất"],"language":true}'

# ASR
curl -X POST localhost:5000/search/asr -H "Content-Type: application/json" \
  -d '{"query":"chủ tịch công bố","k":50}'

# OCR
curl -X POST localhost:5000/search/ocr -H "Content-Type: application/json" \
  -d '{"query":"TEAM A","k":100}'
```

---

## 7. UI mới dùng thế nào

- **Mode selector** (góc phải): KIS / QA / **TRAKE**.
  - Chọn **TRAKE** → hiện panel: nhập N event (Add event) → **TRAKE search** → list tổ hợp → bấm 1 tổ hợp để bung grid frame verify.
- **Sidebar (nút menu)**: 2 khối search text — **ASR search** (spoken content) và **OCR search** (on-screen text).
  - Mỗi khối có toggle **Standalone** (search riêng, hiện kết quả) / **Merge into main search** (gộp vào nút search Screen 1/2/3, đẩy frame khớp lên đầu).

---

## 8. ⚠️ Reconcile với Mongo/Qdrant của teammate

Backend đây build theo **schema data đang có**. Khi pull code teammate (Mongo/Qdrant) về, kiểm tra:
1. **Tên collection ASR**: đang là `asr_segments` (`app/models/eeiot_model.py`). Nếu teammate đặt khác → đổi cho khớp.
2. **Field name**: `ocr_text` (frames), `text/frame_start/frame_end/video_id` (asr_segments). Khớp lại nếu khác.
3. **Atlas Search index** `default` trên `ocr_text` / `text` — chưa có thì đang chạy regex fallback.
4. **Data ASR chưa nạp**: nếu teammate chưa nạp `metadata_asr_clean/*.json` vào `asr_segments`, cần script ingest (chưa viết — báo mình nếu cần).
5. **Qdrant/embedding semantic cho ASR/OCR**: hiện ASR/OCR chạy **full-text lexical (Mongo)**. Khi Qdrant + embeddings sẵn sàng thì thêm leg semantic sau.

---

## 9. Checklist PR (theo README_MEMBERS.md)

- **Env key mới**: các key `TRAKE_*`, `QWEN_*` ở mục 4 (đã cập nhật `.env.example`).
- **Endpoint mới**: `/search/trake`, `/search/frame`, `/search/asr`, `/search/ocr`; `/search/collection` thêm `asr`/`ocr`.
- **Data mới**: collection `asr_segments` cần được nạp.
- **Không commit**: `.env`, video/keyframe, checkpoint, embeddings.
- **Ảnh hưởng model**: Qwen2.5-VL chạy **local + quantize** (không API); CLIP là leg chính (BEiT-3 chưa dùng cho TRAKE vì thiếu package `beit3/`).
```
