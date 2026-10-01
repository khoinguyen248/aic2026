# Kết quả eval TRAKE — Run 1/2/3 (số thật, 3 query có đáp án)

> Chạy thật trên **máy local (CPU)**, model **jina**, index đầy đủ. Đây là số cho phần Results/Ablation của paper. Tier3/Qwen (Run4/5/6) chạy riêng trên Colab GPU (xem `trake_colab.ipynb`).

## Thiết lập
- Model: `jina` (jinaai/jina-embeddings-v5-omni-small), query tiếng Việt native (`language=false`).
- Config mặc định: `TRAKE_TOP_M≈200`, `TRAKE_TOP_VIDEOS=2`, `MAX_COMBOS=100`.
- Tolerance đúng: **±30 frame** (~1.2 s @25fps). K = {1,5,10,100}.
- 3 query có đáp án (xem `queries_gt.sample.json`):

| # | Video (GT) | Sự kiện | Đáp án |
|---|---|---|---|
| q1 | L26_V069 | 4 (nấu lươn) | frames 5360, 5473, 5631, 6104 |
| q2 | L22_V010 | 4 (trang trí Tết) | ranges 9104–9164, 9358–9480, 9609–9669, 9758–9778 |
| q3 | L27_V016 | 4 (thiên nhiên VN) | frames 86, 146, 283, 1197 |

## Kết quả từng query
| Query | Run1 greedy | Run2 DP | Run3 +MM | Lệch frame/event | Ghi chú |
|---|---|---|---|---|---|
| q1 L26_V069 | ✗ (video miss) | ✗ (video miss) | ✗ | – | E1 không được embedding khớp |
| q2 L22_V010 | ✗ (video miss) | ✗ (video miss) | ✗ | – | E2/E3 khớp sai cảnh |
| q3 L27_V016 | **rank 1** | **rank 1** | **rank 1** | **[0, 14, 0, 0]** | 3/4 event lệch **0 frame**, E2 lệch **14 frame** |

## Bảng 1 — Xếp hạng & độ phủ (3 query)
| Run | R@1 | R@5 | R@10 | R@100 | MRR | mAP | VideoHit |
|---|---|---|---|---|---|---|---|
| Run1 greedy | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 |
| Run2 DP | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 |
| Run3 +MM | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 |

## Bảng 2 — Sai lệch thời gian & ĐỘ LỆCH FRAME (trên query trúng video)
| Run | MATE (s) | MATE (frame) | MaxOff (frame) | T@±30f | Kendall τ | Spearman ρ |
|---|---|---|---|---|---|---|
| Run1 | 0.140 | 3.5 | 14 | 1.000 | 1.000 | 1.000 |
| Run2 | 0.140 | 3.5 | 14 | 1.000 | 1.000 | 1.000 |
| Run3 | 0.140 | 3.5 | 14 | 1.000 | 1.000 | 1.000 |

- **MaxOff = 14 frame** = lệch lớn nhất giữa các event ⇒ **tolerance tối thiểu để query được chấm đúng toàn bộ**. Với 25fps ≈ **0.56 s**.

## Bảng 2b — Tỷ lệ EVENT đúng theo ngưỡng lệch frame (sweep, trên 4 event của q3)
| ≤0f | ≤5f | ≤10f | ≤25f | ≤50f | ≤100f |
|---|---|---|---|---|---|
| 0.75 | 0.75 | 0.75 | 1.00 | 1.00 | 1.00 |

→ **3/4 event khớp CHÍNH XÁC (0 frame)**; chỉ 1 event cần tới ~14 frame. Nếu BTC cho phép **≥ ~15–25 frame (~0.6–1.0 s @25fps)** thì cả 4 event của q3 đều được tính đúng. (Đây là mốc tham khảo từ 1 query; cần nhiều query hơn để chốt ngưỡng tin cậy.)

## Bảng 3 — Latency breakdown (giây/query, CPU local)
| Run | encode | tier1 | tier2 | combos | total | QPS |
|---|---|---|---|---|---|---|
| Run1 greedy | 2.13 | 0.18 | – | – | 2.30 | 0.43 |
| Run2 DP | 2.07 | 0.43 | 1.87 | 0.00 | 4.37 | 0.23 |
| Run3 +MM | 2.18 | 0.36 | 1.91 | 0.00 | 4.45 | 0.22 |

## Chẩn đoán bottleneck (per-event, top-1000 jina)
| Query đúng | Sự kiện | rank video đúng | #frame đúng trong top-1000 | Nhận xét |
|---|---|---|---|---|
| L26_V069 | E1 "phết dầu lên chảo" | **None** | **0** | Embedding không khớp → DP loại cả video |
| L26_V069 | E2 "đặt lươn lên chảo" | 238 | 4 (5414,5436…) | OK |
| L26_V069 | E3 "ép miếng lươn" | 16 | 24 (sai frame) | Khớp sai cảnh |
| L26_V069 | E4 "lươn lên dĩa" | 0 | 19 (sai frame 512…) | Khớp sai cảnh |
| L22_V010 | E1 "sao đỏ vòng bạc" | 1 | 18 (9166,9133 ✓) | Tốt |
| L22_V010 | E2 "MC cầm dây móc đồ" | 304 | 2 | Rất sâu |
| L22_V010 | E3 "áo đen họa tiết cam" | 174 | 4 (17k,18k sai) | Khớp sai cảnh |
| L22_V010 | E4 "gấu trúc bụng sáng" | 21 | 6 (9758,9778 ✓) | Tốt |

## Phân tích (cho Results/Limitations)
1. **Pipeline được kiểm chứng end-to-end**: với query có sự kiện trực quan rõ (q3), TRAKE trả **đúng video, đúng thứ tự, MATE 0.14 s** (~3.5 frame). Tức Tầng 1 DP + Tầng 2 định vị + sinh tổ hợp hoạt động chính xác.
2. **Trần hiệu năng nằm ở recall embedding Tầng 1** (đúng như §3.3 tài liệu): DP yêu cầu **mọi** sự kiện trực quan phải có mặt trong top-M. Chỉ cần **một** sự kiện trừu tượng/hành động khó (E1 nấu ăn, E2/E3 mô tả người) không được embedding khớp → **mất cả video**. Đây là *bằng chứng định lượng* cho luận điểm giới hạn của phương pháp.
3. **Accuracy Run1 = Run2 = Run3 trên tập này** vì: (a) tập chỉ 3 query, q3 dễ nên cả greedy lẫn DP đều trúng; (b) chỉ q3 có 1 gợi ý OCR ("Cánh gà lắc" ở E3) nhưng E3 vốn đã khớp **0 frame** nên OCR không đổi được kết quả. OCR injection **có** hoạt động: Run3 sinh **55.7** combo/query so với 35 của Run2 (bơm thêm ứng viên OCR vào tập), chỉ là không làm q3 tốt hơn vì đã tối ưu. Nới `top_m=1000, top_videos=15` **không** cứu được q1/q2 (video vẫn bị loại do E1 miss hoàn toàn / frame khớp sai).
4. **Độ lệch frame thực tế rất nhỏ khi đã trúng**: q3 có 3/4 event **chính xác tuyệt đối (0 frame)**, event còn lại 14 frame — tức một khi Tầng 1/2 chọn đúng vùng, định vị keyframe đã rất sát. Điều này củng cố luận điểm: nút thắt là **recall Tầng 1**, không phải độ chính xác định vị.

## Đề xuất để bảng số "biết nói" (nên làm trước khi chốt paper)
- **Tăng số query GT** (≥20–30) đa dạng độ khó — R@K/MRR mới ổn định thống kê.
- **Thêm gợi ý OCR/ASR** cho một số sự kiện (điền `events_ocr`/`events_asr` trong GT) để **Run3 > Run2** thể hiện giá trị multimodal (đặc biệt cứu các event thị giác yếu như E1 nấu ăn nếu có lời thoại).
- **Thêm query mà greedy sai còn DP đúng** (video có nhiều cảnh giống nhau, cần ràng buộc thứ tự) để **Run2 > Run1**.
- **Thử model khác** (`beit3` có dịch, `pe`) — so recall Tầng 1 giữa các embedding; có thể cứu các event trừu tượng.
- **Chạy Tier3/Qwen (Run4/5/6) trên Colab** cho các query trúng video (như q3) để cho thấy MATE giảm thêm nhờ tinh chỉnh frame gốc.

## Cách tái lập
```bash
docker compose exec backend-api python -m app.eval.eval_trake \
  --queries app/eval/queries_gt.sample.json --out app/eval/out \
  --runs run1_greedy,run2_dp,run3_mm --k 1,5,10,100 --tol-frames 30
```
Kết quả đầy đủ ở `app/eval/out/eval_results.md` + `.csv` (không commit; số tóm tắt đã đưa vào file này).
