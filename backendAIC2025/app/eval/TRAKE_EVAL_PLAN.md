# TRAKE — Kế hoạch đáp ứng review (biến critique thành bằng chứng)

> Phản hồi review "borderline / weak reject". Nhận định của reviewer **đúng**: vấn đề không phải accuracy thấp mà là **experimental design chưa chứng minh từng thành phần**. Phần lớn công cụ đo đã dựng xong trong `eval_trake.py`; việc còn lại chủ yếu là **gán thêm query có nhãn** (nhóm làm) rồi chạy.

## Trạng thái: `READY` = harness đã có · `DATA` = cần nhóm gán nhãn · `RUN` = chỉ cần chạy (máy/Colab)

| # | Reviewer yêu cầu | Hành động | Trạng thái |
|---|---|---|---|
| W1 | N=3 không có ý nghĩa thống kê | Gán **≥30–50 query** vào `queries_gt.json` (format có sẵn) | **DATA** |
| W2 | Greedy=DP=MM, DP chưa chứng minh | (a) Harness đã tách `run1_greedy`/`run2_dp`; (b) cần **query lặp sự kiện** để DP ăn greedy | READY + **DATA** |
| W3 | MATE chỉ tính khi trúng video, chưa nói rõ | Report đã ghi "trên query trúng video"; tách **Level 2 conditional** | **READY** |
| W4 | Multimodal chưa chứng minh (chỉ tăng #combo) | Harness đã tách **`run3a_ocr`/`run3b_asr`/`run3_mm`**; cần **query phụ thuộc OCR/ASR** | READY + **DATA** |
| W5 | DP tốn latency mà không tăng accuracy | Latency breakdown đã có; khi có query lặp sự kiện → DP sẽ có accuracy gain biện minh cost | READY + **DATA** |
| W6 | Novelty cần sắc hơn | Formalize objective + DP recurrence (xem `TRAKE_METHOD_DRAFT.md` §4,8) + mục novelty bên dưới | **READY (viết)** |

## 3 tầng đánh giá (reviewer §5) — ĐÃ có trong harness
Chạy 1 lệnh ra cả 3 tầng:
```bash
docker compose exec backend-api python -m app.eval.eval_trake \
  --queries app/eval/queries_gt.json --out app/eval/out --runs all \
  --k 1,5,10,100 --tol-frames 30 --event-recall-k 10,50,100,500,1000
```
- **Level 1 — Event Recall** (mục 0 trong `eval_results.md`): `EventRecall@K` (per-event) + `CandidateRecall@K` (đủ cả chuỗi). *CandidateRecall là TRẦN của End-to-End.*
- **Level 2 — Temporal Localization (conditional)** (mục 2/2b): `MATE(s)`, `MATE(frame)`, `MaxOff`, sweep `≤0/5/10/25/50/100/150f` — **chỉ trên query trúng video** (đã ghi rõ).
- **Level 3 — End-to-End** (mục 1): `R@K`, `MRR`, `mAP`, `VideoHit`.

Số thật hiện tại (3 query) đã cho thấy chuỗi nhân-quả: `CandidateRecall@1000=0.33 → R@1=0.33`, còn khi trúng thì `MATE=3.5 frame`. Đây đúng là **two-stage error profile** reviewer gợi ý viết (§20).

## Bảng ablation A–G (reviewer §13) — map sẵn run key
| Ablation | Run key | Câu hỏi khoa học | Trạng thái |
|---|---|---|---|
| A: Event ANN | *(mục 0 Event Recall)* | Event retrieval đủ không? | **READY** |
| B: +Greedy | `run1_greedy` | Temporal aggregation giúp? | READY |
| C: +DP | `run2_dp` | Ordering constraint giúp? | READY (cần query lặp sự kiện) |
| D: +OCR | `run3a_ocr` | Textual evidence giúp? | READY (cần query OCR) |
| E: +ASR | `run3b_asr` | Speech evidence giúp? | READY (cần query ASR) |
| F: +OCR+ASR | `run3_mm` | Multimodal fusion giúp? | READY (cần query đa phương thức) |
| G: +Tier3 | `run5_tier3_peak` | Fine refinement giúp? | READY (cần video gốc + Colab) |

## 5 experiment ưu tiên (reviewer §19) — việc cụ thể
1. **≥30–50 query** *(DATA)* — đa dạng độ khó; điền `queries_gt.json`. Dùng web app đọc `frame_id`.
2. **Greedy vs DP với sự kiện LẶP** *(DATA)* — chọn video mà E1/E2/E3 **xuất hiện nhiều lần**; greedy dễ ghép sai thứ tự (1000→5000→3000), DP phải ra (1000→2000→3000). Đây là **bằng chứng DP cần thiết** → `run1_greedy` vs `run2_dp` sẽ khác nhau.
3. **Visual vs +OCR vs +ASR vs +OCR+ASR** *(DATA+RUN)* — gán `events_ocr`/`events_asr` cho các event có chữ/lời nói; chạy `--runs run2_dp,run3a_ocr,run3b_asr,run3_mm`. Cần có **query phụ thuộc OCR** (vd chỉ đọc được qua biển "Cánh gà lắc") và **phụ thuộc ASR** (chỉ nghe lời dẫn).
4. **Hình Event→Localization→End-to-End** *(READY)* — vẽ từ `eval_results.csv` (mục 0/2/1). Biến q1/q2 fail thành phân tích khoa học.
5. **Parameter sensitivity** *(RUN)* — quét `TOP_M ∈ {100,300,1000}`, `TOP_VIDEOS ∈ {2,5,15}`, `MAX_COMBOS ∈ {10,25,50,100,200}`:
   ```bash
   for M in 100 300 1000; do docker compose exec -e TRAKE_TOP_M=$M backend-api \
     python -m app.eval.eval_trake --queries app/eval/queries_gt.json \
     --out app/eval/out_M$M --runs run2_dp --k 1,5,10,100 --tol-frames 30; done
   ```
   Báo cáo R@1 / MATE / latency theo từng giá trị → biện minh `MAX_COMBOS=100` (§12) và chọn TOP_M.

## Novelty & formulation (reviewer §14–15, W6)
Khung mạnh để viết Intro/Method (đã khớp implementation):
> **TRAKE formulates multi-event video retrieval as a constrained temporal-sequence retrieval problem**: các event candidate độc lập được **đồng tối ưu** dưới ràng buộc thứ tự thời gian + bằng chứng đa phương thức.

DP không phải implementation detail mà là **cơ chế tối ưu** giải temporal consistency. Objective (viết vào paper):
$$ S(\mathbf{t},v)=\sum_i S_\text{sem}(e_i,t_i)+\lambda_m S_\text{mm}(e_i,t_i)\quad \text{s.t. } t_1<\dots<t_N,\ t_{i+1}-t_i\le\Delta $$
giải bằng DP đơn điệu: $DP[i,j]=\max_{k<j} DP[i-1,k]+S(e_i,t_j)$ (chi tiết `TRAKE_METHOD_DRAFT.md` §4,§8).

## Cách viết Results (reviewer §9,§10,§20)
- **MATE** luôn ghi "**conditioned on correct video retrieval**"; không trình bày như end-to-end.
- **±30 frame** = *operational tolerance*, kèm sweep; viết "we use ±30f as the primary criterion" + bảng sweep, **không** nói "30f là đúng tuyệt đối".
- **Không giấu q1/q2**: trình bày two-stage error profile (recall bottleneck vs localization accuracy) → thành insight.

## Checklist trước khi nộp
- [ ] `queries_gt.json` có ≥30 query (gồm ≥5 query lặp sự kiện cho DP, ≥5 OCR-dependent, ≥5 ASR-dependent).
- [ ] Chạy `--runs all` → điền 3 bảng (Level 0/1/2/3) + ablation A–G vào paper.
- [ ] Parameter sensitivity (TOP_M, TOP_VIDEOS, MAX_COMBOS).
- [ ] Tier3/Qwen (Run4/5/6) trên Colab cho query trúng video.
- [ ] Hình decompose Event→Localization→End-to-End.
- [ ] Objective + DP recurrence + novelty statement trong Method.
