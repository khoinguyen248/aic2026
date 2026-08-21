# Chạy AIC 2026 trên Linux (bản GPU)

Tài liệu này thay cho `README_MEMBERS.md` (viết cho Windows/PowerShell). Áp dụng cho máy
Ubuntu/Debian có Docker Engine; phần GPU dành cho máy có card NVIDIA.

Máy tham chiếu: Ubuntu, kernel 6.8, RTX 4060 Laptop 8GB, driver 580.x.

## 1. Yêu cầu

```bash
docker --version && docker compose version && docker info | grep -i 'Server Version'
```

Nếu chưa có Docker Engine (không cần Docker Desktop trên Linux):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # đăng xuất/đăng nhập lại để có hiệu lực
```

Máy có GPU NVIDIA thì cài thêm nvidia-container-toolkit:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
```

Kiểm tra:

```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu20.04 nvidia-smi
```

## 2. Bố trí dữ liệu

Dữ liệu nặng (17GB keyframes + 5GB qdrant) để **ngoài** repo, `runtime-data/` chỉ là symlink trỏ tới.
Mặc định script lấy thư mục cha của repo làm `DATA_ROOT`:

```text
AIC-2026/                     <- DATA_ROOT
├── keyframes/                <- 873 thư mục L21_V001/ ...
├── metadata/
├── qdrant_storage/           <- collections beit3, jina, pe
└── aic2026/                  <- repo này
    └── runtime-data/
        ├── keyframes       -> ../../keyframes
        ├── qdrant_storage  -> ../../qdrant_storage
        ├── metadata        -> ../../metadata
        ├── checkpoints/      (đặt beit3_*.pth vào đây nếu có)
        └── videos/           (trống, chỉ cần cho TRAKE tier-3)
```

OCR/ASR nằm trong Docker volume `aic2026_mongodb_data_v2`, không phải trong repo.

## 3. Setup

```bash
./setup-linux.sh
```

Script chạy lại được nhiều lần, và tự làm các việc sau:

1. Kiểm tra docker / compose / GPU.
2. Tạo symlink `runtime-data/*` từ `DATA_ROOT`.
3. Tạo volume `aic2026_mongodb_{data,config,mongot}_v2` nếu chưa có.
4. Vá `compose.yaml` (mongo `:8.0.25`, volume `_v2`) và thêm stage `search-cuda` vào `backendAIC2025/Dockerfile` nếu bị mất.
5. Sinh `.env` (chỉ khi chưa có) với `BACKEND_BUILD_TARGET=search-cuda`, `SEARCH_DEVICE=cuda`, `COMPOSE_FILE=compose.yaml:compose.gpu.yaml`.
6. Chạy `docker compose config` để xác thực.

Biến tùy chọn:

```bash
GPU=0 ./setup-linux.sh                  # ép chạy CPU (target search, device cpu)
DATA_ROOT=/mnt/ssd/aic ./setup-linux.sh # dữ liệu nằm chỗ khác
```

## 4. Chạy hệ thống

```bash
docker compose up -d --build   # lần đầu: build search-cuda ~15-25 phút, ảnh ~9.8GB
docker compose ps
```

Các lần sau không cần `--build`.

| Dịch vụ | Địa chỉ |
|---|---|
| Frontend | http://localhost:8088 |
| Backend API | http://localhost:5000 |
| Frame server | http://localhost:8081 |
| Qdrant | http://localhost:6333 |
| MongoDB | mongodb://localhost:27017 |

## 5. Kiểm tra

```bash
curl -s localhost:5000/health/app
curl -s localhost:5000/search/health
curl -s localhost:6333/collections
curl -s -o /dev/null -w '%{http_code}\n' localhost:8081/Keyframes/L21_V001/000000.webp

# GPU có vào tới container không
docker exec aic2026-backend-api-1 python -c "import torch;print(torch.__version__, torch.cuda.is_available())"

# Visual search (lần đầu ~20s vì nạp model lên VRAM, sau đó <0.1s)
time curl -s -X POST localhost:5000/search/collection \
  -H 'Content-Type: application/json' \
  -d '{"query":"a man riding a motorbike","model":"jina","top_k":3}'

# OCR / ASR
curl -s -X POST localhost:5000/search/ocr -H 'Content-Type: application/json' -d '{"query":"thời sự","top_k":2}'
curl -s -X POST localhost:5000/search/asr -H 'Content-Type: application/json' -d '{"query":"kinh tế","top_k":2}'

# Số document OCR/ASR (kỳ vọng 317961 / 25168)
docker exec aic2026-mongodb-1 mongosh -u aicadmin -p "$(grep ^MONGO_ROOT_PASSWORD .env | cut -d= -f2)" \
  --authenticationDatabase admin --quiet \
  --eval 'db=db.getSiblingDB("aic2026");db.getCollectionNames().forEach(c=>print(c,db[c].countDocuments()))'
```

## 6. Giới hạn cần biết

- **Chỉ dùng model `jina`.** `beit3` cần file checkpoint `.pth` (chưa có trong `runtime-data/checkpoints` → lỗi 500). `pe` là PE-Core-bigG-14-448 (~2,5 tỉ tham số), không vừa 8GB VRAM.
- `SEARCH_MODEL_CACHE_SIZE=1`: đổi qua lại giữa các model sẽ evict và nạp lại rất tốn thời gian.
- CPU vs GPU cho cùng một query jina: **13 phút 32 giây** so với **~20 giây (lần đầu) / 0,07 giây (các lần sau)**.
- Muốn bật Visual Search phải có **cả hai**: `SEARCH_ENABLED=true` và build target chứa torch (`search` hoặc `search-cuda`). Target `production` chỉ cài `requirements-core.txt` nên thiếu numpy.
- MongoDB phải là tag **`8.0.25`**, không dùng `:preview` — bản preview đăng ký search index nhưng không bao giờ chạy initial sync, index kẹt vĩnh viễn ở `status=PENDING`.

## 7. Vận hành hằng ngày

```bash
docker compose down     # dừng, giữ nguyên dữ liệu
docker compose up -d    # chạy lại
docker compose logs -f backend-api
```

Không dùng `docker compose down -v` (xóa volume Mongo) và không xóa `qdrant_storage`.

## 8. Sự cố thường gặp

| Triệu chứng | Xử lý |
|---|---|
| `permission denied` khi gọi docker | `sudo usermod -aG docker "$USER"` rồi đăng nhập lại |
| `could not select device driver "nvidia"` | Chưa cài/chưa cấu hình nvidia-container-toolkit, xem mục 1 |
| `torch.cuda.is_available()` = False | Ảnh build bằng target `search` (CPU). Đặt `BACKEND_BUILD_TARGET=search-cuda` rồi `docker compose up -d --build backend-api` |
| Mất `.env`, `compose.gpu.yaml`, `runtime-data/` sau khi đổi branch hoặc `git clean` | Chạy lại `./setup-linux.sh` |
| Qdrant collection màu `grey` | `curl -X PATCH localhost:6333/collections/jina -H 'Content-Type: application/json' -d '{"optimizers_config":{}}'` rồi chờ `green`, đừng restart khi đang `yellow` |
| Mongo search index kẹt `PENDING` | Kiểm tra dung lượng volume mongot: `docker system df -v \| grep mongot` (index thật ~42MB; ~1MB là rỗng). Đừng đo bằng `du` trong `/data/mongot` vì `diagnostic.data` tăng liên tục gây hiểu nhầm |
| Query đầu tiên timeout | Stage `search-cuda` đã đặt gunicorn `--timeout 900`; nếu vẫn timeout, kiểm tra VRAM trống bằng `nvidia-smi` |
| Port 5000/8088/27017 bị chiếm | Đổi `BACKEND_PORT`, `FRONTEND_PORT`, `MONGO_PORT` trong `.env` |

## 9. File cấu hình riêng cho Linux

| File | Trạng thái git | Vai trò |
|---|---|---|
| `setup-linux.sh` | mới, nên commit | Dựng lại toàn bộ cấu hình |
| `compose.gpu.yaml` | mới, nên commit | Cấp GPU cho `backend-api` |
| `backendAIC2025/Dockerfile` | đã sửa (thêm stage `search-cuda`) | Build torch cu124 |
| `compose.yaml` | đã sửa (mongo `8.0.25` + volume `_v2`) | Sửa lỗi search index |
| `.env` | bị `.gitignore`, không commit | Cấu hình máy cá nhân |
| `runtime-data/` | bị `.gitignore` | Symlink tới dữ liệu |
