---
name: local-llm-workbench
description: "Run, evaluate, and deploy LLMs locally — llama.cpp for GGUF inference, vLLM for serving, and lm-evaluation-harness for benchmarks."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [llm, inference, serving, evaluation, gguf, quantization, benchmark, local]
    related_skills: [huggingface-hub, huggingface-local-models]
---

# Local LLM Workbench

Three complementary tools for running LLMs on local hardware:

1. **llama.cpp** — GGUF quantization + CPU/GPU inference
2. **vLLM** — high-throughput serving via PagedAttention
3. **lm-evaluation-harness** — standard LLM benchmarks (MMLU, GSM8K, etc.)

## 1. llama.cpp — Local GGUF Inference

### Installation

```bash
# Clone
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp

# Build
cmake -B build
cmake --build build --config Release

# Or pip (Python bindings only)
pip install llama-cpp-python
```

### Usage

```bash
# Basic inference
./build/bin/llama-cli -m model.gguf -p "Hello, world!" -n 128

# Chat mode
./build/bin/llama-cli -m model.gguf \
  -p "You are a helpful assistant.\nUser: Hello\nAssistant:" -n 256

# Server mode
./build/bin/llama-server -m model.gguf --port 8080
# Then: curl http://localhost:8080/v1/chat/completions ...
```

### Key Flags
- `-n N` — max tokens to generate
- `-t N` — thread count
- `-ngl N` — GPU layers offload (0 = CPU only)
- `--temp F` — temperature (default 0.8)
- `--ctx-size N` — context size (default 512)
- `-c N` — alias for --ctx-size

### Finding GGUF Models

Use the `huggingface-local-models` skill or browse Hugging Face:

```bash
# Search for GGUF files
hf search "GGUF" --limit 20
```

This searches the `hf` CLI tool. For specific model families: `hf search "Qwen2.5-7B-GGUF"`.

### Pitfalls
- On macOS with Metal: `-ngl 1` or higher enables GPU acceleration. Without it, inference is CPU-only.
- Windows with CUDA: build with `cmake -B build -DLLAMA_CUDA=ON`.
- Context size matters: set `--ctx-size` high enough for your task (4096 for most chats).
- `llama-cpp-python` pip package has prebuilt wheels for most platforms; if they don't work, build from source.

## 2. vLLM — High-Throughput Serving

### Installation

```bash
pip install vllm
# Or for latest:
pip install https://github.com/vllm-project/vllm/releases/download/v0.8.3/vllm-0.8.3-cp312-cp312-manylinux1_x86_64.whl
```

### Usage

```bash
# Start server
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --port 8000

# Query via OpenAI-compatible API
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "Qwen/Qwen2.5-7B-Instruct", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Key Parameters
- `--tensor-parallel-size N` — multi-GPU splitting
- `--max-model-len N` — context window (default: model's max)
- `--gpu-memory-utilization F` — memory budget (default 0.9)
- `--dtype auto|half|bfloat16` — precision
- `--enforce-eager` — disable CUDA graphs (debug mode)
- `--trust-remote-code` — allow remote code in model config

### Auto-Start with Hermes

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000 --max-model-len 4096 &
# Wait for startup (check logs for "Uvicorn running on")
sleep 30

# Configure Hermes to use it
hermes config set model.provider openai
hermes config set model.base_url http://localhost:8000/v1
hermes config set model.default Qwen/Qwen2.5-7B-Instruct
```

### Pitfalls
- vLLM requires CUDA GPU with sufficient VRAM (>16GB for 7B models).
- First start downloads the model to `~/.cache/huggingface/` (takes time).
- `--enforce-eager` disables CUDA graphs — use for compatibility, not performance.
- Windows support is experimental. Prefer Linux/WSL2 for production serving.
- vLLM 0.8.x requires Python 3.12 on some platforms.

## 3. lm-evaluation-harness — Benchmarks

### Installation

```bash
git clone https://github.com/EleutherAI/lm-evaluation-harness.git
cd lm-evaluation-harness
pip install -e .
```

### Usage

```bash
# Evaluate a Hugging Face model
python -m lm_eval \
  --model hf \
  --model_args pretrained=Qwen/Qwen2.5-7B-Instruct \
  --tasks mmlu \
  --num_fewshot 5 \
  --device cuda:0

# Evaluate via local API endpoint
python -m lm_eval \
  --model local-completions \
  --model_args model=Qwen,base_url=http://localhost:8000/v1/completions,num_concurrent=4 \
  --tasks gsm8k

# List available tasks
python -m lm_eval --tasks list
```

### Common Tasks
| Task | Description | Metric |
|------|-------------|--------|
| `mmlu` | 57-subject knowledge | accuracy |
| `gsm8k` | Grade-school math | exact_match |
| `hellaswag` | Commonsense reasoning | accuracy |
| `arc_challenge` | Science reasoning | accuracy |
| `truthfulqa_mc2` | Truthfulness | mc2 |

### Key Args
- `--num_fewshot N` — few-shot examples (default: 0)
- `--limit N` — limit test samples (for quick checks)
- `--batch_size N` — samples per batch
- `--output_path PATH` — save results as JSON
- `--log_samples` — log individual predictions

### Pitfalls
- Some tasks require specific few-shot counts (e.g., MMLU 5-shot).
- Large benchmarks (MMLU: 14k questions) can take hours on CPU.
- The `local-completions` model type expects vLLM-style API.
- Results format: JSON in `--output_path` with metrics per task.

## References

- `llama.cpp`: https://github.com/ggml-org/llama.cpp
- `vLLM`: https://github.com/vllm-project/vllm
- `lm-evaluation-harness`: https://github.com/EleutherAI/lm-evaluation-harness
- `huggingface-local-models` skill: for GGUF model discovery via `hf search`
