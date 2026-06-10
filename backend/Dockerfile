# ============================================================
# MEDICAL VEILLE — Dockerfile
# ============================================================
# Multi-stage build : image finale legere sans outils de build
# ============================================================

# ── STAGE 1 : Builder ───────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-warn-script-location \
    -r requirements.txt

# ── STAGE 2 : Image finale ──────────────────────────────────
FROM python:3.11-slim AS final
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les packages installes depuis le builder
COPY --from=builder /install /usr/local

# Copier le code source
COPY ./app ./app

# ── SECURITE : utilisateur non-root ─────────────────────────
RUN useradd --create-home --shell /bin/false appuser && \
    mkdir -p /home/appuser/.cache/huggingface && \
    mkdir -p /home/appuser/.cache/torch && \
    mkdir -p /tmp/hf_cache && \
    chown -R appuser:appuser /home/appuser/.cache && \
    chown -R appuser:appuser /tmp/hf_cache && \
    chmod -R 755 /home/appuser/.cache && \
    chmod -R 777 /tmp/hf_cache

# Variables d'environnement Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/home/appuser/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface \
    TORCH_HOME=/home/appuser/.cache/torch

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "info"]