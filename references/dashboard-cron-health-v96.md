# 棠溪驾驶舱 v9.6 · 六市场分析流程与 cron 健康

更新时间：2026年6月29日22：32

## 驾驶舱分析标准流程

| 市场 | 品种 | full 步骤 (按序) | quick 步骤 | 主周期 | 数据源 |
|---|---|---|---|---|---|
| 加密 | BTCUSDT | tv→binance→cg_pro→macro→x_sent→cron_read→cvd→depth→corr→card | tv→binance→macro→x_sent→card | 15m | TV SVP/ Binance OI Funding Taker / CG / X / Poly / Deribit / Dune |
| 贵金属 | XAUUSD | tv→macro→x_sent→cron_read→cvd→corr→gold_macro→card | tv→macro→x_sent→card | 5m | TV结构 / gold-api / 金十 / DXY US10Y / GLD GDX TIP / COT |
| 外汇 | EURUSD | tv→macro→x_sent→cron_read→corr→forex_rate→card | tv→macro→x_sent→card | 15m | TV结构 / DXY 利差 / 央行窗口 / COT / 事件日历 |
| 股票 | AAPL | tv→macro→x_sent→cron_read→corr→fmp→options_chain→card | tv→macro→x_sent→card | 1h | TV结构 / VIX SPX / 财报基本面 / 板块 / 期权链 |
| 期货 | ES1! | tv→macro→x_sent→cron_read→corr→card | tv→macro→x_sent→card | 15m | TV结构 / COT / 宏观事件 / 跨资产相关 |
| 期权 | BTC-CALL | tv→options_chain→card | tv→card | 跟底层 | 标的结构 / IV Greeks OI / 到期 MaxPain |

每步做什么详见 `references/analysis-flow-capability-map-v96.md`。

## GO/NO-GO 硬闸门（下单前七问）

| # | 闸门 | 权重 | 红灯条件 |
|---:|---|---|---|
| 1 | 数据新鲜度 | 2 | ≤B级或快照>1h |
| 2 | TV现场确认 | 2 | SVP未读或方向冲突 |
| 3 | R:R底线 | 2 | 首选R:R < 1:2 |
| 4 | 事件窗口 | 1 | 重大数据/FOMC/NFP窗口内 |
| 5 | 风控保护 | 2 | Protections拦截 |
| 6 | 样本/WFO | 1 | 样本<20或WFO<0.5 |
| 7 | 组合暴露 | 1 | 相关>0.7或组合>15% |

任一红灯 → NO-GO，禁止执行。已接入 auto_card 全卡尾部。

## 当前 cron 清单（17个，清理后）

| # | 名称 | 频率 | 类型 | 成本 |
|---:|---|---|---|---|
| 1 | 每日技能SkillMCP更新 | 07:00 | no_agent | $0 |
| 2 | OpenRouter免费模型同步 | 07:00 | no_agent | $0 |
| 3 | 每日系统审计 | 07:20 | no_agent | $0 |
| 4 | 每日系统备份 | 07:45 | no_agent | $0 |
| 5 | BTC关键位同步 | 10:00,22:00 | LLM(2x/d) | ~$0.06/d |
| 6 | Orion全市场雷达 | 9-23 */30m | no_agent | $0 |
| 7 | Dune链上刷新 | */2h | no_agent | $0 |
| 8 | COT报告刷新 | 周六08:00 | no_agent | $0 |
| 9 | Deribit期权刷新 | */15m | no_agent | $0 |
| 10 | BTC守护看门狗 | */5m | no_agent | $0 |
| 11 | 每日复盘提醒 | 22:00 | LLM(1x/d) | ~$0.03/d |
| 12 | X情绪刷新 | */30m | no_agent | $0 |
| 13 | 清算压力监控 | */30m | no_agent | $0 |
| 14 | 稳定币供应监控 | */2h | no_agent | $0 |
| 15 | 数据新鲜度看门狗 | */15m | no_agent | $0 |
| 16 | QLib因子信号 | */30m | no_agent | $0 |
| 17 | 交易执行桥接 | */30m | no_agent | $0 |

**月成本估算**：~$0.09/d × 30 = ~$2.70/月（仅 BTC关键位同步 + 每日复盘提醒使用LLM）

## 已终止的 cron（3个LLM分析cron）

| 名称 | 原频率 | 月成本 | 原因 |
|---|---|---|---|
| Orion雷达分析 | 9-23 */30m | ~$43/mo | 原始数据已由no_agent采集，LLM解读属重复 |
| QLib因子解读 | */30m | ~$43/mo | 因子信号已由no_agent脚本落盘 |
| 清算压力推演 | */30m | ~$43/mo | 清算数据已由no_agent采集 |

终止后月节省 ~$129 → 回到 $5/月预算内。

## XAU 分析卡改善

之前：所有价位 = 现价，描述 "XAU 4h K线待TV MCP采集"
现在：使用 gold-api 现货价 + 金十 24h高/低，推算 VAH/VAL/POC
实测：XAU$4,027 · 日内高4,086 低4,000 · VAH 4,056 VAL 4,001

## 当前运行态

| 守护 | 状态 | 心跳 |
|---|---|---|
| 行情守望 | running | <1min |
| BTC daemon | running | <1min |
| BTC关键位同步 | ok | 最后: 20:13 |

| 数据 | 新鲜度 |
|---|---|
| BTC快照 | <1h |
| XAU快照 | <1h |
| xau_macro | <1h |
| strategy_model_stats | <1h |
| btc_signal | 147h (仅交易时写入) |
| protections_state | 199h (无交易无变更) |
| strategy_governance | 238h (月度更新) |

| 测试 | 状态 |
|---|---|
| pytest | 116 passed |
| BTC auto_card | GO/NO-GO 七问正常 |
| XAU auto_card | GO/NO-GO 七问正常 |

## 下一轮建议

| 优先级 | 动作 |
|---|---|
| P1 | 复盘闭环：auto_card 自动生成 A/B/C 预评级并写 trade_plans |
| P1 | 116 dirty files → 大归档 |
| P2 | 期权卡加入 IV/Greeks |
| P2 | protections_state 自动刷新（无交易时30min心跳标记） |
