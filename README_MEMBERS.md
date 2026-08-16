# Hướng dẫn setup AIC 2026 - TO BE UPDATED


## 1. Tool

- Git.
- Docker Desktop với Linux containers.
- Node.js 20 nếu chạy frontend ngoài Docker.
- Python 3.11 nếu chạy backend ngoài Docker.

Kiểm tra:

```powershell
git --version
docker version
docker compose version
node --version
py -3.11 --version
```

## 2. Lấy source code

```powershell
git clone https://github.com/khoinguyen248/aic2026.git
cd aic2026
Copy-Item .env.example .env
```

Môi trường local mặc định chưa sử dụng MongoDB và search model:

```env
MONGO_ENABLED=false
SEARCH_ENABLED=false
USER_ROUTES_ENABLED=false
```

Không commit file `.env`.

## 3. Quy trình branch

Cập nhật `main` và tạo branch mới:

```powershell
git checkout main
git pull
git checkout -b feature/ten-tinh-nang
```

Quy ước tên branch:

```text
feature/frame-server
feature/qdrant-ingestion
fix/frontend-image-url
chore/update-dependencies
```

Không push trực tiếp vào `main`.

## 4. Chạy ứng dụng local

```powershell
docker compose up -d --build
docker compose ps
```

Mở frontend:

```text
http://localhost:8088
```

Kiểm tra backend:

```powershell
Invoke-RestMethod http://localhost:8088/api/health/app
```

Dừng môi trường local:

```powershell
docker compose down
```

## 5. Chạy kiểm tra trước khi push

Backend tests:

```powershell
docker build `
  --target test `
  -t aic2026-backend-test `
  ./backendAIC2025

docker run --rm aic2026-backend-test
```

Frontend lint:

```powershell
docker build `
  --target test `
  -t aic2026-frontend-test `
  ./frontend-final/vite-project
```

Kiểm tra Compose:

```powershell
docker compose config --quiet
docker compose up -d --build --wait
```

Chỉ tạo Pull Request khi các kiểm tra đều thành công.

## 6. Commit và Pull Request

```powershell
git status
git add .
git commit -m "Mô tả thay đổi"
git push -u origin feature/ten-tinh-nang
```

Pull Request cần ghi rõ:

- Nội dung thay đổi.
- Cách kiểm tra.
- Env key mới nếu có.
- Ảnh giao diện nếu có thay đổi UI.
- Ảnh hưởng tới API, MongoDB, frames hoặc model.
- Migration dữ liệu nếu có.

## 7. Những file không được commit

- `.env` và `.env.production`.
- API key, PAT, password hoặc database URI.
- Keyframes, video và audio.
- Checkpoint `.pth`, `.pt`, `.ckpt`.
- Embeddings `.npy`.
- Virtual environment và `node_modules`.

Nếu một credential từng xuất hiện trong Git, phải báo maintainer để rotate; chỉ xóa khỏi commit mới là chưa đủ.

