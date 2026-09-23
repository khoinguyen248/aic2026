# AIC 2026 — Hướng dẫn chạy MongoDB Local cho OCR & ASR

Tài liệu này hướng dẫn các thành viên trong nhóm chạy MongoDB local đã được chuẩn bị cho hệ thống AIC 2026.

Mục tiêu của package:

- Lưu metadata **OCR** và **ASR** vào MongoDB chạy hoàn toàn trên máy local.
- Search fuzzy OCR/ASR bằng MongoDB Search.
- Database được lưu persistent bằng **Docker named volumes**.
- Sau khi setup lần đầu, **không cần ingest lại dữ liệu**.
- Project khác chỉ cần kết nối tới `localhost:27017` để gọi `search_ocr()` và `search_asr()`.

---

## 1. Cấu trúc thư mục

Sau khi giải nén `MondoDB_Database.zip`:

```text
MondoDB_Database/
├── aic_mongodb_local/
│   ├── data/
│   │   └── raw/
│   │       ├── metadata_ocr.zip
│   │       └── metadata_asr_clean.zip
│   ├── scripts/
│   │   ├── 00_wait_mongo.py
│   │   ├── 01_ingest_metadata.py
│   │   ├── 02_create_indexes.py
│   │   ├── 03_wait_search_indexes.py
│   │   └── 04_show_stats.py
│   ├── src/
│   │   └── mongo_connection.py
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── setup_first_time.ps1
│   ├── start_mongodb.ps1
│   ├── stop_mongodb.ps1
│   ├── search.ps1
│   └── search_metadata.py
│
└── Test/
    ├── mongo_search.py
    └── test.py
```

Hai thư mục có vai trò khác nhau:

- `aic_mongodb_local/`: dùng để **khởi tạo, lưu và chạy MongoDB local**.
- `Test/`: ví dụ một project khác kết nối tới database đã có và gọi hai hàm search.

---

# PHẦN A — SETUP DATABASE LẦN ĐẦU

## 2. Yêu cầu trước khi chạy

Máy Windows cần có:

1. **Docker Desktop**
2. **Python 3**
3. **PowerShell**

Có thể kiểm tra bằng PowerShell:

```powershell
docker --version
docker compose version
python --version
docker info
```

`docker info` phải hiển thị cả phần `Client` và `Server`.

> Nếu chỉ có `Client` hoặc báo không kết nối được Docker engine, hãy mở Docker Desktop và chờ Docker chạy hoàn toàn.

---

## 3. Mở Docker Desktop

Trước khi setup:

1. Mở **Docker Desktop** từ Start Menu.
2. Chờ Docker Desktop hoàn tất khởi động.
3. Không cần tạo container thủ công trên giao diện Docker Desktop.

Script setup sẽ tự tạo MongoDB container và volumes.

---

## 4. Mở PowerShell tại thư mục MongoDB

Ví dụ:

```powershell
cd C:\Users\<USERNAME>\Downloads\MondoDB_Database\aic_mongodb_local
```

Thay `<USERNAME>` bằng user Windows của bạn.

---

## 5. Cho phép chạy PowerShell script trong terminal hiện tại

Chạy:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Lệnh này chỉ áp dụng cho cửa sổ PowerShell hiện tại.

---

## 6. Chạy setup lần đầu

Chạy duy nhất:

```powershell
.\setup_first_time.ps1
```

Script sẽ tự động:

```text
Check Docker Desktop
        ↓
Pull mongodb/mongodb-atlas-local
        ↓
Tạo 3 Docker named volumes
        ↓
Start MongoDB
        ↓
Chờ container HEALTHY
        ↓
Tạo/reuse Python .venv
        ↓
Cài pymongo + python-dotenv
        ↓
Chờ MongoDB writable ổn định
        ↓
Ingest OCR
        ↓
Ingest ASR
        ↓
Tạo MongoDB indexes
        ↓
Tạo ocr_search + asr_search
        ↓
Chờ Search indexes READY
        ↓
SETUP COMPLETE
```

Setup thành công sẽ có kết quả gần giống:

```text
OCR documents: 317,961
OCR non-empty: 194,248
ASR documents: 25,168

OCR: ocr_search status=READY queryable=True
ASR: asr_search status=READY queryable=True

SETUP COMPLETE
```

### Quan trọng

`setup_first_time.ps1` chỉ cần chạy **một lần trên mỗi máy** để xây database ban đầu.

Sau khi đã setup thành công, không cần ingest OCR/ASR lại mỗi lần chạy hệ thống.

---

# PHẦN B — DATABASE ĐƯỢC LƯU Ở ĐÂU?

## 7. MongoDB local sử dụng Docker named volumes

Database không nằm trong một folder Windows như `D:\AIC_DATA`.

Docker Desktop giữ dữ liệu local bằng ba named volumes:

```text
aic2026_mongodb_data
aic2026_mongodb_config
aic2026_mongodb_mongot
```

Ý nghĩa:

- `aic2026_mongodb_data`: MongoDB documents OCR/ASR.
- `aic2026_mongodb_config`: MongoDB config/keyfile.
- `aic2026_mongodb_mongot`: MongoDB Search indexes.

Có thể xem các volumes trong Docker Desktop tại **Volumes**, hoặc bằng:

```powershell
docker volume ls
```

### Tuyệt đối không xóa ba volumes trên nếu muốn giữ database.

Đặc biệt **không chạy**:

```powershell
docker compose down -v
```

`-v` sẽ xóa volumes và làm mất database đã ingest.

---

# PHẦN C — START / STOP MONGODB SAU KHI ĐÃ SETUP

## 8. Start bằng Docker Desktop GUI

Sau khi restart Windows hoặc Docker Desktop:

1. Mở **Docker Desktop**.
2. Vào tab **Containers**.
3. Tìm container/group có `aic2026-mongodb`.
4. Nhấn nút **Start**.
5. Chờ container chạy ổn định.

Sau đó có thể chạy project search bình thường.

### Hoặc start bằng PowerShell

Trong `aic_mongodb_local/`:

```powershell
.\start_mongodb.ps1
```

Script sẽ chờ MongoDB healthy và writable trước khi kết thúc.

---

## 9. Stop bằng Docker Desktop GUI

1. Mở **Docker Desktop**.
2. Vào **Containers**.
3. Chọn `aic2026-mongodb`.
4. Nhấn **Stop**.

Stop container **không làm mất dữ liệu**.

### Hoặc stop bằng PowerShell

```powershell
.\stop_mongodb.ps1
```

---

## 10. Sau khi restart máy có cần setup lại không?

**Không.**

Quy trình sau khi database đã được tạo là:

```text
Mở Docker Desktop
      ↓
Start aic2026-mongodb
      ↓
Chờ MongoDB chạy
      ↓
Chạy project/search
```

Không chạy lại `setup_first_time.ps1` trừ khi muốn rebuild database từ đầu.

---

# PHẦN D — TEST OCR + ASR SEARCH

## 11. Test trực tiếp bằng script có sẵn trong `aic_mongodb_local`

Khi MongoDB đang chạy, tại thư mục:

```text
aic_mongodb_local/
```

search cả OCR và ASR:

```powershell
.\search.ps1 "Cơm Tấm"
```

Mặc định tương đương:

```powershell
.\search.ps1 "Cơm Tấm" -Mode both -Limit 10 -MaxEdits 1 -PrefixLength 1
```

### Search chỉ OCR

```powershell
.\search.ps1 "Cơm Tấm" -Mode ocr
```

### Search chỉ ASR

```powershell
.\search.ps1 "Cơm Tấm" -Mode asr
```

### Lấy top 20 mỗi branch

```powershell
.\search.ps1 "Cơm Tấm" -Mode both -Limit 20
```

### Fuzzy rộng hơn

```powershell
.\search.ps1 "Cơm Tám" -Mode both -MaxEdits 2
```

### Ý nghĩa arguments

| Argument | Mặc định | Ý nghĩa |
|---|---:|---|
| `Query` | bắt buộc | Text cần search |
| `-Mode` | `both` | `both`, `ocr` hoặc `asr` |
| `-Limit` | `10` | Số kết quả tối đa cho mỗi branch |
| `-MaxEdits` | `1` | Số edit fuzzy cho phép, `1` hoặc `2` |
| `-PrefixLength` | `1` | Số ký tự đầu phải match chính xác |

---

# PHẦN E — TEST TỪ MỘT PROJECT KHÁC

Thư mục `Test/` mô phỏng cách pipeline AIC chính kết nối tới MongoDB local đã lưu.

## 12. Vào thư mục Test

```powershell
cd C:\Users\<USERNAME>\Downloads\MondoDB_Database\Test
```

> Không nên dùng lại `.venv` được copy từ máy khác. Mỗi máy nên tự tạo virtual environment riêng.

Nếu có `.venv` cũ được đóng gói trong ZIP, có thể xóa:

```powershell
Remove-Item -Recurse -Force .venv
```

Tạo môi trường mới:

```powershell
python -m venv .venv
```

Activate:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

Cài PyMongo:

```powershell
pip install pymongo
```

---

## 13. Test kết nối tới MongoDB

Khi `aic2026-mongodb` đang chạy:

```powershell
python -c "from mongo_search import client; print(client.admin.command('ping'))"
```

Nếu kết nối thành công:

```text
{'ok': 1.0}
```

MongoDB endpoint đang dùng:

```text
mongodb://localhost:27017
```

Database:

```text
aic2026
```

Collections:

```text
ocr_metadata
asr_metadata
```

Search indexes:

```text
ocr_search
asr_search
```

---

## 14. Test cả OCR và ASR từ `Test/test.py`

File hiện tại có dạng:

```python
from mongo_search import search_ocr, search_asr

query = "Cơm Tấm"

ocr_results = search_ocr(query=query, limit=10)
asr_results = search_asr(query=query, limit=10)

print("OCR RESULTS")
for result in ocr_results:
    print(result)

print("\nASR RESULTS")
for result in asr_results:
    print(result)
```

Chạy:

```powershell
python test.py
```

Muốn test query khác, chỉ cần sửa:

```python
query = "Cơm Tấm"
```

thành ví dụ:

```python
query = "Bệnh viện Lê Văn Thịnh"
```

rồi chạy lại:

```powershell
python test.py
```

---

# PHẦN F — DÙNG TRONG PIPELINE AIC CHÍNH

## 15. File cần copy sang project chính

Chỉ cần copy:

```text
Test/mongo_search.py
```

sang project AIC chính.

Project chính cần cài:

```powershell
pip install pymongo
```

MongoDB container `aic2026-mongodb` phải đang chạy.

---

## 16. Kết nối database

`mongo_search.py` kết nối qua:

```python
MONGO_URI = (
    "mongodb://aicadmin:aic2026_local_password"
    "@localhost:27017/"
    "?authSource=admin&directConnection=true"
)
```

Project **không cần biết Docker lưu volume vật lý ở đâu**.

Chỉ cần endpoint:

```text
localhost:27017
```

---

## 17. Gọi OCR search

```python
from mongo_search import search_ocr

ocr_hits = search_ocr(
    query="Cơm Tấm",
    limit=50,
)
```

Các field quan trọng trong kết quả OCR:

```python
hit["video_id"]
hit["frame_id"]
hit["ocr_text"]
hit["score"]
```

---

## 18. Gọi ASR search

```python
from mongo_search import search_asr

asr_hits = search_asr(
    query="Cơm Tấm",
    limit=50,
)
```

Các field quan trọng trong kết quả ASR:

```python
hit["video_id"]
hit["frame_start"]
hit["frame_end"]
hit["frame_mid"]
hit["text"]
hit["score"]
```

Lưu ý: ASR đại diện cho **một đoạn thời gian/frame range**, không phải một frame duy nhất.

---

## 19. Gọi cả hai trong pipeline

```python
from mongo_search import search_ocr, search_asr

query = "Cơm Tấm"

ocr_hits = search_ocr(query, limit=50)
asr_hits = search_asr(query, limit=50)
```

Sau đó pipeline chính có thể kết hợp hai ranking này với kết quả Qdrant/visual retrieval.

---

# PHẦN G — TEST LOCAL/OFFLINE TRƯỚC KHI THI

## 20. Kiểm tra MongoDB không phụ thuộc Internet

Sau khi setup đã hoàn tất:

1. Start `aic2026-mongodb` khi máy vẫn có mạng.
2. Chờ container chạy ổn định.
3. Tắt Wi-Fi.
4. Chạy:

```powershell
python test.py
```

hoặc:

```powershell
.\search.ps1 "Cơm Tấm"
```

Nếu OCR/ASR vẫn trả kết quả thì MongoDB Search đang hoạt động hoàn toàn local.

MongoDB runtime search không cần Internet. Internet chỉ cần cho những việc như tải Docker image hoặc cài Python package lần đầu nếu máy chưa có sẵn.

---

# PHẦN H — QUICK START CHO THÀNH VIÊN NHÓM

## Lần đầu trên một máy mới

```text
1. Cài Docker Desktop + Python 3
2. Mở Docker Desktop
3. Giải nén package
4. Vào aic_mongodb_local/
5. Set-ExecutionPolicy -Scope Process Bypass
6. .\setup_first_time.ps1
7. Chờ SETUP COMPLETE
8. Test: .\search.ps1 "Cơm Tấm"
```

## Những lần sau

```text
1. Mở Docker Desktop
2. Start aic2026-mongodb trong Docker Desktop
   hoặc chạy .\start_mongodb.ps1
3. Chạy project/search
4. Khi xong có thể Stop container
```

## Để dùng trong project chính

```text
1. Copy Test/mongo_search.py
2. pip install pymongo
3. Đảm bảo aic2026-mongodb đang chạy
4. Import:
   from mongo_search import search_ocr, search_asr
5. Gọi:
   ocr_hits = search_ocr(query)
   asr_hits = search_asr(query)
```

---

# Cảnh báo cuối cùng

### Có thể làm

- Stop container.
- Start container.
- Restart Docker Desktop.
- Restart Windows.
- `docker compose down` nếu cần.

Database vẫn được giữ trong named volumes.

### Không được làm nếu muốn giữ database

```powershell
docker compose down -v
```

Không xóa thủ công các volume:

```text
aic2026_mongodb_data
aic2026_mongodb_config
aic2026_mongodb_mongot
```

Nếu xóa chúng, OCR/ASR database và MongoDB Search indexes sẽ phải setup/ingest lại từ đầu.
