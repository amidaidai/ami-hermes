# 双指标现场审计增量：执行完整性、数据质量与社区证据

**审计对象**：SVP+ICT+VWAP+CVD 主指标与 Volume Aggregated Spot & Futures 副指标。适用于成熟 Pine v6 双指标驾驶舱，不是单次修复清单；后续遇到相同结构应复用这些断言。

## 一、证据边界

- 源码以用户当轮上传文件为准，不以 Desktop 旧副本或历史会话假设替代。
- TradingView `translate_light` 的 `status=200`、`errors=[]`、`warnings=[]` 只证明语法/服务器诊断通过；不能代替 Pine Editor 的客户端 Token、plot、20秒计算和 Add/Update on chart 验收。
- 运行态必须单独记录：图表品种、周期、study 实体、主/副行动格、Data Window、Packed Bus。非目标品种的安全降级不能当作加密模式验收。
- CVD、Volume Profile 的买卖分类和 Pine Footprint 都不能笼统写成交易所真实逐笔 aggressor 流；真实清算、资金费率、Taker、DOM 属外部交易所/订单簿数据。

## 二、上传版基线与验证

| 项目 | SVP 主指标 | AggVol 副指标 |
|---|---:|---:|
| Pine 版本 | v6 | v6 |
| 行数 | 3,442 | 861 |
| Unicode 字符（去 BOM） | 222,510 | 63,239 |
| UTF-8 字节 | 243,855 | 76,928 |
| input | 193 | 46 |
| request 调用点 | 8 | 8 |
| request 展开估算 | 约8 | 默认约30 |
| plot 调用 | 32 | 44 + 1 plotcandle |
| fill/bgcolor | 2 / 1 | 0 / 0 |
| 行动格 | 13行/18行容量 | 6行/10行容量 |
| 云端编译 | 0错0警 | 0错0警 |
| 行尾 | LF | LF |

AggVol 的客户端 plot 最坏预算应按官方 `plotcandle()` 4个OHLC基础计数加颜色/影线/边框系列色重新核算；当前保守估计约61/64，后续只允许负增量优化。主指标脚本级 CE10116 粗估为 `193+32+8=233/254`。这些都是预算，不是客户端最终回执。

Packed Bus 合同为 `22002`。按照源码编码/解码公式做10,000组随机边界往返，0失败；最大编码值约 `2.20e15`，低于 `2^53≈9.01e15`，当前十进制总线的精确性设计成立。

## 三、P0 执行完整性断言

### 1. Sweep 与 breakout 必须拆开

危险签名：

```pine
SWEEP_MARK_MODE == "收盘即扫" ? (barstate.isconfirmed and touchOrGap) : ...closeReclaim...
```

如果 `swept=true` 不要求收盘回到水平位内，真实突破会被当成扫线，污染有效池、扫线计数、磁吸和路径。ICTLevel 与 nPOC 必须共享：

- `crossed`：价格穿过；
- `rejected/swept`：穿过后收回且确认收线；
- `brokenThrough`：收盘在外侧的突破消费。

默认人工驾驶舱应优先使用收回确认，不应把所有穿越都当成反转扫线。

### 2. 最终硬阻断必须覆盖结构冲突和 SMT

不能只让 `setupX` 或面板文字知道风险。若 `xConflict` 只在可选开关开启时进 X，或 `smtConflict` 仅进入 `actionWeakened`，就可能出现“面板警告冲突、MCP Entry Valid 仍可执行”的分叉。

统一断言：

```text
finalHardBlock → executablePlan
finalDecision → Side / Grade / EntryValid / ExecutionPack / panel
```

当前用户合同下，选定方向存在结构冲突或 SMT 反向冲突时，至少降到 WAIT；执行价格必须为空，B/C 观察价格必须与执行字段隔离。

## 四、P1 数据与路径断言

### 1. CVD 背离必须使用同一价格摆动

`ta.highest(high, N)-ta.lowest(low, N)` 只是窗口范围，不等于当前 Pivot 到上一 Pivot 的摆动。正确顺序：确认价格 Pivot → 读取对应 CVD → 比较同侧上一 Pivot → 用 Pivot 时刻 ATR、关键位、CVD slope 和收线状态过滤。

当前/历史 CVD 方法必须独立编码：当前图表所低周期估算、聚合K线估算、无效/回退；背离事件不能冒充数据质量。

### 2. 路径要持久化阶段

“扫低收回”只在事件柱为真，会导致下一根 K 丢失“等 MSS↑”阶段。至少维护 `pathStage/pathBornBar/pathZoneId/pathFailCode`，或用 `sweepAge <= acceptanceWindow` 表示已完成步骤仍在有效期内。路径只能显示最近已完成步骤和当前唯一下一步。

### 3. MSS 语义不能把 VA/VWAP 穿越冒充内部结构

如果 MSS level 回退到 `resPrice/curVah/sVwap`，应改名为价值突破/接受，或新增真实内部摆动高低点。Sweep→internal MSS→FVG/OB回踩与 VAH/VAL/VWAP接受应是不同路径。

### 4. FVG 距离必须是区间距离

对任意 `[bot, top]`：

```text
price < bot → bot-price
price > top → price-top
bot <= price <= top → 0
```

不要用“多头只计算 close-top、空头只计算 bot-close”的单侧公式，否则位于缺口另一侧的远端 FVG 会被误算为距离0，影响最近区、显示、质量和计划绑定。

### 5. OB 缓解要区分触碰和失效

浅触不等于完全缓解。建议状态为 `untouched → touched → CE/50% mitigated → close-through invalidated`，并让 `REMOVE_MITIGATED_OB` 作用于用户选择的状态，而不是任何进入区域的第一根 K。

### 6. AggVol freshness 不能只看非空

`value>0`、EMA 基线和连续缺失计数只能识别部分掉线，不能证明源在更新。成交量与 OI tuple 应携带源时间，逐 venue 维护年龄、恢复和有效性；覆盖率、源冻结、无成交必须分开编码。五所成交量与四所 OI 保持不变。

### 7. OI 单源不等于跨所100%共识

当 `oiAggValid=1` 时，`agreement=100%` 只是单样本自洽。显示应为 `有效1/4·不足共识`，且不要把源不足命名成 OI 背离。只有有效源达到最低数量后，agreement/dispersion 才能进入确认票。

### 8. 非加密显示必须和 Valid Code 一致

当 `HALDRO Valid Code=0` 时，不应继续显示“聚合K/今日买/滚动卖”等加密方向文案。推荐 `非加密·不参与方向 / 仅图表活跃度 / 看主指标`；方法细节放 Data Window/tooltip。

### 9. 市场类别和交易场所要分离

`XAUUSDT.P` 可能是贵金属资产，但交易场所是 Binance U本位期货。资产识别为金属不应自动丢弃所有期货 OI/成交量；使用 `assetClass=metal` 与 `venueClass=cryptoFutures` 双维路由。期权标的同理只分析底层方向，不把普通 CVD 当作期权交易决策。

### 10. 低流动性门控先正规化 volume

任何“日成交额”必须先按 `syminfo.volumetype` 区分 base/quote/tick/n/a；禁止无条件 `volume*price`。否则薄量资产闸门本身可能误判。

## 五、P2 性能与界面断言

- `timenow` 过滤近30天线时，Bar Replay 应使用 replay 分支，不能把真实当前时间套在历史回放。
- HTF FVG/OB 若表达式已确认但外层 `lookahead_off`，标签为“延迟”，不能误报未来泄漏；可换 `lookahead_on` 提前发布已确认结果。
- 只有真正被消费的变量才保留。典型死链包括 `calctype`、`coverageRowA`、`htfTxtA`、`signalA`、`atrPctile`、`bosChochText`、`replayStopAtr`、`rdyGauge` 等；清理前先搜 Data Window、面板和外部解析器消费者。
- readiness 数值如果不渲染，只改变颜色就不能宣称“行动格显示就绪度”；方向/结构字符串需做重复词消除。
- `mcpLvCode=0` 且没有真实 LV 状态时，不能把 LV 写成已具备功能；要么标为保留字段，要么移除命名。
- Pine v6 的 request 条件、动态 context 和 plot color qualifier 不能靠简单 grep 推断；同时报告调用点、最坏运行时 context 和客户端最终预算。

## 六、社区证据与实现含义

| 来源 | 等级 | 可复用原则 |
|---|---|---|
| [TradingView CVD官方](https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/) | A | lower-TF价格/成交量分类是估算；低周期精度与历史覆盖有取舍 |
| [TradingView Repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/) | A | HTF确认使用表达式偏移与 `lookahead_on` |
| [TradingView Limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/) | A | 40 unique request、64 plot、lower-TF数据量需预算 |
| [TradingView Volume Profile](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/) | A | VA通常70%，POC向外比较候选桶 |
| [TradingView Open Interest](https://www.tradingview.com/support/solutions/43000685269-open-interest/) | A | OI不是多空人数，方向需结合价格和其他证据 |
| [Bookmap CVD教学](https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy) | B | CVD要靠关键位、成交量和价格反应，不能单独入场 |
| [ATAS吸收教学](https://atas.net/blog/absorption-of-demand-and-supply-in-the-footprint-chart/) | B | 吸收是 effort vs result，Pine只能做代理 |
| [ICT Killzones](https://innercircletrader.net/tutorials/master-ict-kill-zones/) | B | 使用纽约本地时间处理夏令时；黄金重点伦敦/纽约 |
| [TradingView社区Sweep→MSS→FVG](https://ar.tradingview.com/script/TP7yixOx-ICT-Entry-Model-Liquidity-Sweep-MSS-FVG-LunqFX/) | C | 连续路径、收回确认、触发有效期和失败重置 |
| [Stack Overflow request语义](https://stackoverflow.com/questions/79288126/optimizing-performance-in-pine-script-when-using-request-security-v6-using-co) | C | 条件块/三元不是可靠的性能开关，需 Profiler/客户端验证 |
| [TradeBobbyTerminal](https://github.com/SoCloseSociety/TradeBobbyTerminal) | C | 外部 freshness、清算、源匹配和 last-known-good 是可借鉴的系统架构 |

Reddit/论坛讨论只用于发现故障模式和待验证假设，不用于证明胜率或盈利 edge。

## 七、双指标人工决策验收矩阵

```text
主X                         → X，副指标不得翻案
主WAIT + 副S1/S2             → WAIT，继续等主触发
主A + 副同向且数据健康         → 人工可考虑的A候选
主A + 副S3/S4/源冻结/SMT反向   → WAIT或最高B，不得执行A
主B/C + 副同向                → 仍为B/C，不升级A
非加密                       → AggVol方向归零，只看主指标
```

A候选还必须同时满足：已收线、触发新鲜、价格几何正确、R:R达标、没有最终硬冲突。B/C价格只能进入观察字段，不能进入执行型 Data Window。

## 八、推荐实施顺序

1. Sweep/Breakout 分离与默认收回确认；
2. `finalHardBlock/finalDecision` 贯穿所有消费者；
3. AggVol source-time freshness、CVD method/quality、单源语义；
4. CVD Pivot配对、收线门和持久化路径；
5. MSS内部结构与OB缓解/FVG区间距离；
6. XAUUSDT.P 双维市场路由与 volume 正规化；
7. SVP增量桶缓存、AggVol plot 预算和客户端 Profiler；
8. 最后再评估 iFVG、EQH/EQL、HVN/LVN、前日VP；不加第三套CVD/总分/伪Footprint。
