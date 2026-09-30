#!/usr/bin/env bash
set -euo pipefail

COLLECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$COLLECT_DIR")"
OUT_DIR="$COLLECT_DIR/hardware-report"
REC_DIR="$SKILL_DIR/recommend/output"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="$OUT_DIR/linux-hardware-$STAMP.txt"
JSON_FILE="$OUT_DIR/linux-hardware-$STAMP.json"
REC_FILE="$REC_DIR/recommendations-$STAMP.txt"

mkdir -p "$OUT_DIR" "$REC_DIR"

# ---------------------------------------------------------------------------
# Self-healing installs
# ---------------------------------------------------------------------------

install_if_missing() {
  local cmd="$1"
  local pkg="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[INFO] Installing missing package: $pkg"
    if sudo -n true 2>/dev/null; then
      sudo apt-get update -y -qq && sudo apt-get install -y -qq "$pkg" \
        || echo "[WARN] Failed to install $pkg — continuing without it"
    else
      echo "[WARN] sudo requires a password — skipping $pkg install (run manually: sudo apt-get install $pkg)"
    fi
  fi
}

install_if_missing inxi inxi
install_if_missing hwinfo hwinfo
install_if_missing lshw lshw
install_if_missing lsusb usbutils
install_if_missing lspci pciutils

# ---------------------------------------------------------------------------
# Full human-readable report
# ---------------------------------------------------------------------------

{
  echo "Linux Hardware Report"
  echo "Generated: $(date -Is)"
  echo

  echo "===== OS ====="
  cat /etc/os-release || true
  uname -a || true
  echo

  echo "===== CPU ====="
  lscpu || true
  echo

  echo "===== RAM ====="
  free -h || true
  cat /proc/meminfo || true
  echo

  echo "===== Storage ====="
  lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL || true
  df -h || true
  echo

  echo "===== PCI / GPU / Audio / Network ====="
  lspci || true
  echo

  echo "===== USB ====="
  lsusb || true
  echo

  echo "===== inxi summary ====="
  if command -v inxi >/dev/null 2>&1; then
    inxi -Fxz || true
  else
    echo "inxi not installed"
  fi
  echo

  echo "===== lshw short ====="
  if command -v lshw >/dev/null 2>&1; then
    sudo lshw -short || lshw -short || true
  else
    echo "lshw not installed"
  fi
  echo

  echo "===== hwinfo short ====="
  if command -v hwinfo >/dev/null 2>&1; then
    hwinfo --short || true
  else
    echo "hwinfo not installed"
  fi
  echo

  echo "===== NVIDIA ====="
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi || true
  else
    echo "nvidia-smi not installed or NVIDIA driver unavailable"
  fi
} | tee "$OUT_FILE"

# ---------------------------------------------------------------------------
# Machine-readable JSON
# ---------------------------------------------------------------------------

OS_NAME="$(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '"')"
CPU_MODEL="$(lscpu | grep 'Model name:' | sed 's/Model name:[[:space:]]*//')"
RAM_GB="$(free -g | awk '/Mem:/ {print $2}')"
RAM_AVAIL_GB="$(free -g | awk '/Mem:/ {print $7}')"
SWAP_GB="$(free -g | awk '/Swap:/ {print $2}')"

if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo none)"
  VRAM_MB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo 0)"
  VRAM_FREE_MB="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 || echo 0)"
  DRIVER_VER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo unknown)"
  CUDA_VER="$(nvidia-smi 2>/dev/null | grep -oP 'CUDA Version: \K[\d.]+' | head -1 || echo unknown)"
else
  GPU_NAME="none"
  VRAM_MB=0
  VRAM_FREE_MB=0
  DRIVER_VER="none"
  CUDA_VER="none"
fi

TOTAL_THREADS="$(nproc)"
PHYSICAL_CORES="$(lscpu | awk '/^Core\(s\) per socket:/ {print $4}')"
THREADS_PER_CORE="$(lscpu | awk '/^Thread\(s\) per core:/ {print $4}')"
CPU_MAX_MHZ="$(lscpu | awk '/^CPU max MHz:/ {print $4}')"

cat > "$JSON_FILE" <<EOF
{
  "timestamp": "$(date -Is)",
  "os": "$OS_NAME",
  "kernel": "$(uname -r)",
  "cpu": "$CPU_MODEL",
  "cpu_physical_cores": $PHYSICAL_CORES,
  "cpu_threads_per_core": $THREADS_PER_CORE,
  "cpu_threads_total": $TOTAL_THREADS,
  "cpu_max_mhz": "${CPU_MAX_MHZ:-unknown}",
  "ram_gb": $RAM_GB,
  "ram_available_gb": $RAM_AVAIL_GB,
  "swap_gb": $SWAP_GB,
  "gpu": "$GPU_NAME",
  "vram_mb": $VRAM_MB,
  "vram_free_mb": $VRAM_FREE_MB,
  "driver_version": "$DRIVER_VER",
  "cuda_version": "$CUDA_VER"
}
EOF

echo
echo "Saved JSON profile to:"
echo "$JSON_FILE"

# ---------------------------------------------------------------------------
# Model recommendations
# ---------------------------------------------------------------------------

VRAM_MB_INT=${VRAM_MB:-0}

{
  echo "Model Recommendations"
  echo "Generated: $(date -Is)"
  echo "Hardware: $GPU_NAME — ${VRAM_MB_INT} MiB VRAM — ${RAM_GB}GB RAM"
  echo

  echo "===== Recommended Models ====="
  if [ "$VRAM_MB_INT" -ge 24000 ]; then
    echo "COMFORTABLE:"
    echo "  Qwen3 32B Instruct UD Q4_K_XL"
    echo "  Qwen2.5-Coder 32B Instruct Q4_K_M"
    echo
    echo "BALANCED:"
    echo "  Qwen3 14B Instruct Q4_K_M"
    echo "  DeepSeek-Coder 33B Q4_K_M"
    echo
    echo "STRETCH:"
    echo "  Qwen3.6 35B A3B UD Q4_K_XL (MoE — stays within VRAM budget)"
    echo "  Llama 3.3 70B Q2_K with partial CPU offload"
  elif [ "$VRAM_MB_INT" -ge 12000 ]; then
    echo "COMFORTABLE:"
    echo "  Qwen3 14B Instruct UD Q4_K_XL"
    echo "  Qwen2.5-Coder 14B Instruct Q4_K_M"
    echo
    echo "BALANCED:"
    echo "  Qwen3 8B Instruct Q4_K_M"
    echo "  Qwen2.5-Coder 7B Instruct Q4_K_M"
    echo
    echo "STRETCH:"
    echo "  Qwen3.6 35B A3B UD Q4_K_XL (MoE — active params stay low)"
    echo "  Warning: requires 16GB+ RAM for CPU offload layers"
  elif [ "$VRAM_MB_INT" -ge 7500 ]; then
    echo "COMFORTABLE:"
    echo "  Qwen3 4B Instruct UD Q4_K_XL"
    echo "  Qwen2.5-Coder 7B Instruct Q4_K_M"
    echo "  DeepSeek-Coder 6.7B Q4_K_M"
    echo
    echo "BALANCED:"
    echo "  Qwen3 8B Instruct Q4_K_M  (tight — test VRAM headroom)"
    echo "  Llama 3.1 8B Instruct Q4_K_M"
    echo
    echo "STRETCH:"
    echo "  Qwen3.6 35B A3B UD Q4_K_XL (MoE — partial CPU offload required)"
    echo "  Warning: keep context <= 8192 tokens; do not run alongside VRAM-heavy processes"
    echo "  Warning: monitor swap — ${SWAP_GB}GB swap detected"
  else
    echo "COMFORTABLE:"
    echo "  Qwen3 1.7B Instruct Q4_K_M"
    echo "  Qwen2.5-Coder 3B Instruct Q4_K_M"
    echo
    echo "BALANCED:"
    echo "  Qwen3 4B Instruct Q4_K_M"
    echo
    echo "STRETCH:"
    echo "  Qwen2.5-Coder 7B Instruct Q3_K_M with CPU offload"
    echo "  Warning: low VRAM — expect degraded speed on any 7B+ model"
  fi

  echo
  echo "===== Runtime Notes ====="
  if [ "$SWAP_GB" -ge 5 ]; then
    echo "WARNING: ${SWAP_GB}GB swap currently in use. Stretch-class offload will compete with active swap."
    echo "         Consider closing background processes before loading large models."
  fi
  echo "Runtime: llama.cpp / llama-server"
  echo "Flags:   -ngl 99 --flash-attn on --jinja"
  echo "For MoE: add --n-cpu-moe 999 to offload MoE routing layers to CPU"
} | tee "$REC_FILE"

echo
echo "Saved recommendations to:"
echo "$REC_FILE"
