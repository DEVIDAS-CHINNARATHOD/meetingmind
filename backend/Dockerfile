# ── MeetingMind AI — Multi-stage Dockerfile ──────────────────
# Stages:
#   base    → Python + system deps + ffmpeg
#   deps    → pip install
#   api     → FastAPI/Uvicorn server
#   worker  → Celery AI worker

# ── Stage 1: base ─────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies: ffmpeg for audio extraction, libmagic for file validation
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Stage 2: deps ─────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Pre-download embedding model so worker startup is instant
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Stage 3: api ──────────────────────────────────────────────
FROM deps AS api

COPY . .

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/chromadb

EXPOSE 8000

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]

# Production: replace CMD with gunicorn
# CMD ["gunicorn", "main:app", \
#      "--worker-class", "uvicorn.workers.UvicornWorker", \
#      "--workers", "4", \
#      "--bind", "0.0.0.0:8000", \
#      "--timeout", "120", \
#      "--access-logfile", "-"]

# ── Stage 4: worker ───────────────────────────────────────────
FROM deps AS worker

COPY . .

RUN mkdir -p /app/data/uploads /app/data/chromadb

# Note: Only 1 worker concurrency — Whisper is CPU/GPU bound
CMD ["celery", "-A", "workers.celery_app", "worker", \
     "--queues", "ai,reports", \
     "--concurrency", "1", \
     "--loglevel", "info", \
     "--hostname", "worker@%h"]
