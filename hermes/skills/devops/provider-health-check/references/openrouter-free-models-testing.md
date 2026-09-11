# OpenRouter Free Models — 批量测试记录

测试日期：2026-06-23
环境：Hermes Agent on Windows 11, MSYS bash, Python 3.11
方法：`execute_code` → urllib → OpenRouter API `/v1/chat/completions`

## 测试结果

测试所有 23 个可用免费模型，调用 `Reply just: OK`（max_tokens=10），间隔 1.5s。

### ✅ 可直接调用 (9)

| 模型 ID | 返回模型 | 上下文 |
|---------|----------|:------:|
| `openrouter/free`（路由器） | 随机选中的免费模型 | — |
| `google/gemma-4-31b-it:free` | google/gemma-4-31b-it-20260402 | 262K |
| `openai/gpt-oss-120b:free` | openai/gpt-oss-120b:free | 131K |
| `openai/gpt-oss-20b:free` | openai/gpt-oss-20b:free | 131K |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | nvidia/nemotron-3-ultra-550b-a55b-20260604 | 1M |
| `nvidia/nemotron-3-super-120b-a12b:free` | nvidia/nemotron-3-super-120b-a12b-20230311 | 1M |
| `nvidia/nemotron-3-nano-30b-a3b:free` | nvidia/nemotron-3-nano-30b-a3b:free | 256K |
| `nvidia/nemotron-nano-12b-v2-vl:free` | nvidia/nemotron-nano-12b-v2-vl:free | 128K |
| `liquid/lfm-2.5-1.2b-instruct:free` | liquid/lfm-2.5-1.2b-instruct-20260120 | 32K |

### ⏳ 被限流 (HTTP 429) — 加余额后可试 (7)

这些模型本身免费，但免费用户请求频率被上游 provider 限制。充值 $5+ 后解限。

| 模型 ID | 上下文 | 说明 |
|---------|:------:|------|
| `qwen/qwen3-coder:free` | 1M | 最想要的——强编码 + 长上下文 |
| `qwen/qwen3-next-80b-a3b-instruct:free` | 262K | |
| `meta-llama/llama-3.3-70b-instruct:free` | 131K | |
| `meta-llama/llama-3.2-3b-instruct:free` | 131K | |
| `nousresearch/hermes-3-llama-3.1-405b:free` | 131K | |
| `cognitivecomputations/dolphin-mistral-24b-venice-edition:free` | 32K | |
| `google/gemma-4-26b-a4b-it:free` | 262K | Gemma 4 的 26B 版 |

### ❌ 彻底不可用 / 空响应 (7)

| 模型 ID | 现象 |
|---------|------|
| `poolside/laguna-m.1:free` | 返回空响应 |
| `poolside/laguna-xs.2:free` | 返回空响应 |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 返回空响应 |
| `nvidia/nemotron-3.5-content-safety:free` | 返回空响应 |
| `nvidia/nemotron-nano-9b-v2:free` | 返回空响应 |
| `cohere/north-mini-code:free` | 返回空响应 |
| `liquid/lfm-2.5-1.2b-thinking:free` | 返回空响应 |

"空响应" = HTTP 200 但 `choices[0].message` 无 `content` 字段。可能是这些模型用了非标准响应格式或需要特殊参数。

## 注意事项

1. **`openrouter/free` 路由器随机选模型** — 不保证选到最好的。需要确定性时用具体 `:free` 模型 ID。
2. **Model ID 经常变** — 今天能用的下周可能 404。重复测试前先 `GET /api/v1/models` 拉最新列表。
3. **429 ≠ 不可用** — 被限流的模型本身是好的，只是免费请求频率超了。休息几分钟或加余额即可。
4. **Hermes 路由 vs OpenRouter 路由** — `openrouter/free` 是 OpenRouter 端的路由器。Hermes 的 `--provider openrouter --model "openrouter/free"` 是 Hermes 把模型名传给 OpenRouter。两者配合使用。
