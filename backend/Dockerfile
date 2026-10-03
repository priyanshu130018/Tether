# ==============================================================================
# Tether Backend - Production Multi-Stage Dockerfile
# ==============================================================================

# --- Stage 1: Build Dependencies ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: Hardened Runtime Container ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /app

# Create non-root system group and user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source code
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser tests ./tests
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
COPY --chown=appuser:appuser requirements.txt .

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
