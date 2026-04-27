# syntax=docker/dockerfile:1.7
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip curl libsndfile1 ffmpeg

WORKDIR /app

COPY requirements.txt .
# faster-whisper uses CTranslate2 which has built-in CUDA support (no PyTorch needed)
# CUDA 12.3.2 base image includes all necessary CUDA/cuDNN libraries
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip3 install -r requirements.txt

COPY main.py .

# Create models directory
RUN mkdir -p /app/models

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python3", "main.py"]

