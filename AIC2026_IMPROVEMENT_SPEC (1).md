# Đặc tả kỹ thuật — Nâng cấp hệ thống truy vấn AIC 2026

> Tài liệu tổng hợp toàn bộ phương án cải tiến từ hệ thống 2025 (BEiT-3 + CLIP + FAISS + MongoDB)
> sang kiến trúc **ensemble đa model + Qdrant + rerank Qwen2.5-VL**, đặc tả từng kỹ thuật kèm ví dụ.
> Phạm vi: 3 loại truy vấn của vòng sơ tuyển — **Textual KIS**, **Q&A**, **TRAKE**.

---

## Mục lục
0. [Tóm tắt kiến trúc & sơ đồ tổng](#0-kiến-trúc-tổng)
1. [Model & vai trò từng thành phần](#1-model--vai-trò)
2. [Sinh embedding (2 leg chủ lực + leg share)](#2-sinh-embedding)
3. [Qdrant — schema & cấu hình](#3-qdrant-schema)
4. [Ingestion — nạp dữ liệu](#4-ingestion)
5. [Query augmentation (template, HyDE, dịch song ngữ)](#5-query-augmentation)
6. [Ensemble tầng 1 — RRF đa leg](#6-rrf-đa-leg)
7. [Ensemble tầng 2 — cross-encoder rerank Qwen2.5-VL](#7-rerank-qwen)
8. [OCR leg](#8-ocr)
9. [Audio leg — ASR + sự kiện âm thanh](#9-audio)
10. [Pipeline theo từng loại truy vấn](#10-pipeline-truy-vấn)
    - 10.1 [Textual KIS](#101-kis)
    - 10.2 [Q&A + VQA](#102-qa)
    - 10.3 [TRAKE 3 tầng + DP alignment](#103-trake)
11. [Ensemble embedding do team khác share](#11-shared-embeddings)
12. [Dev-set & cách chọn trọng số](#12-dev-set)
13. [Tối ưu độ trễ](#13-độ-trễ)
14. [Dọn security & config](#14-security)
15. [Kiến trúc hybrid Mongo + Qdrant (orchestrator)](#15-hybrid)
16. [Thứ tự triển khai](#16-lộ-trình)

---

<a name="0-kiến-trúc-tổng"></a>
## 0. Kiến trúc tổng

```
                 ┌─────────────── QUERY (tiếng Việt) ───────────────┐
                 │                                                   │
        ┌────────┴─────────┐                            ┌────────────┴───────────┐
        │  Query augment   │                            │  HyDE (Qwen2.5-VL)     │
        │  template + VI/EN│                            │  → caption giả định    │
        └────────┬─────────┘                            └────────────┬───────────┘
                 │  encode song song mỗi text tower                  │
   ┌────────┬────┴─────┬──────────┬──────────────┬──────────────────┐
   ▼        ▼          ▼          ▼              ▼                  ▼
 jina     CLIP      BEiT-3    (share teams)   OCR-text          ASR-text
 (img)    (img)     (img)     (img)           (text↔text)       (text↔text)
   └────────┴──────────┴──────────┴──────────────┴──────────────────┘
                 │  mỗi leg = 1 Prefetch trong Qdrant
                 ▼
        ╔═══════════════════════╗
        ║  RRF fusion (weighted)║   ← Tầng 1: bi-encoder ensemble, quét toàn kho
        ╚═══════════╤═══════════╝
                    │  top-50..100 ứng viên
                    ▼
        ╔═══════════════════════╗
        ║ Qwen2.5-VL rerank     ║   ← Tầng 2: cross-encoder, đọc nội dung frame
        ╚═══════════╤═══════════╝
                    │
          ┌─────────┼───────────┐
          ▼         ▼           ▼
        KIS       Q&A(VQA)    TRAKE (video-select → align → refine)
                    │
              top-100 nộp
```

**Hai nguyên tắc bất biến:**
1. **Không trộn embedding khác không gian** (không average CLIP với BEiT-3…). Chỉ hợp ở **mức hạng** bằng RRF.
2. **Mỗi leg retrieval query bằng đúng text tower của model đó.** Qwen2.5-VL **không** phải leg vector — nó là generative (HyDE / rerank / VQA).

---

<a name="1-model--vai-trò"></a>
## 1. Model & vai trò

| Model | Loại | Dim | Vai trò | Query tiếng Việt |
|---|---|---|---|---|
| **jina-clip-v2** | dual-encoder ảnh↔text, đa ngữ | 1024 | Leg retrieval **chủ lực** | Encode thẳng, **không dịch** |
| **CLIP ViT-L-14** (laion2B) | dual-encoder | 768 | Leg retrieval (tái dùng `.npy` cũ) | Dịch + cache |
| **BEiT-3 large** | dual-encoder (XLM-R tokenizer) | 1024 | Leg retrieval, đa dạng tín hiệu | Chịu được VI phần nào; nên vẫn thử EN |
| **Qwen2.5-VL** (7B/72B) | **generative VLM** | — | HyDE · caption keyframe · **rerank** · **VQA** | Native VI/EN |
| PhoWhisper / Whisper-v3 | ASR | — | Leg ASR-text | — |
| VietOCR / PaddleOCR | OCR | — | Leg OCR-text | — |
| (Embedding team share) | dual-encoder | * | Leg retrieval bổ sung (mục 11) | Cần text tower tương ứng |

---

<a name="2-sinh-embedding"></a>
## 2. Sinh embedding

**Kỹ thuật:** encode toàn bộ keyframe bằng nhiều encoder ảnh, lưu song song thành **named vectors** trong Qdrant.

- **Đầu vào:** thư mục `Keyframes/<video_id>/*.jpg` + metadata (frame_id gốc, fps).
- **Đầu ra:** với mỗi keyframe → vector `jina` (1024), `clip` (768), `beit3` (1024), tất cả **normalize L2**.
- **Tham số:** batch GPU 128–256 ảnh; distance **Cosine**; bỏ bước `.npy` trung gian (upsert thẳng), nhưng **tái dùng** `.npy` CLIP cũ nếu keyframe set không đổi.
- **Bất biến quan trọng:** `frame_id` lưu là **chỉ số frame gốc trong video**, KHÔNG phải thứ tự keyframe → để TRAKE map đúng cửa sổ `[s,e]` (<10 frame).

**Ví dụ record sau khi encode** (khái niệm, trước khi upsert):
```json
{
  "idx": 152344,
  "video_id": "L01_V001",
  "frame_id": 505,               // frame gốc, dùng để chấm
  "keyframe_order": 87,          // thứ tự keyframe trong video
  "fps": 25.0,
  "vectors": { "jina": [...1024], "clip": [...768], "beit3": [...1024] }
}
```

---

<a name="3-qdrant-schema"></a>
## 3. Qdrant — schema & cấu hình

**Kỹ thuật:** 1 collection `keyframes`, mỗi keyframe = 1 point, gộp vector + payload để **ANN có filter**.

```python
# create_collection (đặc tả tham số)
vectors_config = {
    "jina":    VectorParams(size=1024, distance=Distance.COSINE),
    "clip":    VectorParams(size=768,  distance=Distance.COSINE),
    "beit3":   VectorParams(size=1024, distance=Distance.COSINE),
    "caption": VectorParams(size=1024, distance=Distance.COSINE),  # caption Qwen embed thẳng thành vector
}
hnsw_config       = HnswConfigDiff(m=16, ef_construct=200)
on_disk_payload   = True          # cần cho batch 2

# payload (chỉ metadata + text theo-frame; KHÔNG chứa asr_text, KHÔNG chứa caption dạng text)
payload = {
  "idx", "video_id", "frame_id", "keyframe_order", "fps",
  "frame_stamp", "objects", "detection", "ocr_text",
  "video_path", "video_url", "path"
}

# payload index BẮT BUỘC (mở khóa TRAKE + lọc)
create_payload_index("video_id",  KEYWORD)
create_payload_index("frame_id",  INTEGER)
create_payload_index("ocr_text",  TEXT)     # full-text (OCR theo frame)
```

> **`caption`** → embed bằng text-encoder thành **named vector `caption`**, không lưu text trong payload.
> **`asr_text`** → nằm trọn ở collection `asr_segments` (§7), không lưu trên keyframe. Chỉ `ocr_text` (theo frame) ở lại payload.

**Vì sao Qdrant thắng FAISS ở bài này:** FAISS `IndexFlatIP` không lọc payload → TRAKE phải rerank offset thủ công. Qdrant làm **ANN + filter `video_id`/`frame_id` cùng lúc** trong một call.

---

<a name="4-ingestion"></a>
## 4. Ingestion

**Kỹ thuật:** duyệt keyframe → encode batch → `upsert` theo lô, tạo payload index **sau khi** nạp xong.

- Lô upsert ~256 point, `wait=false` cho nhanh.
- **Idempotent theo `idx`** → chạy lại được khi có batch 2 (không nhân đôi).
- `ocr_text` nạp **bổ sung sau** bằng `set_payload` (không encode lại vector ảnh). `caption` nạp thành named vector `caption`; ASR nạp vào collection `asr_segments` riêng.
- Kiểm tra sau nạp: `count(video_id=X)` == số keyframe thật của video X.

---

<a name="5-query-augmentation"></a>
## 5. Query augmentation

Mục tiêu: tăng recall mà không phá độ trễ. Chia **đường nhanh (no-LLM)** và **đường chất lượng (LLM)**.

### 5.1 Template ensembling (no-LLM, bật mặc định)
Bọc query vào nhiều template, **mean-pool embedding text → 1 vector**:
```
templates = [
  "{q}",
  "a video frame showing {q}",
  "a scene of {q}",
  "a photo of {q}",
]
q_vec = normalize(mean([encode(t.format(q)) for t in templates]))
```
→ 1 lần search, không thêm độ trễ, +1–3% recall.

### 5.2 Song ngữ VI/EN (tận dụng leg đa ngữ)
```
q_vec_jina = mean(encode_jina(q_vi), encode_jina(translate_en(q_vi)))
```

### 5.3 HyDE (LLM — Qwen2.5-VL, mạnh nhất)
Thay vì paraphrase câu hỏi, sinh **caption mô tả khung hình** cần tìm rồi mới embed. Khớp không gian ảnh↔caption tốt hơn ảnh↔câu-hỏi.

**Prompt mẫu (KIS):**
```
Bạn là chuyên gia mô tả ảnh. Cho truy vấn tìm kiếm sau, hãy viết 1 câu
tiếng Anh mô tả CHI TIẾT THỊ GIÁC của khung hình khớp nhất (vật thể, màu sắc,
hành động, bối cảnh). Không giải thích, chỉ trả về câu mô tả.
Truy vấn: "{q}"
```
**Ví dụ:**
- Query: *"Tìm video về một diễn giả mặc áo đỏ phát biểu tại một cuộc họp báo ngoài trời, phía sau có nhiều cây xanh."*
- HyDE output: *"A male speaker in a red shirt standing at a podium giving a speech at an outdoor press conference, lush green trees in the background, microphones in front."*
- → embed câu này bằng cả 3 encoder ảnh.

### 5.4 Trích entity → nhánh filter
Rút vật thể/tên riêng → dùng làm `ocr_text` filter hoặc rerank. VD từ query trên: `["red shirt","podium","trees","press conference"]`.

**Fuse các biến thể:** đường nhanh **mean-pool** (5.1+5.2); đường chất lượng thêm HyDE thành **leg riêng** rồi RRF (mục 6). LLM chạy **1 lần/query + cache** (đề cho sẵn mô tả trọn vẹn nên augment offline được).

---

<a name="6-rrf-đa-leg"></a>
## 6. Ensemble tầng 1 — RRF đa leg

**Kỹ thuật:** mỗi leg trả 1 danh sách hạng; hợp bằng **Reciprocal Rank Fusion có trọng số**.

**Công thức:**
```
score(d) = Σ_leg  w_leg · 1 / (k_rrf + rank_leg(d))          k_rrf = 60
```
RRF dựa trên **hạng** nên miễn nhiễm việc các model lệch thang điểm.

**Qdrant Query API (đặc tả):**
```python
client.query_points(
  "keyframes",
  prefetch=[
    Prefetch(query=q_jina,  using="jina",  limit=200),
    Prefetch(query=q_clip,  using="clip",  limit=200),
    Prefetch(query=q_beit3, using="beit3", limit=200),
    Prefetch(query=q_hyde_jina, using="jina", limit=200),   # leg HyDE
    Prefetch(query=ocr_kw, ... )                            # leg OCR (text)
  ],
  query=FusionQuery(fusion=Fusion.RRF),
  limit=100, with_payload=True,
)
```
→ thay hẳn `RRF_ranking()` viết tay ở `search_controller.py:347`.

**Trọng số khởi điểm (tinh chỉnh bằng dev-set, mục 12):**
```
beit3 1.0 · jina 1.0 · clip 0.7 · HyDE 0.8 · OCR 0.6 · ASR 0.5
```
> Lưu ý tương quan: jina & CLIP cùng họ CLIP → hạ bớt trọng số CLIP để tránh "đếm 2 lần".

---

<a name="7-rerank-qwen"></a>
## 7. Ensemble tầng 2 — cross-encoder rerank Qwen2.5-VL

**Kỹ thuật:** đưa **ảnh keyframe thật + query** vào Qwen2.5-VL để chấm mức khớp — mô hình "đọc" nội dung frame, sửa lỗi mà cosine embedding hay nhầm (đếm số, quan hệ không gian, chữ).

- **Đầu vào:** top-K của tầng 1 (K=30–50, không chạy toàn kho vì đắt).
- **Đầu ra:** điểm 0–100 mỗi frame → sắp xếp lại.

**Prompt mẫu (rerank):**
```
Bạn là giám khảo truy vấn video. Ảnh dưới đây có khớp với mô tả không?
Mô tả: "{q}"
Chấm điểm 0-100 mức độ khớp (chỉ trả về số).
```

**Ví dụ:** query "diễn giả áo đỏ họp báo ngoài trời". Tầng 1 trả 1 frame áo đỏ nhưng **trong nhà** ở hạng 3 → Qwen chấm 40, tụt hạng; frame ngoài trời đúng ở hạng 8 → chấm 95, lên top-1. Đây chính là chỗ cứu R@1.

**Batch:** gửi nhiều ảnh/1 prompt (grid) để giảm số call, hoặc chấm theo lô 5–10 ảnh.

---

<a name="8-ocr"></a>
## 8. OCR leg

**Kỹ thuật:** trích chữ trên màn hình offline → payload → 2 cách dùng.

- **Pipeline:** detection (PaddleOCR/DB) → nhận dạng **VietOCR / PaddleOCR đa ngữ** (chú ý dấu tiếng Việt) → lưu `ocr_text` + confidence.
- **Cách dùng:**
  1. **Filter/rerank** khi query có chuỗi trong ngoặc, tên riêng, tỉ số → match `ocr_text` (full-text index).
  2. **Leg text↔text**: embed `ocr_text` bằng text encoder → RRF.
- **Giá trị cao cho Q&A** (đáp án literal: tên, số, tỉ số).

**Ví dụ:** Q&A *"Đội nào thắng theo bảng tỉ số?"* → OCR đọc "3 - 1  TEAM A" trên khung hình → trả lời trực tiếp.

---

<a name="9-audio"></a>
## 9. Audio leg — ASR + sự kiện âm thanh

**Kỹ thuật:** khai thác tiếng nói & âm thanh (feature BTC cấp KHÔNG có → tín hiệu mới).

- **ASR:** **PhoWhisper** (Việt) / Whisper-v3 → transcript **kèm timestamp** → lưu vào collection **`asr_segments`** (§7, file `metadata_asr/<video_id>.json`); embed `text` theo đoạn. Lúc fusion mới **chiếu về frame** qua `frame_start/end`.
- **Cách dùng:** tìm theo *nội dung được nói* (MC công bố, người phát biểu). Cực mạnh cho video tin tức/sự kiện và Q&A khi đáp án nằm ở lời nói.
- **Sự kiện âm thanh (nâng cao):** CLAP/PANNs tag vỗ tay, còi, reo hò → **mỏ neo thời gian cho TRAKE**.

**Ví dụ:** query "khoảnh khắc trọng tài thổi còi bắt đầu" → audio-event "whistle" tại t=12.3s → frame ≈ 12.3×fps → anchor cho TRAKE event 1.

**Bất biến:** OCR là **theo frame**, ASR/audio là **theo đoạn thời gian** → phải join tất cả về `(video_id, frame_id / cửa sổ thời gian)` thì RRF mới trộn được.

---

<a name="10-pipeline-truy-vấn"></a>
## 10. Pipeline theo từng loại truy vấn

<a name="101-kis"></a>
### 10.1 Textual KIS — `<video_id>, <frame_id>`
1. Augment (template + VI/EN + HyDE).
2. RRF đa leg → top-100.
3. Rerank Qwen top-30.
4. **Khử keyframe trùng** bằng `query_points_groups(group_by="video_id", group_size=3)` để top-k không bị 1 cảnh chiếm chỗ → tăng R@5/R@20.
5. Nộp đủ 100.

**Ví dụ chấm:** đáp án `L01_V001 [500,510]`. Nộp `L01_V001,505` → R-Score=1.

<a name="102-qa"></a>
### 10.2 Q&A — `<video_id>, <frame_id>, <answer>`
Retrieval như KIS để **định vị khoảnh khắc**, rồi **VQA bằng Qwen2.5-VL** sinh `answer`.

**Prompt VQA:**
```
Xem khung hình và trả lời NGẮN GỌN câu hỏi (bằng tiếng Việt hoặc số).
Câu hỏi: "{question}"
```
**Ví dụ:** *"Có bao nhiêu người lên sân khấu nhận giải lớn nhất?"* → định vị frame lễ trao giải → Qwen đếm → answer="5". Nộp `L?_V?, 3450, 5`.
> Không có bước VQA thì Q&A **luôn 0 điểm** dù tìm đúng frame.

<a name="103-trake"></a>
### 10.3 TRAKE — `<video_id>, <frame_id_1>, ..., <frame_id_N>`

**Bất biến chấm:** sai video = **0 điểm**; đúng video → điểm = tỉ lệ event khớp cửa sổ `[s_j,e_j]` (<10 frame).

**Tầng 1 — chọn 1 video:**
- Encode N event (mỗi event augment riêng).
- Mỗi event → `query_points_groups(group_by="video_id")`.
- Gom điểm mỗi video bằng **DP đơn điệu** (bắt buộc thứ tự thời gian).

**DP alignment (đặc tả):**
```
# sim[j][t] = độ khớp event j với keyframe thứ t (theo thời gian) trong video
# Chọn t_1 < t_2 < ... < t_N cực đại tổng sim
dp[j][t] = sim[j][t] + max_{t' < t} dp[j-1][t']
best_score(video) = max_t dp[N][t]
# backtrack → (t_1..t_N)
```
Xếp video theo `best_score`, lấy top ứng viên.

**Tầng 2 — căn từng event trong video đã chọn:**
```python
prev = -1
for j, ev_vec in enumerate(event_vecs):
    hit = query_points("keyframes", query=ev_vec, using="jina",
        query_filter=Filter(must=[
            FieldCondition("video_id", MatchValue(vid)),
            FieldCondition("frame_id", Range(gt=prev)),   # ép thứ tự
        ]), limit=5).points[0]
    frames[j] = hit.payload["frame_id"]; prev = frames[j]
```

**Tầng 3 — tinh chỉnh bắt cửa sổ <10 frame (BẮT BUỘC):**

Keyframe thường thưa (1/shot hoặc 1/giây) → cửa sổ đáp án `<10 frame gốc` gần như **không chứa keyframe** → tầng 1–2 chỉ định vị *thô*. Tầng 3 quét ở **độ phân giải frame gốc** để chọn đúng semantic keyframe. Đây là bước quyết định có ăn trọn điểm TRAKE hay không.

**Đầu vào:** video đã chọn (`video_path`), `fps`, và với mỗi event j: `frame_id` thô `f_j` (từ tầng 2) + vector text event `ev_vec_j` + (tùy chọn) khoảng ASR `[frame_start,frame_end]` của event.

**Thuật toán (đặc tả):**
```
R = 15                                  # bán kính quét quanh frame thô (theo fps ~25 → ±0.6s)
STRIDE = 1                              # 1 = quét mọi frame; 2-3 nếu cần nhanh
for j, (f_j, ev_vec_j) in enumerate(events):
    lo = max(prev_fine + 1, f_j - R)    # prev_fine: frame tinh của event j-1 → ép thứ tự
    hi = f_j + R
    frames = decode_native(video_path, lo, hi, STRIDE)   # đọc frame GỐC (OpenCV/decord)
    embs   = encode_image(frames)                        # jina (leg chủ lực); có thể +CLIP
    scores = embs @ ev_vec_j                             # cosine, đã normalize
    # (tùy chọn) cộng thưởng nếu frame nằm trong khoảng ASR của event
    # (tùy chọn) rerank top-3 bằng Qwen2.5-VL để chọn đúng khoảnh khắc ngữ nghĩa
    t_star     = argmax(scores)
    fine[j]    = lo + t_star * STRIDE                     # frame gốc để NỘP
    prev_fine  = fine[j]
```

**Ràng buộc & lưu ý:**
- `lo = max(prev_fine+1, ...)` giữ **thứ tự thời gian** giữa các event (event j sau j-1).
- Decode bằng **decord** (nhanh, seek theo index) hoặc OpenCV `set(CAP_PROP_POS_FRAMES, lo)`; chỉ đọc `[lo,hi]`, không decode cả video.
- **frame gốc** trả về đúng chuẩn chấm — vì cửa sổ `[s_j,e_j] < 10 frame`, sai 1–2 frame là mất điểm event đó.
- **Tối ưu R@k:** ngoài `fine[j]`, nộp thêm biến thể `fine[j] ± 1..2` (top-2/3 theo `scores`) để tăng xác suất trúng `[s_j,e_j]`.
- **Semantic vs cường độ hình:** khoảnh khắc ngữ nghĩa (vd "chân giậm nhảy rời đất") nhiều khi 2 frame kề rất giống về hình → nên **Qwen2.5-VL rerank** top-3 với prompt mô tả *đúng khoảnh khắc* để chọn frame ngữ nghĩa, không chỉ frame giống caption chung.

**Prompt Qwen chọn semantic keyframe (tầng 3):**
```
Trong các ảnh sau (liên tiếp theo thời gian), ảnh nào ĐÚNG khoảnh khắc:
"{mô tả event j, vd: bàn chân của chân giậm nhảy vừa rời hoàn toàn khỏi mặt đất}"?
Chỉ trả về số thứ tự ảnh.
```

**Ví dụ (nhảy cao, event 2 "bay qua xà", đáp án `[145,155]`):**
- Tầng 2 chọn keyframe thô `f_2 = 150` (keyframe gần nhất).
- Tầng 3 decode `[135,165]` fps gốc → cosine đỉnh ở 149 & 151 (2 frame hông cao nhất gần bằng nhau).
- Qwen rerank chọn 150 (hông cao nhất so với xà) → nộp `150` (kèm biến thể 149, 151) → trúng `[145,155]`.

**Chi phí:** mỗi event decode ~`2R/STRIDE` frame (≈30 ảnh) + encode → vài trăm ms/event trên GPU; chỉ chạy cho **1 video đã chọn**, không phải toàn kho → chấp nhận được.

**Tối ưu R@k:** không nộp 1 tổ hợp argmax, mà **sinh tổ hợp Cartesian từ top-k ứng viên mỗi event** rồi xếp hạng — xem chi tiết §10.3.1.

**Ví dụ (nhảy cao 4 event):** đáp án `L10_V010` cửa sổ `[95,105],[145,155],[195,205],[245,255]`.
- Tầng 1 chọn đúng `L10_V010`.
- Tầng 2 định vị thô: keyframe gần nhất `100,150,200,250`.
- Tầng 3 tinh chỉnh trên frame gốc → `101,150,203,251` → khớp 4/4 → R-Score=1.0.

#### 10.3.1 Chiến lược nộp tổ hợp (Cartesian) — tối ưu R@k *(cải tiến miễn phí)*

Chấm TRAKE dùng `R@k = max` trên `k∈{1,5,20,50,100}` rồi trung bình → **được nộp tối đa 100 tổ hợp**.
Nộp 1 tổ hợp argmax là lãng phí. Thay vào đó: mỗi event lấy **top-k frame ứng viên + xác suất**,
sinh **tích Descartes** các tổ hợp, xếp giảm dần theo tích xác suất, nộp 100 tổ hợp đầu.

**Ví dụ (dùng đúng đề nhảy cao, `L10_V010`, N=4, cửa sổ `[95,105],[145,155],[195,205],[245,255]`):**

Top-3 ứng viên mỗi event (in đậm = frame nằm trong cửa sổ đúng):

| Sự kiện | ƯV 1 | ƯV 2 | ƯV 3 |
|---|---|---|---|
| E1 Giậm nhảy | **101** (0.50) | 88 (0.30) | 112 (0.20) |
| E2 Bay qua xà | 160 (0.45) | **150** (0.35) | 141 (0.20) |
| E3 Tiếp đất | **203** (0.60) | 190 (0.25) | 215 (0.15) |
| E4 Đứng dậy | **251** (0.55) | 240 (0.30) | 262 (0.15) |

Chú ý E2: model đoán **sai top-1** (160 lệch ngoài `[145,155]`), frame đúng ở vị trí 2.

**Cách ngây thơ (chỉ nộp argmax mỗi chiều):** `(101,160,203,251)` → khớp 3/4 → R-Score 0.75.
Đó là đáp án duy nhất → `R@1=…=R@100=0.75` → **Final Score = 0.75**.

**Cách Cartesian:** sinh `3⁴=81` tổ hợp, xếp giảm theo tích xác suất:

| Hạng | Tổ hợp | Tích | R-Score |
|---|---|---|---|
| 1 | 101, 160, 203, 251 | 0.0743 | 0.75 |
| **2** | **101, 150, 203, 251** | **0.0578** | **1.00** |
| 3 | 88, 160, 203, 251 | 0.0446 | 0.50 |
| 4 | 101, 160, 203, 240 | 0.0405 | 0.50 |
| 5 | 88, 150, 203, 251 | 0.0347 | 0.75 |

Tổ hợp hoàn hảo rơi vào **hạng 2** (chỉ đổi 1 chiều so với hạng 1) → `R@1=0.75`, `R@5=R@20=R@50=R@100=1.00`
→ **Final Score = (0.75+1+1+1+1)/5 = 0.95**. **Chênh +0.20** trên **cùng model, cùng tập ứng viên**, không train thêm.

**Vì sao không bao giờ lỗ:** tổ hợp hạng 1 của Cartesian **chính là** đáp án ngây thơ → `R@1` luôn bằng nhau,
`R@5` trở lên chỉ có thể tăng. Cải tiến thuần túy, **không đánh đổi**.

> Đại lượng cần tối ưu đổi theo: không còn là **độ chính xác top-1 mỗi event**, mà là **recall@k mỗi event**
> (frame đúng *có mặt đâu đó* trong tập ứng viên). Model tệ ở top-1 nhưng recall@3 tốt vẫn ăn điểm cao.

```python
from itertools import product
from math import prod
combos = sorted(product(*cands), key=lambda c: -prod(p[i][f] for i, f in enumerate(c)))
submit(video_id, combos[:100])
```

**Ngân sách slot theo N** (tổng ≤ 100 tổ hợp):

| N | ƯV / event | Số tổ hợp |
|---|---|---|
| 2 | 10 | 100 |
| 3 | 4 | 64 |
| 4 | 3 | 81 |
| 5 | 3,3,2,2,2 | 72 |
| 6 | 2 | 64 |
| 7+ | 2 cho event khó nhất, 1 cho phần còn lại | ≤ 64 |

Khi N lẻ / không chia đều: **dồn ứng viên cho event có phân phối xác suất bẹt nhất** (top-1 thấp → cho 3;
event chắc 0.95 → cho 1). Tham lam theo mức tăng recall biên mỗi lần nhân đôi ngân sách.

**Ba cái bẫy (bắt buộc xử lý):**
1. **Giãn cách ứng viên (NMS thời gian).** Cửa sổ đáp án <10 frame → nếu 3 ƯV của E1 là 101/103/105 thì
   cùng 1 cửa sổ, trả 3 slot mà chỉ mua 1 lần cược. **Ép giãn tối thiểu ~15 frame** giữa các ứng viên cùng event.
2. **Ràng buộc thứ tự thời gian.** Chuỗi event đơn điệu tăng (giậm nhảy trước tiếp đất). Loại mọi tổ hợp
   không tăng dần → thường cắt **30–50%** tổ hợp, giải phóng slot cho ƯV thứ 4 hoặc video dự phòng.
3. **Không dồn hết 100 slot cho 1 video khi chưa chắc.** Nếu `P(video1)≈0.65`: chia 81 slot cho video 1
   (3 ƯV/event) + 16 slot cho video 2 (2 ƯV/event) có kỳ vọng cao hơn dồn tất cả. Ngưỡng thô: độ tin cậy
   video top-1 **< ~0.8** thì luôn để dành slot cho video thứ hai. **Hiệu chỉnh ngưỡng này trên dev-set**
   (§12) — phụ thuộc retrieval của bạn calibrate xác suất tốt đến đâu.

---

<a name="11-shared-embeddings"></a>
## 11. Ensemble embedding do team khác share

**Được**, mỗi bộ share = thêm 1 named vector + 1 leg RRF. **4 điều kiện sống–còn:**
1. **Phải kèm danh tính model** (để load đúng text tower) — chỉ có vector ảnh mà không biết model → **vô dụng** cho text→image.
2. **Join bằng `(video_id, frame_id)`, KHÔNG theo thứ tự mảng** (team khác trích keyframe khác → lệch hàng).
3. **Chọn model đa dạng** (CLIP+SigLIP+BEiT-3+…), tránh cộng model tương quan; sweet spot 3–4 leg.
4. **Validate từng leg trên dev-set** trước khi thêm; gán trọng số theo điểm, loại leg làm giảm điểm.

> ⚠️ **Kiểm điều lệ AIC 2026**: xác nhận được phép dùng feature/model bên ngoài do team khác share.

---

<a name="12-dev-set"></a>
## 12. Dev-set & cách chọn trọng số

Nền tảng để mọi ensemble/OCR/audio không thành "thêm nhiễu".

- **Dựng:** ~50–100 query tự tạo trên data batch 1, tự gán đáp án `(video, [s,e])` (hoặc dùng đề mẫu).
- **Đo:** R@{1,5,20,50,100} và Final Score (trung bình) **cho từng leg riêng** rồi **cho tổ hợp**.
- **Chọn trọng số RRF:** grid nhỏ / coordinate search trên dev-set.
- **Quy tắc:** chỉ giữ leg nào **làm tăng** Final Score khi thêm vào (ablation).

---

<a name="13-độ-trễ"></a>
## 13. Tối ưu độ trễ ("query không ra liền")

- Bỏ dịch ở leg đa ngữ; **cache** dịch ở leg CLIP.
- **Giữ model ấm trên GPU**, bỏ `.to(device)` mỗi request (`search_model.py:125`).
- Augment/HyDE **offline + cache** (đề cho sẵn mô tả trọn vẹn).
- Encode N event của TRAKE **1 lần**, tái dùng cho cả 3 tầng.
- Rerank Qwen chỉ trên top-30..50, không toàn kho.
- Tinh chỉnh `ef` (HNSW) cân recall/tốc độ; `on_disk` cho batch 2.
- **Ngân sách mục tiêu:** tầng 1 < 300ms, rerank Qwen 1–3s (chỉ khi cần độ chính xác cao).

---

<a name="14-security"></a>
## 14. Dọn security & config (làm khi migrate)

- 🔴 **Rotate ngay** API key Gemini (`app/utils/helpers.py:33`) và **Mongo URI có user/pass** (`app/config.py:9-10`) — đưa vào `.env`.
- 🔴 Bỏ path checkpoint hardcode `C:\Users\PC\...` (`app/models/search_model.py:19`) → config.
- Nếu bỏ Mongo hẳn: chuyển object/OCR filter sang payload Qdrant, gỡ `fuzzy_search`.

---

<a name="15-hybrid"></a>
## 15. Kiến trúc hybrid Mongo + Qdrant (orchestrator)

Phương án giữ **OCR/ASR trong MongoDB Atlas** (để có **fuzzy `maxEdits` thật** — điều Qdrant không có)
và **embedding trong Qdrant**. Đánh đổi: 2 store → phải join + gọi khéo. Mục này đặc tả cách làm để
**không hy sinh tốc độ lẫn độ chính xác**.

### 15.1 Phân vai & khóa join
| Store | Giữ gì | Truy vấn |
|---|---|---|
| **Qdrant** | vectors `jina/clip/beit3` + payload tối thiểu | dense ANN (+ sparse char-n-gram nếu có) |
| **Mongo Atlas** | `ocr_text`, `asr_segments`, `objects` | `$search` **fuzzy** (`maxEdits:1, prefixLength:2`) |

- **Khóa join chung: `idx` (global unique).** Mọi kết quả 2 bên quy về danh sách `idx` rồi mới fuse
  → chỉ trao đổi `(idx, score)`, **không** di chuyển vector.
- **OCR** khớp → ra `idx` keyframe trực tiếp.
- **ASR** khớp segment → **chiếu về frame**: `idx` của keyframe có `frame_id ∈ [frame_start,frame_end]`
  (nếu không có keyframe: frame đại diện = `round((t_start+t_end)/2 · fps)`). Xem §7 & §9.

### 15.2 Sơ đồ orchestrator (GỌI SONG SONG)

```
                          QUERY (VI)  ── phân loại route ──┐
                              │                            │ (KIS / Q&A / TRAKE / text-heavy)
        ┌─────────────────────┴─────────────────────┐     │
        ▼ (async, đồng thời)                         ▼     │
 ┌──────────────┐                          ┌───────────────────────┐
 │   QDRANT      │                          │   MONGO ATLAS ($search)│
 │ dense ANN     │                          │  ocr_fuzzy  asr_fuzzy  │
 │ limit=200     │                          │  limit=200  limit=200  │
 └──────┬───────┘                          └───────────┬───────────┘
        │ ranked idx (dense)                            │ ranked idx (ocr), (asr→frame)
        └───────────────┬───────────────────────────────┘
                        ▼
             ┌─────────────────────────┐
             │  RRF THEO ROUTE (§15.4)  │   ← hợp trên idx, trọng số theo loại query
             └───────────┬─────────────┘
                         │ top-K idx
                         ▼
      batch  Mongo.find({idx:{$in:[...]}})  +  Qdrant.retrieve(ids)   (1 round-trip mỗi bên)
                         │
                         ▼
             Qwen2.5-VL rerank/verify top-K (đọc lại chữ trên ảnh)  →  top-100 nộp

  Độ trễ ≈ max(t_qdrant, t_mongo)  (KHÔNG phải tổng, vì song song)
```

### 15.3 Route classifier (rẻ, quyết định trọng số)
Phân loại query trước bằng luật/LLM-nhẹ:
| Route | Dấu hiệu | Ý đồ |
|---|---|---|
| `visual` | mô tả cảnh/hành động thuần | dense áp đảo |
| `text_in_scene` | có chuỗi trong ngoặc, tên riêng, số/tỉ số | tăng OCR-fuzzy |
| `spoken` | "ai nói…", "được công bố…", lời thoại | tăng ASR |
| `trake` | chuỗi ≥2 khoảnh khắc | dense + DP (§10.3), OCR/ASR làm anchor |

### 15.4 Công thức RRF theo route
Hợp trên `idx`, mỗi nguồn đóng góp nghịch đảo hạng, nhân trọng số theo route:

```
score(idx) =  w_dense · 1/(k + rank_qdrant(idx))
            + w_ocr   · 1/(k + rank_ocr(idx))
            + w_asr   · 1/(k + rank_asr(idx))
            + w_obj   · 1/(k + rank_obj(idx))
        k = 60 ;  rank = +∞  nếu idx không xuất hiện ở nguồn đó (số hạng = 0)
```

**Bảng trọng số khởi điểm (tinh chỉnh bằng dev-set §12):**

| Route | w_dense | w_ocr | w_asr | w_obj |
|---|---|---|---|---|
| `visual`        | 1.0 | 0.3 | 0.2 | 0.3 |
| `text_in_scene` | 0.6 | **1.0** | 0.3 | 0.4 |
| `spoken`        | 0.6 | 0.3 | **1.0** | 0.2 |
| `trake`         | 1.0 | 0.4 (anchor) | 0.4 (anchor) | 0.3 |

> ASR/OCR trong route `trake` dùng chủ yếu làm **ràng buộc thời gian** cho DP, không chỉ cộng điểm.

### 15.5 Tối ưu THỜI GIAN (bắt buộc)
1. **Gọi Qdrant và Mongo SONG SONG** (asyncio/thread) → độ trễ = `max`, không phải tổng.
2. **Mongo Atlas LOCAL bằng Docker** (`mongodb/mongodb-atlas-local`, có sẵn `mongot`) → hết RTT mạng.
   ⚠️ Mongo Community **không** có `$search` fuzzy — phải dùng image `atlas-local` hoặc Atlas cloud.
3. **1 round-trip mỗi bên** để lấy payload: `find({idx:{$in:[...]}})` + `retrieve(ids)` sau khi fuse.
4. `limit` mỗi nguồn ~200; index `idx` (unique) + Atlas Search index trên `ocr_text/asr_text`.
5. **Cache** dịch/augment; giữ client 2 engine warm (connection pool).

### 15.6 Tối ưu ĐỘ CHÍNH XÁC
- **RRF theo route** (§15.4) + trọng số học từ dev-set.
- **Fuzzy chuỗi**: kết hợp Atlas `maxEdits` với **sparse char-3gram** trong Qdrant (§8) → bù OCR sai/mất chữ.
- **Qwen2.5-VL verify top-K**: đọc lại chữ trên ảnh gốc → không phụ thuộc chất lượng OCR đã index.

### 15.7 Tránh & phòng lỗi
- ❌ **Không cross-filter** (đẩy tập `idx` lớn từ Mongo sang Qdrant làm filter) — Qdrant lọc theo danh sách id khổng lồ rất chậm. Luôn **parallel + RRF**.
- **Fallback**: nếu 1 store lỗi/timeout → trả kết quả của store còn lại (đừng để cả truy vấn fail).
- **Nhất quán `idx`**: ingest Qdrant và Mongo phải từ **cùng nguồn metadata** (§METADATA_SPEC) để `idx` khớp tuyệt đối.

### 15.8 Triển khai (docker-compose gợi ý)
```
services:
  qdrant:       image: qdrant/qdrant                 # 6333
  mongo-atlas:  image: mongodb/mongodb-atlas-local   # 27017, có $search fuzzy
```
Backend gọi cả hai qua localhost → độ trễ nội bộ ~ vài ms.

---

<a name="16-lộ-trình"></a>
## 16. Thứ tự triển khai (ROI cao → thấp)

1. Dựng Qdrant Docker + chốt schema (mục 3).
2. Ingest 3 leg ảnh (jina/CLIP/BEiT-3) (mục 2, 4).
3. Search KIS + RRF Qdrant (mục 6, 10.1) — thay FAISS.
4. **TRAKE 3 tầng + DP alignment** (mục 10.3) — ưu tiên ăn điểm.
5. Rerank Qwen2.5-VL (mục 7) + VQA cho Q&A (mục 10.2).
6. OCR leg (mục 8) — Mongo Atlas fuzzy + sparse char-3gram.
7. Audio/ASR leg (mục 9).
8. **Orchestrator hybrid Mongo+Qdrant gọi song song + RRF theo route** (mục 15).
9. Ghép embedding team share (mục 11).
10. Dev-set + tinh chỉnh trọng số (mục 12) — chạy song song từ bước 3.
11. Tối ưu độ trễ + dọn security (mục 13, 14).

---
*Ghi chú: chọn model cụ thể (jina-clip-v2, CLIP ViT-L-14, BEiT-3 large, Qwen2.5-VL 7B/72B, PhoWhisper) là đề xuất khởi điểm; thay thế/ nâng cấp phiên bản tùy GPU và kết quả dev-set.*
