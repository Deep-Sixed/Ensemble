#!/usr/bin/env python3
"""
gguf-fit.py — GGUF model fit estimator

Preferred backend: gguf-parser (https://github.com/gpustack/gguf-parser-go)
  Accurate VRAM estimates with flash-attention, KV cache types, overhead.
Fallback backend: internal GGUF binary parser (stdlib only, no deps).

Ensemble owns:
  - fit verdicts
  - tier classification
  - launch flag generation
  - deployment recommendations

gguf-parser / internal parser owns:
  - GGUF spec interpretation
  - tensor metadata
  - KV cache formulas

Usage:
    python3 gguf-fit.py <model.gguf> [hardware.json]

hardware.json defaults to the latest in ../hardware-report/
Emits JSON to stdout. Saves artifact to ../recommendations/
"""

import json
import shutil
import struct
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ── GGUF type registry (internal fallback) ───────────────────────────────────
# (label, block_elements, bytes_per_block)

GGML_TYPES: dict[int, tuple[str, int, int]] = {
    0:  ("F32",      1,    4),
    1:  ("F16",      1,    2),
    2:  ("Q4_0",    32,   18),
    3:  ("Q4_1",    32,   20),
    6:  ("Q5_0",    32,   22),
    7:  ("Q5_1",    32,   24),
    8:  ("Q8_0",    32,   34),
    9:  ("Q8_1",    32,   36),
    10: ("Q2_K",   256,   84),
    11: ("Q3_K_S", 256,  110),
    12: ("Q3_K_M", 256,  110),
    13: ("Q3_K_L", 256,  110),
    14: ("Q4_K_S", 256,  144),
    15: ("Q4_K_M", 256,  144),
    16: ("Q5_K_S", 256,  176),
    17: ("Q5_K_M", 256,  176),
    18: ("Q6_K",   256,  210),
    19: ("Q8_K",   256,  292),
    28: ("IQ2_XXS",256,   66),
    29: ("IQ2_XS", 256,   74),
    30: ("IQ3_XXS",256,   98),
    31: ("IQ1_S",  256,   50),
    32: ("IQ4_NL",  32,   18),
    33: ("IQ3_S",  256,  110),
    34: ("IQ2_S",  256,   74),
    35: ("IQ4_XS", 256,  136),
    36: ("IQ1_M",  256,   56),
    37: ("BF16",     1,    2),
}

GGUF_MAGIC = 0x46554747  # "GGUF"

CONTEXT_POINTS = [4096, 8192, 32768]


# ── Internal GGUF parser (fallback) ─────────────────────────────────────────

class GGUFReader:
    """
    Reads GGUF v2/v3 header + tensor info blocks only.
    Does NOT read tensor data — fast even on 20GB+ files.
    """

    def __init__(self, path: Path):
        self.path = path
        self.file_size_mb = path.stat().st_size / (1024 ** 2)
        self.metadata: dict = {}
        self.tensors: list[dict] = []
        with open(path, "rb") as f:
            self._f = f
            self._parse()

    def _u8(self):  return struct.unpack("<B", self._f.read(1))[0]
    def _i8(self):  return struct.unpack("<b", self._f.read(1))[0]
    def _u16(self): return struct.unpack("<H", self._f.read(2))[0]
    def _i16(self): return struct.unpack("<h", self._f.read(2))[0]
    def _u32(self): return struct.unpack("<I", self._f.read(4))[0]
    def _i32(self): return struct.unpack("<i", self._f.read(4))[0]
    def _f32(self): return struct.unpack("<f", self._f.read(4))[0]
    def _u64(self): return struct.unpack("<Q", self._f.read(8))[0]
    def _i64(self): return struct.unpack("<q", self._f.read(8))[0]
    def _f64(self): return struct.unpack("<d", self._f.read(8))[0]

    def _string(self) -> str:
        return self._f.read(self._u64()).decode("utf-8", errors="replace")

    def _value(self, vtype: int):
        dispatch = {
            0: self._u8,   1: self._i8,
            2: self._u16,  3: self._i16,
            4: self._u32,  5: self._i32,
            6: self._f32,  7: lambda: bool(self._u8()),
            8: self._string,
            10: self._u64, 11: self._i64, 12: self._f64,
        }
        if vtype == 9:
            item_type = self._u32()
            return [self._value(item_type) for _ in range(self._u64())]
        if vtype not in dispatch:
            raise ValueError(f"Unknown GGUF value type {vtype}")
        return dispatch[vtype]()

    def _parse(self):
        magic = self._u32()
        if magic != GGUF_MAGIC:
            raise ValueError(f"Not a GGUF file (magic={magic:#010x})")
        _version = self._u32()
        tensor_count = self._u64()
        kv_count = self._u64()
        for _ in range(kv_count):
            key = self._string()
            self.metadata[key] = self._value(self._u32())
        for _ in range(tensor_count):
            name = self._string()
            n_dims = self._u32()
            dims = [self._u64() for _ in range(n_dims)]
            dtype = self._u32()
            _offset = self._u64()
            self.tensors.append({"name": name, "dims": dims, "dtype": dtype})

    def meta(self, *keys, default=0):
        for k in keys:
            if k in self.metadata:
                return self.metadata[k]
        return default

    def weights_mb(self) -> float:
        total = 0
        for t in self.tensors:
            n_elem = 1
            for d in t["dims"]:
                n_elem *= d
            info = GGML_TYPES.get(t["dtype"])
            if info:
                _, blk_elems, blk_bytes = info
                total += ((n_elem + blk_elems - 1) // blk_elems) * blk_bytes
            else:
                total += n_elem * 2
        return total / (1024 ** 2)

    def dominant_quant(self) -> str:
        # Weighted by bytes so MoE router tensors (many small F32) don't swamp
        # the large expert weight tensors (few big Q4_K).
        by_bytes: dict[str, int] = {}
        for t in self.tensors:
            n_elem = 1
            for d in t["dims"]:
                n_elem *= d
            info = GGML_TYPES.get(t["dtype"])
            if info:
                label, blk_elems, blk_bytes = info
                size = ((n_elem + blk_elems - 1) // blk_elems) * blk_bytes
            else:
                label, size = "UNK", n_elem * 2
            by_bytes[label] = by_bytes.get(label, 0) + size
        return max(by_bytes, key=by_bytes.get) if by_bytes else "unknown"


# ── gguf-parser backend ──────────────────────────────────────────────────────

GGUF_PARSER_BIN = "gguf-parser"


def gguf_parser_available() -> bool:
    return shutil.which(GGUF_PARSER_BIN) is not None


def _run_gguf_parser(model_path: Path, ctx: int, ngl: int = -1) -> dict:
    cmd = [
        GGUF_PARSER_BIN,
        "--json",
        "--skip-metadata",
        "--skip-tokenizer",
        "--flash-attn",
        "--ctx-size", str(ctx),
        "--gpu-layers", str(ngl),
        "--path", str(model_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"gguf-parser exited {r.returncode}: {r.stderr.strip()}")
    return json.loads(r.stdout)


def extract_via_gguf_parser(model_path: Path) -> dict:
    """
    Returns normalised metadata dict using gguf-parser for VRAM estimates.
    Runs once per context point; each call reads only the GGUF header (fast).

    Division of responsibility:
      gguf-parser  → total VRAM estimates (flash-attn aware, includes overhead)
      Ensemble     → KV cache formula (from authoritative arch fields gguf-parser exposes)
    """
    results = {}
    for ctx in CONTEXT_POINTS:
        results[ctx] = _run_gguf_parser(model_path, ctx, ngl=-1)

    base = results[CONTEXT_POINTS[0]]
    arch = base["architecture"]

    n_layers   = arch.get("blockCount", 0)
    n_heads    = arch.get("attentionHeadCount", 32)
    n_kv_heads = arch.get("attentionHeadCountKV", n_heads)
    head_dim   = arch.get("attentionKeyLength",
                          arch.get("embeddingLength", 4096) // max(1, n_heads))

    def vram_bytes(data: dict) -> float:
        return data["estimate"]["items"][0]["vrams"][0]["nonuma"] / (1024 ** 2)

    vram_at = {ctx: vram_bytes(results[ctx]) for ctx in CONTEXT_POINTS}

    # KV cache: Ensemble formula using architecture fields from gguf-parser.
    # K + V, fp16 (2 bytes each), across all layers.
    def kv_mb(ctx: int) -> float:
        return 2 * n_layers * n_kv_heads * head_dim * ctx * 2 / (1024 ** 2)

    kv_at = {ctx: kv_mb(ctx) for ctx in CONTEXT_POINTS}

    return {
        "backend": f"gguf-parser {_gguf_parser_version()}",
        "architecture": arch.get("architecture", "unknown"),
        "n_layers": n_layers,
        "n_kv_heads": n_kv_heads,
        "head_dim": head_dim,
        "max_context": arch.get("maximumContextLength", 4096),
        "vram_at": vram_at,
        "kv_at": kv_at,
    }


def _gguf_parser_version() -> str:
    try:
        r = subprocess.run([GGUF_PARSER_BIN, "--version"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip().split()[-1]
    except Exception:
        return "unknown"


# ── Internal fallback metadata extraction ───────────────────────────────────

def extract_via_internal(reader: GGUFReader) -> dict:
    arch = reader.metadata.get("general.architecture", "unknown")
    n_layers   = reader.meta(f"{arch}.block_count",            "llama.block_count")
    n_heads    = reader.meta(f"{arch}.attention.head_count",   "llama.attention.head_count",    default=32)
    n_kv_heads = reader.meta(f"{arch}.attention.head_count_kv","llama.attention.head_count_kv", default=n_heads)
    embed_len  = reader.meta(f"{arch}.embedding_length",       "llama.embedding_length",         default=4096)
    max_ctx    = reader.meta(f"{arch}.context_length",         "llama.context_length",           default=4096)
    head_dim   = embed_len // n_heads if n_heads > 0 else 128
    w_mb       = reader.weights_mb()

    def kv_mb(ctx: int) -> float:
        return 2 * n_layers * n_kv_heads * head_dim * ctx * 2 / (1024 ** 2)

    vram_at = {ctx: w_mb + kv_mb(ctx) for ctx in CONTEXT_POINTS}
    kv_at   = {ctx: kv_mb(ctx) for ctx in CONTEXT_POINTS}

    return {
        "backend": "internal",
        "architecture": arch,
        "n_layers": n_layers,
        "n_kv_heads": n_kv_heads,
        "head_dim": head_dim,
        "max_context": max_ctx,
        "vram_at": vram_at,
        "kv_at": kv_at,
    }


# ── Fit verdict + launch flags ───────────────────────────────────────────────

VERDICT_LABELS = {
    "fits_in_vram":        "Fits cleanly in VRAM",
    "fits_in_vram_tight":  "Fits in VRAM with <512MB headroom — monitor for OOM",
    "partial_cpu_offload": "Exceeds VRAM — partial CPU offload required",
    "exceeds_hardware":    "Exceeds both VRAM and safe RAM budget — not recommended",
}


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


def recommended_ngl(weights_mb: float, vram_free_mb: float, n_layers: int) -> int:
    if n_layers <= 0 or weights_mb <= 0:
        return n_layers
    mb_per_layer = weights_mb / n_layers
    return min(n_layers, max(0, int(vram_free_mb / mb_per_layer)))


def build_launch_flags(verdict: str, ngl: int, arch: str) -> str:
    flags = f"-ngl {ngl} --flash-attn on --jinja"
    needs_offload = verdict in ("partial_cpu_offload", "exceeds_hardware")
    is_moe = any(x in arch.lower() for x in ("moe", "mixtral"))
    if needs_offload and is_moe:
        flags += " --n-cpu-moe 999"
    return flags


# ── I/O helpers ──────────────────────────────────────────────────────────────

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


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if sys.argv[1:] else 1)

    model_path = Path(sys.argv[1]).resolve()
    if not model_path.exists():
        print(f"Error: model not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    skill_dir = Path(__file__).parent.parent
    hw_path = Path(sys.argv[2]).resolve() if len(sys.argv) >= 3 else find_latest_hw_json(skill_dir)

    hw = json.loads(hw_path.read_text())
    vram_mb      = hw.get("vram_mb", 0)
    vram_free_mb = hw.get("vram_free_mb", vram_mb)
    ram_gb       = hw.get("ram_gb", 0)
    ram_avail_gb = hw.get("ram_available_gb", ram_gb)

    size_gb = model_path.stat().st_size / (1024 ** 3)
    print(f"# Parsing {model_path.name} ({size_gb:.2f} GB) ...", file=sys.stderr)

    # Always run GGUFReader — fast, gives us quant label + precise weights_mb.
    reader = GGUFReader(model_path)
    quant     = reader.dominant_quant()
    weights_mb = reader.weights_mb()

    # Preferred backend: gguf-parser for accurate VRAM estimates.
    # Fallback: internal formula.
    if gguf_parser_available():
        print(f"# Backend: gguf-parser ({_gguf_parser_version()})", file=sys.stderr)
        extracted = extract_via_gguf_parser(model_path)
    else:
        print("# Backend: internal (install gguf-parser for more accurate estimates)", file=sys.stderr)
        extracted = extract_via_internal(reader)

    arch       = extracted["architecture"]
    n_layers   = extracted["n_layers"]
    max_ctx    = extracted["max_context"]
    vram_at    = extracted["vram_at"]   # {ctx: mb}
    kv_at      = extracted["kv_at"]     # {ctx: mb}
    backend    = extracted["backend"]

    base_ctx       = CONTEXT_POINTS[0]
    verdict        = fit_verdict(vram_at[base_ctx], vram_free_mb, ram_avail_gb)
    ngl            = recommended_ngl(weights_mb, vram_free_mb, n_layers)
    flags          = build_launch_flags(verdict, ngl, arch)

    result = {
        "timestamp": datetime.now().isoformat(),
        "backend": backend,
        "model": model_path.name,
        "model_path": str(model_path),
        "hardware_profile": str(hw_path),
        "model_info": {
            "architecture": arch,
            "quantization": quant,
            "n_layers": n_layers,
            "n_kv_heads": extracted["n_kv_heads"],
            "head_dim": extracted["head_dim"],
            "max_context": max_ctx,
            "weights_mb": round(weights_mb),
            "file_size_mb": round(reader.file_size_mb),
        },
        "kv_cache_mb": {
            f"{ctx // 1024}k": round(kv_at[ctx]) for ctx in CONTEXT_POINTS
        },
        "total_vram_needed_mb": {
            f"{ctx // 1024}k_ctx": round(vram_at[ctx]) for ctx in CONTEXT_POINTS
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
            "recommended_ngl": ngl,
            "vram_headroom_mb": round(vram_free_mb - vram_at[base_ctx]),
            "ram_spillover_gb": round(max(0.0, vram_at[base_ctx] - vram_free_mb) / 1024, 2),
        },
        "launch_flags": flags,
    }

    print(json.dumps(result, indent=2))

    stamp    = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = skill_dir / "recommend" / "output" / f"gguf-fit-{model_path.stem}-{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(f"# Saved to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
