# Production Multi-Stage Dockerfile for AI CCTV Backend Gateway
FROM python:3.11-slim as builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev ffmpeg libsm6 libxext6 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim as runner

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ffmpeg libsm6 libxext6 curl \
    && rm -rf /var/lib/apt/lists/*

# Run as unprivileged appuser
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

COPY --chown=appuser:appuser . .

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
