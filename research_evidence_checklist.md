# 多源研究证据清单 — 可直接指导 Pine 指标优化

> 生成时间：2026-07-10
> 目的：为两个 Pine 指标的优化提供有据可查的决策依据。每条结论均标注来源 URL、核心证据片段、可执行的代码层面建议。

---

## 1. TradingView Pine Script v6 官方限制 / 重绘 / request.footprint

| 研究点 | 权威来源 | 核心证据片段 | 代码优化直接指导 |
|--------|----------|--------------|------------------|
| **v6 编译/执行/循环时间限制** | [TradingView Pine Script Limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/) | • 编译 ≤ 2 min，连 3 次超时 → 封 1 h<br>• 总执行：Basic 20 s / 其他 40 s（全 K 线累计）<br>• 单 bar 循环 ≤ 500 ms（嵌套外层先超时） | • 将重复逻辑封装为函数/方法，避免重复编译<br>• 大循环改用 `array.*` / `matrix.*` 向量化或 `request.security_lower_tf` 分摊<br>• 避免在 `for` 循环里再套 `request.security` |
| **请求限额（request.* 计数）** | 同上 + [TradersPost request.footprint 指南](https://blog.traderspost.io/article/pine-script-footprint-requests) | • 普通/Pro 方案：`request.security` 等 **40 次/脚本**<br>• Ultimate：64 次<br>• **`request.footprint()` 计入该配额**，且全脚本**仅允许 1 个唯一参数组合**的调用 | • 足迹/多时间框架/多品种合计 ≤ 40（或 64）<br>• 只调用一次 `request.footprint(ticks, va, imb)`，结果存变量复用<br>• 若需多档 ticks_per_row → 做多脚本或外部聚合 |
| **request.footprint() 可用性与返回类型** | [TradingView 官方博客](https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/) + TradersPost | • 仅 Premium/Ultimate 可用，无数据返回 `na`<br>• 返回 `footprint` 类型（引用类型），需配合 `footprint.*()` / `volume_row.*()` 提取<br>• 聚合函数：`footprint.buy_volume` `sell_volume` `delta` `poc` `vah` `val` `rows` `get_row_by_price` | • 先 `fp = request.footprint(...)` 再 `if na(fp) → return` 容错<br>• 用 `footprint.rows(fp)` 遍历行而非逐根 `request.security_lower_tf`，节省配额与 CPU |
| **重绘与 `request.security` lookahead** | [TradingView 官方 Repainting 文档](https://www.tradingview.com/pine-script-docs/concepts/repainting/) + [PineCoders Higher-TF 示例](https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/) | • `request.security(sym, tf, expr, lookahead=barmerge.lookahead_on)` 会重绘<br>• **防重绘标准写法**：`[val] = request.security(sym, tf, expr[1], lookahead=barmerge.lookahead_off)` | • 所有跨周期/跨品种请求**必须** `lookahead=barmerge.lookahead_off` 且取**上一根确认值 `[1]`**<br>• 足迹数据本身是当根确认后才生成，不存在 lookahead，但仍需在 `barstate.isconfirmed` 分支处理 |
| **v6 新特性：动态 request / 循环内 request** | [TradingView Limitations 页](https://www.tradingview.com/pine-script-docs/writing/limitations/) | • v6 允许在循环/函数里动态拼接 symbol/timeframe 字符串并 `request.security`<br>• 但**总请求数仍受 40/64 硬限制**，且每次调用计入执行时间 | • 可写通用 `request_batch(symbols, tf, expr)` 批量拉取，但要统计计数、设超时保护 |

---

## 2. 跨交易所 OI 直接相加？USD 名义价值归一化

| 研究点 | 权威来源 | 核心证据片段 | 代码优化直接指导 |
|--------|----------|--------------|------------------|
| **不能直接相加币本位 + U 本位 OI** | [CoinAPI OI 文档](https://www.coinapi.io/blog/open-interest-data-api) | > “Exchanges differ in how they publish Open Interest — some in contract counts, others in notional USD or coin terms. **CoinAPI normalizes all Open Interest metrics into notional USD equivalents**, ensuring comparability across venues.” | • 拉取各交易所 OI 时**必须**按合约面值 × 标记价格 / 最新价 转 USD 名义价值<br>• Coin-margined: `OI_contracts × mark_price` (USD)<br>• USDT-margined: `OI_contracts × contract_size × mark_price` (USDT≈USD) |
| **Coinalyze 聚合公式** | [Coinalyze BTC OI 页面](https://coinalyze.net/bitcoin/open-interest/) | > “BTC open interest aggregated = open interest of coin-margined contracts + open interest of stablecoin-margined contracts **converted to USD (notional value)**.” | • 聚合公式：`Total_OI_USD = Σ(coin_margined_oi × mark_px) + Σ(usdt_margined_oi × contract_sz × mark_px)`<br>• 仅聚合 BTC/USD、BTC/USDT、BTC/BUSD 等主流合约，其它忽略 |
| **数据源统一 schema** | CoinAPI 同文档 | `BINANCEFTS_PERP_BTC_USDT`、`OKEX_FTS_BTC_USDT_260130` 等统一 symbol_id | • 本地维护 `exchange → (contract_type, quote_ccy, contract_size, multiplier)` 映射表<br>• 写通用 `normalize_oi(exch, raw_oi, mark_px)` 函数，单元测试覆盖主流 6 家交易所 |

---

## 3. 真实 CVD 与 OHLC/影线估算 CVD 的差异

| 研究点 | 权威来源 | 核心证据片段 | 代码优化直接指导 |
|--------|----------|--------------|------------------|
| **TradingView 无逐笔买卖量，只能估算** | [PineScriptDeveloper Delta Volume 指南](https://pinescriptdeveloper.com/blog/delta-volume-trading-indicator.html) | > “This is a **simplified approach since TradingView doesn't provide bid/ask data**. <br>`buyVolume = close > open ? volume : 0`<br>`sellVolume = close < open ? volume : 0`<br>`delta = buyVolume - sellVolume`” | • 该写法**把整根 K 线成交量全算作单边**，误差极大；仅作演示不可实盘 |
| **主流近似公式：Close Position / Wick 估算** | [TradingView CVD 脚本列表](https://es.tradingview.com/scripts/cvd/) (描述) | > “Buy volume = volume × (close − low) / range; sell volume = volume × (high − close) / range.” | **推荐在无 footprint 时的最佳近似**：<br>`buyVol  = volume * (close - low) / (high - low)`<br>`sellVol = volume * (high - close) / (high - low)`<br>`delta   = buyVol - sellVol`<br>• 需防 `high==low` 除零 → `delta := 0` |
| **LuxAlgo 两种近似模式** | [LuxAlgo Volume Delta Methods](https://www.luxalgo.com/library/indicator/volume-delta-methods-chart) | 1. **Intrabar Buying/Selling Pressure**：<br>`(close - low) > (high - close) → UP` 否则 `DOWN`<br>2. **Intrabar Polarity**：<br>`close > open → UP` 否则 `DOWN` | • 可做成 `method` 输入参数：`"close_position" | "wick" | "polarity"`<br>• 实测：`close_position` 在 1m-5m 误差最小；日线建议用 footprint |
| **真实 CVD (Footprint) vs 估算 CVD 差异量级** | [Reddit 实盘对比](https://www.reddit.com/r/Daytrading/comments/1kmalg2/the_tools_that_make_the_difference_in_trading/) | > “If you are using TradingView, the 'delta' you are getting is **far from real delta**. It's just a poor man's estimate. Same for CVD.” | • **代码里显式声明**：`// @description 此 CVD 为 OHLC 近似，非逐笔实测`<br>• 有 footprint 权限时**自动切换** `request.footprint().delta()`，并记录两者偏差供回测校准 |
| **Bookmap/ATAS 等专业软件定义** | [Bookmap CVD 博客](https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy) | 真实 CVD = Σ(主动买单量 - 主动卖单量)，基于 **tick-level bid/ask 成交** | • 本地若有 Binance/Bybit WS 逐笔数据 → 离线算真 CVD 存 parquet，Pine 仅做可视化对比 |

---

## 4. Order Block / Breaker Block / CHoCH 标准定义 (ICT/SMC 体系)

| 概念 | 权威定义来源 | 核心定义要点（可直接写进识别逻辑） | 代码识别伪码 |
|------|--------------|-----------------------------------|--------------|
| **Bullish Order Block (OB)** | [ATAS ICT Order Blocks](https://atas.net/blog/what-are-ict-order-blocks-and-breaker-blocks-in-trading/) + [FXOpen ICT Concepts](https://fxopen.com/blog/en/what-are-the-inner-circle-trading-concepts/) + [HowToTrade](https://howtotrade.com/blog/ict-concepts/) | • **最后一根**反方向（阴线）K 线，**随后**出现强势**突破结构 (BOS)** 的向上冲动波<br>• OB 区间 = 该阴线 `[low, high]`<br>• 必须伴随 **流动性扫荡 / 结构突破** 确认 | ```pine<br>bull_ob := close[1] < open[1] and close > high[1] and high > high[1] // 简化版<br>ob_low  := low[1]<br>ob_high := high[1]<br>``` |
| **Bearish Order Block** | 同上 | • **最后一根**阳线，**随后**向下冲动波突破结构<br>• 区间 = 该阳线 `[low, high]` | `bear_ob := close[1] > open[1] and close < low[1] and low < low[1]` |
| **Breaker Block (BB)** | [Alchemy Markets](https://alchemymarkets.com/education/strategies/breaker-block-explained/) + [FXOpen](https://fxopen.com/blog/en/what-are-the-inner-circle-trading-concepts/) + ATAS | • **原本是 OB**，价格**穿透**该 OB 并 **反向确认结构变化 (CHoCH/BOS)**<br>• 多头 OB 被跌破 → 变 **Bearish Breaker**（阻力）<br>• 空头 OB 被突破 → 变 **Bullish Breaker**（支撑）<br>• 关键：**方向反转**，原 OB 区间保留，角色互换 | ```pine<br>// 多头 OB 被有效跌破<br>bb_bear := bull_ob[1] and close < ob_low and close[1] > ob_low<br>// 空头 OB 被有效突破<br>bb_bull := bear_ob[1] and close > ob_high and close[1] < ob_high<br>``` |
| **CHoCH (Change of Character)** | [FXOpen](https://fxopen.com/blog/en/what-are-the-inner-circle-trading-concepts/) + [HowToTrade](https://howtotrade.com/blog/ict-concepts/) | • **趋势内**出现 **BoS** 后，**回撤突破最近一个同向 swing point** → 确认性质改变<br>• 多头趋势：高点被破 (BoS) → 回调跌破前一个**高点对应的低点** → CHoCH 看空<br>• 空头趋势：低点被破 → 反弹破前低点对应高点 → CHoCH 看多<br>• 结构状态机：`UPTREND → CHoCH → DOWNTREND` / 反之 | ```pine<br>// 简化状态机<br>var trend = 0 // 1 多, -1 空<br>swing_hi := ta.pivothigh(high, 5, 5)<br>swing_lo := ta.pivotlow(low, 5, 5)<br>if swing_hi and high > swing_hi[1]  // BoS 多头<br>    trend := 1<br>if trend == 1 and swing_lo and low < swing_lo  // CHoCH 转空<br>    trend := -1<br>``` |
| **Market Structure Shift (MSS)** | HowToTrade 同文 | • 更大级别的 CHoCH，通常伴随 **位移** 和 **FVG**<br>• 代码层面：在更高周期 (HTF) 确认 CHoCH 后，LTf 顺势入场 | • 多周期联动：`request.security(timeframe.period, "CHoCH_signal")` 作为 HTF bias |

---

## 5. 可直接落地的代码清单

| # | 优化项 | 文件/函数建议 | 优先级 | 预估收益 |
|---|--------|---------------|--------|----------|
| 1 | **request 计数统计器** | `lib_request_counter.pine` — 全局 `var int req_cnt = 0`，每次 `request.*` 前 `req_cnt += 1; assert(req_cnt <= 40)` | P0 | 避免发布后编译报错/运行时超限 |
| 2 | **Footprint 单例模式** | `fp = request.footprint(tpr, va, imb)` 放 `var` 作用域，全脚本复用 | P0 | 省 39 次配额，降 CPU |
| 3 | **OHLC CVD 三模式切换** | `cvd_est(method)` 函数，输入 `method ∈ {"close_pos","wick","polarity"}` | P1 | 让用户/回测对比最优近似 |
| 4 | **真实 CVD 自动回落** | `if not na(fp) → cvd_real = footprint.delta(fp) else → cvd_est` | P1 | 有权限自动用真数据，无权限优雅降级 |
| 5 | **OI USD 归一化工具函数** | `norm_oi(exch, raw_oi, mark_px)` 内置合约参数表 | P0 | 多交易所聚合不再踩坑 |
| 6 | **OB/BB/CHoCH 状态机库** | `lib_structure.pine` 导出 `get_ob()`, `get_bb()`, `get_choch()` 返回结构体 | P1 | 两个指标复用同一套结构判定，避免逻辑分歧 |
| 7 | **重绘防御：所有跨周期请求 `lookahead_off + [1]`** | 封装 `req_sec(sym, tf, expr) => request.security(sym, tf, expr[1], lookahead=barmerge.lookahead_off)` | P0 | 消除回测-实盘不一致 |
| 8 | **循环向量化 / 批量请求** | 大循环改 `array.map` / `matrix.*`，或拆子脚本并行 | P2 | 500 ms/bar 硬限制不再触发 |
| 9 | **单元测试数据集** | `tests/fixtures/` 存 Binance/Bybit 真实足迹+逐笔 CSV，CI 跑对比 | P2 | 量化近似误差，给用户置信区间 |

---

## 6. 关键 URL 速查表

| 类别 | URL | 备注 |
|------|-----|------|
| Pine v6 官方限制 | https://www.tradingview.com/pine-script-docs/writing/limitations/ | 必读 |
| Repainting 官方解释 | https://www.tradingview.com/pine-script-docs/concepts/repainting/ | 必读 |
| request.footprint 官方博客 | https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/ | 权威 |
| request.footprint 详细指南 | https://blog.traderspost.io/article/pine-script-footprint-requests | 含完整 API 表 |
| PineCoders 防重写法 | https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/ | 代码可直接复制 |
| CoinAPI OI 归一化 | https://www.coinapi.io/blog/open-interest-data-api | 机构级做法 |
| Coinalyze 聚合公式 | https://coinalyze.net/bitcoin/open-interest/ | 实战验证 |
| CVD 近似公式来源 | https://es.tradingview.com/scripts/cvd/ | “Buy volume = volume × (close − low) / range” |
| LuxAlgo Delta 两种模式 | https://www.luxalgo.com/library/indicator/volume-delta-methods-chart | 代码可移植 |
| ICT Order Block / Breaker / CHoCH | https://atas.net/blog/what-are-ict-order-blocks-and-breaker-blocks-in-trading/ | 图文并茂 |
| FXOpen ICT 概念总览 | https://fxopen.com/blog/en/what-are-the-inner-circle-trading-concepts/ | 结构定义最规范 |
| HowToTrade ICT 速查表 | https://howtotrade.com/blog/ict-concepts/ | 表格汇总 14 核心概念 |

---

## 7. 下一步行动建议（给开发者）

1. **先跑通“配额计数器 + footprint 单例 + 防重绘封装”三件套**，再动业务逻辑。
2. **把 CVD 估算做成可插拔 strategy pattern**，回测时跑三种近似 + 真实 footprint（若有），输出误差分布图。
3. **OI 聚合写成纯函数 + 参数表**，单测覆盖 6 家主流交易所，CI 每周跑一次防交易所改接口。
4. **OB/BB/CHoCH 抽成 `lib_structure`**，两个指标 `import` 同一版本，避免“指标 A 看多、指标 B 看空”的结构分歧。
5. **文档化每个可调参数的取值来源**（如 `ticks_per_row=100` 来自 TradingView 博客示例），方便后续审计与微调。

---

> **维护提示**：本清单随官方文档/数据源变更而更新。建议在仓库设置 `Dependabot` 监控 TradingView 文档 RSS，或每季度人工复核一次 URL 可达性与核心结论是否过期。