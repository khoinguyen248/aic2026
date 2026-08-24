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

# CPU mặc định; build GPU: --build-arg TORCH_INDEX=.../cu121 --build-arg GPU_EXTRAS="accelerate bitsandbytes"
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG GPU_EXTRAS=

COPY requirements-search.txt .
RUN pip install \
        torch==2.6.0 \
        torchvision==0.21.0 \
        --index-url ${TORCH_INDEX} \
    && pip install -r requirements-search.txt \
    && pip install --no-deps torchscale==0.2.0 \
    && if [ -n "${GPU_EXTRAS}" ]; then pip install ${GPU_EXTRAS}; fi

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
