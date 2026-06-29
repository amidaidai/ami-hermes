# 棠溪驾驶舱 v9.6 · 六市场分析流程与能力映射

更新时间：2026年6月29日22：10

## 1. 本轮使用的技能与工具

| 类型 | 名称 | 用途 | 结果 |
|---|---|---|---|
| Skill | `crypto-multisource-analysis` | 六市场 router、五层周期、cron_read、TV/Binance/X/宏观流程 | 确认 v9.5 流程，已按 v9.6 渲染层升级 |
| Skill | `trading-card-generation` | 出卡路径、auto_card、模板合规 | 发现仍写 v8.0 叙事，已列为需同步 |
| Skill | `trading-system-audit` | 社区审计、运行态、测试、P0/P1/P2 方法 | 继续沿用 full-stack 验证 bundle |
| Skill | `web-access` | 联网搜索与网页提取方式 | 用于社区/官方资料对照 |
| Web | TradingView footprint 搜索 | Pine v6/request.footprint/volume footprint | 确认 footprint/order-flow 是 2026 新增重点 |
| Web | Freqtrade Protections | StoplossGuard/MaxDrawdown/Cooldown/LowProfitPairs | 对照风控闸门与回测启用 protections |
| Web | NautilusTrader Architecture | 多资产事件驱动、pre-trade risk、crash-only | 对照我们的 daemon/watchdog/状态持久化 |
| Web | Bookmap CVD/Iceberg | CVD背离、冰山吸收、stop-run | 对照 CVD/吸收/扫荡模块 |
| Web | Reddit r/algotrading | Walk-forward/OOS/过拟合 | 对照回测与复盘闭环 |
| X | `x_search` | 2026 crypto futures 风控/ATR/SMC/CVD 社区观点 | 确认 ATR 1.5-2.5、单笔0.5-1%、冷却/WFO/CVD吸收 |
| TV MCP | health/timeframe/screenshot | 实测 TradingView 连接与 full截图 | CDP 正常，已截 `v96_pipeline_btc_20260629_2205.png` |
| Terminal | pytest/router/auto_card | 实测代码与管线 | 116 passed，BTC/XAU 表格卡通过 |

## 2. 六市场标准流程

| 市场 | 品种例 | full 流程 | quick 流程 | 主周期 | 核心能力 |
|---|---|---|---|---|---|
| 加密 | BTCUSDT/ETHUSDT/SOLUSDT | tv → binance → cg_pro → macro → x_sent → cron_read → cvd → depth → corr → card | tv → binance → macro → x_sent → card | 15m | TV SVP v10、Binance OI/Funding/Taker、多空比、Deribit、Dune、稳定币、清算、X情绪、CG |
| 贵金属 | XAUUSD/XAGUSD | tv → macro → x_sent → cron_read → cvd → corr → gold_macro → card | tv → macro → x_sent → card | 5m | TV主指标、金十、gold-api、DXY、US10Y、COT、GLD/GDX/TIP、伦敦/纽约窗口 |
| 外汇 | EURUSD/GBPJPY/USDJPY | tv → macro → x_sent → cron_read → corr → forex_rate → card | tv → macro → x_sent → card | 15m | TV结构、DXY、利差、央行窗口、COT、事件日历 |
| 股票 | AAPL/TSLA/NVDA | tv → macro → x_sent → cron_read → corr → fmp → options_chain → card | tv → macro → x_sent → card | 1h | TV结构、指数/VIX、财报/基本面、板块、期权链、新闻情绪 |
| 期货 | ES1!/NQ1!/CL1! | tv → macro → x_sent → cron_read → corr → card | tv → macro → x_sent → card | 15m | TV结构、COT、宏观事件、跨资产相关、主力合约流动性 |
| 期权 | BTC-202606-CALL / AAPL Call | tv → options_chain → card | tv → card | 跟底层 | 标的TV结构、IV、Greeks、OI、成交量、到期/MaxPain |

## 3. 每一步具体做什么

| 步骤 | 能力/脚本 | 数据 | 用途 | 失败时处理 |
|---|---|---|---|---|
| tv | TradingView MCP / SVP v10 | D/4h/1h/15m/5m，study_values、tables、labels、lines、截图 | 主驾驶，决定结构/关键位/行动格 | MCP不可用则降级，正式BTC/XAU不得无截图出结论 |
| binance | Binance API/MCP + `_collect_binance_data` | 价格、OI、Funding、Taker、多空比、K线 | 加密副驾驶，验证趋势真假与拥挤度 | 现货失败不跳过期货端点 |
| cg_pro | `multi_source_collector` / CG | Top10、trending、市值、流动性 | 板块轮动和热点确认 | 标注不可用，不覆盖TV结构 |
| macro | `macro_filter`、金十、Poly、FG、Yahoo | DXY/VIX/SPX/US10Y/事件/预测概率 | 事件窗口与风险环境 | 数据不可用则中性处理 |
| x_sent | `x_search` / `x_sentiment_collector` | X实时情绪、大V观点、热词 | 验证/挑战，不覆盖结构 | 回退 web_search，标注非实时 |
| cron_read | data/*.json | deribit、dune、cot、x_sentiment、qlib、liquidation、stablecoin | 读取后台采集，不重复烧API/token | mtime过期则标注降级 |
| cvd | TV CVD / `cvd_analyzer` / `orderflow_absorption` | 背离、吸收、主动买卖 | 判断扫荡/突破真假 | 无真实CVD则不得给A级 |
| depth | `depth_wall`/清算压力 | 挂单墙、清算池 | 找磁吸位和挤压风险 | 无数据标注跳过 |
| corr | FinanceKit / `correlation_matrix` | BTC-SPX-XAU-DXY 等滚动相关 | 控组合风险/系统性风险 | 失败不编造相关系数 |
| gold_macro | DXY/TIP/GLD/GDX/COT | 黄金专属宏观 | 判断金价驱动 | 不套加密Funding/OI |
| forex_rate | 利差/央行窗口 | 利差、carry、事件 | 外汇方向过滤 | 事件窗口优先降级 |
| fmp/options_chain | FinanceKit/stock/期权链 | 基本面、IV、Greeks、OI | 股票/期权专属 | 缺Greeks则期权只跟标的 |
| card | `render_v8.py` 现为 v9.6 渲染器 | 汇总所有源 | 表格驾驶舱输出 | 缺核心源则状态降级 |

## 4. 本轮代码变化

| 文件 | 改动 | 验证 |
|---|---|---|
| `scripts/render_v8.py` | 保留旧函数名，实际升级为 v9.6 表格驾驶舱渲染器 | BTC/XAU 出卡含五大表格 |
| `hermes/scripts/auto_card.py` | 标准手动出卡不再被旧极简卡覆盖，统一返回 v9.6 表格卡 | `auto_card_BTCUSDT.md` / `auto_card_XAUUSD.md` 均为完整表格 |
| `tests/test_card_render_locked.py` | 回归测试从 v8.0 叙事 marker 更新为 v9.6 表格 marker | pytest 116 passed |

## 5. 社区对照后的下一批优化

| 优先级 | 社区依据 | 当前差距 | 建议动作 |
|---|---|---|---|
| P0 | NautilusTrader：数据完整性优先，无效数据比无数据更危险 | XAU 仍用占位K线进入表格，价位全等于现价 | XAU 必须 TV MCP现场切 5m/15m/1h/4h 读关键位后再出正式可执行价位 |
| P1 | Freqtrade Protections：保护要参与回测/优化 | protections 能检查，但复盘样本少，回测未强制 enable | 回测/日评脚本加 protections 开关与报告行 |
| P1 | Reddit/WFO：专业回测必须 walk-forward + OOS | 有 backtest/walk_forward 脚本，但不强制入分析卡 | 卡片增加“历史胜率/样本不足”闸门；样本<20禁止A |
| P1 | Bookmap：CVD + 冰山吸收用于 stop-run | 有模块但表格只写粗略CVD | 多源表加入“吸收/派发/扫荡/冰山”四字段 |
| P1 | TradingView 2026 footprint | SVP/CVD强，但未评估 Pine footprint API接入 | 下一版 Pine 审计评估 request.footprint/volume_row 是否能替代近似CVD |
| P1 | 多资产 OEMS：pre-trade risk check | 当前分析和执行桥接还不够强 | 下单前加7问 GO/NO-GO 硬闸门 |
| P2 | Options best practice：IV/Greeks/OI/Volume | 期权流程只有 options_chain 声明 | 期权卡加入 Delta/Gamma/Vega/Theta/IV Rank/到期/流动性 |
| P2 | Crash-only / event-driven | 守护已恢复，但状态/锁仍可继续强化 | daemon 启停统一写 system_events，重启原因可观测 |

## 6. 核心结论

v9.6 已经把“文档模板”推进到“实际渲染层”：BTC/XAU 现在出的是表格驾驶舱卡，不再只是叙事卡。下一步重点不是再加数据源，而是把 TV 现场五层读取、XAU真实关键位、复盘A/B/C、Walk-forward 胜率和下单前 GO/NO-GO 闸门接成硬流程。
