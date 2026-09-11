# 成熟双指标：2025–2026 官方/社区证据化优化

抓取日期：2026-07-19。适用：`SVP/ICT/VWAP/CVD` 主指标 + 聚合量/OI/CVD 副指标。目标不是继续堆 ICT 模块，而是识别真正增加数据质量、决策闭环和可验证性的增量。

## 一、结论优先级

1. **CVD 方法/范围/质量编码**：主指标 lower-TF CVD 与副指标 K线估算 CVD 同属代理值，不可当两票独立确认；同源信息只计一次，另一口径仅用于冲突检测。
2. **跨所 OI 正规化**：各所先统一 USD notional 或 base coin，再聚合 OI% change / z-score；输出 coverage、dominance、venue count、freshness、dispersion。raw OI total 仅展示兼容，不决定方向。
3. **Footprint Pro 独立脚本**：不要塞入现有主/副指标。用于滚动窗口 POC/VA、逐行 delta、stacked imbalance、关键位 absorption；无数据时明确 `NO DATA`，不得伪装同等级回退。
4. **事件结果日志与校准**：按品种×周期×时段×setup×体制记录 Grade、风险码、Entry/SL/Target、MFE/MAE/+1R/-1R；检查分桶兑现率和置信区间。CVD divergence 只作 confluence，不假设单独有 edge。
5. **减法优先**：删重复 CVD 投票、raw OI 方向判断、低价值 OB 家族变体、重复 alert/plot、常驻叙事卡；不要在 Pine 内模拟 DOM、冰山或完整清算热力图。

## 二、官方事实：TradingView / Pine

### Native footprint（2026 新能力）

- Pine release notes 在 **2026年1月**加入 `request.footprint()`、`footprint`、`volume_row`。
- 可读取 bar 总 buy/sell volume、总 delta、POC、VAH/VAL 和逐价格行的 volume、delta、imbalance。
- 每脚本只允许 **1 个 unique `request.footprint()`**，且只有 Premium / Ultimate 用户可运行。
- 官方博客于 **2026-03-02**发布说明。

来源：
- https://www.tradingview.com/pine-script-docs/release-notes/
- https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/
- https://www.tradingview.com/pine-script-docs/writing/limitations/

### 当前 Pine 限制（抓取于 2026-07-19）

- 编译后 IL：100,000 tokens；导入库合计 1,000,000。
- `request.*()`：通常 40 个 unique calls，Ultimate 64。
- plot count：64。
- lower-TF intrabars：最高 200,000，实际随方案变化。
- tuple 请求同 symbol/timeframe 多字段更高效。
- HTF 非重绘标准：expression `[1]` 与 `lookahead_on` 配套；两者不可拆。

来源：
- https://www.tradingview.com/pine-script-docs/writing/limitations/
- https://www.tradingview.com/pine-script-docs/concepts/repainting/
- https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/
- https://www.tradingview.com/pine-script-docs/faq/data-structures/

## 三、TradingView 社区实现（经验，不是官方标准）

### 聚合 CVD 的诚实口径

`Cumulative Volume Delta Candles Aggregated (Lite)`（更新 2025-10-18）：

- 聚合 Binance、Bybit、OKX、Bitget、Coinbase；支持 anchor reset；统一币/USD单位。
- 作者明确披露：Lite 版根据 lower-TF K线开收方向分配成交量，是估算，不是交易所逐笔 delta。

来源：https://www.tradingview.com/script/CRKW4dvv-Cumulative-Volume-Delta-Candles-Aggregated-Lite/

**落地规则**：输出 `CVD_METHOD`、`CVD_SCOPE`、`CVD_ANCHOR`、`CVD_QUALITY`。建议编码：1=K线估算、2=lower-TF估算、3=native footprint、4=外部 aggressor/taker 流。

### 聚合 OI 正规化

`Open Interest Aggregated (Lite)`（抓取 2026-07-19）：

- 聚合 Binance、Bybit、OKX、Bitget、Coinbase。
- 明确对 USD-denominated OI 按资产价格正规化，并支持 coins/USD denomination。

来源：https://www.tradingview.com/script/qiqehv0U-Open-Interest-Aggregated-Lite/

**落地规则**：不要跨所 raw sum 后直接做背离；每所先换算同单位，再计算变化。若单所 dominance 过高、数据过期或各所方向分歧，应降级。

### Footprint 社区模式

- `Footprint Lookback [Order Flow]`（2026-06-22）：单请求聚合滚动窗口，输出 POC/VA/imbalance；无数据时显示 `No footprint data`，不发明替代数据；限制 300 bars 控制性能。
  - https://www.tradingview.com/script/mFzdS8hv-Footprint-Lookback-Order-Flow/
- `Institutional Footprint Divergence Engine`（2026-03-18）：结构、delta、量能、累计 delta、波动体制五维质量评分。可借鉴维度拆分，但“机构行为”和分数阈值仍属作者解释，必须独立回测。
  - https://www.tradingview.com/script/2BbEtZFe-Institutional-Footprint-Divergence-Engine/

## 四、Bookmap / ATAS / Reddit：社区经验边界

### Bookmap

2026-01-21 更新的 CVD 教材强调：

- CVD 是 ask 主动买量减 bid 主动卖量的累积；不同平台的数据质量和成交分类会改变结果。
- 背离应发生在已知参考位（前高低、VWAP、可见流动性区），并等待价格 reaction / failure-to-continue 与 CVD 转向，不能看到背离就反手。
- CVD 是 confluence，不是 standalone signal。

来源：https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy

2025-07-08 的突破清单：真实突破需同时观察穿越关键位时的主动成交、流动性变化以及突破后的持续成交/结构接受。

来源：https://bookmap.com/blog/breakout-or-fakeout-the-3-point-checklist-for-confirmation

### ATAS

Footprint 教材（原文发布 2024-02-21，抓取 2026-07-19）强调 `effort vs result`：大量主动成交却无法推动价格才是有意义的吸收；stacked imbalance 应与价格反应和其他结构工具合用。

来源：https://atas.net/blog/how-to-read-footprint/

ATAS 2026-07-02 changelog 将 CVD、Market Pressure、Value Area 加入流动性分析模块，并为 Big Trades 增加 Weak/Medium/Strong 自动过滤，说明成熟平台趋势是“数据质量+过滤+上下文”，不是更多同义指标。

来源：https://feedback.atas.net/changelog

### Reddit

Reddit OrderFlow / ICT 帖子可用于发现问题模式（吸收 vs exhaustion、FVG需 HTF context+displacement、等待收柱），但属于匿名轶事，不得当作胜率或官方 ICT 标准。页面受反爬时，只引用可核验摘要并标抓取日期，不扩写为确定事实。

## 五、GitHub 开源：架构证据，不是行业标准

### TradeBobbyTerminal

2026-07-10 提交记录：对 CVD divergence 做诚实回测，当前样本显示**无 standalone edge**，只有较弱 distribution 倾向，因此定位为 confluence lens。

来源：
- https://github.com/SoCloseSociety/TradeBobbyTerminal
- https://github.com/SoCloseSociety/TradeBobbyTerminal/commit/bed5b8b67391da728bfaec73a476d95844f11cd3

### HyperData Terminal

2026-07-08 最新提交的可迁移原则：

- per-venue freshness，避免一个活跃源掩盖另一失效源；
- 坏交易所 payload 逐条丢弃并计数；
- degraded startup/health 明示；
- smart-money 排名要求最低样本和成交规模并输出 sample-size confidence。

来源：https://github.com/Co-Messi/HyperData-Terminal

**注意**：这两个仓库星数与用户量有限，只能作为实现/架构样本，不能称为社区共识。

## 六、推荐裁决协议

### CVD 背离成为正式事件的最小门槛

- 价格确认 HH/LL；
- CVD 未确认；
- 位于 VWAP、前高低、VA边界、FVG CE、OB或流动性池附近；
- 满足最低摆动幅度和量能；
- 历史事件已收柱；
- 后续出现 reclaim、MSS或位移；
- 若价格/OI/CVD互相冲突，最高 B 级。

### 行动格保持五行

1. 方向：偏多/偏空 + PD + KillZone
2. 触发：扫位/MSS/位移 + 等待价格
3. 流向：Footprint/CVD/OI 摘要
4. 执行：Entry/SL/TP/RR
5. 风险：coverage/dominance/freshness/LIVE状态

硬规则：

- `LIVE未锁` 不得 A；
- CVD 估算方法必须明示；
- 主副强冲突不得 A；
- 无 Entry/SL/TP 或 RR 不足时输出 X/等待，Data Window 不导出可执行价格。

## 七、证据标签

报告每条建议必须标注：

- **官方事实**：TradingView 文档、release notes、官方博客的能力/限制。
- **平台教育材料**：Bookmap/ATAS 的订单流解释和工作流，不是胜率证明。
- **社区实现**：TradingView 开源脚本/Reddit，只用于实现模式和假设。
- **开源架构**：GitHub 仓库用于数据质量、freshness、回测闭环参考；小样本项目不得称行业标准。
