# 2026-09-10 全通道模型审计 · 同题横评 · 视觉夹具 · 免费池重探

审计背景：用户问「我现在有的模型应该怎么推荐 —— MoA 与不用 MoA 两种情况」。
下面全部是现场实测（真请求、真工具调用、真读数），不是目录/参数量推断。

## 1. 实际拥有的通道（凭证 → 可达性）

| 通道 | 可用模型 | 实测 | 额度性质 |
|---|---|---|---|
| openai-codex（OAuth） | gpt-6-astra(priority 1) · gpt-5.6-sol(6) · gpt-5.6-terra(7) · gpt-5.6-luna(8) · gpt-5.5 · gpt-5.4-mini（隐藏：gpt-reserve、codex-auto-review） | 全部工具链路通过；luna 23s / sol 34s / astra 49s（端到端含启动） | 订阅制，窗口限速 |
| xai-oauth（OAuth） | grok-4.6 · grok-4.5 · grok-4.3 · grok-4.20-0309-{reasoning,non-reasoning,multi-agent} · grok-build-0.1（+imagine 图/视频） | grok-4.6 工具✅ 24s，但流式不稳（见 §4） | 订阅制 |
| deepseek（按量） | `deepseek-flash`(=V4.1-Flash) · `deepseek-v4-pro` | 工具✅ 14s；真实会话均值 5.1s | 极便宜 |
| openrouter | 21 个真免费；付费被 key 限额挡住（403） | 免费层可用 | **key limit $1 已用满**，账户还有 $13.57 |
| nous | — | ❌ `providers.nous.last_auth_error.relogin_required: true` | 登录失效 |
| copilot | — | ❌ `No usable credentials found`（.env 有 GITHUB_TOKEN 但非 Copilot 授权） | 不可用 |
| ollama-cloud | — | ❌ 无 `OLLAMA_API_KEY`；`config.yaml providers:` 也未定义 | 不可用 |

注意：`config.yaml` 的 `providers:` 只列了 deepseek/openrouter/xai-oauth，但 `auth.json` 的 `credential_pool` 还挂着 copilot/ollama-cloud 等 —— **凭证存在 ≠ 通道可用**，要逐层查。

## 2. 同题横评（决策卡 + 裁决陷阱）

固定证据包：BTCUSDT 现价 108,420；1D/4h SVP 多头持有、15m 空头反转并跌破 108,600、5m 量价背离；资金费率 +0.0108%、OI -3.2%、Taker 0.94；**S0 missing、S3 冲突**；X 偏空未验证；FinalVerdict=WAIT(executable=false)。
命令：`hermes chat --query-file <fixture> --provider P --model M -t file --ignore-rules -Q --yolo`。

| 模型 | 端到端 | WAIT | 三件套清空 | 唯一⭐ | 编造 | 信息完整度 |
|---|---|---|---|---|---|---|
| deepseek-v4-flash | **16s** | ✅ | ✅ | ✅ | 无 | **最全**（点出 ATR 缺失、1D/4h 与 15m 行动格未收敛、给条件观察候选） |
| gpt-5.6-luna | 22s | ✅ | ✅ | ✅ | 无 | 合规但压缩 |
| gpt-6-astra | 46s | ✅ | ✅ | ✅ | 无 | 合规完整 |
| grok-4.6 | 29s（首次 67s 失败） | ✅ | ✅ | ✅ | 无 | 合规 |
| nemotron-super-120b:free | 46s | ✅ | ✅ | ✅ | 数字未编造，**伪造一行「看盘截图(MEDIA)」占位** | 最薄 |

结论：合规/保真/速度三项上 DeepSeek 不输订阅模型，而便宜 1–2 个数量级。单题样本，不作为绝对质量排序。

## 3. 视觉夹具（带交易所真值）

夹具：`tools/tradingview-mcp/screenshots/BTCUSDT_15m_20260905_0100.png`（文件 mtime = 2026-09-05 02:26 BJT）。
真值：Binance 公开 K 线 15m — 02:15 收盘 79,534.55 / 02:30 开盘 79,534.56。

| 模型 | 品种 | 周期 | 最后价格 | 副窗格 | 结果 |
|---|---|---|---|---|---|
| deepseek-v4-flash | BTCUSDT.P ✅ | 15m ✅ | **79,536.2** ✅ | 1 个 AggVol ✅ | 通过 19s |
| gpt-5.6-luna | BTCUSDT.P ✅ | 15m ✅ | 79,536.2 ✅ | 1 个 AggVol ✅ | 通过 25s |
| gemma-4-31b-it:free | — | — | — | — | ❌ 真实图片请求 429 |

差异只在可见区间最低价一处（deepseek 76,927.3 vs luna 76,300），不影响结论。
要点：**读图能力可用交易所真值直接判分，不需要人眼**；免费视觉候选会在真实图片路径上 429。

## 4. 失败模式与重跑规则

- grok-4.6 经 xai-oauth 三次调用中两次失败，报 `Codex stream produced no SSE events for 12s after first byte`；重跑即成功。→ 单次零事件失败先重跑一次再评分；MoA 参考层少一个成员不影响整体跑完。
- `minimax/minimax-m3:free` 服务端原文：`This model is unavailable for free. The paid version is available now - use this slug instead: minimax/minimax-m3`。当时 AMI 预设与 delegation 都钉着它，MoA 实跑（72s）就在这一成员上白等一轮。

## 5. 真实会话延迟 / 成本（logs/agent.log 聚合）

| provider/model | n | avg_in | avg_out | avg_latency |
|---|---|---|---|---|
| deepseek/deepseek-v4-flash | 45 | 70,976 | 961 | **5.1s** |
| openai-codex/gpt-5.6-luna | 3 | 11,509 | 61 | 16.1s |
| openai-codex/gpt-6-astra | 3 | 11,476 | 13 | 15.1s |
| openai-codex/gpt-5.6-sol | 3 | 11,479 | 59 | 11.0s |
| xai-oauth/grok-4.6 | 3 | 13,250 | 251 | 7.1s |
| openrouter/nemotron-super-120b:free | 2 | 4,570 | 124 | 5.5s |
| moa/AMI | 2 | 5,713 | 965 | 7.6s |

DeepSeek 官方价格（元/百万 token，来源 api-docs.deepseek.com/zh-cn/quick_start/pricing）：

| 模型 | 输入(缓存命中) | 输入(未命中) | 输出 |
|---|---|---|---|
| deepseek-flash | 0.02 / 0.04 | 1 / 2 | 4 / 8 |
| deepseek-v4-pro | 0.15 / 0.30 | 4.5 / 9 | 13.5 / 27 |

（左=空闲时段，右=高峰；高峰为北京时间周一至周五 09:00–12:00、14:00–18:00。）
按实测 71K in / 961 out：单次 ≈ ¥0.075（空闲）～¥0.15（高峰）；100 次/天 ≈ ¥8–15/天。

DeepSeek V4.1-Flash 能力：1M 上下文、输出上限 384K、工具调用✅、**图像理解✅**、并发 2500。
旧别名 `deepseek-v4-flash`、`deepseek-v4-flash-vision-exp` 仍可调用但落到 V4.1-Flash。
**`deepseek-v4-pro` 北京时间 2026-09-14 12:00 后全部路由到 Flash 并按 Flash 计费**（官方自述 V4.1 Flash 全面超越 V4 Pro）。

## 6. 本次给出的分工建议（待用户确认，配置尚未落地）

- 不用 MoA：主模型 deepseek-flash；升级档 gpt-6-astra（手切）；兜底链 deepseek-flash → openai-codex/luna → nemotron-super:free；委派/压缩/视觉 = deepseek-flash（视觉已过夹具）；x_search 保持 grok-4.20-non-reasoning。
- 用 MoA（AMI）：参考 grok-4.6 + nemotron-3.5-lightning:free + ling-3.0-flash-fin:free + gpt-5.6-sol；汇总 gpt-6-astra；`active_preset` 留空手动升级。实测 MoA 72s+、5 次调用，日常档不值。
- 待办：主模型改名后 `prefill_messages_file` 里写死的模型文案要同步；OpenRouter key 抬限额才能用付费参考。
