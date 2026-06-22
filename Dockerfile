# syntax=docker/dockerfile:1

# ---- builder: install deps into an isolated venv ----
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

# ---- runtime: slim image, non-root, healthchecked ----
FROM python:3.12-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000
WORKDIR /app

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 appuser

# Copy only what the service needs at runtime (no tests, docs, or dev deps).
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY data ./data
COPY static ./static

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/health')" || exit 1

# exec form via sh so $PORT (injected by the host) is honored, and `exec` makes
# uvicorn PID 1 for correct signal handling / graceful shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
