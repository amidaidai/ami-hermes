# 免费档性能榨干：社区研究 + 双指标实测（2026-08-06）

适用：TradingView 免费 Basic 账号榨干 SVP+ICT+VWAP+CVD 主指标 + AggVol 副指标性能，不炸 20s 时限、不超配额。本会话多源搜索（Tavily/Exa/Brave 轮换）+ 逐行审计实测结论。

## 一、社区证据（来源已标注）

### Pine Profiler（官方，免费可用）
- 官方 Profiler 逐行显示执行耗时/内存，免费账号可用。用法：图表右下角 Profiler 面板打开。
- `memory.log()` 是 Pine v6 新增运行时内存监控函数。
- 来源：https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/ + 官方博客 https://www.tradingview.com/blog/en/boost-scripts-with-pine-profiler-44449/

### LuxAlgo「5 个慢脚本成因」（2025-04 更新，2026-07 复核）
1. **Poor Loop Design**：自定义循环比内建函数慢 **18–100×**。实测 20 周期：custom loop 57.9ms vs `ta.highest()` 3.2ms；200 周期 600ms vs 5.8ms。
2. **Redundant Calculations**：同一函数/计算重复调用。多次函数调用 2.5s vs 优化后 0.6s。
3. **Misused Built-ins**：`request.security()` 放对位置，用优化过的 native 函数。
4. **Too Many Data Requests**：合并多个 `request.*()` 为 tuple 调用（9→1 可从 340ms 降到 228ms）。
5. **Poor Memory Usage**：预分配数组大小比动态 `push` 高效；`memory.log()` 跟踪。
- 来源：https://www.luxalgo.com/blog/5-causes-of-slow-pine-scripts-on-tradingview

### calc_bars_count（官方）
- 官方文档在 `indicator()` 用 `calc_bars_count` 限制可用历史；`request.security_lower_tf()` 的 `calc_bars_count` 限制 intrabar 拉取量。免费档 intrabar 上限 100K。
- 不传则按图表全量K拉 intrabars（5m 挂 1m = 25,000 根；4h 挂 60m = 20,000 根）→ 爆 20s。
- ⚠ 绝不能硬编码 `calc_bars_count=1000`：SVP 分布图 D 周期需 1440 根 1m intrabar，1000 截断 30% 使 POC/VAH/VAL 算错。必须动态算 `max(1000, profSec/precSec, chartSec/precSec)`。
- 来源：https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/

### TradersPost（v6 dynamic requests）
- 表格/面板绘制逻辑包 `if barstate.islast` 避免历史每根K重绘。
- 每个 unique symbol-timeframe-expression 组合计入 40 调用上限。
- 来源：https://blog.traderspost.io/article/pine-script-v6-dynamic-requests

### Bookmap / ATAS / Reddit（决策层面，非性能）
- CVD 背离须发生在已知参考位（前高低/VWAP/VA/流动性区）+ 等价格 reaction/failure-to-continue，**不能看到背离就反手**（Bookmap 2026-01）。
- 吸收 = 大量主动成交却推不动价格（effort vs result），须与价格反应合用（ATAS）。
- TradeBobbyTerminal 对 CVD divergence 诚实回测：**无 standalone edge**，只作 confluence lens。

## 二、双指标实测性能热点（2026-08-06 主指标 2983 行 / 副指标 603 行）

### 主指标：`processAndRender()` 是最大热点
- L1573 每根K全量重算（`barstate.islast` 只控制绘图，数值计算每根K跑）。
- 复杂度：`MAX_ARRAY_SIZE=95000` × 每元素 3–5 个 bucket 循环 × 5000 bars = 数亿次。
- 实际：5m 图 D profile 累积 1440 元素、W=10080、M=43200；M profile 下 O(43200)×5000 ≈ 2 亿次 → 危险。
- **已落地缓解**：`estCost = FINAL_ROWS * estBarsInProfile` + `AUTO_DEGRADE_PRECISION`，超 `DEGRADE_THRESHOLD`（默认 220000）自动降级到图表周期计算，砍 intrabar 量。
- **✅ 已落地（本会话实施）**：histogram 数组（`vaPositions`/`nonVaPositions`）构建 + `rowHeight` 已移入 `if renderProfileObjects` 门控。历史K（renderObjects=false）跳过 O(FINAL_ROWS) 的数组分配与 push。主指标 5000 根K × ~70 次 ≈ 35 万次数组操作直接消除。POC/VAH/VAL 数值计算仍在门控外每根K确定性执行（消费端 curPoc 需要），只把纯绘图数组移入渲染分支——这是「决策完整性增量检查 #1 数值每根K/绘图仅islast」的又一实例。

### 副指标：两处廉价优化（✅ 均本会话实施）
- `FX_CONV_RATE`：改为 `coinusd=='USD' ? na : request.security(...)` 短路。默认 USD 单位运行时跳过自身 close 请求；**静态配额仍计 1 个，不影响编译**（v6 dynamic requests 下未执行分支不形成运行时 unique context，但源码调用点仍占用静态计数）。EUR/RUB 用户不受影响。
- `EXlist.sum()`：提出循环为 `float exTotalSum = EXlist.sum()`，5 元素循环内不再每轮重算总和。

## 三、免费档性能优化优先级排序（按性价比）

1. **P0**：lower_tf 加动态 `calc_bars_count`（主指标两处：SVP 精度 + CVD）——最大 20s 超时缓解。
2. **P0**：`alertcondition()` → 事件化 `alert()`（免费档 0 技术告警，alertcondition 纯死重又占 plot count）。
3. **P1**：主指标 `processAndRender` histogram 数组移入 `renderProfileObjects`。
4. **P1**：副指标 `FX_CONV_RATE` 短路 + `EXlist.sum` 提出循环。
5. **P2**：合并 `request.security()` 为 tuple（LuxAlgo 340→228ms）。

## 四、静态验证
改完跑 `scripts/pine_static_scan.py`，确认 plot/request/未定义变量/def-before-use 全绿。最终编译必须贴回 TradingView 实测（Profiler 面板看实际耗时是否降）。

## 五、交付注意
文件命名带修改日期（`_20260806.txt`），indicator 内部标题不动，旧版归档 `历史版本/`。
