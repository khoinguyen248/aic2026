# Eval TRAKE — hướng dẫn chạy & lấy số cho paper

Harness: [`eval_trake.py`](eval_trake.py). Chạy **ma trận ablation Run 1–6** (§4 tài liệu *"Đánh giá Thuật toán TRAKE"*), tính đủ metric §1, xuất `eval_results.md` + `eval_results.csv`.

## 1. Chạy

Chạy **trong container backend** (cần SearchEngine + Qdrant + model). Thư mục `app/` đã mount nên không cần rebuild:

```bash
docker compose exec backend-api python -m app.eval.eval_trake \
  --queries app/eval/queries_gt.json --out app/eval/out --runs all --k 1,5,10,100 --tol-frames 25
```

- `--runs all` hoặc chọn: `run1_greedy,run2_dp,run3_mm,run4_tier3_argmax,run5_tier3_peak,run6_full`
- `--tol-frames` : cửa sổ dung sai khung hình để tính "đúng" (mặc định ±25f ≈ 1s@25fps).
- Kết quả ghi ở `app/eval/out/` → trên host là `backendAIC2025/app/eval/out/`.

## 2. Định dạng ground-truth (GT)

`--queries` là JSON list; xem [`queries_gt.template.json`](queries_gt.template.json). Mỗi phần tử:

| Trường | Bắt buộc | Ý nghĩa |
|---|---|---|
| `events` | ✅ | Chuỗi mô tả **hình ảnh** từng sự kiện (theo thứ tự thời gian). Rỗng `""` nếu sự kiện chỉ dùng OCR/ASR. |
| `events_ocr` / `events_asr` | – | Mảng **song song** với `events` (chuỗi OCR / lời nói mong đợi). Chỉ dùng ở Run 3–6. |
| `language` | – | `true` = dịch vi→en trước khi encode (dùng cho `beit3`). `jina` đa ngữ có thể để `false`. |
| `model` | – | `beit3` \| `jina` \| `pe` (mặc định `beit3`). **batch2 S/M/N chỉ có ở `jina`.** |
| `max_event_gap_s` | – | Khoảng cách tối đa giữa 2 sự kiện (giây). `null` = không giới hạn. |
| `gt` | (để tính accuracy) | `{ "video_id", "frame_ids":[...], "fps" }`. `frame_ids` **cùng độ dài & thứ tự** với `events`. |

Không có `gt` → chỉ tính **latency/throughput/behavioral** (vẫn chạy được).

### Lấy GT từ đáp án công khai AIC
- **Task TRAKE**: đáp án đã là `video_id` + danh sách `frame_id` → điền thẳng vào `gt`.
- **Task KIS/QA** (đáp án là mốc **millisecond**): quy ra frame `frame_id = round(ms/1000 * fps)`. Với video **N (VFR)** nên lấy `frame_id` tương ứng `frame_stamp` gần nhất thay vì nhân fps.
- Đặt `fps` đúng của video (đọc từ `ocr_metadata`/kết quả search) để MATE ra giây chính xác.

## 3. Metric xuất ra

- **Bảng 1 — xếp hạng/độ phủ:** `Recall@K`, `MRR`, `mAP` (giả định 1 target/query), `VideoHit` (tỷ lệ trả đúng video, bất kể frame).
- **Bảng 2 — thứ tự & sai lệch thời gian:** `MATE` (giây, sai số frame TB / fps), `T@±tol` (tỷ lệ sự kiện có frame lệch ≤ tol), `Kendall τ`, `Spearman ρ`.
- **Bảng 3 — vận hành:** latency breakdown `encode/tier1/tier2/tier3/qwen/combos/total` (giây TB/query) + `QPS`.
- **Bảng 4 — behavioral:** số combo TB, số sự kiện dùng Qwen.

"Đúng" (cho Recall/MRR): submission có **cùng video** GT **và** mỗi frame lệch ≤ `tol` so với `gt.frame_ids` theo vị trí sự kiện.

## 4. Ma trận ablation (Run 1–6)

| Run | Cấu hình | Giả thuyết |
|---|---|---|
| `run1_greedy` | ANN/event + ghép tham lam, **không DP, không refine** | DP + ràng buộc đơn điệu đóng góp bao nhiêu |
| `run2_dp` | Tier1+2 DP, keyframe-only | DP loại liên kết sự kiện giả xuyên video |
| `run3_mm` | +OCR/ASR soft-boost + injection | Multimodal cứu chuỗi mất dấu thị giác |
| `run4_tier3_argmax` | +Tier3 decode, rerank **argmax** | Lợi ích decode video gốc (chưa khử bình nguyên) |
| `run5_tier3_peak` | +Tier3 decode, rerank **peak prominence** | Dò đỉnh giảm trôi khung hình (frame drift) |
| `run6_full` | +Qwen2.5-VL tie-break có điều kiện | SOTA; phân xử biên tối ưu |

## 5. Lưu ý trung thực (đọc trước khi đưa số vào paper)

- **Tier3 (Run4/5/6) cần `VIDEO_ROOT` + video gốc trên máy** và `TRAKE_TIER3_ENABLED` (harness tự bật khi chạy Run4-6). Nếu không có video, hệ thống **tự về case2** (dừng ở keyframe) ⇒ số accuracy Run4/5/6 sẽ **≈ Run3**. Harness in `tier3_globally_ready` để bạn biết.
- **Qwen (Run6) cần GPU + `transformers` + model**; thiếu → tự fallback về thuật toán ⇒ Run6 ≈ Run5. Harness in `qwen_ready`.
- **Kendall τ / Spearman ρ** thường ≈ 1 vì DP đã ép đơn điệu tăng; chúng chủ yếu để **xác nhận** trật tự nhân quả được giữ, không phải chỉ số phân biệt mô hình (nêu rõ trong paper).
- **1 target/query** ⇒ `mAP` ≈ `MRR`; giữ cả hai cho khớp bảng chuẩn nhưng nêu giả định.
- Muốn số Tier3/Qwen thật: chạy harness trên máy có ổ video + GPU, đặt `VIDEO_ROOT` trong `.env`.
- Recall của multimodal phụ thuộc chất lượng GT `events_ocr/asr` (nên là cụm thật xuất hiện trong lời nói/chữ).
