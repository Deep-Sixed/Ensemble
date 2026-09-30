#!/usr/bin/env python3
"""
hf-fit.py — HuggingFace model fit estimator (no download required)

Reads safetensors headers via HTTP range requests and config.json to estimate:
  - weights VRAM (raw bf16/fp16, or override for quantized loading)
  - KV cache at multiple context lengths
  - fit verdict against local hardware profile

Complements gguf-fit.py:
  gguf-fit.py  →  local GGUF files  (what you have)
  hf-fit.py    →  remote HF repos   (what you're considering downloading)

Usage:
    python3 hf-fit.py <model_id> [options]

    --revision BRANCH     default: main
    --ctx 4096,8192,32768 context sizes to estimate (comma-separated)
    --batch INT           concurrent sequences (default: 1)
    --kv-dtype fp16|fp8   KV cache dtype (default: fp16)
    --quant INT|FLOAT     effective bytes-per-param override:
                            4 = int4 (0.5), 8 = int8 (1.0), or pass float directly
    --hardware PATH       explicit hardware JSON path
    --json                emit JSON only (no human-readable output)

Requires: pip install requests
"""

import json
import struct
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' is required.  pip install requests", file=sys.stderr)
    sys.exit(1)

from typing import Any

CONTEXT_POINTS_DEFAULT = [4096, 8192, 32768]

DTYPE_BYTES: dict[str, int] = {
    "F64": 8, "F32": 4, "BF16": 2, "F16": 2,
    "I64": 8, "I32": 4, "I16": 2, "I8": 1, "U8": 1,
}

VERDICT_LABELS = {
    "fits_in_vram":        "Fits cleanly in VRAM",
    "fits_in_vram_tight":  "Fits in VRAM with <512MB headroom — monitor for OOM",
    "partial_cpu_offload": "Exceeds VRAM — partial CPU offload required",
    "exceeds_hardware":    "Exceeds both VRAM and safe RAM budget — not recommended",
}


# ── HuggingFace fetchers ─────────────────────────────────────────────────────

def hf_list_safetensors(model_id: str, revision: str = "main") -> list[str]:
    api = f"https://huggingface.co/api/models/{model_id}"
    resp = requests.get(api, params={"revision": revision}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    files = [
        s.get("rfilename", "")
        for s in data.get("siblings", [])
        if s.get("rfilename", "").endswith(".safetensors")
    ]
    if not files:
        raise RuntimeError(f"No .safetensors files found in {model_id}@{revision}")
    return sorted(files)


def range_get(url: str, start: int, end: int) -> bytes:
    headers = {"Range": f"bytes={start}-{end}"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.content


def read_safetensors_header(model_id: str, filename: str, revision: str = "main") -> dict:
    url = f"https://huggingface.co/{model_id}/resolve/{revision}/{filename}"
    (header_len,) = struct.unpack("<Q", range_get(url, 0, 7))
    return json.loads(range_get(url, 8, 8 + header_len - 1).decode("utf-8"))


def fetch_config(model_id: str, revision: str = "main") -> dict:
    url = f"https://huggingface.co/{model_id}/resolve/{revision}/config.json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Weight estimation ─────────────────────────────────────────────────────────

def estimate_weights(model_id: str, revision: str = "main") -> tuple[int, int]:
    """Returns (total_bytes, total_params) from safetensors metadata."""
    files = hf_list_safetensors(model_id, revision)
    total_bytes = 0
    total_params = 0
    for fn in files:
        header = read_safetensors_header(model_id, fn, revision)
        for k, v in header.items():
            if k == "__metadata__":
                continue
            dtype = v["dtype"]
            if dtype not in DTYPE_BYTES:
                raise RuntimeError(f"Unsupported dtype: {dtype} (tensor={k})")
            n = 1
            for d in v["shape"]:
                n *= int(d)
            total_params += n
            total_bytes  += n * DTYPE_BYTES[dtype]
    return total_bytes, total_params


# ── KV cache estimation ───────────────────────────────────────────────────────

def kv_cache_bytes(cfg: dict, batch: int, ctx: int, kv_dtype_bytes: int = 2) -> int:
    num_layers   = int(cfg["num_hidden_layers"])
    hidden_size  = int(cfg["hidden_size"])
    num_heads    = int(cfg["num_attention_heads"])
    num_kv_heads = int(cfg.get("num_key_value_heads", num_heads))
    head_dim     = int(cfg.get("head_dim", hidden_size // num_heads))
    return batch * ctx * num_layers * num_kv_heads * head_dim * 2 * kv_dtype_bytes


# ── Fit verdict ───────────────────────────────────────────────────────────────

def fit_verdict(total_vram_mb: float, vram_free_mb: float, ram_avail_gb: float) -> str:
    headroom = vram_free_mb - total_vram_mb
    if headroom >= 512:
        return "fits_in_vram"
    if headroom >= 0:
        return "fits_in_vram_tight"
    overflow_gb = -headroom / 1024
    if overflow_gb <= ram_avail_gb * 0.75:
        return "partial_cpu_offload"
    return "exceeds_hardware"


# ── Hardware profile ─────────────────────────────────────────────────────────

def find_latest_hw_json(skill_dir: Path) -> Path:
    candidates = sorted(
        (skill_dir / "collect" / "hardware-report").glob("linux-hardware-*.json"),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No hardware JSON in {skill_dir / 'collect' / 'hardware-report'}/\n"
            "Run collect/linux-hardware.sh first."
        )
    return candidates[0]


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> dict[str, Any]:
    args: dict[str, Any] = {
        "model_id": None,
        "revision": "main",
        "ctx_points": CONTEXT_POINTS_DEFAULT,
        "batch": 1,
        "kv_dtype": "fp16",
        "quant": None,
        "hardware": None,
        "json_only": False,
    }
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif a == "--revision":
            args["revision"] = argv[i + 1]; i += 2
        elif a == "--ctx":
            args["ctx_points"] = [int(x) for x in argv[i + 1].split(",")]; i += 2
        elif a == "--batch":
            args["batch"] = int(argv[i + 1]); i += 2
        elif a == "--kv-dtype":
            args["kv_dtype"] = argv[i + 1]; i += 2
        elif a == "--quant":
            raw = argv[i + 1]
            if raw in ("4", "int4"):
                args["quant"] = 0.5
            elif raw in ("8", "int8"):
                args["quant"] = 1.0
            else:
                args["quant"] = float(raw)
            i += 2
        elif a == "--hardware":
            args["hardware"] = Path(argv[i + 1]); i += 2
        elif a == "--json":
            args["json_only"] = True; i += 1
        elif not a.startswith("--"):
            args["model_id"] = a; i += 1
        else:
            print(f"Unknown flag: {a}", file=sys.stderr); sys.exit(1)
    return args


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args(sys.argv)
    if not args["model_id"]:
        print(__doc__)
        sys.exit(1)

    model_id  = args["model_id"]
    revision  = args["revision"]
    ctx_pts   = args["ctx_points"]
    batch     = args["batch"]
    kv_dtype  = args["kv_dtype"]
    quant_bpp = args["quant"]
    json_only = args["json_only"]

    skill_dir = Path(__file__).parent.parent
    hw_path   = args["hardware"] or find_latest_hw_json(skill_dir)
    hw        = json.loads(hw_path.read_text())

    vram_mb      = hw.get("vram_mb", 0)
    vram_free_mb = hw.get("vram_free_mb", vram_mb)
    ram_gb       = hw.get("ram_gb", 0)
    ram_avail_gb = hw.get("ram_available_gb", ram_gb)

    if not json_only:
        print(f"# Fetching metadata for {model_id}@{revision} ...", file=sys.stderr)

    weights_bytes_raw, total_params = estimate_weights(model_id, revision)

    quant_overhead = 0.03
    if quant_bpp is not None:
        weights_bytes = int(total_params * quant_bpp * (1.0 + quant_overhead))
        weight_label  = f"{quant_bpp * 8:.0f}-bit quant (effective)"
    else:
        weights_bytes = weights_bytes_raw
        weight_label  = "raw (bf16/fp16 mix)"

    cfg = fetch_config(model_id, revision)

    kv_dtype_bytes = 1 if kv_dtype.lower() == "fp8" else 2

    vram_at: dict[int, float] = {}
    kv_at:   dict[int, float] = {}
    runtime_overhead = 0.15
    for ctx in ctx_pts:
        kv = kv_cache_bytes(cfg, batch, ctx, kv_dtype_bytes)
        base = weights_bytes + kv
        total = int(base * (1.0 + runtime_overhead))
        vram_at[ctx] = total / (1024 ** 2)
        kv_at[ctx]   = kv  / (1024 ** 2)

    base_ctx = ctx_pts[0]
    verdict  = fit_verdict(vram_at[base_ctx], vram_free_mb, ram_avail_gb)

    result = {
        "timestamp": datetime.now().isoformat(),
        "model": model_id,
        "revision": revision,
        "hardware_profile": str(hw_path),
        "model_info": {
            "params_b": round(total_params / 1e9, 2),
            "architecture": cfg.get("model_type", "unknown"),
            "n_layers": cfg.get("num_hidden_layers"),
            "n_kv_heads": cfg.get("num_key_value_heads", cfg.get("num_attention_heads")),
            "max_context": cfg.get("max_position_embeddings"),
            "weights_gb_raw": round(weights_bytes_raw / (1024 ** 3), 2),
            "weights_gb_effective": round(weights_bytes / (1024 ** 3), 2),
            "weight_label": weight_label,
        },
        "kv_cache_mb": {
            f"{ctx // 1024}k": round(kv_at[ctx]) for ctx in ctx_pts
        },
        "total_vram_needed_mb": {
            f"{ctx // 1024}k_ctx": round(vram_at[ctx]) for ctx in ctx_pts
        },
        "inference_params": {
            "batch_size": batch,
            "kv_dtype": kv_dtype,
            "runtime_overhead_pct": int(runtime_overhead * 100),
        },
        "hardware": {
            "vram_mb": vram_mb,
            "vram_free_mb": vram_free_mb,
            "ram_gb": ram_gb,
            "ram_available_gb": ram_avail_gb,
        },
        "fit": {
            "verdict": verdict,
            "verdict_label": VERDICT_LABELS[verdict],
            "vram_headroom_mb": round(vram_free_mb - vram_at[base_ctx]),
            "ram_spillover_gb": round(max(0.0, vram_at[base_ctx] - vram_free_mb) / 1024, 2),
        },
    }

    print(json.dumps(result, indent=2))

    stamp    = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug     = model_id.replace("/", "--")
    out_path = skill_dir / "recommend" / "output" / f"hf-fit-{slug}-{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    if not json_only:
        print(f"# Saved to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
