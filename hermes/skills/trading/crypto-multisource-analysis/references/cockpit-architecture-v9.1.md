# 驾驶舱架构 v9.2 (2026-06-29)

## 守护进程（2个）

| 进程 | 脚本 | 监控 | 推送 | Token |
|------|------|------|------|-------|
| 行情守望 | `行情守望.py` | BTC+XAU 实时价格 | 写入 snapshot JSON | 0 |
| BTC守护 | `btc_daemon.py` | BTC 多因子评分 ≥8 | btc_push_386 → TG:386 | 0 |

## Cron 任务（17个）

### 维护类（每天）

| 名称 | ID尾号 | 频率 | 投递 |
|------|------|------|------|
| 每日SkillMCP更新 | a88f..caa | 07:00 | TG:846 |
| OpenRouter模型同步 | 73ce..fb1 | 07:00 | local |
| 每日系统审计 | ea5e..ebd | 07:20 | TG:846 |
| 每日系统备份 | 330c..c2 | 07:45 | TG:846 |
| 每日复盘提醒 | f71d..007 | 22:00 (LLM) | TG:846 |

### 数据采集类

| 名称 | ID尾号 | 频率 | 投递 | 表格化 |
|------|------|------|------|:--:|
| Orion全市场雷达 | ef4c..24 | 每30min(9-23) | TG:846 | ✅ |
| X情绪刷新 | d624..30 | 每30min | TG:846 | ✅ |
| 清算压力监控 | 5db6..1d | 每30min | TG:846 | ✅ |
| QLib因子信号 | fd78..32 | 每30min | TG:846 | ✅ |
| 交易执行桥接 | 2bcc..24 | 每30min | local | — |
| Deribit期权刷新 | 0764..94 | 每15min | TG:846 | ✅ |
| 稳定币供应监控 | 5f71..29 | 每2h | TG:846 | ✅ |
| Dune链上刷新 | 3a8b..d4 | 每2h | TG:846 | ✅ |
| BTC关键位同步 | ada5..fd | 每4h (LLM) | TG:846 | — |
| COT报告刷新 | b664..04c | 周六08:00 | TG:846 | — |

### 守护类

| 名称 | ID尾号 | 频率 | 投递 |
|------|------|------|------|
| BTC守护看门狗 | 5466..39 | 每5min | local |
| 数据新鲜度看门狗 | 1550..34 | 每15min | TG:846 |

## 月 Token 消耗

- BTC关键位同步: ~$3/月（仅LLM cron）
- 每日复盘提醒: ~$0.50/月
- 总计: ~$3.50/月

## 数据采集器（按脚本）

| 脚本 | 数据源 | 输出 | 新增 |
|------|--------|------|:--:|
| orion_screener_radar.py | Orion+Binance+CG | 全市场异动 | |
| x_sentiment_collector.py | CG trending+恐贪 | 情绪表格 | ✅ |
| liquidation_collector.py | Binance OI×价格 | 清算压力 | ✅ |
| qlib_factors.py | QLib 30因子 | 量化信号 | ✅ |
| trade_exec_bridge.py | 信号→日志 | trade_events.jsonl | ✅ |
| deribit_options.py | Deribit | 期权OI/MaxPain | |
| stablecoin_collector.py | DeFiLlama | USDT/USDC/Dai | ✅ |
| dune_collector.py | Dune Analytics | BTC流/CEX净流 | |
| cot_collector.py | CFTC | 持仓报告 | |
| alert_dedup.py | — | 告警去重模块 | ✅ |
| fallback_chain.py | 多源 | IP-ban回退链 | ✅ |
| data_freshness_watchdog.py | 本地文件 | 过期告警 | ✅ |

## 已删除

- XAUUSD监控 (每5分钟刷屏)
- ETF Flow刷新 (SoSoValue Cloudflare封锁)
- BTC深度分析 (每3分钟僵尸任务)
- BTC关键区到价提醒 (僵尸任务)

## 五层架构

| 层 | 得分 | 关键组件 |
|------|:--:|------|
| 数据层 | 4.5 | 17源 + IP-ban回退链 + DeFiLlama |
| 信号层 | 3.5 | SVP v10 + QLib 30因子 + DMI + CVD |
| 策略层 | 3 | risk_constitution + five_model_matcher |
| 执行层 | 2.5 | trading_system + trade_exec_bridge |
| 风控层 | 3 | freshness watchdog + dedup + BTC daemon |

## 输出格式标准

所有TG推送的cron脚本使用Markdown表格（`references/cron-output-table-format.md`），配合去重模块（`references/cron-alert-dedup.md`）防刷屏。
