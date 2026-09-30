# Method (draft) — TRAKE: Temporal-Sequence Keyframe Retrieval

> Bản nháp phần **Method** cho paper, mô tả thuật toán **TRAKE** (truy hồi chuỗi sự kiện theo thời gian trong cùng một video). Gồm: phát biểu bài toán, ký hiệu, tổng quan pipeline 3 tầng, **mã giả (pseudocode)** từng bước, phân tích độ phức tạp và ghi chú trung thực.
>
> Bám sát cài đặt thực tế: `backendAIC2025/app/services/trake_service.py` (hàm `run_trake`) và `trake_controller.py`. Thuật ngữ toán học ở đây ánh xạ 1–1 với hàm trong code (nêu tên hàm trong ngoặc để dễ đối chiếu khi viết paper).

---

## 1. Phát biểu bài toán

Cho một kho video, mỗi video $V$ gồm chuỗi keyframe đã lập chỉ mục và nhúng (embedding) bằng một mô hình thị giác–ngôn ngữ $\phi$ (BEIT3 / JINA / PE). Một **truy vấn TRAKE** là một chuỗi **có thứ tự thời gian** gồm $N \ge 2$ sự kiện:

$$
Q = \langle q_1, q_2, \dots, q_N \rangle,
$$

trong đó mỗi $q_j$ có thể là (a) mô tả hình ảnh (text), (b) chuỗi OCR, (c) chuỗi ASR, hoặc kết hợp; **ít nhất một** trong ba phải khác rỗng.

**Mục tiêu:** tìm một video $V^\*$ và một bộ khung hình

$$
F^\* = (f_1 < f_2 < \dots < f_N), \qquad f_j \in V^\*,
$$

sao cho $f_j$ khớp sự kiện $q_j$ và **thứ tự khung hình tăng nghiêm ngặt** (phản ánh thứ tự thời gian của các sự kiện). Đầu ra nộp lên hệ thống là cặp $(\text{video\_id},\, [f_1,\dots,f_N])$; hệ thống sinh **tối đa $C_{\max}=100$ tổ hợp** để tối ưu recall (chuẩn nộp TRAKE của AIC/VBS).

**Ràng buộc khoảng cách (tuỳ chọn):** người dùng có thể giới hạn khoảng cách thời gian tối đa giữa hai sự kiện liên tiếp bằng $\Delta_s$ giây; quy ra khung hình $\Delta = \mathrm{round}(\text{fps}\cdot\Delta_s)$ (hàm `_max_event_gap_frames`). $\Delta_s \le 0$ hoặc rỗng $\Rightarrow$ không giới hạn (mặc định).

---

## 2. Ký hiệu

| Ký hiệu | Ý nghĩa | Trong code |
|---|---|---|
| $\phi_m$ | encoder text/ảnh của model $m$ (L2-normalize) | `engine.registry.encode_text/encode_image` |
| $\mathbf{e}_j$ | vector nhúng của sự kiện $q_j$ (hoặc $\varnothing$ nếu $q_j$ chỉ OCR/ASR) | `encode_events` |
| $s(\mathbf{e}, f)$ | độ tương đồng cosine giữa event và keyframe $f$ | Qdrant score |
| $M$ | số ứng viên top mỗi event ở Tầng 1 | `top_m` |
| $K_v$ | số video giữ lại sau Tầng 1 | `top_videos` |
| $B(N)$ | ngân sách ứng viên mỗi event (để Cartesian $\le 100$) | `candidate_budget` |
| $R, s_\text{tride}$ | bán kính & bước decode frame ở Tầng 3 | `TRAKE_TIER3_RADIUS/STRIDE` |
| $C_{\max}$ | số tổ hợp tối đa nộp | `TRAKE_MAX_COMBOS` (=100) |
| $\Delta$ | khoảng cách frame tối đa giữa 2 event | `max_gap` |

Ngân sách ứng viên (đảm bảo $\prod_j B(N) \le 100$):

$$
B(N) = \begin{cases} 10 & N=2\\ 4 & N=3\\ 3 & N\in\{4,5\}\\ 2 & N=6 \\ \le 2 & N>6\end{cases}
$$

---

## 3. Tổng quan pipeline

TRAKE dùng kiến trúc **thô-đến-tinh (coarse-to-fine) ba tầng** cộng bước **sinh tổ hợp** có ràng buộc thời gian:

```
        Q = <q_1..q_N>
              │
   ┌──────────▼───────────┐   Tầng 1  (select_video_dp + ocr_asr_candidate_videos)
   │  Chọn video ứng viên  │   top-M mỗi event → gom theo video → DP đơn điệu → K_v video
   └──────────┬───────────┘   (+ video được OCR/ASR bảo chứng)
              │  phân bổ slot (allocate_video_slots)
   ┌──────────▼───────────┐   Tầng 2  (locate_events_exact)
   │ Định vị event/1 video │   Qdrant filter (video_id, frame_id>prev) → ứng viên/event
   └──────────┬───────────┘   (event chỉ OCR/ASR → ứng viên từ Mongo)
              │
   ┌──────────▼───────────┐   Tầng 3  (refine_event_fine) — CHỈ khi có VIDEO_ROOT
   │ Tinh chỉnh frame gốc  │   decode ±R, encode cùng model, peak-rerank, Qwen tie-break
   └──────────┬───────────┘
              │  (+ OCR/ASR soft-boost & inject)
   ┌──────────▼───────────┐   Sinh nộp  (build_cartesian_submissions)
   │  Cartesian + NMS +    │   thứ tự tăng + max_gap + trọng số softmax → top C_max combo
   │  ràng buộc thời gian  │
   └──────────────────────┘
```

Hai chế độ đầu ra: **Case 1 (`case1_full`, tier 3)** khi có video gốc để tinh chỉnh; **Case 2 (`case2_coarse`, tier 2)** khi chỉ có keyframe (dừng ở tầng 2, tie-break bằng Qwen trên ảnh keyframe).

---

## 4. Tầng 1 — Chọn video bằng quy hoạch động đơn điệu

**Ý tưởng.** Với mỗi sự kiện có mô tả hình ảnh, lấy top-$M$ keyframe toàn kho. Gom theo `video_id`. Một video là ứng viên tốt nếu tồn tại một cách chọn **một keyframe cho mỗi sự kiện với `frame_id` tăng nghiêm ngặt** và tổng độ tương đồng lớn nhất. Đây là bài toán **Weighted Longest Increasing Subsequence** theo tầng sự kiện, giải bằng DP.

### Thuật toán 1 — DP đơn điệu trong một video (`_dp_align`)

Cho mỗi sự kiện $j$ một tập ứng viên trong video: $\mathcal{C}_j = \{(f, s)\}$ đã sort theo $f$ tăng.

```
Input : C_1..C_N  (mỗi C_j = list (frame_id, score), sort theo frame_id)
Output: best_cum, path=(f_1<...<f_N)

layer[1] ← {(f, s, ⊥) : (f,s) ∈ C_1}
for j = 2..N:
    prev ← sort(layer[j-1]) theo frame_id
    cur ← ∅
    for (f, s) ∈ C_j:
        best ← -∞ ; arg ← ⊥
        for (pf, pcum, ·) ∈ prev:      # duyệt tăng
            if pf ≥ f: break            # cần pf < f (tăng nghiêm ngặt)
            if pcum > best: best ← pcum ; arg ← pf
        if arg ≠ ⊥:
            cur ← cur ∪ {(f, s + best, arg)}   # cực đại tổng score
    layer[j] ← cur
    if cur = ∅: return (-∞, [])         # video thiếu 1 event ⇒ loại
(f*, best_cum, ·) ← argmax over layer[N] theo cumulative
path ← backtrack các con trỏ arg từ layer[N] về layer[1]
return best_cum, path
```

$best\_cum$ là **điểm video** (tổng tương đồng của chuỗi khớp tốt nhất).

### Thuật toán 2 — Chọn K_v video (`select_video_dp`)

```
visual ← {j : e_j ≠ ∅}                       # bỏ event chỉ OCR/ASR
if visual = ∅: return []                      # để OCR/ASR lo Tầng 1
for j ∈ visual: H_j ← Qdrant top-M(e_j)       # query toàn collection model m
group H_j theo video_id → per_video[v].events[j] = [(frame_id, score)]
for v ∈ per_video:
    if |events(v)| < |visual|: continue        # video thiếu event hình ⇒ loại
    best, _ ← _dp_align( sort_j C_j(v) )
    score(v) ← best
return top-K_v video theo score giảm dần
```

**Tự nới:** nếu không video nào đủ, $M \leftarrow 3M$ (lặp tối đa 3 lần) và $M \ge K_v\cdot 100$ (`run_trake`).

### Tầng 1 mở rộng bằng OCR/ASR (`ocr_asr_candidate_videos`)

Với các event có OCR/ASR, đếm "phiếu" video khớp chữ/lời nói (Atlas Search trên Mongo). Video có phiếu được **thêm vào** danh sách ứng viên với điểm ngang top-visual (OCR/ASR là tín hiệu mạnh, tránh bỏ sót khi hình ảnh yếu). Cờ `from_ocr_asr` được dùng ở bước phân bổ slot.

### Phân bổ slot nộp (`allocate_video_slots`)

Cho tập video ứng viên điểm $\{u_i\}$, tính $p = \mathrm{softmax}(u)$. Chia $C_{\max}$ slot:

- **1 video** → toàn bộ slot.
- **Chắc chắn** ($p_1 \ge \tau=0.8$) **và** không có bảo chứng OCR/ASR **và** $\le 2$ video → dồn hết cho top-1.
- **Ngược lại** (khám phá / có OCR/ASR): mỗi video một **sàn** $\lfloor C_{\max}/(3n)\rfloor$, phần còn lại chia theo $p_i$ (bù phần lẻ cho video điểm cao). Sàn đảm bảo không video nào "biến mất".

---

## 5. Tầng 2 — Định vị từng sự kiện trong một video (`locate_events_exact`)

Duyệt sự kiện theo thứ tự, ràng buộc **nhân quả thời gian** $f_j > f_{j-1}$ ngay tại truy vấn:

```
prev ← ⊥
for j = 1..N:
    if e_j ≠ ∅:                                  # event có mô tả hình
        H ← Qdrant top-k(e_j | video_id=v, frame_id > prev)
        if H = ∅: H ← Qdrant top-k(e_j | video_id=v)   # nới nếu rỗng
        C_j ← [(frame_id, score) ∈ H]
    else:                                         # event chỉ OCR/ASR
        C_j ← OCR/ASR candidates in video v, frame_id > prev   # từ Mongo
    center_j ← argmax score in C_j ; prev ← center_j
return {C_j}, path_map(frame_id → keyframe path)
```

Ứng viên OCR/ASR-only (`_ocr_asr_frames_for_event`): OCR → keyframe khớp chữ (điểm giảm dần theo thứ hạng $1-0.02\cdot\text{rank}$); ASR → keyframe nằm trong khoảng lời nói khớp (điểm $0.9$). Ép $f>prev$; nếu rỗng thì nới ràng buộc.

---

## 6. Tầng 3 — Tinh chỉnh khung hình gốc (`refine_event_fine`)

Chỉ chạy khi **có `VIDEO_ROOT` + video gốc** (Case 1). Quanh khung thô $f_j^{c}$, decode cửa sổ

$$
[\max(f_j^{c}-R,\; f_{j-1}^{\text{fine}}+1,\; 0),\; f_j^{c}+R]
$$

lấy mỗi $s_\text{tride}$ frame, encode ảnh bằng **đúng model $m$** của collection, tính điểm $s = E\mathbf{e}_j$ (cosine, do đã chuẩn hoá), rồi rerank:

### Thuật toán 3 — Peak-detection rerank (`_rank_by_peak`, `pick_semantic_frame_algorithmic`)

```
if len(scores) ≥ 3:
    peaks, prom ← find_peaks(scores, prominence=0)     # cực đại cục bộ
    if peaks ≠ ∅:
        rank peaks theo (prominence desc, score desc)
        return (peaks_ranked ++ các frame còn lại theo score)[:topk]
return argsort(-scores)[:topk]                           # fallback
```

Chọn **đỉnh nổi bật (prominent peak)** thay vì chỉ điểm cao nhất giúp bắt đúng "thời điểm" sự kiện (cực đại cục bộ theo thời gian), giảm nhiễu do frame lân cận điểm cao đều.

### Tie-break bằng VLM (`qwen_rerank_candidates`)

Nếu top-2 ứng viên chênh nhau $< \varepsilon$ (`TRAKE_RERANK_TIE_MARGIN`) và Qwen bật: đưa $\le 3$ ảnh (theo thứ tự thời gian) cho **Qwen2.5-VL** chọn "ảnh nào đúng khoảnh khắc $q_j$"; kết quả thay vị trí đầu. Ở **Case 2** (không video), tie-break dùng ảnh keyframe (`qwen_rerank_tier2`). Qwen là **tuỳ chọn**; thiếu GPU/thư viện → tự fallback về thuật toán peak.

---

## 7. Hợp nhất OCR/ASR mức sự kiện (soft-boost + inject)

Với mỗi sự kiện có OCR/ASR, xác định trong video đang xét: tập frame khớp OCR $O_j$ và các khoảng ASR $A_j$ (`_event_ocr_asr_targets`). Áp lên ứng viên (`_apply_ocr_asr_boost`):

$$
s'(f) = s(f)\cdot(1+\beta)\quad\text{nếu } \exists\, o\in O_j:\ |f-o|\le w \ \text{hoặc}\ \exists (a,b)\in A_j:\ a\le f\le b,
$$

với $\beta=$ `TRAKE_OCRASR_BOOST`, $w=$ `TRAKE_OCRASR_WINDOW`. Đồng thời **inject** tối đa 3 frame OCR khớp chưa nằm gần ứng viên nào (điểm $=$ max hiện có $\times(1+\beta)$), đảm bảo bằng chứng văn bản chắc chắn được xét.

---

## 8. Sinh tổ hợp nộp có ràng buộc thời gian (`build_cartesian_submissions`)

### Thuật toán 4 — Cartesian + NMS thời gian + ràng buộc thứ tự

```
Input : {C_j} ứng viên mỗi event, C_max, min_gap=15, max_gap=Δ
# 1) NMS thời gian mỗi event: bỏ frame quá gần nhau (giữ điểm cao)
for j: C_j ← nms(sort_desc_score(C_j), min_gap)        # (nms_candidates)
        p_j ← softmax(scores in C_j)                    # xác suất mềm
# 2) Tích Descartes có ràng buộc
best ← ∅
for combo ∈ C_1 × C_2 × ... × C_N:
    f ← (f_1..f_N)
    if ∀i: f_i < f_{i+1}                     (tăng nghiêm ngặt)
       and (Δ=∞ or ∀i: f_{i+1}-f_i ≤ Δ):     (khoảng cách ≤ Δ)
        w ← Π_i p_{i}(f_i)                    (trọng số = tích xác suất)
        best ← best ∪ {(f, w)}
return top-C_max của best theo w giảm dần
```

**NMS thời gian** (`nms_candidates`): giữ frame khi cách mọi frame đã giữ $\ge$ `min_gap` (=15), tránh nộp nhiều frame gần trùng. **Trọng số tổ hợp** là tích xác suất softmax nội-sự-kiện → tổ hợp gồm các frame "tự tin" ở mọi bước được xếp trên.

---

## 9. Orchestrator (`run_trake`) — ghép toàn bộ

### Thuật toán 5 — TRAKE end-to-end

```
E ← encode_events(Q, m)                                  # e_j hoặc ∅
Vc ← select_video_dp(E, M, K_v)   (tự nới M×3 nếu rỗng)
Vc ← Vc ∪ ocr_asr_candidate_videos(Q_ocr, Q_asr)         # bảo chứng OCR/ASR
if Vc = ∅: return {ok:false}
slots ← allocate_video_slots(Vc, C_max, τ)
for (v, slot) ∈ slots:
    coarse, path_map ← locate_events_exact(E, v, topk=B(N), Q_ocr, Q_asr)
    if coarse rỗng: continue
    if VIDEO_ROOT có v:                                   # Tầng 3
        for mỗi event: C_j ← refine_event_fine(...)        # peak + Qwen tie
    else:                                                 # Case 2
        C_j ← coarse.cands
    C_j ← apply_ocr_asr_boost(C_j)                         # boost + inject
    if Case 2 và Qwen sẵn sàng: C_j ← qwen_rerank_tier2(C_j)
    combos_v ← build_cartesian_submissions(C_j, slot, max_gap=Δ)
submissions ← ⋃_v {(v, combo)}  [:C_max]
return { submissions, per_video(event_candidates, scores, paths), mode, tier, ... }
```

Đầu ra kèm **ứng viên từng sự kiện** (frame_id + score + path keyframe) để UI hiển thị điểm tương đồng, cho **nhích thủ công (nudge)** và **verify** từng khung hình trước khi nộp.

---

## 10. Phân tích độ phức tạp

- **Tầng 1:** $N$ truy vấn ANN top-$M$ ($O(N\log|\mathcal{D}|)$ với ANN). DP mỗi video: $O(\sum_j |\mathcal{C}_j|^2)$ tệ nhất, nhưng $|\mathcal{C}_j|$ nhỏ (giới hạn bởi $M$ và số hit/video). Tổng thực nghiệm rất nhẹ.
- **Tầng 2:** $N$ truy vấn ANN có filter, mỗi truy vấn $O(\log)$.
- **Tầng 3:** decode $\le (2R/s_\text{tride})$ frame/event + $N$ lần encode ảnh (nặng nhất, chỉ khi Case 1); Qwen chỉ khi tie.
- **Sinh tổ hợp:** $\prod_j |\mathcal{C}_j| \le \prod_j B(N)\le 100$ nhờ ngân sách $B(N)$ ⇒ Cartesian bị chặn cứng, $O(C_{\max}\cdot N)$.

---

## 11. Ghi chú trung thực (cho Limitations)

- **Điểm số** ở Tầng 1/2 là **cosine similarity thật** từ Qdrant; Tầng 3 tính lại cosine trên embedding ảnh decode bằng đúng model. Không có điểm hợp nhất "đa phương thức" dạng học được — OCR/ASR tham gia qua **bảo chứng video (Tầng 1)**, **ứng viên (Tầng 2)** và **soft-boost/inject (mức sự kiện)**, đều là heuristic có hệ số cấu hình ($\beta, w$).
- **Tầng 3 & Qwen là tuỳ chọn:** cần `VIDEO_ROOT` (video gốc) cho Tầng 3 và GPU/thư viện cho Qwen; thiếu → hệ thống chạy **Case 2** (dừng ở keyframe) và rerank bằng **peak-detection thuần thuật toán**. Điều này cần nêu rõ khi báo cáo kết quả (cấu hình nào đang bật).
- **Ràng buộc thời gian** chỉ áp ở mức **thứ tự tăng** (bắt buộc) và **khoảng cách tối đa $\Delta$** (tuỳ chọn); không mô hình hoá thời lượng/nhịp giữa các sự kiện.
- **DP đòi hỏi video chứa đủ các event hình ảnh** (bỏ video thiếu); các event chỉ-OCR/ASR không tham gia DP mà được định vị ở Tầng 2 — có thể bỏ sót nếu tín hiệu hình ảnh của các event còn lại quá yếu (giảm nhẹ bằng ứng viên OCR/ASR ở Tầng 1).

---

## 12. Bảng siêu tham số (điền giá trị thực khi chạy thí nghiệm)

| Tham số | Ký hiệu | Nguồn | Giá trị |
|---|---|---|---|
| Top-M Tầng 1 | $M$ | `TRAKE_TOP_M` | … |
| Số video giữ | $K_v$ | `TRAKE_TOP_VIDEOS` | … |
| Ngưỡng tự tin | $\tau$ | `TRAKE_VIDEO_CONFIDENCE_THRESHOLD` | 0.8 |
| Bán kính Tầng 3 | $R$ | `TRAKE_TIER3_RADIUS` | … |
| Bước decode | $s_\text{tride}$ | `TRAKE_TIER3_STRIDE` | … |
| Biên tie | $\varepsilon$ | `TRAKE_RERANK_TIE_MARGIN` | … |
| Boost OCR/ASR | $\beta$ | `TRAKE_OCRASR_BOOST` | … |
| Cửa sổ OCR/ASR | $w$ | `TRAKE_OCRASR_WINDOW` | … |
| NMS thời gian | — | `min_gap` | 15 |
| Số combo tối đa | $C_{\max}$ | `TRAKE_MAX_COMBOS` | 100 |

> **TODO khi hoàn thiện paper:** (i) điền giá trị siêu tham số + cấu hình phần cứng; (ii) bảng ablation: DP-only vs +OCR/ASR vs +Tầng 3 vs +Qwen; (iii) ví dụ định tính (hình chuỗi sự kiện + frame chọn); (iv) chỉ số đánh giá theo chuẩn TRAKE của BTC.
