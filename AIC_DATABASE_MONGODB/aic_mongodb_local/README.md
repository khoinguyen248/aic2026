# AIC 2026 — Local MongoDB OCR/ASR Search (Windows, Named Volumes)

Package này dành cho **Windows + Docker Desktop + PowerShell**.

Mục tiêu:

1. Chạy `setup_first_time.ps1` **một lần**.
2. OCR + ASR được ingest vào MongoDB local.
3. Database và MongoDB Search indexes được giữ persistent bằng **Docker named volumes**.
4. Những lần sau chỉ chạy `start_mongodb.ps1` rồi search, **không ingest lại**.

## Vì sao dùng Docker named volumes?

`mongodb/mongodb-atlas-local` cần ghi keyfile Unix vào `/data/configdb`. Bind mount trực tiếp từ `D:\...` trên Windows có thể gây lỗi `permission denied` với keyfile. Named volumes tránh vấn đề permission này và vẫn lưu dữ liệu local/persistent trên máy qua Docker Desktop.

Package sử dụng ba volume có tên cố định:

```text
aic2026_mongodb_data
aic2026_mongodb_config
aic2026_mongodb_mongot
```

- `aic2026_mongodb_data` → MongoDB documents
- `aic2026_mongodb_config` → MongoDB config/keyfile
- `aic2026_mongodb_mongot` → MongoDB Search (`mongot`) data/indexes

## Cấu trúc

```text
aic_mongodb_local_windows_named_volumes/
├── data/
│   └── raw/
│       ├── metadata_ocr.zip
│       └── metadata_asr_clean.zip
├── scripts/
│   ├── 00_wait_mongo.py
│   ├── 01_ingest_metadata.py
│   ├── 02_create_indexes.py
│   ├── 03_wait_search_indexes.py
│   └── 04_show_stats.py
├── src/
│   ├── __init__.py
│   └── mongo_connection.py
├── .env
├── .env.example
├── docker-compose.yml
├── requirements.txt
├── search_metadata.py
├── search.ps1
├── setup_first_time.ps1
├── setup_first_time.bat
├── start_mongodb.ps1
├── start_mongodb.bat
├── stop_mongodb.ps1
└── stop_mongodb.bat
```

## Yêu cầu

Mở Docker Desktop trước. Kiểm tra trong PowerShell:

```powershell
docker --version
docker compose version
python --version
docker info
```

`docker info` phải có phần `Server:`.

## Lần đầu: chạy một lệnh

Trong PowerShell tại thư mục package:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_first_time.ps1
```

Script tự thực hiện:

```text
Check Docker
    ↓
Create/reuse Docker named volumes
    ↓
Pull + start mongodb/mongodb-atlas-local:preview
    ↓
Wait container HEALTHY
    ↓
Create/reuse .venv
    ↓
Install pymongo + python-dotenv
    ↓
Wait MongoDB writable-primary ổn định
    ↓
Ingest OCR + ASR (upsert + transient retry)
    ↓
Create normal indexes
    ↓
Create ocr_search + asr_search
    ↓
Wait Search indexes READY/queryable
    ↓
Print stats
    ↓
SETUP COMPLETE
```

Nếu một bước lỗi, script dừng ngay và không in `SETUP COMPLETE` giả.

## Kiểm tra volumes

Sau khi setup bắt đầu hoặc hoàn tất:

```powershell
docker volume ls
```

Bạn sẽ thấy:

```text
aic2026_mongodb_data
aic2026_mongodb_config
aic2026_mongodb_mongot
```

## Search

OCR + ASR:

```powershell
.\search.ps1 "Bệnh viện Lê Văn Thịnh"
```

Chỉ OCR:

```powershell
.\search.ps1 "Herbalife" -Mode ocr -Limit 20
```

Chỉ ASR:

```powershell
.\search.ps1 "bệnh viện Lê Văn Thịnh" -Mode asr -Limit 20
```

Fuzzy rộng hơn:

```powershell
.\search.ps1 "Herbalifer" -Mode ocr -MaxEdits 2 -PrefixLength 1
```

## Sau khi restart Windows

Bật Docker Desktop, sau đó:

```powershell
.\start_mongodb.ps1
```

Rồi search:

```powershell
.\search.ps1 "query"
```

**Không chạy ingest lại.**

## Tắt MongoDB

```powershell
.\stop_mongodb.ps1
```

Hoặc `docker compose stop`. Dữ liệu trong named volumes vẫn còn.

Bạn cũng có thể dùng:

```powershell
docker compose down
```

Container/network sẽ bị xóa nhưng named volumes vẫn còn và được reuse lần sau.

### Cảnh báo quan trọng

Không dùng lệnh sau nếu muốn giữ database:

```powershell
docker compose down -v
```

`-v` sẽ xóa named volumes, đồng nghĩa xóa MongoDB đã ingest.

## Kết nối từ project AIC khác

Project khác không cần biết nơi Docker Desktop lưu volume vật lý. Chỉ cần MongoDB endpoint:

```text
mongodb://localhost:27017
```

Với credentials mặc định:

```text
mongodb://aicadmin:aic2026_local_password@localhost:27017/?authSource=admin&directConnection=true
```

Database:

```text
aic2026
├── ocr_metadata
└── asr_metadata
```

Hai hàm fuzzy search mẫu nằm trong `search_metadata.py`:

- `search_ocr(...)`
- `search_asr(...)`

## Nếu muốn reset hoàn toàn database

Chỉ làm khi bạn thật sự muốn ingest lại từ đầu:

```powershell
docker compose down

docker volume rm aic2026_mongodb_data
docker volume rm aic2026_mongodb_config
docker volume rm aic2026_mongodb_mongot
```

Sau đó chạy lại:

```powershell
.\setup_first_time.ps1
```
