# OpenRouter 免费池兜底选型实测（2026-09-13 13:05–13:20 BJT 快照）

触发问题：「openrouter 的哪一些免费模型适合兜底」。只读取证 + 直连探针，**未改任何配置**。

## 0. 通道现场（先看这层，否则选型无意义）

| 项 | 值 |
|---|---|
| OpenRouter key | `limit=1` / `limit_remaining=0` / `usage=1.43` → 付费模型全 403「Key limit exceeded (total limit)」；**只有 `:free` 可打** |
| OpenRouter 账户 | `GET /api/v1/credits` → `total_credits=15`（key 限额用满 ≠ 账户欠费，两者分开报） |
| 主模型 | `config.yaml` `model.default=deepseek-v4.1-flash` / `provider=custom:b.ai`；日志 12:51 `credit insufficient balance: balance=1746181 required=1855720` → 中转余额也会打满 |
| Codex | 当天 429 `usage_limit_reached`（plus，`resets_in_seconds` 倒计时） |
| `fallback_providers` | **当前 config.yaml 里没有这个键**。09-12 21:13 备份里是 `nemotron-3-super-120b-a12b:free → nemotron-3-ultra-550b-a55b:free → ling-3.0-flash-fin:free`；09-12 19:49 备份是 `lightning → ultra → super` |
| MoA | `default_preset=AMI`（enabled=true，`active_preset=""`）；AMI 参考位含 `nemotron-3.5-lightning:free`；`presets.default`（enabled=false）仍钉着已转付费的 `minimax/minimax-m3:free` |

**grep 陷阱**：`grep ':free' config.yaml` 命中的是 `moa.presets.*.reference_models`（行 329–332、344–345），不是兜底链。要确认兜底链是否健在，直接查顶层 `fallback_providers` 键（或 walk 所有含 `fallback` 的键）。

## 1. 工具调用 shape（带 `read_file` tools，`max_tokens=1500`，并发 10）

13/19 COMPLETE：

| 模型 | 延迟 | shape |
|---|---|---|
| cohere/north-mini-code:free | 1.1s | COMPLETE |
| nvidia/nemotron-3.5-lightning:free | 1.2s | COMPLETE |
| nvidia/nemotron-3-super-120b-a12b:free | 1.2s | COMPLETE |
| liquid/lfm-2.5-2.6b:free | 1.2s | COMPLETE |
| openrouter/free | 1.2s | COMPLETE（**落到 `cohere/north-mini-code:free`**，动态路由不可控） |
| poolside/laguna-s-2.1:free | 1.4s | COMPLETE |
| nex-agi/nex-n2.5-pro:free | 1.5s | COMPLETE |
| inclusionai/ling-3.0-flash-fin:free | 1.6s | COMPLETE |
| inclusionai/ling-3.0-flash-sante:free | 1.6s | COMPLETE |
| dots-studio/dots-3-note-preview:free | 1.6s | COMPLETE |
| inclusionai/ling-3.0-flash-vl:free | 1.7s | COMPLETE |
| nex-agi/nex-n2.5-mini:free | 1.8s | COMPLETE |
| nvidia/nemotron-3-ultra-550b-a55b:free | 2.2s | COMPLETE |

不可用：

- `thinkingmachines/inkling:free` / `inkling-small:free` → 403「only available on agentic harnesses」（历次一致）
- `poolside/laguna-xs-2.1:free` / `google/gemma-4-31b-it:free` / `google/gemma-4-26b-a4b-it:free` → 429「temporarily rate-limited upstream」
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` / `nvidia/nemotron-3-ultra-550b-a55b:free` → **间歇性 HTTP 200 + error body**（见 §3）
- `nvidia/nemotron-3.5-content-safety:free`（tools 支持字段为 false）、`google/lyria-3-*`（音乐）→ 与交易无关

**延迟读法**：1–2s 是「模型直接回 tool_call 的首包」，不是生成延迟。真实体感看 §2。

## 2. 纯文本延迟（无工具，中文档位复述，`max_tokens=1200`）

dots 1.9s · north-mini-code 2.0s · ling-3.0-flash-fin 2.5s · nex-n2.5-pro 2.6s · super-120b 4.9s · **nemotron-3.5-lightning 9.4 / 62.2 / 114.5s**（三次抖动 12 倍，reasoning 模型，1M ctx 也救不了）。

→ 结论：`nemotron-3.5-lightning:free` 探针 1.2s 但纯文本 9–114s，**不能排兜底链第 1 位**（与「兜底链按实测延迟排序」一节的老结论互相印证）。

## 3. Nvidia 免费池的「200 + error body」形状

```json
{"id":"gen-…","object":"chat.completion","error":{
  "message":"Upstream error from Nvidia: ResourceExhausted: Worker local total request limit reached (1843/16)",
  "code":502,"metadata":{"error_type":"provider_unavailable"}}}
```

HTTP 状态仍是 200，`choices` 键不存在 → 直接 `d["choices"][0]` 的探针抛 `KeyError: 'choices'`，会把上游过载误报成「模型坏」。

复测同批同模型几分钟后：`ultra-550b` 带工具 200 + tool_calls COMPLETE（2.7s / 4.2s）、不带工具 11.6s 正常。**属间歇性，不能一次定性除名。**

## 4. 真图夹具（外部真值 + 人眼基准）

- 夹具：`D:/Hermes agent/tools/tradingview-mcp/screenshots/BTCUSDT_15m_20260913_130440.png`（mtime 13:04:40 BJT）
- 币安现货真值：15m 12:45 收 77,210.01 / 13:00 收 77,238.86；1m 13:03 收 77,214.01 / 13:04 收 77,219.45
- 主模型 `vision_analyze` 亲自核验（人眼基准）：`BTCUSDT.P / 15分钟 / 77,194.2 / 1 个副图窗格 AggVol（窗格内 Signal 图例）/ 可见 78,442.7–75,600.0`

| 模型 | 延迟 | 品种 | 周期 | 价格 | 副图 |
|---|---|---|---|---|---|
| inclusionai/ling-3.0-flash-vl:free | 17.8s | BTCUSDT.P ✅ | 15分钟 ✅ | 77,194.2 ✅ | 2 个（AggVol + 无名粉线）≈ |
| dots-studio/dots-3-note-preview:free | 24.6s | BTCUSDT.P ✅ | 15分钟 ✅ | 77,194.2 ✅ | 2 个（AggVol + 无名）≈ |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | 122.9s | BTCUSDT.P ✅ | 15 ✅ | 77,194.3 ✅ | 2 个（AggVol、Signal）✅ |
| nex-agi/nex-n2.5-pro:free | 131.8s | — | — | 空（`finish_reason=length`，reasoning 吃光 4000） | — |
| nvidia/nemotron-3-super-120b-a12b:free | 2.3s | 404「No endpoints found that support image input」 | — | — | — |

**判读更正**：三个独立免费模型 + 主模型人眼基准读到的 77,194.2 是**正确的**（TV 上 BTCUSDT.P 当时的报价）。此前把它当成「价格轴游标误读」，是因为拿**币安现货 15m 收盘**（77,238.86）当真值——永续 vs 现货属同波动维度微差，不构成否决。真值应取**截图分钟附近的 1m K 线**。

`super-120b` 的 404 是「文本模型」最可靠的硬证据，适合当视觉探针的阴性对照。

## 5. 推荐形状（回答「哪些适合兜底」）

| 槽位 | 选谁 | 判据 |
|---|---|---|
| 免费链第 1 位 | `inclusionai/ling-3.0-flash-fin:free` | 2.5s 出文、工具✅、金融专精 |
| 免费链第 2 位 | `cohere/north-mini-code:free` 或 `nex-agi/nex-n2.5-pro:free` | 1.1–1.5s 工具✅、1.9–2.6s 出文 |
| 免费链第 3 位 | `nvidia/nemotron-3-super-120b-a12b:free` | 120B/262K、4.9s 出文、需 `max_tokens≥1500`、**禁出实盘卡**（无真工具结果会编造占位截图） |
| 免费视觉兜底 | `inclusionai/ling-3.0-flash-vl:free` → `dots-studio/dots-3-note-preview:free` | 17.8s / 24.6s，读图全对；≥18s 只能排最后一道 |

不要进链：lightning（9–114s 抖动）· ultra-550b / nano-omni（间歇上游过载）· lfm-2.5-2.6b（2.6B 太小）· openrouter/free（动态路由落到谁不可控）· inkling ×2（403）· laguna-xs-2.1 / gemma ×2（429）。

## 6. 可复跑

- 视觉 fanout：`scripts/or_vision_fixture_probe.py`（后台 + JSONL 增量落盘；**别放 execute_code**，300s 单元上限会 kill 掉 5-way 读图并把中间结果全丢）
- 工具/目录探针：`scripts/relay_capability_probe.py`、`scripts/or_free_model_probe.py`
- 清单纯度：`GET https://openrouter.ai/api/v1/models`，过滤 `pricing.prompt==0 and pricing.completion==0`；`architecture.input_modalities` 判图像，`supported_parameters` 判 tools
- key 限额 vs 账户余额：`GET /api/v1/key`（`limit_remaining`）与 `GET /api/v1/credits`（`total_credits`）分开看
