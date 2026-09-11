# 驾驶舱架构 v9.4 (2026-06-29)

## 守护进程（2个）

| 进程 | 脚本 | 监控 | 推送 | Token |
|------|------|------|------|-------|
| 行情守望 | `行情守望.py` | BTC+XAU 实时价格 | 写入 snapshot JSON | 0 |
| BTC守护 | `btc_daemon.py` | BTC 多因子评分 ≥8 | btc_push_386 → TG:386 | 0 |

## Cron 任务（17个）

| 名称 | 频率 | 类型 | 投递 | Job ID |
|------|------|------|------|--------|
| 每日SkillMCP更新 | 07:00 | no_agent | TG:846 | a88f5b994caa |
| OpenRouter模型同步 | 07:00 | no_agent | local | 73ce98436fb1 |
| 每日系统审计 | 07:20 | no_agent | TG:846 | ea5e5b9cbebd |
| 每日系统备份 | 07:45 | no_agent | TG:846 | 330c626c53c2 |
| BTC关键位同步 | 每4h | LLM | TG:846 | ada5d94913fd |
| Orion全市场雷达 | 每30min, 9-23 | no_agent | TG:846 | ef4cf5f7cd24 |
| XAUUSD监控 | 每5min, 8-23 | no_agent | TG:846 | e55cc21726b9 |
| ETF Flow刷新 | 每4h | no_agent | TG:846 | 78fdecc04c7f |
| Dune链上刷新 | 每2h | no_agent | TG:846 | 3a8bee120dd4 |
| COT报告刷新 | 周六 08:00 | no_agent | TG:846 | b664f56f904c |
| Deribit期权刷新 | 每15min | no_agent | TG:846 | 0764c6922694 |
| BTC守护看门狗 | 每5min | no_agent | local | 54661a43c839 |
| 每日复盘提醒 | 22:00 | LLM | TG:846 | f71dcf102007 |
| **X情绪刷新** | **每30min** | **no_agent** | **TG:846** | **d6247e06ac30** |
| **清算压力监控** | **每30min** | **no_agent** | **TG:846** | **5db6dd683b1d** |
| **稳定币供应监控** | **每2h** | **no_agent** | **TG:846** | **5f7192fd9029** |
| **数据新鲜度看门狗** | **每15min** | **no_agent** | **TG:846** | **155082fc5e34** |

**新增4项加粗标记（v9.4）**

## 月 Token 消耗

- BTC关键位同步: ~$3/月（仅LLM cron）
- 每日复盘提醒: ~$0.50/月（每天1次）
- 总计: ~$3.50/月

## 数据采集器（按脚本）

| 脚本 | 数据源 | 输出 | 状态 |
|------|--------|------|:--:|
| x_sentiment_collector.py | CG trending + 恐贪 | 情绪摘要 | ✅ v9.4 |
| liquidation_collector.py | Binance OI×价格联动 | 清算压力 | ✅ v9.4 |
| stablecoin_collector.py | DeFiLlama免费API | USDT/USDC/DAI | ✅ v9.4 |
| data_freshness_watchdog.py | 本地文件mtime | 过期告警 | ✅ v9.4 |
| etf_flow_collector.py | SoSoValue | ETF 日净流 | ❌ Cloudflare封 |
| dune_collector.py | Dune Analytics | BTC流/CEX净流 | ✅ |
| cot_collector.py | CFTC | 持仓报告 | ✅ |
| deribit_options.py | Deribit | 期权OI/MaxPain | ✅ |
| orion_screener_radar.py | Orion+Binance+CG | 全市场异动 | ✅ |
| gold_monitor.py | Yahoo+Jin10 | XAU触发 | ✅ |

## 引擎接线状态

| 引擎 | 行数 | v9.3 | v9.4 |
|------|:--:|:--:|:--:|
| dmi_decision.py | 368 | 未接 | ✅ 已接线 pipeline_integration.py |
| trading_system.py | 980 | 未接 | 未接 |
| risk_constitution.py | 739 | 未接 | 未接 |
| five_model_matcher.py | 569 | 未接 | 未接 |
| scoring_engine.py | 511 | 未接 | 未接 |
| vwap_ema_cvd_engine.py | 476 | 未接 | 未接 |
| cvd_analyzer.py | 367 | 未接 | 未接 |
| orderflow_absorption.py | 294 | 未接 | 未接 |
| render_tv_card.py | 497 | 未接 | 未接 |
| backtest_runner.py | 713 | 未接 | 未接 |
| regime_backtest.py | 301 | 未接 | 未接 |

## MarkdownV2 表格乱码注意

Telegram MarkdownV2 不支持 `|` 管道表格语法。Hermes 适配器检测到 MarkdownV2 错误后降级为纯文本，降级过程可能导致 emoji/特殊字符乱码。脚本 UTF-8 输出本身无问题——问题在 Telegram 网关层。含表格的 cron 输出在 TG 端可能显示异常。
