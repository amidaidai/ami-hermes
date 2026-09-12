# 2026-09-12 全通道现场清单（快照）

推荐前必须重探。本文件只记录当时状态与探测形状，不当成永久可用表。

## 探测形状（可复跑）

1. `hermes config path` + 读 `model` / `fallback_providers` / `delegation` / `moa` / `auxiliary`（不打印密钥）。
2. `hermes auth list` + `.env` 里哪些 `*_API_KEY` **存在**（只报有/无，不报值）。
3. 分通道拉目录：xAI `/v1/models`、DeepSeek `/models`、OpenRouter `/models` + `/api/v1/key` + `/api/v1/credits`、b.ai `/v1/models` + `/v1/user`。
4. 付费容量与免费容量分开：OpenRouter `limit_remaining=0` 时付费 403，`:free` 仍可能 200。
5. 每个候选一次短文本 + 一次强制 tool_call（`read_file` 一个已知路径）。看 HTTP、`choices[0].message.tool_calls` 长度、响应 `model` 字段。`tools=0` 或 `model=None` 不当主模型。
6. 会话实际路由看系统提示 `Model/Provider`，不要只看 `config.yaml model.default`。

探针脚本可放工作区 `outputs/audit_YYYYMMDD/`；技能内长期脚本仍是 `scripts/or_free_model_probe.py`。

## 当时通道（北京时间约 17:27）

| 通道 | 凭证 | 现场 | 主模型资格 |
|---|---|---|---|
| 本会话 | xAI OAuth `grok-4.6` | 已工具、已路由 | **当时唯一高质量主通道** |
| config 默认 | openai-codex `gpt-5.6-luna` | 429 冷却 | 冷却结束后仍可回驾驶舱 |
| OpenRouter | key 有 | spend limit 用尽；`:free` 通 | 免费只做兜底/委派 |
| DeepSeek 官方 | key 有 | 402 余额不足 | 充值前不可用 |
| b.ai | key 有 | balance=0 | 充值前不可用 |
| Ollama | `.env` 无 key | 未探通 | 不当通道 |

## 当时 OpenRouter `:free`（工具探针）

钉死具体 id，不要钉 `openrouter/free`（动态路由，当时落到 `poolside/laguna-xs-2.1:free`）。

- 首选固定免费：`nvidia/nemotron-3-super-120b-a12b:free`（200 · ~1.2s · tools=1）
- 1M 上下文：`nvidia/nemotron-3.5-lightning:free`（200 · ~2.2s · tools=1）
- 金融子任务：`inclusionai/ling-3.0-flash-fin:free`
- 轻量委派：`nex-agi/nex-n2.5-pro:free` / `mini`
- 代码向：`cohere/north-mini-code:free`
- 不要钉：`nvidia/nemotron-3-ultra-550b-a55b:free`（200 但 tools=0）；`thinkingmachines/inkling:free`（403）；`google/gemma-4-31b-it:free`（400）；config MoA 仍钉的 `minimax/minimax-m3:free`（已转付费，会白等）

## 路由注意

- 辅助槽全是 `auto` 时，主模型切到免费池会把压缩/视觉一起拉差。主通道走 Grok/Luna，压缩另钉便宜通道。
- 交易主模型要真 tool_use，不是文本 OK。免费池过文本探针 ≠ 能出实盘卡。
- 目录里有的旗舰（DeepSeek Flash、b.ai 全家桶）在余额为 0 时是**不可用**，不是候选。
