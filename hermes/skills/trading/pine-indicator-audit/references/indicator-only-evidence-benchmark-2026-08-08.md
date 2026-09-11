# 指标本身的官方＋社区优化基准（2026-08-08）

适用：TradingView Pine v6、SVP/Volume Profile、聚合 CVD/OI、ICT/SMC 决策面板的**指标本体**研究与审计。排除策略回测、交易复盘和盈利主张。

复用前重新访问 URL；无发布日期页面写访问日期。证据等级：A=官方技术/API/定价事实，B=专业平台教育材料，C=开放源码社区实现，D=匿名论坛问题线索。

## 1. 2026-08-08 官方复核增量

### 2026 Release Notes：只筛指标决策价值

截至 2026-08-08，官方 2026 Release Notes 中与指标本体相关的增量应这样分级：

- **2026-01 `request.footprint()` / `footprint` / `volume_row`**：唯一直接增加订单流数据面的新能力；仅 Premium/Ultimate、每脚本最多一个 unique footprint request。Basic 通用源码不能把它藏在关闭分支中，因为官方限制的是“scripts that call it”，应维护独立 Pro fork。
- **2026-04 UDT collection sorting**：`array.sort()`、`array.sort_indices()`、`matrix.sort()`可用 `sort_field` 按 UDT 的 int/float/string 字段排序。适合关键位、区域、venue 状态对象的原子排序，但不自动提高决策质量。
- **2026-08 UDT array binary search**：`array.binary_search*()`可按 UDT 字段搜索；数组必须预先按同一字段升序排列。仅在 Profiler 证明线性扫描是热点时采用，小数组不要为“新功能”重构。
- **2026-04 multiline strings、2026-07 automatic parentheses/编辑器设置**：只改善可维护性或编辑体验，不列为决策增强。
- **2026-07 `calc_on_every_history_tick` 等 strategy 改进**：属于策略模拟，用户要求“不回测/不复盘”时明确排除。

来源：
- https://www.tradingview.com/pine-script-docs/release-notes/#january-2026
- https://www.tradingview.com/pine-script-docs/release-notes/#april-2026
- https://www.tradingview.com/pine-script-docs/release-notes/#july-2026
- https://www.tradingview.com/pine-script-docs/release-notes/#august-2026

### Pine v6 dynamic request

- v6 默认启用动态请求；单个 `request.*()` 调用可用 series symbol/timeframe，并可在条件、循环、导出函数局部作用域执行。
- 配额按运行时 unique context/call 计：普通账号 40，Ultimate 64；相同函数和参数通常复用。
- 一个动态调用访问 N 个 symbol/timeframe 可能消耗 N 个 unique context；源码调用点数量不能直接等同配额。
- 实时阶段不能首次访问历史阶段未预取的新上下文或 expression。
- 审计必须分别报告默认配置与最坏可达配置；不能再写“开关必省”或“开关绝不省”。

来源：
- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#dynamic-requests
- https://www.tradingview.com/pine-script-docs/writing/limitations/#number-of-calls

### Plot 与 Basic 档

- 每脚本 64 plot counts。`alertcondition()`、`bgcolor()`、`barcolor()`、series-color `fill()`均可能计数。
- `plot(series, color=seriesColor)`可产生两个 count；`plotcandle()`最多七个。只数 `plot(` 行数是不合格审计。
- `hline()`、`line.new()`、`label.new()`、`box.new()`、`table.new()`不占 plot count，但受对象配额约束。
- 2026-08-08 定价页渲染 DOM：Basic 为 2 指标/图、5,000 历史K、20秒计算、0技术告警。
- Basic 专用生产脚本中的大量 `alertcondition()`既无法被该档技术告警使用，又占 plot count；应为 Basic 版本物理删除或交给外部监控，不把动态 `alert()`误写成可绕过账号告警权限。

### Basic 双指标的 `input.source()` 决策总线

- 当前 `input.source()` 官方文档明确允许一个脚本选择**另一个脚本的 plot 值**作为输入，用于连接两个指标；官方定价表显示 Basic 的 indicator-on-indicator 数量为 1。
- 双指标最有价值的用法不是新增第三个指标，而是让 AggVol 复用一个现有数值 plot 导出 packed `valid/confirm/risk`，主指标用单个 `input.source()`读取。
- 主指标仍是唯一 Entry/Stop/Target 与授权源；副指标只允许确认、降级或否决。连接需用户在 Inputs 中选择正确的副指标输出，未连接/无效值必须中性降级，不能自动判坏。
- 若必须新增桥接 plot，先核对副指标真实 64-count 预算；能复用现有 Composite/Valid/Risk Data Window plot 时不再新增。

双指标联动来源：
- https://www.tradingview.com/pine-script-docs/concepts/inputs/#source-input
- https://www.tradingview.com/pricing/

Plot/档位来源：
- https://www.tradingview.com/pine-script-docs/writing/limitations/#plot-limits
- https://www.tradingview.com/pricing/

### `request.footprint()` 当前签名与语义

当前技术文档签名已是：

```pine
request.footprint(ticks_per_row, va_percent, imbalance_percent) → series footprint
```

- `va_percent`默认70；`imbalance_percent`默认300。
- 每脚本只允许一个 footprint request；仅 Premium/Ultimate；无数据可返回 `na`。
- 当前 API 文档明确：把低周期 volume 根据 intrabar price action 分类为 “buy/upward” 或 “sell/downward”，再按价格行汇总。
- 2026-03-02 官方营销博客写过 “Exact buy (ask) / sell (bid)”；这与当前技术文档和 Footprint 完整指南冲突。审计文案以当前技术文档为准，不宣传交易所逐笔 aggressor tape。
- 官方 Footprint chart 指南还说明该图表会因实时与历史使用的 intrabar 数据源粒度不同而“repainting by design”；这条直接约束内建图表，不要不加区分地扩写成“所有 `request.footprint()` 都一定重绘”，但必须披露实时/历史口径可能变化。

来源：
- https://www.tradingview.com/pine-script-docs/release-notes/#january-2026
- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#requestfootprint
- https://www.tradingview.com/pine-script-docs/writing/limitations/
- https://www.tradingview.com/support/solutions/43000726164-volume-footprint-charts-a-complete-guide/
- https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/

## 2. VP、CVD 与 OI 的诚实口径

### 普通 Volume Profile

- TradingView 普通 VP 用同品种低周期K线；`close >= open`记 up volume，否则 down volume。
- VP 的 Up/Down/Delta 不是交易所 ask/bid aggressor flow。POC/VAH/VAL可作结构，但买卖颜色不得命名为真实主动买卖。
- Forex、指数、crypto CFD可能只有 tick volume；Renko、Heikin Ashi 等非标准图会扭曲价格与量。
- 当前官方 Value Area 算法：从 POC 比较上下候选桶；若加入较大候选会超过剩余目标量则停止，并有平局规则。声称“对齐TV”的自建 SVP 必须逐条对齐；midpoint-only 分配应标自定义近似。

来源：https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/

### TradingView CVD

- 官方 CVD 是估算：低周期K上涨量记正、下跌记负，平开平收再参考前一 intrabar close。
- LTF 越细，精度越高但历史覆盖越少；越粗则相反。
- 聚合多所不会把估算 CVD 自动变成真 CVD。最低披露：method、LTF、anchor、venues、coverage、confirmed/live。
- 两套使用相近价格方向法的 CVD 不能作为两张独立投票；一套为主确认，另一套只做覆盖或冲突检测。

来源：
- https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/
- https://www.tradingview.com/script/CRKW4dvv-Cumulative-Volume-Delta-Candles-Aggregated-Lite/ （开放源码，更新 2025-10-17 UTC）

### 聚合 OI

- OI 是未结算衍生合约总数，不自带方向。
- TradingView 加密 OI 可分钟级，传统期货通常日级；面板不得给相同 freshness 标签。
- Bybit：`BTCUSD` inverse OI 单位为 USD，`BTCUSDT` linear OI 单位为 BTC；其 OI 是多空双方总和。
- 跨所 raw OI 直接相加量纲无效。先统一 base coin 或 USD notional，再消费 `%change / breadth / agreement / dispersion`；raw total只作展示。
- 极端波动时交易所接口可能延迟；`not na`或前向填充值不能证明新鲜。输出请求 cadence、最后更新时间（若源有 timestamp）、年龄/缺口代理、venue coverage、dominance。
- LSR必须注明语义。Bybit account ratio是持仓账户数比例，不是名义仓位比例。
- “真爆仓”需要 position side、executed size、bankruptcy price 等事件字段；PERP-SPOT量差或影线模型只能标爆仓压力代理。

来源：
- https://www.tradingview.com/support/solutions/43000685269-open-interest/
- https://bybit-exchange.github.io/docs/v5/market/open-interest
- https://bybit-exchange.github.io/docs/v5/market/long-short-ratio
- https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation
- https://www.tradingview.com/script/qiqehv0U-Open-Interest-Aggregated-Lite/ （开放源码，更新 2026-03-11）

## 3. 只针对指标本身的高价值实现基准

### 主指标

1. HTF 确认值统一使用 expression `[1]` + `lookahead_on`；两者缺一不可。
2. Sweep 状态机：`potential wick cross → confirmed close reclaim → MSS/CHoCH within N bars`；收盘留在水平外归 breakout/consumed。
3. 只有一个 `finalState/finalEntry/finalStop/finalTarget`；行动格、Data Window、告警共用，不允许面板X但机器字段仍导出订单价。
4. 没有合法触发、方向几何或R:R时显示具体等待路径，不伪造 Entry/Stop/Target。
5. VP/CVD/OI/ICT因子有大量共源输入，不做简单票数堆叠。

来源：
- https://www.tradingview.com/pine-script-docs/concepts/repainting/
- https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/
- https://www.tradingview.com/script/qBUHu6aW-Mirage-Liquidity-Sweep-Pro-WillyAlgoTrader/ （开放源码，2026-06-17）
- https://www.tradingview.com/script/RyafCWPs-Trade-Execution-Desk-JOAT/ （开放源码，2026-06-04 UTC）

### 副指标

1. 每 venue 先正规化；显示 venue count、contract type、coverage、dominance、agreement、dispersion、freshness。
2. 与主指标同源的估算 CVD只计一票。
3. 副指标只能确认、降级、否决，不能独立授权开单。
4. 非加密市场不强套聚合永续/OI副指标，也不因副指标缺失自动扣分。

### 面板

默认保持约5–7个决策概念：结论、方向/位置、触发/年龄、Entry、Stop、Target/R:R、订单流质量。交易所级诊断放详细模式或 Data Window；禁止19行“圣诞树”和同一分数三种重复表达。

专业平台交叉证据：
- Bookmap CVD：背离应在前高低、VWAP、可见流动性位等参考位，并等待 failure-to-continue / CVD转向；不是 standalone signal。
  https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy
- ATAS Footprint：重点看 effort vs result；大量主动成交不能推动价格才支持吸收解释，仍需价格和结构确认。
  https://atas.net/blog/how-to-read-footprint/

## 4. “能否由源码验证”列的统一判定

- `✓`：开放源码，主张可在当前源码中静态定位（请求、公式、门控、显示消费链）。
- `△`：源码可查，但结论还依赖账号档位、运行时 unique context、数据覆盖、服务器编译或图表数据；静态 grep不能验收。
- `✗`：受保护脚本、只读产品文档或平台教育材料；只能验证描述/API语义，不能验证实现。
- TradingView页面显示 `OPEN-SOURCE SCRIPT`且可打开 Source code时可标“源码可核验”；`PROTECTED SOURCE SCRIPT`必须标否。
- 作者描述中的“real/exact/institutional”等营销词不因源码开放而自动成为事实；先与官方数据语义交叉。

## 5. 联网取证的稳健路径

1. 先定官方深链接，再做少量（约4–6个）社区发现搜索；不要一次扇出几十个共享RPM的搜索请求。
2. 搜索后端限流时，转为已知 URL 直抓，而不是重复撞相同搜索：静态页用 `requests`/`curl --compressed`，JS定价页用浏览器 DOM。
3. **动态图标表格不能只读 `innerText`**：TradingView Pricing 的不可用项是× SVG，整页文本会省略空单元格。先读取表头确认 `Basic → Essential → Plus → Premium → Ultimate` 列序，再逐行读取直接子列并检查 check/cross class或SVG；不得把“文本缺失”自行补0。
4. 页面只显示 `Mar 2/Mar 11/Jun 22`且无 `<time datetime>` 时，检查 `script[type="application/ld+json"]` 的 `datePublished/dateModified`。本轮从博客JSON-LD确认Footprint营销文发布于2026-03-02、修改于2026-03-17。
5. TradingView社区页面优先读取 HTML `time[datetime]`；本轮确认：OI Aggregated Lite 2026-03-11、Footprint Lookback 2026-06-22、Orderflow Suite 2026-07-11、Quantum Liquidity Map 2026-04-18。
6. 长技术文档用浏览器控制台按heading定位，提取到下一同级heading之间的段落/列表；这比整页快照截断后猜缺失文本可靠。
7. Reddit正文不可稳定取得时降为D级并排除出硬结论，不用搜索摘要补写正文。
8. 输出矩阵至少含：主张、主/副指标、URL、发布日期或访问日期、证据级别、源码可验证性、设计含义和禁止误读。
