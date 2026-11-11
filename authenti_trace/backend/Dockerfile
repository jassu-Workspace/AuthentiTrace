# API and Celery worker image. The command decides which one runs (see docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# libglib is needed by OpenCV at import time even in the headless build
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Postgres driver included; add requirements-ml.txt / requirements-s3.txt here if you use those features
COPY requirements.txt requirements-postgres.txt ./
RUN pip install -r requirements-postgres.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Run as a normal user. /data holds media, the SQLite file (if used) and the ledger anchor file.
RUN useradd --create-home app && mkdir -p /data && chown -R app /data /app
USER app
ENV STORAGE_DIR=/data/storage LEDGER_ANCHOR_PATH=/data/ledger_anchor.jsonl

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"

# --proxy-headers: trust X-Forwarded-For from the reverse proxy in front (set FORWARDED_ALLOW_IPS to its address)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
