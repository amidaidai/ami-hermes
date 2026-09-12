# 2026-09-12 晚 · 全通道体检明细（辅助槽位 / 中转身份 / 兜底排序）

触发语：「是什么模型？看一下我们现在有什么模型，哪一些是可以作为主模型的哪一些路由好一点？全面检查」。

## 骨架结论

- 本会话实际：`custom`（b.ai 中转）/ `deepseek-v4.1-flash`；`config.yaml` 默认：`openai-codex` / `gpt-5.6-luna`（不一致，属会话级覆盖）。
- MoA：`active_preset` 为空 = 未激活；`AMI` 预设 enabled 但不在主路由上；`default` 预设的参考 `minimax/minimax-m3:free` 已转付费（404）。

## 探针（同一脚本、同一天）

| 通道 | 工具调用 shape | 读图（真实 TV 截图） | 探针延迟 | 实战延迟（agent.log 聚合） |
|---|---|---|---|---|
| custom:b.ai（47 模型，中转） | COMPLETE（flash / luna / opus-5 / glm-5.2 / kimi-k3 全过） | 四项全对：flash 7.3s、luna 6.9s、opus-5 12.9s（写「≈76,400」偏保守）、gemini-3.1-pro 输出破损 | flash 2.1s / luna 1.9s / opus-5 2.9s / glm-5.2 2.2s / kimi-k3 11.7s | `deepseek-v4.1-flash` 6.0s（16 次） |
| openai-codex | COMPLETE（真实 terminal 调用） | 未单测（当日 429） | — | `gpt-5.6-luna` 10.0s（850 次）、`gpt-6-astra` 12.8s |
| openrouter（免费池 22 个） | COMPLETE：lightning / ultra-550b / super-120b / ling-fin / nex-n2.5-pro | dots-3-note 四项全对；nex-n2.5-pro 空 content | super-120b 2.1s / ling-fin 1.5s / ultra 4.4s / lightning 7.1s | `nemotron-3.5-lightning:free` 16.3s（87 次） |
| xai-oauth | COMPLETE（grok-4.3 1.5s、grok-4.6 6.3s） | 未单测 | 1.5–6.3s | `grok-4.6` 13.8s（169 次） |
| deepseek 直连 | — | — | `HTTP 402 Insufficient Balance` | 最后一次成功 9-11 14:17（此前 2055 次的工作马） |
| ollama-cloud | — | — | `Primary auth failed → fallback`（OLLAMA_API_KEY 为空） | — |
| nous / copilot | — | — | `relogin_required` / classic PAT 不支持 | — |

## 当天故障时间线（errors.log，按日期过滤）

- 15:53 `openai-codex` 429 `usage_limit_reached`（多个 runner 同时中招），**同一分钟** `tools.vision_tools: Error analyzing image: 429` → 视觉槽 auto 跟随主模型的直接证据。
- 15:55 / 16:04 `openai-codex` `AuthenticationError`。
- 16:35 / 17:06 `xai-oauth` `APIConnectionError`（重试后成功，属瞬态）。
- 19:25 `hermes_cli.copilot_auth: Token from GITHUB_TOKEN is not supported: Classic Personal Access Tokens (ghp_*)`。
- 19:35 `Primary provider auth failed ... provider 'ollama-cloud'` → 落到 openrouter 兜底。
- 每次都出现的配置噪音：`providers.xai-oauth: unknown config keys ignored: type`。

## 视觉槽钉死 + 三层验证（本次实际执行）

```bash
cp config.yaml "config.yaml.bak.$(date +%Y%m%d_%H%M%S)_before_vision_pin"
hermes config set auxiliary.vision.provider "custom:b.ai"
hermes config set auxiliary.vision.model "gpt-5.6-luna"
```

1) 解析层（Hermes venv python）：

```python
from agent.auxiliary_client import resolve_vision_provider_client
prov, client, model = resolve_vision_provider_client()
print(prov, model, type(client).__name__)   # → b.ai gpt-5.6-luna OpenAI
```

2) 真图（同 client 直接发真实截图）：读回 `BTCUSDT.P / 15分钟 / 77,162.2 / 76,000.3`，与我本人读图一致。

3) 现场：会话内 `vision_analyze` 同一张图，`agent.log` 记 `Image analysis completed` + 工具 6.62s（与该通道实测 6.9s 同档），无 429、无 fallback。

## 兜底链重排

`lightning(最慢) → ultra → super-120b` 改为 `super-120b(2.1s) → ultra → lightning`，并用 `hermes config set fallback_providers '[...]'` 后读回确认 `type=list, len=3`。

## 读图夹具真值（可复用）

`D:\Hermes agent\tools\tradingview-mcp\screenshots\btc_now_latest_15m.png`（mtime 2026-09-12 13:26 BJT）：真值 = BTCUSDT.P / 15m / 最后价 77,162.2 / 可见低标注「周五低 76,000.3」/ 副窗 1 个 `AggVol`。与 Binance 现货同刻（13:15 bar 77,196–77,258、13:26 ≈ 77,220）微差属合约贴水，同波动维度内不构成品种错配。

## 未决（交用户定，不要自行改）

- 主模型是留 `openai-codex/gpt-5.6-luna`（独立通道但会 429）还是换 `custom:b.ai/deepseek-v4.1-flash`（快、但不透明中转）。
- OpenRouter key 的 `limit=1` 已用满（账户额度 15 / 已用 1.43）：付费能力是「提高 key limit 就能恢复」，不是欠费。
- Ollama 的 `OLLAMA_API_KEY` 缺失使「视觉优先 Ollama（qwen3.5:397b）」当前无法执行；要么补密钥、要么承认视觉走中转。
- 残留 0 凭据 provider（xiaomi / custom:www.micuapi.ai / custom:ccapi.us）、`prefill_trading_rules.json` 里写死的「默认使用当前单模型 GPT-5.6 Luna」、cron 里钉的中转模型名 `deepseek-v4-flash-vision-exp` 待规范化。
