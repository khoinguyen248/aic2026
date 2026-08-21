#!/usr/bin/env bash
# ============================================================
# setup-linux.sh - Dựng aic2026 trên máy Linux (tùy chọn NVIDIA GPU).
# Chạy được nhiều lần: bước nào đã xong thì bỏ qua.
#   ./setup-linux.sh          # tự dò GPU
#   GPU=0 ./setup-linux.sh    # ép chạy CPU
#   DATA_ROOT=/duong/dan ./setup-linux.sh
# ============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Nơi chứa keyframes/ qdrant_storage/ metadata/ (mặc định: thư mục cha).
DATA_ROOT="${DATA_ROOT:-$(cd .. && pwd)}"
MONGO_USER="${MONGO_USER:-aicadmin}"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m  ok\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m  !!\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mLỖI:\033[0m %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------
info "1/6 Kiểm tra công cụ"
command -v docker >/dev/null || die "Chưa có docker. Cài docker engine + compose plugin trước."
docker compose version >/dev/null 2>&1 || die "Thiếu plugin 'docker compose' (v2+)."
docker info >/dev/null 2>&1 || die "Không nối được docker daemon. Thử: sudo systemctl start docker (và thêm user vào nhóm docker)."
ok "docker $(docker --version | awk '{print $3}' | tr -d ,) / compose $(docker compose version --short)"

GPU="${GPU:-auto}"
if [ "$GPU" = auto ]; then
  if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1 \
     && docker info 2>/dev/null | grep -q ' nvidia'; then GPU=1; else GPU=0; fi
fi
if [ "$GPU" = 1 ]; then
  ok "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"
  BUILD_TARGET=search-cuda; SEARCH_DEVICE=cuda
  COMPOSE_FILES='compose.yaml:compose.gpu.yaml'
else
  warn "Chạy CPU (query jina ~13 phút/lần). Cần GPU: cài nvidia-container-toolkit rồi chạy lại."
  BUILD_TARGET=search; SEARCH_DEVICE=cpu
  COMPOSE_FILES='compose.yaml'
fi

# ------------------------------------------------------------
info "2/6 Liên kết dữ liệu vào runtime-data/ (DATA_ROOT=$DATA_ROOT)"
mkdir -p runtime-data/checkpoints runtime-data/videos
link_data() { # $1 = tên thư mục dữ liệu
  if [ -e "$DATA_ROOT/$1" ]; then
    ln -sfn "$DATA_ROOT/$1" "runtime-data/$1"; ok "runtime-data/$1 -> $DATA_ROOT/$1"
  else
    warn "Không thấy $DATA_ROOT/$1 - bỏ qua"
  fi
}
link_data keyframes
link_data qdrant_storage
link_data metadata
[ -n "$(ls -A runtime-data/checkpoints 2>/dev/null)" ] \
  || warn "runtime-data/checkpoints trống: model beit3 sẽ lỗi 500, dùng model 'jina'."

# ------------------------------------------------------------
info "3/6 Volume MongoDB"
for v in aic2026_mongodb_data_v2 aic2026_mongodb_config_v2 aic2026_mongodb_mongot_v2; do
  if docker volume inspect "$v" >/dev/null 2>&1; then ok "$v đã có"
  else docker volume create "$v" >/dev/null; warn "$v mới tạo - cần ingest lại OCR/ASR"; fi
done

# ------------------------------------------------------------
info "4/6 Vá compose.yaml + Dockerfile (giữ nguyên nếu đã vá)"
# Tag :preview đăng ký search index nhưng không bao giờ initial sync -> index kẹt PENDING.
if grep -q 'mongodb-atlas-local:preview' compose.yaml; then
  sed -i 's#mongodb-atlas-local:preview#mongodb-atlas-local:8.0.25#' compose.yaml
  warn "compose.yaml: đổi mongo :preview -> :8.0.25"
fi
for n in data config mongot; do
  if grep -q "name: aic2026_mongodb_${n}\$" compose.yaml; then
    sed -i "s#name: aic2026_mongodb_${n}\$#name: aic2026_mongodb_${n}_v2#" compose.yaml
    warn "compose.yaml: volume aic2026_mongodb_${n} -> _v2"
  fi
done
grep -q 'AS search-cuda' backendAIC2025/Dockerfile || {
  cat >> backendAIC2025/Dockerfile <<'DOCKERFILE'


FROM base AS search-cuda

# Giống stage `search` nhưng lấy wheel CUDA 12.4 để chạy trên NVIDIA GPU.
COPY requirements-search.txt .
RUN pip install \
        torch==2.6.0 \
        torchvision==0.21.0 \
        --index-url https://download.pytorch.org/whl/cu124 \
    && pip install -r requirements-search.txt \
    && pip install --no-deps torchscale==0.2.0

COPY . .

EXPOSE 5000

# Timeout 900s: lần query đầu phải nạp model lên VRAM.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "900", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
DOCKERFILE
  warn "Dockerfile: thêm stage search-cuda"
}
[ -f compose.gpu.yaml ] || {
  cat > compose.gpu.yaml <<'COMPOSEGPU'
services:
  backend-api:
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: compute,utility

    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities:
                - gpu
COMPOSEGPU
  warn "Tạo compose.gpu.yaml"
}
ok "compose.yaml + Dockerfile đã đúng"

# ------------------------------------------------------------
info "5/6 File .env"
if [ -f .env ]; then
  ok ".env đã có - giữ nguyên (sửa tay nếu cần đổi GPU/CPU)"
else
  MONGO_PASSWORD="${MONGO_PASSWORD:-$(openssl rand -hex 12)}"
  sed -e "s#^SECRET_KEY=.*#SECRET_KEY=$(openssl rand -hex 32)#" \
      -e "s#^SEARCH_ENABLED=.*#SEARCH_ENABLED=true#" \
      -e "s#^BACKEND_BUILD_TARGET=.*#BACKEND_BUILD_TARGET=${BUILD_TARGET}#" \
      -e "s#^SEARCH_DEVICE=.*#SEARCH_DEVICE=${SEARCH_DEVICE}#" \
      -e "s#^MONGO_SEARCH_ENABLED=.*#MONGO_SEARCH_ENABLED=true#" \
      -e "s#^MONGO_ROOT_USER=.*#MONGO_ROOT_USER=${MONGO_USER}#" \
      -e "s#^MONGO_ROOT_PASSWORD=.*#MONGO_ROOT_PASSWORD=${MONGO_PASSWORD}#" \
      -e "s#^MONGO_SEARCH_URI=.*#MONGO_SEARCH_URI=mongodb://${MONGO_USER}:${MONGO_PASSWORD}@mongodb:27017/?authSource=admin\&directConnection=true#" \
      .env.example > .env
  printf '\nCOMPOSE_FILE=%s\n' "$COMPOSE_FILES" >> .env
  chmod 600 .env
  warn ".env vừa tạo mới. Mongo password: ${MONGO_PASSWORD}"
  warn "Nếu volume mongo cũ dùng password khác, sửa lại .env cho khớp."
fi

# ------------------------------------------------------------
info "6/6 Kiểm tra cấu hình"
docker compose config --quiet && ok "docker compose config hợp lệ"

cat <<EOM

Xong phần cấu hình. Bước tiếp theo:

  docker compose up -d --build     # lần đầu (build search-cuda mất ~15-25 phút)
  docker compose ps

Kiểm tra:
  curl -s localhost:5000/health/app
  curl -s localhost:5000/search/health
  curl -s localhost:6333/collections
  xdg-open http://localhost:8088

EOM
