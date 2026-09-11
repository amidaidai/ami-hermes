# 六市场流程与社区优化对照 v9.6

适用：用户要求“看各个市场分析流程、用了什么能力/skill/搜索、联网看还有什么优化”。

## 本轮使用的技能与能力

| 类型 | 名称 | 用途 |
|---|---|---|
| Skill | `crypto-multisource-analysis` | 六市场 router、五层周期、cron_read、TV/Binance/X/宏观流程 |
| Skill | `trading-card-generation` | 出卡路径、auto_card、模板合规 |
| Skill | `trading-system-audit` | 社区审计、运行态、P0/P1/P2 方法 |
| Web | TradingView footprint | Pine v6 / request.footprint / volume_row 对照 |
| Web | Freqtrade Protections | StoplossGuard / MaxDrawdown / Cooldown / LowProfitPairs 对照 |
| Web | NautilusTrader | 多资产事件驱动、pre-trade risk、crash-only 对照 |
| Web | Bookmap | CVD、冰山吸收、stop-run 对照 |
| Web | Reddit r/algotrading | Walk-forward、OOS、过拟合对照 |
| X | `x_search` | 2026 crypto futures 风控、ATR、SMC、CVD 社区观点 |
| TV MCP | health/timeframe/screenshot | 验证 TV 连接、主周期截图 |

## 六市场流程

| 市场 | full 流程 | quick 流程 | 主周期 | 核心能力 |
|---|---|---|---|---|
| 加密 | tv → binance → cg_pro → macro → x_sent → cron_read → cvd → depth → corr → card | tv → binance → macro → x_sent → card | 15m | TV SVP v10、Binance OI/Funding/Taker、多空比、Deribit、Dune、稳定币、清算、X情绪、CG |
| 贵金属 | tv → macro → x_sent → cron_read → cvd → corr → gold_macro → card | tv → macro → x_sent → card | 5m | TV主指标、金十、gold-api、DXY、US10Y、COT、GLD/GDX/TIP |
| 外汇 | tv → macro → x_sent → cron_read → corr → forex_rate → card | tv → macro → x_sent → card | 15m | TV结构、DXY、利差、央行窗口、COT、事件日历 |
| 股票 | tv → macro → x_sent → cron_read → corr → fmp → options_chain → card | tv → macro → x_sent → card | 1h | TV结构、指数/VIX、财报/基本面、板块、期权链 |
| 期货 | tv → macro → x_sent → cron_read → corr → card | tv → macro → x_sent → card | 15m | TV结构、COT、宏观事件、跨资产相关、主力合约 |
| 期权 | tv → options_chain → card | tv → card | 跟底层 | 标的TV结构、IV、Greeks、OI、成交量、到期/MaxPain |

## 社区对照后的优化建议

| 优先级 | 社区依据 | 差距 | 动作 |
|---|---|---|---|
| P0 | NautilusTrader 数据完整性优先 | XAU 若用占位K线，关键位全等于现价 | 正式XAU卡必须 TV MCP现场读5m/15m/1h/4h关键位 |
| P1 | Freqtrade Protections | protections 只实时检查，未强制入回测/日评 | 回测/日评加 protections 报告与开关 |
| P1 | Reddit/WFO | 有脚本但无卡片闸门 | 样本<20或无WFO/OOS，不允许A |
| P1 | Bookmap CVD/Iceberg | CVD表述太粗 | 加入 CVD背离、吸收/派发、扫荡、冰山四字段 |
| P1 | TradingView footprint | 未评估 footprint API | Pine审计时评估 `request.footprint`/`volume_row` |
| P1 | OEMS/Nautilus | 缺下单前 pre-trade risk | 增加 GO/NO-GO 七问硬闸门 |
| P2 | Options best practices | 期权链只是声明 | 加 IV Rank、Greeks、OI、Volume、到期、MaxPain |

## 工作流要点

- 先跑 `pipeline_router.route_pipeline(symbol, mode)`，按 router 返回步骤执行。
- 正式分析输出要能回溯每条数据来源；用户问“用了什么能力”时，用本文件表格解释。
- cron_read 是读后台落盘，不是重跑脚本；mtime 过期则标注降级。
- X情绪优先 `x_search`，不可用再 web_search，并标注非实时。
- 加密/XAU 分析必须 TV full截图在首行；不能只发文字。
