FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements-core.txt .
RUN python -m pip install --upgrade pip \
    && pip install -r requirements-core.txt

COPY . .


FROM base AS test

COPY requirements-test.txt .
RUN pip install -r requirements-test.txt

CMD ["pytest", "-q"]


FROM base AS production

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "run:app"]