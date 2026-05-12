#!/usr/bin/env bash
set -euo pipefail

MODEL_CHOICE="${1:-qwen3-4b}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="${ENSEMBLE_HOST_MODEL_DIR:-$ROOT_DIR/models}"
WEBUI_DIR="$ROOT_DIR/docker/llama-webui"
CONTAINER_NAME="${ENSEMBLE_QWEN_CONTAINER:-ensemble-qwen}"
PORT="${ENSEMBLE_SERVER_PORT:-8888}"
IMAGE="${ENSEMBLE_LLAMA_IMAGE:-ghcr.io/ggml-org/llama.cpp:server-vulkan}"
WAIT_SECONDS="${ENSEMBLE_SWITCH_WAIT_SECONDS:-60}"

case "$MODEL_CHOICE" in
  auto|default|fast|coding|4b|qwen3-4b|qwen3-4b-instruct)
    MODEL_ID="qwen3-4b-instruct-2507-ud-q4_k_xl"
    MODEL_PATH="/models/qwen3-4b-instruct-2507-ud-q4_k_xl.gguf"
    CTX_SIZE="32768"
    EXTRA_ARGS=(--flash-attn on -ngl 99)
    ;;
  reasoning|35b|qwen3.6|qwen3.6-35b|qwen3.6-35b-a3b)
    MODEL_ID="qwen3.6-35b-a3b-ud-q4_k_xl"
    MODEL_PATH="/models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf"
    CTX_SIZE="8192"
    EXTRA_ARGS=(--flash-attn on -ngl 99 --n-cpu-moe 999)
    ;;
  *)
    echo "Unknown model choice: $MODEL_CHOICE" >&2
    echo "Use one of: qwen3-4b, coding, reasoning, qwen3.6-35b" >&2
    exit 2
    ;;
esac

echo "Switching Ensemble model on :$PORT to $MODEL_ID"
echo "Stopping $CONTAINER_NAME if it is running..."
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "Starting $MODEL_ID..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "$PORT:$PORT" \
  -v "$MODELS_DIR:/models:ro" \
  -v "$WEBUI_DIR:/webui:ro" \
  -e LLAMA_ARG_HOST=0.0.0.0 \
  "$IMAGE" \
  -m "$MODEL_PATH" \
  --alias "$MODEL_ID" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --path /webui \
  --jinja \
  -c "$CTX_SIZE" \
  "${EXTRA_ARGS[@]}" >/dev/null

echo "Waiting up to ${WAIT_SECONDS}s for $MODEL_ID..."
for second in $(seq 1 "$WAIT_SECONDS"); do
  if curl -fsS "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
    echo "Ready: http://127.0.0.1:$PORT/v1/models"
    exit 0
  fi
  sleep 1
done

echo "Still loading after ${WAIT_SECONDS}s. Check logs with:" >&2
echo "docker logs -f $CONTAINER_NAME" >&2
exit 1
