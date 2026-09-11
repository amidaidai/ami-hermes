# 2026-06-28 流程审计补充：双指标 + Hermes 全链路

本记录来自一次对用户上传的 `主指标.txt` / `副指标.txt`、Hermes auto_card、cron、monitor、TV/Binance/FinanceKit MCP 的综合审计。用于未来审计同类交易系统时快速对照。

## 关键审计结论

1. 指标本身不是主要短板：主指标已覆盖 SVP/ICT/VWAP/EMA/CVD/DMI 行动格；副指标适合作为加密副驾驶，覆盖聚合量、OI、Spot/Perp、CVD估算、爆仓估算。
2. 主要短板在运行态与链路约束：监控守护可能停机、cron 可能只剩维护任务、auto_card 可能使用缓存 TV DMI 而非现场 TV MCP 多周期读取。
3. 分析卡最大风险是 B等待/C等待/X禁做仍输出具体入场价或 R:R 不足方案。状态未达到 A 时，卡片必须写触发条件，不得呈现为可挂单。
4. 技能/模板多版本冲突会污染输出：v4.2、v8.0、旧V5.1、禁表格/可用表格等规则必须由唯一权威模板裁决。

## 审计必跑检查

- 运行态：`hermes cron list`、monitor heartbeat、watchdog log、monitor.log、source_snapshot/monitor_levels 新鲜度。
- 指标静态：request 配额、plot 数、table 行动格字段、Data Window 是否移除、R:R 硬过滤是否存在。
- TV实时链：`tv_health_check` 当前图表 symbol/timeframe 是否正确；不能用 HYPE 当前图或旧缓存冒充 BTC/XAU 实时分析。
- 数据交叉：Binance price/OI/Taker/Funding、FinanceKit/CoinGecko、金十/事件、恐惧贪婪/X情绪按资产适配。
- 卡片回归：B等待不给入场价；R:R<1:2 不作为可执行方案；截图/时间/BJT/数据源新鲜度齐全。

## P0 模式与修法

### B等待出具体入场价

症状：卡片状态是 `B等待`，但仍输出 `入场 当前价 / 止损 / 止盈`。这会让等待卡变成误导性交易指令。

修法：
- `B等待` / `C等待` / `X禁做`：只输出触发条件，如“15m收上控制点 + CVD转买 + Taker>1.2”。
- 只有 `A做多` / `A做空` 才输出具体 entry/stop/tp。
- 若 R:R < 2.0：标为“仅观察，不可执行”，不要作为 A/B 方案展示。

### TV缓存冒充实时

症状：auto_card 显示 `TV DMI(缓存)`，但没有现场切换品种、多周期读取和截图。

修法：
- 手动“分析/现在呢”必须走 TV MCP 实时链：4h→1h→15m(BTC)或5m(XAU)，每周期读取 table/study/labels/lines，最后 full 截图。
- 缓存 TV DMI 只能作为 fallback，并在卡面标注“缓存”。

### 监控离线但文档看似完整

症状：skill/脚本写得完整，但 heartbeat 旧、watchdog 冷却、cron 没交易任务。

修法：审计报告必须区分“配置应然”和“运行实然”。监控离线是 P0，不可只说系统设计完整。

## 市场适配原则

- BTC/ETH：当前系统最适配。主指标 + 副指标 + Binance OI/Funding/Taker + Depth + F&G。
- 山寨：按流动性分层；低流动性自动降级，OI/深度不可强信。
- XAU：副指标不可用；主看 TV主指标、DXY/US10Y、金十事件、Kill Zone、gold-api/Yahoo/金十多源价。
- 外汇：不要套加密 Funding/OI；主看结构、会话、日历、美元指数。
- 股票/指数/期权：必须引入财报、期权链、IV/Greeks 等专属源；不能套加密卡。

## 社区对照要点

- ICT/SMC：扫流动性 + 位移 + FVG + Kill Zone + 溢价/折价，必须绑定可执行触发，不可只写概念。
- Bookmap/Order Flow：吸收=被动大单吸收主动单；衰竭=主动量失去跟随。确认要看 CVD 变化、失败推进、主动量翻向。
- 交易日志：日志必须反哺模型权重。样本 <20 只观察，不升权；记录 entry/exit/R倍数/模型/市场结构/纪律错误。