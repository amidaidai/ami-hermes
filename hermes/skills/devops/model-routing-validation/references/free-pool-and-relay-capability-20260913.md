# 免费池重探 + 中转能力矩阵（2026-09-13 00:30–00:45 BJT 快照）

只读取证：`config.yaml`、`auth.json`、`cron/jobs.json`、`logs/agent.log`、`logs/errors.log` + 直连探针。**未改任何配置。**

## 1. 配置层 vs 现场路由（本机常年不一致，必须分开报）

| 层 | 值 | 备注 |
|---|---|---|
| `model.default` / `model.provider` | `gpt-6-astra` / `custom:b.ai` | 00:25 写入；**带工具必 400**（见 §2） |
| 会话现场路由 | `deepseek-v4.1-flash` / `custom` | 系统提示与 `agent.log` 一致（本会话 n=113，均值 7.2s） |
| `fallback_providers` | b.ai `deepseek-v4.1-flash` → codex `gpt-5.6-luna` → OR `nemotron-3-super-120b-a12b:free` → OR `nemotron-3-ultra-550b-a55b:free` → b.ai `glm-5.3-flash` | 链上第 4 位端点已坏 |
| `auxiliary.vision` | `auto` | 00:27 日志：`Vision auto-detect: using main provider custom:b.ai (gpt-6-astra)` = 视觉跟着坏主模型 |
| 上下文探测 | `Could not detect context length for model 'gpt-6-astra' at https://api.b.ai/v1 — defaulting to 256,000 tokens (probe-down)` | 「主模型坏」的连带症状，别当成真实上下文 |
| `moa` | `default_preset: AMI`（6 参考位：b.ai hy3/mimo-v2.5/qwen3.8-flash/glm-5.3-flash + OR lightning + codex luna；聚合器 b.ai deepseek-v4.1-flash），`active_preset: ""` | AMI 里 hy3 正 429、mimo-v2.5 503 → 手动 `/moa` 会等两三轮 |
| cron | 14 个 job，全部 `no_agent: true` | 其中 `provider=custom model=deepseek-v4-flash-vision-exp` 是残留名，`no_agent` 不解析 → 卫生问题，非死链 |

配置漂移时间线（备份法）：08-29 22:11 vision=openrouter/openrouter/free；09-12 19:49 vision=auto；09-12 20:17 vision=custom:b.ai/mimo-v2.5；09-13 00:22 vision 又回 auto。**vision 被钉过又被重置，每次重置都回到「跟随主模型」。**

## 2. b.ai 中转能力矩阵（47 个目录模型，实测 8 个）

```
gpt-6-astra           带 tools → HTTP 400  Function tools with reasoning_effort are not supported for
                                       gpt-6-astra in /v1/chat/completions. To use function tools, use
                                       /v1/responses or set reasoning_effort to 'none'.
                      不带 tools → 200（同模型同 key，证明是能力矩阵不是模型不存在）
deepseek-v4.1-flash   200  1.6s  tools=1  args={"path": "D:/Hermes agent/docs/系统总览.md"}
deepseek-v4-pro       200  2.3s  tools=1  （1M 上下文，未在链上）
qwen3.8-flash         200  3.4s  tools=1  （读图 36.9s，慢）
kimi-k3               200  4.5s  tools=1
glm-5.3-flash         200  6.9s  tools=1  （链尾兜底）
mimo-v2.5             200 12.0s  tools=0  「我无法帮你读取这个文件…没有访问本地文件系统」→ 只当 MoA 文本参考
hy3                   429
```

链路日志证据（`logs/errors.log`）：

```
00:23:23 WARNING ... error_type=BadRequestError provider=custom:b.ai model=gpt-6-astra
         summary=HTTP 400: Function tools with reasoning_effort are not supported for gpt-6-astra ...
00:23:23 INFO  agent.chat_completion_helpers: Fallback to openai-codex/gpt-6-astra:
         clearing primary credential pool (pool_provider=custom:b.ai) to prevent cross-provider contamination
00:22:34 WARNING ... provider=openai-codex model=gpt-5.6-luna summary=HTTP 429: The usage limit has been reached
```

## 3. OpenRouter 免费池 19 项探针（工具 shape + 延迟）

探针形状：`POST /api/v1/chat/completions`，`tools=[read_file]`，`max_tokens=400`（大模型需 1500），中文 prompt，`ThreadPoolExecutor` 并发。

| 模型 | 工具 | 延迟 | 读图（真图夹具） |
|---|---|---|---|
| nex-agi/nex-n2.5-pro:free | COMPLETE | 1.7s | 能读，但 reasoning 输出慢（20–87s） |
| inclusionai/ling-3.0-flash-vl:free | COMPLETE | 1.7s | 一次空回复、一次 429 → 不可靠 |
| nvidia/nemotron-3.5-lightning:free | COMPLETE | 2.0s（重探 7.4s） | 非视觉（1M ctx） |
| inclusionai/ling-3.0-flash-sante:free | COMPLETE | 2.0s | — |
| cohere/north-mini-code:free | COMPLETE | 2.1s | — |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | COMPLETE | 2.3s（读图 67.6s） | ✅ 准 |
| dots-studio/dots-3-note-preview:free | COMPLETE | 2.4s（读图 24.9s） | ✅ 准 |
| nex-agi/nex-n2.5-mini:free | COMPLETE | 2.5s | ❌ 400 |
| inclusionai/ling-3.0-flash-fin:free | COMPLETE | 2.7s | 非视觉（金融专精） |
| poolside/laguna-s-2.1:free | COMPLETE | 2.8s | — |
| nvidia/nemotron-3-super-120b-a12b:free | COMPLETE（需 max_tokens≥1500） | 5.2s（会话均值 32.6s） | ❌ 404 `No endpoints found that support image input` |
| nvidia/nemotron-3-ultra-550b-a55b:free | ❌ 坏端点 | — | — |
| poolside/laguna-xs-2.1:free | 429 | 1.3s | — |
| liquid/lfm-2.5-2.6b:free | 429 | 1.6s | — |
| google/gemma-4-31b-it:free | 429 | 3.1s | — |
| thinkingmachines/inkling:free / -small:free | 403（agentic harness 专用，历次一致） | — | — |
| nvidia/nemotron-3.5-content-safety:free / gemma-4-26b:free | 未探（非通用/已知限流） | — | — |

## 4. 视觉夹具（带外部真值）

- 夹具图：`D:/Hermes agent/tools/tradingview-mcp/screenshots/BTCUSDT_15m_20260912_234850.png`（1920×994，mtime 23:48:51 BJT）
- 外部真值：`GET api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m`（23:45 收 77,380.37；00:00 区间 77,344–77,414）
- 读回值：`nemotron-3-nano-omni-30b` 与 `dots-3-note-preview` 都给 `BTCUSDT.P / 15m / 77,348.7 / 1 副图 AggVol / 高 77,383.5 低 77,340.1`，与轴游标一致（TV 的 `.P` 永续与币安现货微差，属同波动维度，不构成否决）
- `nvidia/nemotron-3-super-120b-a12b:free` 对同一图回 `404 No endpoints found that support image input` → **这是「文本模型」的硬证据**，比任何目录字段都可靠；把它同时当视觉探针的**阴性对照**很好用
- 结论：免费池真读图可行但 25–68s，只能当最后一道；视觉槽仍钉中转/订阅通道

## 5. 其他通道现场状态

| 通道 | 状态 |
|---|---|
| `openai-codex` / `gpt-5.6-luna` | OAuth #1/#3 `429 usage_limit_reached`（随后转 `ready to retry`）；#2 `api_key manual auth failed token_expired (401) (re-auth may be required)` = 死凭据，建议清或重连 |
| `xai-oauth` / `grok-4.6` | `GET https://api.x.ai/v1/models` 200（12 个模型，含 grok-4.6/4.5/4.3）；昨日会话 n=14 均值 17.8s → 唯一还活着的非中转判断源 |
| OpenRouter | `GET /api/v1/key` → `limit=1, limit_remaining=0, usage=1.43`；`GET /api/v1/credits` → `total_credits=15`（key 限额用满 ≠ 账户欠费；要用付费模型须在 OR 后台抬高该 key 的 spend limit） |
| DeepSeek 直连 | 402 Insufficient Balance（09-12 22:52 / 23:14 日志） |

## 6. 可复跑命令形状

```python
# 免费池清单（含模态与价格字段）
GET https://openrouter.ai/api/v1/models   # 过滤 id.endswith(':free')；architecture.input_modalities 判图像
# 工具能力探针（关键：带 tools 与不带 tools 各打一次，才能区分「不支持工具」与「模型不存在」）
POST {base}/chat/completions  {"model":M,"messages":[{"role":"user","content":"用 read_file 读 D:/Hermes agent/docs/系统总览.md"}],"tools":[read_file],"max_tokens":1500}
# 读图探针：data:image/png;base64,... + max_tokens>=3000，读 finish_reason 与 reasoning_tokens 再判
```

脚本化：`scripts/relay_capability_probe.py`。
