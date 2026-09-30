# Chạy eval TRAKE Tier3 + Qwen (Run 4/5/6) trên Google Colab (GPU)

Colab có GPU (thường T4 16GB) đủ chạy **Tier3 + Qwen2‑VL‑2B**. Để test 3 tầng bạn **không cần Mongo/Atlas, không cần UI** — chỉ cần:

- **Qdrant (collection `jina`)** đã restore từ file payload của bạn.
- **File video gốc** của các `video_id` dùng làm GT (đặt tên `<video_id>.mp4`).
- **GT visual‑only** (không dùng `events_ocr/asr`) → bỏ qua hoàn toàn Mongo.

> Vì sao bỏ được Mongo: OCR/ASR (Run3, hybrid) mới cần Atlas Search. Tier1/Tier2/Tier3 + Qwen chỉ dùng **Qdrant + model embedding + video gốc**. Các helper OCR/ASR nếu vắng Mongo sẽ tự bắt lỗi và bỏ qua. ⇒ Muốn số **Run3/multimodal + hybrid**, chạy trên **máy Docker local** (đã có `mongodb-atlas-local`). Muốn số **Run4/5/6 (Tier3+Qwen GPU)**, chạy Colab theo file này.

Chọn 1 video test trong **L25 / L26 / M02** là ổn (miễn nó có trong index `jina` và bạn có file mp4 gốc của nó).

---

## Cell 1 — Bật GPU + kiểm tra
> Runtime → Change runtime type → **T4 GPU**.
```python
!nvidia-smi --query-gpu=name,memory.total --format=csv
import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())
```
Phải thấy `cuda True`. (Colab đã cài sẵn torch CUDA — KHÔNG cài lại torch.)

## Cell 2 — Lấy code
```bash
%cd /content
!git clone https://github.com/khoinguyen248/aic2026.git
%cd /content/aic2026
!git checkout feature/overral-trake-huy
```

## Cell 3 — Cài phụ thuộc (giữ nguyên torch CUDA của Colab)
```bash
%cd /content/aic2026/backendAIC2025
# core + search, BỎ torch/torchvision (đã có sẵn CUDA trên Colab)
!pip -q install flask==3.0.3 python-dotenv==1.0.1 numpy==1.26.4 scipy==1.15.1 \
  Pillow==11.3.0 einops==0.8.1 timm==0.4.12 opencv-python-headless \
  sentencepiece==0.2.1 transformers==4.55.1 open-clip-torch==2.32.0 torchscale==0.2.0 \
  protobuf==3.20.3 ftfy==6.3.1 qdrant-client==1.15.1 pymongo==4.14.0 deep-translator \
  accelerate bitsandbytes qwen-vl-utils
```

## Cell 4 — Qdrant server + restore dữ liệu `jina`
Tải binary Qdrant (khớp version đã tạo data — sửa `QV` nếu cần) và chạy nền:
```bash
%cd /content
QV=1.15.1   # dùng cùng dòng version với data payload của bạn
!wget -q https://github.com/qdrant/qdrant/releases/download/v$QV/qdrant-x86_64-unknown-linux-musl.tar.gz -O qdrant.tar.gz
!tar xzf qdrant.tar.gz
```
Có 2 trường hợp — xem file zip payload của bạn chứa gì:

**A. Nếu zip là thư mục `storage/` (đủ collections):**
```bash
# giải nén sao cho có /content/qdrant_storage/collections/jina/...
!mkdir -p /content/qdrant_storage && unzip -q /content/YOUR_PAYLOAD.zip -d /content/qdrant_storage
import subprocess, os
os.environ["QDRANT__STORAGE__STORAGE_PATH"] = "/content/qdrant_storage"
subprocess.Popen(["/content/qdrant"])   # chạy nền, cổng 6333
```

**B. Nếu zip là file snapshot `*.snapshot` của collection:**
```bash
import subprocess, time
subprocess.Popen(["/content/qdrant"]); time.sleep(8)
from qdrant_client import QdrantClient
c = QdrantClient(url="http://localhost:6333", check_compatibility=False)
c.recover_snapshot(collection_name="jina", location="file:///content/YOUR_jina.snapshot")
```
Kiểm tra:
```python
import time; time.sleep(6)
from qdrant_client import QdrantClient
c = QdrantClient(url="http://localhost:6333", check_compatibility=False)
print([x.name for x in c.get_collections().collections])
print("jina points:", c.count("jina"))
```
Phải thấy collection `jina` và số point > 0.

## Cell 5 — Tải video gốc của video_id làm GT
Đặt tên đúng `<video_id>.mp4` (resolver luôn thử `VIDEO_ROOT/<video_id>.mp4`):
```bash
!mkdir -p /content/videos
# ví dụ chọn L25_V025 — thay link wget của bạn:
!wget -q "PUT_YOUR_VIDEO_URL_HERE" -O /content/videos/L25_V025.mp4
!ls -lh /content/videos
```
(Không cần keyframes cho Run4/5/6 vì Tier3 decode thẳng từ video.)

## Cell 6 — Tạo GT visual‑only (1 video, 2–3 sự kiện)
Xem video, chọn mốc sự kiện, đọc `frame_id` (số thứ tự khung hình gốc). `fps` = fps thật của video.
```python
import json
gt = [{
  "id": "L25_V025_test",
  "events": [
    "sự kiện 1 mô tả hình",
    "sự kiện 2 mô tả hình",
    "sự kiện 3 mô tả hình"
  ],
  "language": True,          # dịch vi->en; jina đa ngữ có thể để False
  "model": "jina",
  "max_event_gap_s": None,
  "gt": {"video_id": "L25_V025", "frame_ids": [111, 222, 333], "fps": 25}
}]
import os; os.makedirs("/content/aic2026/backendAIC2025/app/eval/out", exist_ok=True)
json.dump(gt, open("/content/aic2026/backendAIC2025/app/eval/queries_gt.json","w"), ensure_ascii=False, indent=2)
print("saved GT")
```

## Cell 7 — Chạy harness Run 2/4/5/6 (Qwen bật, có GPU)
```bash
%cd /content/aic2026/backendAIC2025
%env QDRANT_URL=http://localhost:6333
%env SEARCH_DEVICE=cuda
%env VIDEO_ROOT=/content/videos
%env TRAKE_TIER3_ENABLED=true
%env TRAKE_QWEN_RERANK_ENABLED=true
%env QWEN_MODEL_PATH=Qwen/Qwen2-VL-2B-Instruct
%env QWEN_QUANTIZATION=4bit
%env QWEN_DEVICE_MAP=cuda
!python -m app.eval.eval_trake --queries app/eval/queries_gt.json \
   --out app/eval/out --runs run2_dp,run4_tier3_argmax,run5_tier3_peak,run6_full \
   --k 1,5,10,100 --tol-frames 25
```
Xem kết quả:
```python
print(open("/content/aic2026/backendAIC2025/app/eval/out/eval_results.md", encoding="utf-8").read())
```

Harness sẽ in `tier3_globally_ready=True` (có video) và `qwen_globally_ready=True` (có CUDA). Nếu Qwen OOM (T4 16GB thường không, nhưng nếu dùng 7B), đổi `QWEN_MODEL_PATH=Qwen/Qwen2-VL-2B-Instruct` (2B, nhẹ).

---

## Lưu ý khi ghép số vào paper
- **Latency là số của phần cứng Colab (T4)** — nếu bảng latency gộp cả Run1–3 (chạy máy local CPU) thì phải ghi rõ **hardware từng run**, hoặc chạy lại Run2 trên cả 2 máy để có mốc quy đổi.
- **Run3/multimodal + OCR/ASR‑hybrid** cần Atlas Search → chạy trên **máy Docker local** (có `mongodb-atlas-local`), không chạy Colab. Tách 2 bảng: (i) accuracy multimodal (local), (ii) Tier3/Qwen (Colab).
- **Qwen chỉ nạp khi có CUDA** (đã chốt cứng trong `trake_service._load_qwen`) → trên Colab GPU nó chạy; trên máy CPU nó tự tắt, không treo.
- **Kendall τ/Spearman ρ ≈ 1** do DP ép đơn điệu — dùng để xác nhận trật tự, không phải chỉ số phân biệt.
- Chọn video test có trong index `jina`; nếu Tầng 1 không trả đúng video (VideoHit=0), tăng `--k`/`TRAKE_TOP_M` hoặc chọn sự kiện mô tả rõ hơn.
```bash
# ví dụ nới top_m nếu cần
%env TRAKE_TOP_M=400
```
