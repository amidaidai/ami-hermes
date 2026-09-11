# 全系统审计路线图 v5.1 → A级执行系统

用于用户要求“全面审计”“权威源社区联网”“我的系统每一处都审计”“给出建议”。

## 审计结论口径

当前 v5.1 系统可定位为 B+：模板强，监控可用，但风控闸门、复盘闭环、数据快照、衍生品自动化仍未闭合。不要继续堆模板长度；优先把系统变成“输入 → 判定 → 动作 → 风控 → 记录 → 复盘”。

## 权威源映射

- CME 风控：仓位按账户、止损距离、风险预算反推；不能按保证金最大可开数量决定。
- CFA 行为金融：确认偏误、过度自信、损失厌恶、近期偏误要进入复盘和纪律字段。
- Bookmap 订单流：CVD 是确认工具，不是单独方向信号；吸收/衰竭要看主动成交是否延续和被动流动性是否承接。
- Binance Futures 官方接口：Funding、mark/index、OI、多空、Taker、aggTrades 都应进入衍生品模块。
- TradeZella/TradesViz：日志要记录模型、理由、仓位、情绪、错误标签和日/周/月复盘。
- 多周期社区共识：高周期定方向，中周期找结构，低周期找触发；低周期不能倒逼高周期。
- Santiment/Fear&Greed/X/Reddit：社区情绪只调仓位和拥挤度，不覆盖结构。

## 必查系统面

1. 模板层：状态、评分器、五类模型、仓位器、数据可信度是否都有硬规则。
2. 数据源层：价格三源、催化两源、社区情绪、衍生品数据是否有时间戳和可信度。
3. 监控层：是否支持 near/breach、close_confirm、retest、sweep_reclaim、expired、invalidated。
4. 风控层：risk_state 是否真正拦截日损、连亏、超风险和数据 C级。
5. 复盘层：trade_plans、monitor_events、trade_reviews 是否能按 plan_id 串起来。
6. 工程层：脚本、skill scripts、cron scripts 是否同步；是否有健康检查和测试。

## P0 改造

- 风控闸门：分析和监控触发前读取 `data/risk_state.json`，自动降仓或 X禁做。
- 计划日志：每次分析追加 `data/trade_plans.jsonl`，不能空着。
- 数据快照：每次分析写 `data/source_snapshot.json`，记录价格三源、衍生品、新闻、社区、时间戳、可信度。
- 监控状态机：`condition` 必须真正执行 near_or_breach、close_confirm、retest、sweep_reclaim、expired、invalidated。
- CVD 降权：K线估算 CVD 标 C级，不能给 A单加分。

## P1 改造

- futures aggTrades 真实 CVD。
- 衍生品评分器：Funding、OI、多空、Taker、Basis → 拥挤度、挤压方向、0-2 分。
- 复盘统计器：日计划数、触发数、交易数、胜率、平均R、错因第一名、纪律评分。
- 多品种配置：BTC/ETH/XAU/山寨分别设置杠杆、风险、数据源、阈值和有效期。

## P2 改造

- 清算热力图：接 Coinalyze 或同类源。
- 社区情绪结构化：Santiment/Fear&Greed/X/Reddit 只输出情绪分和拥挤度。
- TradingView 指标同步：自动读取当前图表指标，减少手写偏差。
- 可视化健康面板：当前计划、实时价格、风险状态、监控位、最近事件、今日盈亏、模型表现。

## 输出格式

用户要“审计看看”时，不要先夸。按以下顺序输出：

1. 结论：当前等级和最大短板。
2. 权威源映射：来源原则 → 当前系统差距。
3. 逐层审计：模板、数据、监控、风控、复盘、工程。
4. P0/P1/P2 路线图。
5. 下一步如果用户说“帮我完成”，直接实施 P0。
