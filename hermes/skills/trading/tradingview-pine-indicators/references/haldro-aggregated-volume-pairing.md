# HALDRO Aggregated Volume 副指标 审计 + 与 SVP v10 主指标配对

> 历史记录（2026-08-31）：旧版配对说明；当前双指标合同以定版源码和 `tv_indicator_contract.py` 为准。

用户(安禾/棠溪)的双指标体系：**主指标 = 定位/分级**(SVP+ICT+VWAP+EMA+CVD 六合一, indicator-only, ~3100行)，
**副指标 = 订单流验证**(HALDRO "Volume Aggregated Spot & Futures", @version=6, ~430行)。
两者本来就是为配合设计。审计/改任一指标前先读取用户 Web UI 上传的当前版本文件，不要假设桌面/patched 是最新。

## 配对用法（标准决策流）
1. 主指标给方向 + 等级(A/B/C/X) + 进场/止损/目标 + 磁吸位。
2. 副指标看右下角行动格"信号灯共振/4"与"结论"是否同向确认。
3. 共振绿灯 + 主指标 A级/扫★HTF = 可做；副指标背离 = 即便主给多也降级/放弃。
副指标行动格 comboTxt 里已写死这套联动文案(`配合主指标 A多/扫★HTF = 可做` 等)。

## HALDRO 副指标的三大固有坑（审计必查）

### P0 — request.security 40 调用上限 (static count — 三元/if/开关都不省配额)
`GetExchange()` 每次调 4 次(SPOT1/SPOT2/PERP1/PERP2) × 9 交易所 = **36 个 security**，
加 VAREUR + VARRUB + OI(`syminfo.tickerid+'_OI'`) = **39/40**，贴上限。
**关键陷阱**：Pine 按**编译期静态计数**，三元条件包裹、input.bool 开关关闭、if 块包裹都**不减配额**
（TradingView 在主脚本前预取全部；Stack Overflow 实测 profiler 确认三元内的 request.security 仍每 bar 执行）。
因此：
- ❌ `VAREUR = coinusd=='EUR' ? request.security(...) : na` 不省配额（结果仍被 EditVolume 引用→编译期计入）
- ❌ 把默认交易所关到 false 不省配额，只会让聚合变差
- ✅ 唯一减配额的路径：**物理删除** request.security 调用点（砍 GetExchange 里的交易所，或减掉 GetExchange 调用次数）
- 要加 OI 聚合须先真砍 3-4 家交易所腾 12-16 个配额，不能在现有的 39/40 上加。
- 再多加一个 security 调用就 `too many securities` 编译失败。

### P1 — max_bars_back 偏小
HALDRO 原版 `max_bars_back=500`，有 `ta.cum`(OBV)/累计Delta/sessCvd，长周期图历史被截断。提到 2000。

### P2 — 自定义对 INPT1/INPT2 命名错位（HALDRO 遗留）
原版 PERP2_* 行用 `str.length(INPT1)>0 ? INPT2` 判断了 INPT1 却填 INPT2，与 tooltip"第二字段替换永续1"矛盾。
最终因相加抵消结果碰巧正确，但改动极易踩雷。修正为判断 INPT2。

## 三个口径冲突的处置
- **冲突1 (两套CVD算法不同) = 方法论固有，不可消除，只能定口径**：
  主指标 `request.security_lower_tf` 汇总子K价格方向成交量（粒度较细但仍是估算） vs 副指标影线/实体占比估算（更粗）。两者都不是真实bid/ask逐笔；TradingView官方CVD也明确使用intrabar价格与成交量来“estimate”买卖压力。
  **规则：冲突时以主指标的关键位门控CVD为优先背景，副指标“流向”行只当聚合量能佐证。**
- **冲突2 (CVD锚定周期不同)**：副指标 sessCvd 写死按日重置。修复=加 `会话CVD锚定 日/周/月` input，
  `time(cvdAnchorTf)` 替换 `time('D')`，与主指标日/周/月锚定对齐。
- **冲突3 (非加密品种失真)**：副指标聚合 9 家加密交易所，挂 XAU/外汇/股指时拼出的 `BINANCE:XAUUSDT` 不存在
  → `ignore_invalid_symbol` 返回0 → 整个聚合失真给错误结论。
  修复=`bool isCryptoA = syminfo.type == 'crypto'`，行动格渲染门控：非加密只显示"非加密品种 / 聚合仅对加密有效 / 请看主指标判定"，不出误导结论。

## 零配额可加的优化（不占 security 数，已在副指标落地）
- **OI×价格背离检测**：`oiDivergeA = oiOkA and ((priceUpA and oiDnA) or (priceDnA and oiUpA))`
  价涨仓跌或价跌仓涨 = 杠杆与价格反向 = 挤压/瀑布前兆(社区 Leverage Hunter 口径)，持仓行标 ⚡，纯逻辑零配额。
- **CVD 锚定对齐**：`ta.change(time(cvdAnchorTf))` 替代 `time('D')`，日/周/月可选，零配额。
- **占比并入量能**：`volTxtA` 加 `合67%` 尾缀，省一行表格空间，零配额。

## 行动格优化原则（少占空间 + 信息密度）
- 主指标已有 精简/标准/完整 三档：盯盘默认"精简"(结论/方向/进场/止损/目标 5行)，复盘才切"完整"。社区共识=盘口只需"怎么下单"。
- 磁吸↑/↓ **保持各自一行**（用户明确要求不改，上下分色让准备入场方向一目了然）。
- 副指标 9 行偏多："占比"信息量低可并入"量能"行尾(`放量·合67%⚠主导`)；默认开精简模式(信号/结论/操作 3行)。

## v2 已落地（2026-07-10复核 · 默认展开约32/40配额）

### 交易所精简 9→5 + OI 聚合 4 源（完整实操）

1. **GetExchange 物理删 4 行**：移除 EX_6(KUCOIN)/EX_7(KRAKEN)/EX_8(CRYPTOCOM)/EX_9(MEXC) → 9元组→5元组
2. **收缩所有下游**：GetVolume 解构 9→5 · Processing Volume 9→5 · SPOT/PERP 求和 9→5 · EXlist/EXnames/EXcolors 9→5 · 循环 `0 to 8`→`0 to 4` · EXv 变量 9→5 · 彩色量图 plot 9→5
3. **加 OI 聚合**：`f_oi(ex)` 函数 ×4(BINANCE/BYBIT/OKX/BITGET) + oiSingleA 回退 + SHOW_OI_AGG input
4. **配额核算（2026-07-10按当前源码展开）**：5所×4成交量 = 20 + EUR/RUB 2 + `f_oi()`内USDT/USDC两请求×4所 = 8 + LSR 1 + OI单源回退1 = **约32/40**（默认方案仅余8）。源码旧注释“27/40”漏算每所第二个OI请求和LSR，必须修正。
5. **tooltip 诚实**：开关关闭注明"静态计数不省配额，关仅减运行时负载"

### CVD 背离标注（审计项，不可假设已落地）

社区/Bookmap/LuxAlgo 对副图订单流的共识是：价格 HH/LL 与 CVD LH/HL 背离应在「流向」行显式标出，并参与降级。审计当前生产 `haldro_indicator.txt` 时必须先 grep `cvdBearDiv` / `cvdBullDiv`；如果没有，则标 P1 优化项。推荐实现：`cvdHighLB`/`cvdLowLB` vs `priceHighLB`/`priceLowLB`，再加 `swing > 1.5×ATR` 与 CVD slope 方向过滤。背离时显示 `⚠卖背离`/`⚠买背离`（cWarn 色），正常时保持 `买盘占优/卖盘占优`。不要在未验证源码前写“已落地”。

### 新增：方向行三层信息

主指标标准档方向行携带三层上下文：`偏多 EMA多头 · 折价偏下 ⚡伦敦开盘 · 已扫3/剩5`（溢价折价+KillZone+扫位计数前置标准档）。
