# Tài liệu mô tả Hệ thống & Giao diện — AIC 2026 Multimodal Search

> Tài liệu kỹ thuật phục vụ **viết paper** và onboard thành viên. Mô tả kiến trúc, các pipeline tìm kiếm (semantic, Caption, OCR, ASR, Hybrid, Objects/detection-segmentation, TRAKE), giao diện người dùng, cơ chế nộp bài (DRES), và **ghi chú trung thực** về những đại lượng thực sự được tính so với phần chỉ mang tính trình bày.
>
> **Đội:** MLIoT_Newbie · **Sản phẩm:** công cụ *Interactive Video Retrieval* đa phương thức cho AI Challenge 2026.

---

## Mục lục
1. [Tổng quan & triết lý thiết kế](#1-tổng-quan--triết-lý-thiết-kế)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Dữ liệu & chỉ mục](#3-dữ-liệu--chỉ-mục)
4. [Các pipeline tìm kiếm](#4-các-pipeline-tìm-kiếm)
5. [Tổng hợp metadata theo frame (Frame Detail)](#5-tổng-hợp-metadata-theo-frame-frame-detail)
6. [Mô tả giao diện (UI)](#6-mô-tả-giao-diện-ui)
7. [Cơ chế nộp bài (Submission / DRES)](#7-cơ-chế-nộp-bài-submission--dres)
8. [Xử lý timestamp cho video VFR (nhóm N)](#8-xử-lý-timestamp-cho-video-vfr-nhóm-n)
9. [Design system](#9-design-system)
10. [Bảng API tham chiếu](#10-bảng-api-tham-chiếu)
11. [Ghi chú trung thực (cho phần Evaluation/Limitations)](#11-ghi-chú-trung-thực)
12. [Thuật ngữ dùng trong paper](#12-thuật-ngữ-dùng-trong-paper)

---

## 1. Tổng quan & triết lý thiết kế

Hệ thống là một **search engine chuyên dụng** cho tra cứu keyframe trong kho video lớn, không phải một dashboard quản trị. Toàn bộ UI được tổ chức quanh một luồng duy nhất: **truy vấn → duyệt lưới kết quả → soi chi tiết một frame → nộp**.

Ba nguyên tắc thiết kế:

- **Một thanh tìm kiếm, nhiều phương thức.** Người dùng nhập truy vấn ở một ô trung tâm; **chip phương thức** (Visual / Caption / ASR / OCR / Objects / TRAKE) quyết định pipeline. Không phân mảnh thành nhiều trang.
- **Card để *scan*, Drawer để *inspect*.** Thẻ kết quả chỉ mang thông tin tối thiểu để lướt nhanh; toàn bộ chi tiết (đa phương thức, đối tượng, metadata) dồn vào **Video Result Inspector** khi bấm vào một frame.
- **Multimodal minh bạch.** Với mỗi frame, hệ thống thể hiện *vì sao* nó được trả về: các phương thức khớp và, với Hybrid, **đánh dấu (highlight) chính đoạn văn bản trùng truy vấn** thay vì hiển thị điểm số suy diễn.

---

## 2. Kiến trúc hệ thống

```
                 ┌─────────────────────────────────────────────┐
   Người dùng ──▶│  Frontend  (React + Vite + Ant Design 5)     │
                 │  - Hero search, modality chips + popovers    │
                 │  - Result grid, Inspector drawer             │
                 └───────────────┬─────────────────────────────┘
                                 │ HTTP /api (axios)
                 ┌───────────────▼─────────────────────────────┐
                 │  Backend API  (Flask, Blueprint /search/*)   │
                 └───┬───────────────┬────────────────┬─────────┘
                     │               │                │
            vector search      full-text +        ảnh keyframe
                     │        metadata (Mongo)        │
             ┌───────▼──────┐  ┌──────▼───────┐  ┌────▼──────────┐
             │   Qdrant     │  │   MongoDB    │  │ frame-server  │
             │ (embeddings) │  │ (OCR/ASR/    │  │ (Express,     │
             │ theo model   │  │  caption/    │  │  /Keyframes)  │
             │              │  │  detseg)     │  │               │
             └──────────────┘  └──────────────┘  └───────────────┘
```

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| **Frontend** | React 19, Vite, Ant Design 5, react-icons, axios | Toàn bộ giao diện & điều phối truy vấn |
| **Backend API** | Flask, Blueprint `search_bp` | Điều phối tìm kiếm; ghép Qdrant + Mongo |
| **Qdrant** | Vector DB | Lưu embedding keyframe theo từng model; ANN search |
| **MongoDB** | Atlas Search + wildcard index | OCR/ASR/caption full-text; detection-segmentation |
| **frame-server** | Express | Phục vụ ảnh keyframe tại route `/Keyframes` (resolver đa biến thể path) |
| **Đóng gói** | Docker Compose | Chạy đồng bộ toàn bộ |

**Điều phối cross-store (điểm cốt lõi của paper):** Qdrant trả về ứng viên theo độ tương đồng hình ảnh; MongoDB cung cấp lớp ngữ nghĩa văn bản (OCR/ASR/caption) và thuộc tính đối tượng (detseg). Frontend/Backend **ghép hai nguồn theo khoá `(video_id, frame_id)`**.

---

## 3. Dữ liệu & chỉ mục

### 3.1. Các nhóm video

| Nhóm | Loại | OCR | ASR | Caption | Detection/Seg | Ghi chú |
|---|---|---|---|---|---|---|
| **K / L** | Video thường (batch1) | ✅ | ✅ | ✅ | – | Có mặt ở nhiều collection embedding |
| **S / M** | Video thường (batch2) | ✅ | ✅ | ✅ | – | **Chỉ** ở collection embedding `jina` |
| **N** | Camera giao thông (batch2) | ❌ | ❌ | ❌ | ✅ (parquet) | **VFR** (frame-rate không cố định); tìm qua **Objects** |

### 3.2. Qdrant — vector store
- Mỗi **model embedding** là một collection riêng: `beit3`, `jina`, `pe`, (và `jina_old`). UI cho chọn model ở popover *Nâng cao*.
- **batch2 (S/M/N)** chỉ được nạp vào collection **`jina`**.

### 3.3. MongoDB — metadata store (DB `aic2026`)
| Collection | Trường chính | Chỉ mục |
|---|---|---|
| `ocr_metadata` | `video_id, frame_id, L, V, fps, frame_stamp, caption, ocr_text, path, video_url` | Atlas Search `ocr_search` (path `ocr_text`), `caption_search` (path `caption`) |
| `asr_metadata` | `video_id, frame_start, frame_end, text` | Atlas Search `asr_search` (path `text`) |
| `detseg_metadata` | `video_id, frame_id, vehicle_count, counts{class:count}, dets[{c,x,y}], seg_*, traffic_density_proxy, timestamp_s` | `(video_id, frame_id)`, `vehicle_count`, **wildcard `counts.$**`** |

> `ocr_metadata` là bảng "trục" cho video K/L/S/M: nó vừa chứa OCR **và** caption cho từng keyframe. `detseg_metadata` bổ sung thuộc tính đối tượng cho video N.

### 3.4. Vấn đề lệch index (quan trọng — nên nêu trong paper)
- **Qdrant `idx`**: đánh **liên tục toàn cục** trên toàn kho.
- **Mongo `idx`**: **reset về 0 theo từng nhóm chữ cái video** (L bắt đầu 0, sang M lại 0…).
- ⇒ **Không** được dùng `idx` để tra chéo giữa hai store. Mọi liên kết dùng **`(video_id, frame_id)`**. Đây là bất biến thiết kế xuyên suốt backend (temporal ±10, hybrid filter, frame detail).

### 3.5. frame-server
Phục vụ ảnh tại `/Keyframes`, có **resolver** dò nhiều biến thể đường dẫn: thư mục theo nhóm, tiền tố `frame_`, độ đệm số (zero-padding), đuôi `.webp/.jpg/.jpeg/.png`. Nhờ vậy các định dạng path khác nhau giữa batch1 và batch2 (vd `N010-V001` có dấu `-`) đều hiển thị được.

---

## 4. Các pipeline tìm kiếm

Tất cả nằm dưới Blueprint `/search/*`. Frontend `handleSearchClick()` điều phối theo `searchMode`.

### 4.1. Visual (semantic) — `POST /search/collection`
- **Input:** `query1`, `model`, `k` (top-K), `augment`, `language`.
- **Xử lý:** encode truy vấn → ANN trên Qdrant (collection theo model) → top-K keyframe.
- **Output:** danh sách `{path, video_id, frame_id, score, frame_stamp, fps, video_url}` sắp theo **cosine similarity** giảm dần.
- `score` = độ tương đồng thật từ Qdrant (đại lượng số duy nhất được hiển thị dạng thanh bar).

### 4.2. Caption — `POST /search/caption`
- Atlas Search trên `caption_search` (path `caption`) trong `ocr_metadata`.
- Chiến lược 2 tầng: **exact** → **fuzzy (maxEdits=1)** → **fallback token-overlap + SequenceMatcher** khi $search không đủ kết quả.

### 4.3. OCR (standalone) — `POST /search/ocr`
- Atlas Search `ocr_search` (path `ocr_text`) với fuzzy. Trả keyframe kèm `ocr_text`.

### 4.4. ASR (standalone) — `POST /search/asr`
- Atlas Search `asr_search` (path `text`) → các **đoạn** `(frame_start, frame_end)` khớp lời nói.
- Vì ASR mô tả **một khoảng thời gian** chứ không phải một keyframe, backend **map mỗi đoạn về các keyframe OCR** cùng video nằm trong khoảng đó → hiển thị được dưới dạng dải keyframe.

### 4.5. Hybrid — semantic *rồi* lọc theo OCR/ASR
> Đây là đóng góp cần nhấn mạnh: **kết hợp muộn (late-fusion) dạng lọc** giữa hình ảnh và văn bản.

**Luồng:** `query chính (Visual) → ANN top-K → lọc tập kết quả theo OCR/ASR query → giữ nguyên thứ tự semantic.`

- **`POST /search/ocr_filter`** — input `{frames:[{video_id,frame_id}], query}`; tra `ocr_metadata` cho đúng các cặp `(video_id,frame_id)`, giữ frame có `ocr_text` **chứa** `query` (case-insensitive).
- **`POST /search/asr_filter`** — với mỗi video trong tập, tìm các đoạn ASR khớp `query` (regex, escape) → giữ frame có `frame_id` nằm trong khoảng đoạn khớp.
- Cả hai **bảo toàn thứ tự** ANN đầu vào (chỉ lọc, không rerank), giữ nguyên semantics xếp hạng của Qdrant.
- Bật **đồng thời** OCR-Hybrid và ASR-Hybrid ⇒ **giao (AND)**.

**Bản chất & giới hạn:** đây là **bộ lọc nhị phân** (khớp/không khớp), **không** sinh điểm số hợp nhất per-modality. UI vì vậy **không hiển thị "độ khớp %"** cho OCR/ASR mà **highlight đúng đoạn chữ trùng** — trung thực với dữ liệu.

### 4.6. Objects (detection-segmentation) — `POST /search/traffic`
Dành cho video giao thông **N** (không có OCR/ASR). Truy vấn `detseg_metadata`:
- **Đếm đối tượng:** danh sách điều kiện `counts.<class> ≥ min` (nhiều điều kiện = **AND**), dùng **wildcard index** `counts.$**`.
- **Ngưỡng phương tiện:** `vehicle_count ≥ n`.
- **Quan hệ vị trí tương đối** giữa các đối tượng qua `dets[{c,x,y}]` (toạ độ tâm): `A [trái/phải/trên/dưới/giữa] B (và C)` — nhiều quan hệ = **AND**.
- **Hai chế độ:** *Standalone* (lọc thuần detseg, sort theo số xe / mật độ) hoặc *Hybrid* (nhận thêm `frames` từ kết quả semantic → lọc trên đó, giữ thứ tự semantic).

### 4.7. TRAKE (chuỗi sự kiện) — `POST /search/trake`
- Nhập **nhiều sự kiện** theo thứ tự thời gian trong **cùng một video**.
- Tham số **khoảng cách tối đa giữa 2 sự kiện** `max_event_gap_s` (mặc định **không giới hạn**).
- Chấm điểm từng frame theo từng sự kiện, cho **nhích thủ công (nudge)**, xem **dải keyframe toàn video (±10 / tất cả)**, và **chọn frame cho từng sự kiện rồi nộp combo** (submission dạng TRAKE nộp danh sách `frame_id`).

### 4.8. Tìm bằng ảnh — `POST /search/image`
- Upload ảnh (multipart) → embed → ANN như Visual. Dùng cho *query-by-example*.

### 4.9. Frame lân cận ±10 — `POST /search/infoframes`, `POST /search/framerange`
- Lấy ±10 keyframe quanh một frame, hoặc toàn bộ keyframe của video.
- **Fallback:** khi video không có trong collection semantic (vd N chỉ ở `jina`, không ở beit3) → **đọc trực tiếp từ Mongo** và khớp theo `frame_id` (do lệch idx).

---

## 5. Tổng hợp metadata theo frame (Frame Detail)

`POST /search/frame_detail {video_id, frame_id}` — dùng cho **Video Result Inspector**.

Kết quả semantic (Qdrant) chỉ có `score/path/frame_stamp`; caption/OCR/ASR/objects nằm ở Mongo. Endpoint này **gộp**:
- `ocr_metadata` → `caption, ocr_text, fps, frame_stamp, video_url, path, L, V`
- `detseg_metadata` → `counts, vehicle_count, seg_vehicle_ratio, traffic_density_proxy, timestamp_s`
- `asr_metadata` → `text` của đoạn phủ `frame_id`

Frontend gọi khi mở drawer (qua `useEffect` theo `detailItem`) rồi **merge** vào frame đang xem, nhờ đó các mục *Matched by / Nội dung khớp / Đối tượng phát hiện / Thông tin bổ sung* mới có dữ liệu để hiển thị.

---

## 6. Mô tả giao diện (UI)

### 6.1. Header (cố định)
Tối giản: logo `▲ AIC 2026 | Multimodal Search`, chỉ báo `● Dataset ready · Team MLIoT_Newbie`, và nút `☰` mở Sidebar tiện ích. Không có menu điều hướng nhiều module.

### 6.2. Hero + thanh tìm kiếm
- Tiêu đề *Multimodal Video Search* (ẩn khi đã có kết quả) để tối đa vùng lưới.
- Ô nhập lớn (borderless) + nút **(Nâng cao)** + nút **Tìm kiếm**; Enter để tìm.

### 6.3. Chip phương thức + popover ngữ cảnh
`[Visual] [Caption] [ASR] [OCR] [Objects] [TRAKE]` — chip đang chọn được tô accent.

- **ASR / OCR** là **chip-popover**: chọn chế độ **"only"** (standalone) hoặc **"Hybrid"** + nhập query lọc + **Áp dụng**. Khi Hybrid bật, chip đổi nhãn thành **`OCR · Hybrid`** / **`ASR · Hybrid`** — trạng thái hiển thị ngay trên chip, không cần thanh riêng.
- **Objects** là **chip-popover** chứa toàn bộ bộ lọc detseg (chế độ, ngưỡng xe, danh sách object động + số lượng, quan hệ vị trí, sort). Chip hiện **badge số** = số object đang lọc (vd `Objects 2`).
- **TRAKE** mở panel nhập chuỗi sự kiện.

### 6.4. Popover "Nâng cao"
Gom cấu hình truy hồi: **Model** (BEIT3/JINA/PE/CAPTION), **top-K**, **Translate**, **Augment**, và **SUBMISSION TASK** (KIS/QA).

### 6.5. Sidebar ☰ (tiện ích)
Tìm-bằng-ảnh (kéo-thả), hiển thị Model/Top-K, ô ASR/OCR bản legacy, và **FrameCalc** (đổi frame ↔ thời gian).

### 6.6. Thanh công cụ kết quả
Phía trên lưới: **số kết quả**; **chip Objects đang áp** (bấm `×` để bỏ và tìm lại); **bộ lọc L/V** (chọn/loại trừ theo bộ L, video V; giữ-lọc khi tìm mới); **Sắp xếp** (`Độ liên quan` mặc định | `Thời gian`).

### 6.7. Thẻ kết quả (Result card) — *để scan*
Ảnh keyframe + **pill score** + **badge thời gian** (`▶mm:ss`); meta gọn `Video · frame · time · fps`; caption ngắn; **tag modality nhỏ** (`Visual/OCR/Objects…`, tag Hybrid có accent). Hover hiện 3 nút nhanh: **±10 keyframe**, **Mở video**, **Nộp**. Lưới phân trang 12/24/48/96 (mặc định 24).

### 6.8. Video Result Inspector (drawer chi tiết) — *để inspect*
Bấm vào một thẻ → panel phải, tiêu đề **"Chi tiết frame"** (~448px), thiết kế **phẳng, thoáng** (label + nội dung, ngăn bằng kẻ mảnh):

1. **Frame + overlay** — ảnh lớn, `▶mm:ss` góc trái dưới, **score** góc phải trên.
2. **Metadata** — `L21 · V005` (lớn), `Frame 925 · 00:30 · 30 FPS` (phụ).
3. **Độ tương đồng** — thanh bar theo `score` **thật** từ Qdrant (chỉ hiện khi có score).
4. **Matched by** — tag các phương thức khớp/khả dụng; Hybrid dùng accent xanh.
5. **Nội dung khớp** — Caption / OCR / ASR; **highlight** đúng đoạn trùng query hybrid.
6. **Đối tượng phát hiện** — `counts` từng loại.
7. **Thông tin bổ sung** — Video · Thời điểm · FPS · Số xe · Mật độ (chỉ trường có thật).
8. **Actions** phân cấp — **▶ Mở video** (chính) › **Xem ±10 keyframe** (phụ) › **➕ Nộp kết quả này** (dạng text).

Các mục chỉ hiện khi **có dữ liệu** (nạp qua `frame_detail`).

### 6.9. Xem ±10 keyframe
Dải keyframe quanh frame + toggle xem toàn video; nộp single hoặc chọn cho TRAKE combo. Millisecond lấy từ `frame_stamp`.

---

## 7. Cơ chế nộp bài (Submission / DRES)

- Chuẩn **VBS/DRES**; server chính thức **`https://eventretrieval.one`**.
- **KIS/QA** nộp **milliseconds**; **TRAKE** nộp **danh sách `frame_id`**.
- Modal nộp có bước xác nhận (state-controlled, tương thích React 19) và **banner kết quả** CORRECT/WRONG.
- **VIDEO_ID batch2 (N/S/M)** giữ nguyên id gốc, **không** thêm tiền tố `L` (đúng: `N075`, sai: `LN075`); regex chấp nhận `K01-V01`, `L21-V01`, `N075-V001`.
- ⚠️ Bảo mật: **không** dùng tên miền cũ `eventretrieval.oj.io.vn` (đã bị chiếm dụng, redirect ra ngoài) — không gửi session/bài tới đó.

---

## 8. Xử lý timestamp cho video VFR (nhóm N)

- Camera giao thông N có **frame-rate không cố định (VFR)**. Vì KIS/QA nộp theo **milliseconds**, hệ thống dùng **`frame_stamp`** trong metadata thay vì suy `frame_id / fps` (dễ sai với VFR).
- Đội cắt keyframe theo quy tắc **1 giây / keyframe** (khác BTC cắt 2s/frame), nên `frame_stamp` hiện có là **chính xác** cho việc nộp; độ lệch tối đa so với `pts_time` BTC đo được ~90 ms (chấp nhận được).

---

## 9. Design system

| Token | Giá trị | Ghi chú |
|---|---|---|
| Primary | `#1677FF` | Accent chính (nút, active, Hybrid) |
| Navy | `#0F2747` | Chữ tiêu đề, nền overlay |
| Nền layout | `#F8FAFC` | Nền trung tính |
| Viền | `#E2E8F0 / #EAECF0` | Đường kẻ mảnh |
| Success | `#16A34A` | Chỉ dùng cho trạng thái (đèn "ready") |
| Font | `Inter` | `borderRadius` 10, `controlHeight` 38 |

**Nguyên tắc màu:** tiết chế — modality dùng chung gam **xanh/xám**; **Hybrid** dùng accent xanh nổi. Tránh mỗi phương thức một màu (tránh cảm giác "dashboard").

---

## 10. Bảng API tham chiếu

| Endpoint | Method | Chức năng |
|---|---|---|
| `/search/collection` | POST | Semantic (Visual) — ANN Qdrant |
| `/search/image` | POST | Tìm bằng ảnh |
| `/search/caption` | POST | Caption (Atlas Search) |
| `/search/ocr` | POST | OCR standalone |
| `/search/asr` | POST | ASR standalone (đoạn → keyframe) |
| `/search/ocr_filter` | POST | **Hybrid**: lọc tập frame theo OCR |
| `/search/asr_filter` | POST | **Hybrid**: lọc tập frame theo ASR |
| `/search/traffic` | POST | Objects (detseg): counts + quan hệ vị trí |
| `/search/trake` | POST | Chuỗi sự kiện (TRAKE) |
| `/search/frame` | GET | Ảnh 1 frame gốc (verify) |
| `/search/infoframes` | POST | ±10 keyframe quanh 1 frame |
| `/search/framerange` | POST | Keyframe trong 1 khoảng |
| `/search/frame_detail` | POST | Gộp metadata caption/OCR/ASR/objects của 1 frame |

---

## 11. Ghi chú trung thực

*(Nên đưa vào mục Method/Limitations của paper để tránh over-claim.)*

- **Đại lượng số duy nhất được hiển thị** là **cosine similarity từ Qdrant** (Visual) — dùng cho pill score và thanh "Độ tương đồng".
- **Hybrid OCR/ASR là bộ lọc nhị phân** (substring / regex match trên tập ANN), **không** phải fusion có trọng số; hệ thống **không** sinh "điểm khớp %" per-modality, mà **highlight đoạn văn bản trùng** để giải thích trực quan.
- Nhãn **"Matched by"** liệt kê các phương thức **khớp hoặc có dữ liệu** cho frame; chỉ các tag **Hybrid** phản ánh điều kiện lọc thực sự do người dùng đặt.
- **Không có metadata độ phân giải** (width/height) trong DB hiện tại → không hiển thị (không suy đoán).
- Liên kết cross-store dùng `(video_id, frame_id)` do **lệch `idx`** giữa Qdrant (toàn cục) và Mongo (reset theo nhóm).

---

## 12. Thuật ngữ dùng trong paper

- **Late-fusion filtering (Hybrid):** truy hồi hình ảnh (ANN) trước, sau đó lọc tập ứng viên bằng điều kiện văn bản (OCR/ASR) hoặc thuộc tính đối tượng (detseg), **bảo toàn thứ hạng** của bước hình ảnh.
- **Cross-store join key `(video_id, frame_id)`:** khoá liên kết bất biến giữa vector store và metadata store.
- **VFR-aware timestamping:** dùng `frame_stamp` (mốc thời gian thật) thay cho suy diễn `frame_id/fps` cho video frame-rate không cố định.
- **Spatial relation query:** ràng buộc vị trí tương đối (trái/phải/trên/dưới/giữa) giữa các đối tượng dựa trên toạ độ tâm `dets`.
- **Scan-vs-inspect UI:** thẻ tối giản để lướt nhanh, drawer đầy đủ để soi một kết quả.

---

*Cập nhật khi pipeline hoặc UI thay đổi. Tài liệu này mô tả trạng thái hiện hành: chip OCR/ASR/Objects dạng popover, Hybrid semantic→filter, Video Result Inspector với frame_detail, sắp xếp & chip-filter trên thanh công cụ.*
