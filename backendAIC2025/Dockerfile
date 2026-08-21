FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements-core.txt .
RUN python -m pip install --upgrade pip \
    && pip install -r requirements-core.txt


FROM base AS test

COPY requirements-test.txt .
RUN pip install -r requirements-test.txt
COPY . .

CMD ["pytest", "-q"]


FROM base AS production

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "run:app"]


FROM base AS search

COPY requirements-search.txt .
RUN pip install \
        torch==2.6.0 \
        torchvision==0.21.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements-search.txt \
    && pip install --no-deps torchscale==0.2.0

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "run:app"]


FROM base AS search-cuda

# Giống stage `search` nhưng lấy wheel CUDA 12.4 để chạy trên NVIDIA GPU.
# Ảnh nền python:3.11-slim là đủ: wheel cu124 đã kèm CUDA runtime, driver do
# nvidia-container-toolkit inject vào container.
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
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "900", "--access-logfile", "-", "--access-logformat", "%(h)s \"%(r)s\" %(s)s %(b)sB %(L)ss", "--error-logfile", "-", "run:app"]
