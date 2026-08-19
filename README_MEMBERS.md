# Hướng dẫn dành cho thành viên AIC 2026

Tài liệu này dành cho thành viên phát triển hoặc cần chạy toàn bộ hệ thống trên máy cá nhân. Nếu chỉ sử dụng website do main dev vận hành, đọc `README_USER.md` và mở địa chỉ được cung cấp; không cần cài Docker hay tải model.

## 1. Thành phần hiện tại

Hệ thống chạy bằng Docker Compose gồm:

- Frontend: `http://localhost:8088`.
- Backend API: `http://localhost:5000`.
- Frame server: `http://localhost:8081`.
- Qdrant: lưu collection vector `beit3`, `jina`, `pe`.
- MongoDB Atlas Local: tìm kiếm OCR/ASR.

BEiT-3 text search đã hoạt động ở bước đầu. Jina và PE cần nhiều thời gian/RAM hơn; không nên dùng PE trên máy cấu hình thấp.

## 2. Chuẩn bị

Cài Git và Docker Desktop (Linux containers), sau đó kiểm tra:

```powershell
git --version
docker version
docker compose version
```

Clone source và tạo file môi trường:

```powershell
git clone https://github.com/khoinguyen248/aic2026.git
cd aic2026
Copy-Item .env.example .env
```

Xếp dữ liệu và đặt đúng cấu trúc:

```text
runtime-data/
├── checkpoints/
│   └── beit3_large_patch16_224.pth
├── keyframes/
│   ├── L21_V001/
│   └── ...
├── metadata/
    asr
    ocr
└── qdrant_storage/
    ├── aliases/
    ├── collections/
    │   ├── beit3/
    │   ├── jina/
    │   └── pe/
    └── raft_state.json
```


## 3. Cấu hình `.env`

Tạo secret riêng cho máy và bật các chức năng đã có dữ liệu:

```env
SECRET_KEY=thay-bang-chuoi-ngau-nhien

SEARCH_ENABLED=true
SEARCH_DEVICE=cpu
SEARCH_MODEL_CACHE_SIZE=1
BEIT3_CHECKPOINT_PATH=/models/beit3_large_patch16_224.pth
QDRANT_URL=http://qdrant:6333

MONGO_ROOT_USER=aicadmin
MONGO_ROOT_PASSWORD=thay-bang-password-rieng
MONGO_SEARCH_ENABLED=true
MONGO_SEARCH_URI=mongodb://aicadmin:PASSWORD@mongodb:27017/?authSource=admin&directConnection=true
MONGO_SEARCH_DB=aic2026
```

`MONGO_ROOT_PASSWORD` và password trong `MONGO_SEARCH_URI` phải giống nhau. Không commit `.env`.

Nếu chưa import OCR/ASR, đặt:

```env
MONGO_SEARCH_ENABLED=false
```

## 4. Khởi tạo MongoDB lần đầu

Compose sử dụng ba named volume ngoài. Mỗi máy chỉ cần tạo một lần:

```powershell
docker volume create aic2026_mongodb_data
docker volume create aic2026_mongodb_config
docker volume create aic2026_mongodb_mongot
```

OCR/ASR phải được import bằng package MongoDB riêng do team cung cấp. Không cần import lại sau mỗi lần restart Docker vì dữ liệu nằm trong volume.

## 5. Chạy hệ thống

Tại thư mục gốc dự án:

```powershell
docker compose up -d --build
docker compose ps
```

Kiểm tra:

```powershell
Invoke-RestMethod http://localhost:5000/health/app
Invoke-RestMethod http://localhost:5000/search/health
(Invoke-RestMethod http://localhost:6333/collections).result.collections
```

Mở website:

```text
http://localhost:8088
```

Để kiểm tra bước đầu: chọn Visual Search, chọn `beit3`, nhập mô tả bằng văn bản và tìm kiếm.

## 6. Khi Qdrant hiện `grey`

Storage khôi phục từ ZIP có thể ở trạng thái chờ optimization. Kích hoạt optimizer mà không thay đổi vector:

```powershell
"beit3", "jina", "pe" | ForEach-Object {
    Invoke-RestMethod `
        -Method Patch `
        -Uri "http://localhost:6333/collections/$_" `
        -ContentType "application/json" `
        -Body '{"optimizers_config":{}}'
}
```

Chờ trạng thái `grey -> yellow -> green`. Không restart Qdrant khi đang `yellow`.

Tuyệt đối không chạy lệnh sau trên storage của team:

```powershell
python -m search_engine.search build --model beit3 --recreate
```

`--recreate` sẽ xóa collection hiện tại trước khi tạo lại. `qdrant_storage` của team đã chứa collection hoàn chỉnh nên không cần build lại.

## 7. Dừng và chạy lại

Dừng container nhưng giữ toàn bộ dữ liệu:

```powershell
docker compose down
```

Chạy lại:

```powershell
docker compose up -d
```

Không xóa `runtime-data/qdrant_storage`, không dùng `docker compose down -v` và không xóa Mongo volume nếu chưa có backup.

## 8. Git rules

Cập nhật source và tạo branch riêng:

```powershell
git checkout main
git pull
git checkout -b feature/ten-tinh-nang
```

Trước khi push:

```powershell
docker compose config --quiet
docker compose up -d --build --wait
git status
```

Không push trực tiếp vào `main`. Pull Request cần ghi nội dung thay đổi, cách kiểm tra, biến môi trường mới và ảnh hưởng tới MongoDB, Qdrant, keyframes hoặc model.


