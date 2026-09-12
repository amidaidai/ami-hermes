# 「为什么不是 GPT」现场快照（2026-09-13）

用户问「什么模型」→「为什么不是GPT」。以下是当时的只读取证结果，**仅当天快照，勿当持久事实**。

## 配置层（config.yaml）

| 位置 | 值 |
|---|---|
| `model.default` | deepseek-v4.1-flash |
| `model.provider` | custom:b.ai |
| `fallback_providers[0]` | custom:b.ai / gpt-6-astra |
| `fallback_providers[1]` | openai-codex / gpt-6-astra |
| `fallback_providers[2]` | custom:b.ai / deepseek-v4.1-flash |
| `fallback_providers[3..6]` | openrouter `:free` 三席 + openai-codex / gpt-5.6-luna |
| `moa.presets.AMI.aggregator` | custom:b.ai / deepseek-v4.1-flash |
| `moa.presets.AMI` references | hy3 · nemotron-3.5-lightning:free · mimo-v2.5 · qwen3.8-flash · gpt-5.6-luna · glm-5.3-flash |
| `image_gen` | provider openai / gpt-image-2-low |
| `auxiliary.vision` | provider `auto`（=跟随主模型，见「辅助槽位 auto」条） |
| `x_search.model` | grok-4.20-non-reasoning |
| `agent.prefill_messages_file` | prefill_trading_rules.json |

## 凭据层（`hermes auth list` 原样）

```text
copilot (1):      GITHUB_TOKEN        api_key env:GITHUB_TOKEN
custom:b.ai (1):  b.ai                api_key config:b.ai ←
deepseek (1):     DEEPSEEK_API_KEY    api_key env:DEEPSEEK_API_KEY ←
ollama-cloud (1): OLLAMA_API_KEY      api_key env:OLLAMA_API_KEY
openai-codex (3): #1 oauth    429 usage_limit_reached (13m 44s left)
                  #2 api_key  401 token_expired (re-auth may be required)
                  #3 oauth    429 usage_limit_reached (13m 44s left)
openrouter (1):   OPENROUTER_API_KEY  api_key env:OPENROUTER_API_KEY ←
xai-oauth (1):    device_code        oauth ←
```

要点：`hermes auth list` 一行就给出通道级可用性，429 带倒计时、401 带「re-auth may be required」；`←` 标记的是生效条目。

## 结论形状（用户要的）

1. **配置层**：主模型本来就设成 b.ai 的 `deepseek-v4.1-flash`；`fallback` 只在主模型报错时才顶上，所以链首位的 `gpt-6-astra` 一次都没轮到。这是用户自己的省钱策略（日常走中转低价快档）。
2. **可用性层**：codex 三个凭据全废（两个 429 限流、一个 401 token 过期），就算把主模型切过去也调不通，只会立刻打到 fallback。
3. **GPT 的实际落点**：`image_gen` 与 MoA AMI 参考位仍在吃 OpenAI 侧，没被弃用。
4. **下一步三选**：等约 14 分钟 429 自动解除 / `hermes auth add openai-codex` 重连修 401 / `hermes chat -m gpt-6-astra --provider custom:b.ai` 临时钉住（前提是中转侧确有该型号）。
