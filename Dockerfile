# ====================== UI-Pro Backend ======================
# Multi-stage Docker build for the FastAPI backend

# ---- Stage 1: Base ----
FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies for ML packages (torch, faiss, sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ---- Stage 2: Dependencies ----
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir faiss-cpu

# ---- Stage 3: Runtime ----
FROM base AS runtime

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ ./backend/
COPY models/ ./models/
# Copy config template (user should mount their own config.yaml at runtime)
COPY config.yaml.example ./config.yaml

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    API_PORT=8000

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "backend.transport.main:app", "--host", "0.0.0.0", "--port", "8000"]
