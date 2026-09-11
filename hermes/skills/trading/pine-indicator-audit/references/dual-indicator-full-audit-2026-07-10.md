# 双指标全面审计增量知识（2026年7月10日）

适用：SVP+ICT+VWAP+CVD 主指标 + HALDRO/AggVol 副指标的源码审计、生产替换与自动卡读取。

## 官方现行口径

- TradingView Pine v6 单脚本 IL 上限：100,000 tokens；历史80,000已过时。
- `request.*()`：默认40 unique calls，Ultimate 64；HALDRO当前默认展开约32，不是旧注释27。
- plot count上限64；`alertcondition()`、`bgcolor()`、series-color `fill()`计数，`hline/table/line/label/box`不计。
- `request.security_lower_tf`聚合的是子K价格方向成交量估算，不是真实bid/ask逐笔；官方CVD也称“estimate”。
- `request.footprint()`可取真实buy/sell/delta，但每脚本仅1 unique call且需Premium/Ultimate。

## 主指标新增必查项

### Breaker方向翻转

看涨OB向下失效后应成为看跌Breaker；看跌OB向上失效后应成为看涨Breaker。若源码只设`ob.isBreaker := true`而不翻转有效方向，却继续用原`ob.isBull`驱动标签、颜色、`inBullBreaker/inBearBreaker`、评分和MCP，则属于P1方向性错误。

检查链：`broken` → `isBreaker` → 标签/颜色 → `in*Breaker` → A/B/C gate → `mcpObCode`。

### OB蜡烛选择

看涨OB通常是上行位移前最后一根阴线本身；看跌OB是下行位移前最后一根阳线本身。找到`obOffset`后再取`obOffset+1`的反向蜡烛，会把订单块整体错位。LTF与HTF函数必须同步修。

### HTF OB非重绘

`request.security(..., f_htf_ob(), lookahead_on)`若`f_htf_ob()`使用当前HTF `close`而没有历史偏移，会产生历史lookahead bias和实时变化。图表周期`barstate.isconfirmed`不能替代请求周期确认。表达式必须只返回已收HTF柱数据，例如整体结果历史偏移。

### 方向专属评分

`confirmScore`不得用`bullCondition or bearCondition`统一加分。先确定当前唯一计划方向，再分别计算同向CVD、扫线/接受、FVG/HTF FVG、OB/Breaker。必须检查：

- 反向条件不能给当前计划加分；
- FVG在行动格显示确认时，评分也应一致消费；
- 多空候选同时成立时进入冲突/等待，不按三元优先级强选一边。

### MCP可执行一致性

- `setupX`必须优先于`activeLongPlan/activeShortPlan`编码；
- X/等待态即使保留观察目标，也必须有显式`Executable Code`或Quality bit；
- 机器端不能仅凭非空Target判定可执行；Entry/Stop与可执行码必须共同门控。

### CVD强度与告警

若计算了`cvdDivSwingOk`却只出现一次，说明1.5ATR强度门槛未接入。背离需同时消费摆动幅度、关键位、质量和方向确认。扫线+CVD告警必须使用`cvdAbsorbBuyQualified/cvdDistributeSellQualified`，不能混用raw状态绕过样本/关键位门控。

### 独立开关与显示语义

- `SHOW_ICT_LEVELS=false`不能删除前日/前周独立池或磁吸数据。
- “活跃会话仅显示开盘价”必须真画session open，不能只把高低线设透明。
- 棠溪当前图面术语：`已扫N/剩M`；区域标签用“缺口/订单块/破坏块/真空”，不用FVG/OB/BRK/LV缩写。
- 多市场自动锚定遵循当前棠溪统一规则：`<1h=D`、`1h至<4h=W`、`>=4h=M`，不要给金属/股票静默强制D。

## HALDRO新增必查项

### 请求展开

当前典型展开：

- 五所 × 四类成交量 = 20；
- `f_oi()`内USDT/USDC两请求 × 四所 = 8；
- EUR、RUB、LSR、OI单源回退 = 4；
- 合计约32/40。

静态扫描必须递归展开`GetExchange → GetRequest → request.security`，不能只grep六个调用点。

### LSR

- 常见Long/Short Ratio：`>1`表示多头更多，`>1.3`为多头拥挤；`<0.8`为空头拥挤。
- LSR必须验证运行态非`na`；缺值时显示不可用，不能静默空白。
- 当前方向与拥挤同侧时，Confirm Score扣分并进入Risk Code/告警。

### OI归一

不同交易所原生OI可能是币、张或合约，不能直接相加后把绝对值用于阈值/仓位。优先聚合逐所OI百分比变化和上涨/下跌广度；若要总OI，逐所转换为统一USD名义价值并记录覆盖率。

### “爆仓”语义

`PERP volume - SPOT volume`只能叫“杠杆成交量异常/疑似清算代理”，不是强平数据。不得在行动格输出确定性的“多头爆仓/空头爆仓”，除非接入真实liquidation feed。

### CVD与一致性警告

- `math.sum(volume_buy/sell, len)`是滚动Delta，不是累计Delta；应改名或使用锚定`sessCvdA`。
- `ta.highest/lowest`放在条件表达式会产生CW10002类历史一致性警告；先全局计算，再引用变量。
- 强信号灯/告警必须使用最终Confirm、Valid、Risk及CVD方向一致性门控，避免绿灯与“涨势存疑”同时出现。
- `SHOW_ACT=false`时仍须在last bar清表，避免旧信号残留。

### 非加密机器门控

非加密表格提示正确并不代表Data Window为空。外部脚本必须先检查`HALDRO Valid Code`；Valid=0时忽略CVD、Flow Pack、Composite和OI等方向字段。

## 双指标裁决

修复前临时纪律：关闭主指标`SHOW_OB/SHOW_HTF_OB/SHOW_BREAKER`；主指标只用SVP/VWAP/EMA/FVG/扫线/R:R，副指标只用聚合量能、现永占比、覆盖率和集中度背景。

双指标放行至少要求：主指标可执行Entry+Stop、R:R合格；HALDRO Valid=2、Confirm>=3、Risk=0；无主副CVD强冲突。任一X/等待、Entry/Stop为空、Valid非2或Confirm<=2，一律不下单。

## 实测基准

- 主：2859行，28 plot、2 fill、1 bgcolor、16 alertcondition；最低plot count约47；12个request；12项Data Window；TV服务器编译0错误0警告。
- 副：502行，34 plot、8 alertcondition；默认request展开约32；17项Data Window；TV服务器编译0错误、2条L337-L338历史一致性警告。
- 运行态必须覆盖BTCUSDT.P与XAUUSD：BTC验证双指标冲突裁决；XAU验证HALDRO非加密表格与Data Window Valid门控。

## 权威来源

- https://www.tradingview.com/pine-script-docs/writing/limitations/
- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/
- https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/
- https://www.fluxcharts.com/articles/order-blocks-ob-explained
- https://www.fluxcharts.com/articles/breaker-blocks-bb-explained
