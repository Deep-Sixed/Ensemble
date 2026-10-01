# analyze-local-llm

Analyze local hardware and recommend practical model deployments.

Reasoning must be architecture-aware, not parameter-count-naive.

---

## Core Reasoning Model

Do not reason: `GPU VRAM → model size`.

Reason: `hardware + architecture type + active parameter behavior + runtime + offload strategy + workload class → deployment recommendation`.

The key distinctions:

| Concept | Why it matters |
|---|---|
| Total params | marketing number |
| Active params | actual runtime VRAM cost |
| Architecture type | determines scaling behavior |
| Workload class | determines optimal profile slot |

---

## Architecture Types

| Type | Example | Active-param behavior |
|---|---|---|
| Dense Transformer | Llama 3 8B, Qwen3 4B | All params active every token |
| MoE | Qwen3.6 35B A3B, Mixtral | Subset active per token via routing |
| Sliding Window | Mistral 7B | Bounded attention, lower KV pressure |
| Reasoning-tuned | QwQ, DeepSeek-R1 | Expects longer chains, needs larger context |
| Coder-tuned | Qwen2.5-Coder, DeepSeek-Coder | Optimized for code token distributions |

MoE models can outperform dense models at the same VRAM budget because active parameter count — not total — determines inference cost.

---

## Hardware Collection

Before recommending local LLM models, run:

```bash
./collect-linux-hardware.sh
```

The script writes a timestamped report to:

```
./hardware-report/
```

Use that report as the input source for CPU, RAM, GPU, VRAM, storage, OS, and driver/runtime recommendations.

### Required Tools

The script auto-installs missing tools when `sudo` is available non-interactively. On a fresh install or restricted shell, install manually:

```bash
sudo apt-get install inxi hwinfo lshw usbutils pciutils
```

| Tool | Package | Provides | Required |
|---|---|---|---|
| `lscpu` | `util-linux` (pre-installed) | CPU model, cores, threads, cache, flags | yes |
| `free` | `procps` (pre-installed) | RAM and swap totals | yes |
| `lsblk` | `util-linux` (pre-installed) | Storage devices, sizes, mount points | yes |
| `df` | `coreutils` (pre-installed) | Filesystem usage | yes |
| `lspci` | `pciutils` | GPU, audio, network PCI devices | yes |
| `lsusb` | `usbutils` | USB peripherals | yes |
| `nvidia-smi` | NVIDIA driver (proprietary) | GPU name, VRAM, driver version, CUDA version | yes (NVIDIA only) |
| `lshw` | `lshw` | Full hardware tree including motherboard | recommended |
| `inxi` | `inxi` | Compact full-system summary with GPU arch, display, kernel | recommended |
| `hwinfo` | `hwinfo` | Low-level hardware enumeration | optional |

---

## Inputs

- GPU model
- VRAM (GB)
- RAM (GB)
- OS / virtualization layer (bare metal, VMware, WSL2, etc.)
- Preferred runtime: llama.cpp, Ollama, LM Studio, vLLM, other
- Workload class (optional): coding, reasoning, chat, indexing

---

## Profile Slots

### Comfortable

Runs smoothly with no offload. Low latency. Daily driver.

- 3B–4B instruct or coder model
- Fits entirely in VRAM
- Q4_K_M or Q4_K_XL (UD variants preferred for Qwen)

### Balanced

Best quality/speed tradeoff for interactive agent use.

- 7B–8B instruct or coder model
- Fits in VRAM with minimal pressure
- Q4_K_M default

### Stretch

Largest model viable with acceptable compromises.

- MoE models preferred over dense — active params stay low
- Partial CPU/RAM offload required
- Tighter context window
- Warn on RAM pressure, disk size, thermal risk

---

## Speed Classes

| Class | Latency target | Typical use |
|---|---|---|
| instant | < 1s first token | chat, UI, planning |
| interactive | 1–5s first token | coding agent, repo edits, review |
| thinking | 5–30s first token | architecture decisions, hard reasoning |
| batch-only | latency irrelevant | indexing, evals, background jobs |

---

## JARVIS Default Profile

Hardware:
- GPU: RTX 3060 Ti
- VRAM: 8GB
- OS: Ubuntu 26.04 Desktop LTS — native bare-metal install, AMD64
- Runtime: llama.cpp / OpenAI-compatible server

### Comfortable

```text
Model:          Qwen3 4B Instruct UD Q4_K_XL
Quant:          Q4_K_XL
Speed class:    instant / interactive
Expected TPS:   20–35 tok/s
Best for:       chat, quick edits, planning, lightweight coding

Command:
  llama-server \
    -m /models/qwen3-4b-instruct-2507-ud-q4_k_xl.gguf \
    --host 0.0.0.0 --port 8080 \
    --jinja -c 32768 -ngl 99 --flash-attn on
```

### Balanced

```text
Model:          Qwen2.5-Coder 7B Instruct Q4_K_M
Quant:          Q4_K_M
Speed class:    interactive
Expected TPS:   12–22 tok/s
Best for:       coding agent, repo edits, code review, CLI integration

Command:
  llama-server \
    -m /models/qwen2.5-coder-7b-instruct-q4_k_m.gguf \
    --host 0.0.0.0 --port 8080 \
    --jinja -c 16384 -ngl 99 --flash-attn on
```

### Stretch

```text
Model:          Qwen3.6 35B A3B UD Q4_K_XL  (MoE — preferred over dense 14B)
Quant:          Q4_K_XL
Speed class:    thinking
Expected TPS:   4–10 tok/s
Best for:       hard reasoning, architecture decisions, tasks where latency is acceptable

Warning:
  - Requires 16GB+ RAM for CPU offload layers
  - Keep context <= 8192 tokens
  - Do not run alongside other VRAM-heavy processes
  - MoE routing keeps active VRAM pressure low despite 35B total params

Command:
  llama-server \
    -m /models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf \
    --host 0.0.0.0 --port 8888 \
    --jinja -c 8192 -ngl 99 --n-cpu-moe 999 --flash-attn on
```

---

## Output Format

When applying this skill, always emit:

```text
COMFORTABLE:
Model:
Quant:
Speed class:
Expected TPS:
Best for:
Command:

BALANCED:
Model:
Quant:
Speed class:
Expected TPS:
Best for:
Command:

STRETCH:
Model:
Quant:
Speed class:
Expected TPS:
Best for:
Warning:
Command:
```

Include a Notes section when the recommendation deviates from naive parameter-count reasoning (e.g., MoE vs dense tradeoffs, UD quant advantages, virtualization overhead if applicable).

---

## Future Extensions

Planned capabilities for this skill. **None of these CLI commands exist yet**;
`ensemble --help` lists what is implemented:

- `ensemble detect-hardware` — read GPU/VRAM/RAM, emit hardware profile
- `ensemble recommend-model` — apply this skill, emit ranked recommendations
- `ensemble calibrate-runtime` — benchmark tok/s, first-token latency, VRAM headroom; persist observed values back to `profiles/`
- `ensemble benchmark-model` — structured throughput/quality sweep across loaded models
- `ensemble route-model` — select profile slot automatically based on task workload class

The calibration pass is highest priority: theoretical fit is not sufficient. Observed tok/s, context degradation, and thermal behavior under load must be measured and persisted into profile JSON before routing decisions can be trusted.
