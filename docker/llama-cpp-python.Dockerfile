FROM python:3.14.5-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "llama-cpp-python[server]>=0.3.0"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=10 \
    CMD curl -fsS http://localhost:8080/v1/models >/dev/null || exit 1
