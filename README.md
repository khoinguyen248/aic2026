# AIC 2026

Hệ thống tích hợp gồm frontend, backend API, Qdrant visual search và MongoDB Atlas Local cho OCR/ASR. Toàn bộ dịch vụ được khởi chạy từ **một** file: `compose.yaml` tại thư mục gốc.

## 1. Yêu cầu

- Windows 10/11, Docker Desktop đang chạy và dùng Linux containers.
- Docker Compose v2: `docker compose version`.
- Git chỉ cần khi lấy mã nguồn; Python 3 chỉ cần cho bước ingest MongoDB lần đầu.
- Dữ liệu runtime không được Git quản lý: keyframes, checkpoint, Qdrant storage và video (nếu dùng TRAKE tier 3).

Mở PowerShell tại thư mục gốc:

```powershell
cd "C:\Users\nguye\Downloads\AIC-2025-main\AIC-2025-main"
docker compose version
```

## 2. Chuẩn bị cấu hình một lần

Tạo `.env` từ mẫu nếu chưa có:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Thiết lập tối thiểu trong `.env`:

```dotenv
MONGO_ROOT_USER=aicadmin
MONGO_ROOT_PASSWORD=<mat-khau-local-cua-ban>
MONGO_SEARCH_ENABLED=true
MONGO_SEARCH_DB=aic2026

# Bật sau khi đã đặt đúng checkpoint và Qdrant storage gốc tương thích.
SEARCH_ENABLED=true
BEIT3_CHECKPOINT_PATH=/models/beit3_large_patch16_224.pth
```

Không đặt `MONGO_SEARCH_URI=localhost...`: backend ở trong Docker và Compose tự tạo URI nội bộ tới host `mongodb`.

Đặt các dữ liệu sau đúng vị trí:

```text
runtime-data/
  checkpoints/beit3_large_patch16_224.pth
  keyframes/
  metadata/ocr/                 # JSON theo từng video, ví dụ L21_V001.json
  qdrant_storage/              # storage Qdrant gốc, ví dụ collections/beit3
  videos/                      # tùy chọn, chỉ dùng TRAKE tier 3
```

Không chạy lệnh build lại collection BEiT3 từ các file embedding/metadata không cùng pipeline. Với bộ dữ liệu hiện có, chỉ khôi phục nguyên `runtime-data/qdrant_storage` gốc.

## 3. Khởi chạy toàn bộ hệ thống


```powershell
docker compose -f .\\AIC_DATABASE_MONGODB\\aic_mongodb_local\\docker-compose.yml down
```

Từ đây về sau, chỉ dùng Compose ở thư mục gốc:

```powershell
docker compose up -d --build
docker compose ps
```

Chờ đến khi `backend-api`, `frame-server`, `frontend` có trạng thái `healthy`; MongoDB có thể mất vài phút trong lần đầu vì Atlas Local cần khởi tạo Search engine.

Theo dõi log khi cần:

```powershell
docker compose logs -f mongodb
docker compose logs -f backend-api
docker compose logs -f qdrant
```

Các địa chỉ local:

| Thành phần | Địa chỉ |
| --- | --- |
| Giao diện | `http://localhost:8088` |
| Backend health | `http://localhost:5000/health/app` |
| Qdrant | `http://localhost:6333/dashboard` |
| MongoDB | `mongodb://localhost:27017` |

## 4. Kiểm tra sau khi chạy

```powershell
Invoke-WebRequest http://localhost:5000/health/app
Invoke-WebRequest http://localhost:6333/readyz
Invoke-RestMethod http://localhost:5000/search/health
```

`/health/app` chỉ xác nhận backend hoạt động. `/search/health` phải trả collection Qdrant khi `SEARCH_ENABLED=true`. OCR và ASR vẫn hoạt động độc lập với Qdrant khi `MONGO_SEARCH_ENABLED=true`.

Ví dụ gọi OCR:

```powershell
Invoke-RestMethod -Method Post http://localhost:5000/search/ocr `
  -ContentType "application/json" `
  -Body '{"query":"tin chinh","k":10}'
```

## 5. Ingest MongoDB lần đầu (chỉ khi chưa có dữ liệu)

Không chạy `AIC_DATABASE_MONGODB\aic_mongodb_local\setup_first_time.ps1`, vì script đó có Compose riêng. MongoDB đã do Compose ở thư mục gốc quản lý.

Khi hai ZIP nguồn đã có tại `AIC_DATABASE_MONGODB\aic_mongodb_local\data\raw\metadata_ocr.zip` và `metadata_asr_clean.zip`, chạy:

```powershell
cd "C:\Users\nguye\Downloads\AIC-2025-main\AIC-2025-main\AIC_DATABASE_MONGODB\aic_mongodb_local"
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\00_wait_mongo.py
.\.venv\Scripts\python scripts\01_ingest_metadata.py --ocr data\raw\metadata_ocr.zip --asr data\raw\metadata_asr_clean.zip
.\.venv\Scripts\python scripts\02_create_indexes.py
.\.venv\Scripts\python scripts\03_wait_search_indexes.py
.\.venv\Scripts\python scripts\04_show_stats.py
cd ..\..
```

Lưu ý: `.env` trong `aic_mongodb_local` được các script ingest chạy trên Windows dùng để kết nối `localhost:27017`. Mật khẩu trong file này phải khớp `MONGO_ROOT_PASSWORD` ở `.env` của thư mục gốc.

## 6. Các lần chạy sau

Chỉ cần ở thư mục gốc:

```powershell
docker compose up -d
docker compose ps
```

Không cần ingest lại MongoDB. Dữ liệu MongoDB nằm trong ba Docker named volume `aic2026_mongodb_data`, `aic2026_mongodb_config` và `aic2026_mongodb_mongot`; Qdrant nằm trong `runtime-data/qdrant_storage`.

## 7. Dừng, khởi động lại và xử lý sự cố

Dừng nhưng giữ toàn bộ dữ liệu:

```powershell
docker compose stop
```

Khởi động lại sau khi sửa mã được mount vào backend:

```powershell
docker compose restart backend-api
```

Tạo lại backend sau khi sửa dependency/Dockerfile:

```powershell
docker compose up -d --build --force-recreate backend-api
```

Không dùng `docker compose down -v` trừ khi chủ động muốn xóa toàn bộ named volumes MongoDB. Không xóa `runtime-data/qdrant_storage` trừ khi đã có bộ storage gốc để khôi phục.

Nếu MongoDB chưa `healthy`, xem `docker compose logs -f mongodb`. Nếu Qdrant không có collections, kiểm tra `runtime-data/qdrant_storage/collections/` trước khi chạy lại container; không rebuild BEiT3 từ embedding/metadata không tương thích.
