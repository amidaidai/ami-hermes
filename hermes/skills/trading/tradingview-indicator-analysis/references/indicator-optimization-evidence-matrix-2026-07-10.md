# 指标下一版优化证据矩阵 (2026-07-10)

> 本文档记录基于 TradingView 官方文档、Release Notes、社区高赞脚本的证据矩阵，直接给出**建议做/不建议做**的排序建议。用于指导 `tradingview-indicator-analysis` 技能下的指标迭代决策。

---

## 数据来源分级

| 标记 | 来源类型 | 示例 |
|------|----------|------|
| **[官方]** | TradingView 官方文档、博客、Release Notes、Pine Script 参考手册 | `request.footprint()` 文档、v6 Release Notes、Repainting 定义 |
| **[社区验证]** | TradingView 社区高赞脚本、PineCoders 官方范例、知名开发者 | Zeiierman Ranked FVG `Z4h7vDqN`、ProjectSyndicate `GGo1s64a`、QuantAlgo `2pH4ZOw5` |
| **[推断]** | 基于技术约束与实战逻辑的合理推断 | 请求预算管理器、HMM 离线训练建议 |

---

## 一、高优先级：必须做 / 强烈建议（ROI 最高）

| # | 优化项 | 证据等级 | 核心依据 | 预期收益 | 实施难度 |
|---|--------|----------|----------|----------|----------|
| 1 | **接入 `request.footprint()` 原生订单流** | **[官方]** | 2026年1月正式上线；Premium/Ultimate 可用；提供 POC/VAH/VAL/Delta/Imbalance 逐行数据；无需低周期 workaround | 真实机构级订单流确认、Delta 分歧、POC 支阻、VA 回踩 — 核心短线胜率提升 | 中（需适配 Premium+ 账户、处理 40/64 次请求限制） |
| 2 | **非重绘 HTF 多周期确认架构（v6 动态 request.security）** | **[官方]** | v6 支持 `series string` 参数、循环内调用、lookback 强制对齐 confirmed bar；PineCoders 官方范例 `W1YpYcOI` | 消除 HTF 信号重绘、多周期共振可信度质变、回测/实盘一致 | 低（改写请求逻辑、加 `lookahead=barmerge.lookahead_off`、`gaps=barmerge.gaps_off`） |
| 3 | **Ranked FVG/OB 质量评分体系（0-100 就绪度）** | **[社区验证]** | Zeiierman `Z4h7vDqN`、ProjectSyndicate `GGo1s64a`、Fair-Value-Gap 脚本均实现：缺口大小、成交量验证、回测填补进度、中点回踩质量、共振加分 | 过滤 70%+ 低质量 FVG/OB、仅保留高概率区域、减少假突破止损 | 中（需建立多因子评分：缺口幅度、成交量、HTF 方向一致性、回踩次数、订单流确认） |
| 4 | **市场状态/体制分类器集成（趋势/震荡/收敛/爆发）** | **[社区验证]** | QuantAlgo `2pH4ZOw5`、KK `0GHiGzOp`、AlphaExtract `xQ2fBtZ3`、HMM Enhanced `iF0ZwCVf` 均在生产环境运行 | 策略自适应切换：趋势跟踪 vs 均值回归、风控参数动态调整、避免体制错配亏损 | 中高（建议集成 ADX+波动率状态+HMM 概率，而非单一指标） |
| 5 | **多资产自适应框架（syminfo.type/mintick/pointvalue/minmove）** | **[官方]** | 官方文档 `Chart information`、`syminfo.type` 返回 cfd/stock/futures/indices/forex/crypto/fund；`syminfo.mintick/pointvalue/minmove` 自动适配精度/点值 | 一套代码跑通 Crypto/XAU/FX/股票/期货/期权、无需手动改参数、部署维护成本↓90% | 低（封装 `getAssetConfig()` 返回精度、点值、手续费、交易时段、最小下单量） |

---

## 二、中优先级：建议做（显著增强，非阻断）

| # | 优化项 | 证据等级 | 核心依据 | 预期收益 | 实施难度 |
|---|--------|----------|----------|----------|----------|
| 6 | **订单流确认入场模块（CVD 分歧 + Footprint Delta + Imbalance）** | **[社区验证]** | Supa.is 实战策略、CVD Delta Divergence [JOAT]、Footprintchart 社区脚本：Delta 分歧+K线形态确认、POC 回踩+成交量验证 | 入场胜率提升 15-25%、过滤假突破、提供客观离场依据（Delta 反转） | 中高（需足迹数据、实时计算 CVD、分歧检测延迟 1-2 根 K） |
| 7 | **动态请求限额管理（40/64 次 request.* 预算分配）** | **[官方]** | 官方 Limitations：Basic 20s/40s 执行时间、40 次请求上限（Ultimate 64）、`request.footprint()` 计入预算 | 避免运行时错误、多模块（HTF+Footprint+Multi-symbol）共存、稳定性保障 | 低（建立请求预算管理器、优先级队列、缓存复用） |
| 8 | **v6 新特性全面迁移：Enums、Runtime Logging、Polyline、Multiline Strings** | **[官方]** | v6 2024年11月发布，后续仅 v6 得新功能；Enums 类安全下拉、log.info() 调试、polyline 绘图性能↑ | 代码可维护性↑、调试效率↑、绘图对象上限突破、UI 专业度↑ | 低（逐模块迁移、兼容 v5 降级策略） |
| 9 | **Lower-TF 微观结构分析（request.security_lower_tf 返回 array<intrabar>）** | **[官方]** | 官方文档：最多 200,000 根 intrabars、返回数组而非 series、可重构 1 分钟内部结构 | 5m/15m 图上重现 1s/5s 微观结构、精准定位入场、订单流细分析 | 高（数组处理复杂、执行时间压力大、需严格剪枝） |

---

## 三、低优先级 / 暂缓 / 不建议

| # | 项 | 判定 | 理由 |
|---|-----|------|------|
| 10 | **全 HMM/贝叶斯/RL 在 Pine 原生实现** | **❌ 不建议** | Pine 无矩阵库、无 GPU、循环 500ms 硬限制、200k bars 训练不可行；建议离线 Python 训练 → 仅在 Pine 部署推理权重/阈值 |
| 11 | **期权希腊值/隐含波动率原生计算** | **❌ 不建议** | TradingView 无期权链数据源、无 IV 历史序列、Black-Scholes 在 Pine 逐根 K 算极慢且不精确 |
| 12 | **DOM/Level2 逐笔队列重建** | **❌ 不建议** | 官方明确：足迹数据仅聚合到价格行级、无原始 DOM 深度、无法重建真实队列 |
| 13 | **跨交易所套利/资金费率实时监控** | **❌ 不建议** | `request.security` 仅支持 TV 自有数据源、无多交易所统一符号、延迟不可控 |
| 14 | **全自动化下单/策略实盘（非回测）** | **⚠️ 暂缓** | Pine 策略实盘有已知限制（非标准图表、回测/实盘差异、订单管理原语缺失）；建议用 Webhook→外部执行引擎 |
| 15 | **社交情绪/链上数据/宏观日历原生接入** | **⚠️ 暂缓** | 仅 `request.economic()` 支持有限宏观序列、无链上/情绪数据源；建议外部采集→`request.seed()` GitHub 托管 CSV 注入 |
| 16 | **重写现有所有指标为 v6 语法** | **❌ 不建议** | v5 继续运行、无强制迁移截止；仅新模块用 v6、旧模块按需重构（Enums/动态请求优先） |

---

## 四、关键约束与风险提示（实施前必读）

| 约束项 | 官方铁律 | 规避方案 |
|--------|----------|----------|
| **request.footprint 权限** | 仅 Premium/Ultimate，Free/Essential 完全不可用 | 降级方案：`request.security_lower_tf` 近似合成 Delta/POC、或标注“需高级会员” |
| **请求预算 40/64 次** | 每脚本上限，`request.footprint` 计 1 次，`request.security` 计 1 次 | 预算管理器：HTF 确认 3-5 次、Footprint 1 次、Multi-symbol 轮询复用 |
| **执行时间 20s/40s** | Basic 20s、其它 40s，超时即报错停止 | 剪枝：`calc_bars_count` 限制历史深度、循环早退、数组预分配、避免嵌套循环 |
| **Loop 500ms/bar** | 单 bar 单循环硬上限 | 分批处理、状态机化、仅可见范围 `chart.left/right_visible_bar_time` 绘图 |
| **Plot/视觉对象 64 个** | `plot/plotshape/box/label/line/fill` 共用 | 合并同类绘图、polyline 替代多 line、动态创建/销毁、优先级渲染 |
| **Footprint 数据可用性** | 非全品种、非全时段、CME/加密主流较全、Forex/CFD 可能无 | `not na(reqFootprint)` 守卫、缺失时降级 CVD 近似、UI 提示数据源状态 |
| **非标准图表策略禁用** | Heikin Ashi / Renko / Kagi / Line Break / P&F 策略回测不可靠 | 仅在标准 K 线跑策略、非标图仅做可视化、文档显式声明 |

---

## 五、建议实施路线图（3 迭代）

| Sprint | 交付物 | 关键验收标准 |
|--------|--------|--------------|
| **S1 (1-2 周)** | 1️⃣ v6 迁移 + Enums/Logging<br>2️⃣ 非重绘 HTF 请求封装库<br>3️⃣ 多资产自适应配置模块 | 全模块 v6 语法、HTF 信号历史/实盘 100% 一致、切换 BTC/ETH/XAU/ES/6E 无需改参数 |
| **S2 (2-3 周)** | 4️⃣ Ranked FVG/OB 评分引擎（0-100）<br>5️⃣ 市场状态分类器（ADX+波动率+HMM 阈值）<br>6️⃣ 请求预算管理器 | FVG/OB 评分与人工复盘一致性 >85%、体制切换延迟 <3 根 K、请求数≤35/64 |
| **S3 (2-3 周)** | 7️⃣ Footprint 订单流确认模块（Delta/POC/VA/Imbalance）<br>8️⃣ CVD 分歧+足迹共振入场信号<br>9️⃣ 降级方案：无足迹数据时的 CVD 近似 | Premium 账户实盘胜率对比基线 +15%、信号延迟 ≤1 根 K、Free 账户优雅降级不报错 |

---

## 六、一句话决策清单

| 决策 | 结论 |
|------|------|
| **要不要上 Footprint？** | **必须上** — 核心差异化护城河，Premium 用户直接受益 |
| **要不要重写 HTF 非重绘？** | **必须重写** — v6 动态请求彻底解决旧痛点，成本低收益极高 |
| **要不要做 Ranked FVG/OB？** | **强烈建议** — 社区已有成熟评分模型，直接参考移植即可 |
| **要不要接 HMM/RL？** | **别在 Pine 里练** — 离线训练只部署阈值/权重 |
| **要不要全品种一套代码？** | **必须做** — `syminfo.*` 体系成熟，边际成本极低 |
| **要不要实盘自动下单？** | **暂缓** — 用 Webhook 出信号，外部引擎管风控/执行 |
| **要不要支持 Free 用户？** | **提供降级** — 无 Footprint 时用 CVD 近似、明确标注功能差异 |

---

## 七、来源汇总（可溯源）

1. **TradingView 官方 Release Notes 2026** — Multiline strings、v6 持续更新
2. **TradingView 官方博客 2026-03-02** — "Volume footprints are now available in Pine scripts"
3. **TradingView 官方文档** — `request.footprint()`、Repainting 定义、Limitations、Chart Information、Other Timeframes and Data
4. **TradersPost 2025-2026 系列** — Pine Script v6 发布指南、Dynamic Requests、Footprint Guide
5. **PineCoders 官方脚本** — `W1YpYcOI` Higher-timeframe requests（非重绘范例）
6. **社区高赞脚本** — Zeiierman Ranked FVG `Z4h7vDqN`、ProjectSyndicate FVG Finder `GGo1s64a`、QuantAlgo Turbo Regime `2pH4ZOw5`、KK Multi-Metric Regime `0GHiGzOp`、AlphaExtract Regime Matrix `xQ2fBtZ3`、HMM Enhanced `iF0ZwCVf`、CVD Delta Divergence `V5NHdMI3`
7. **Supa.is 实战教程** — 4 种 Footprint 订单流策略（Delta 分歧、POC 回踩、Imbalance 簇、VA 分析）
8. **Medium 社区教程** — Betashorts "Designing Pine Scripts for Multi-Asset Compatibility"
9. **TradingCode 参考** — `syminfo.type`、`syminfo.mintick`、`syminfo.pointvalue`、`syminfo.minmove` 用法

---

## 更新记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-10 | 1.0 | 初始版本：基于官方文档与社区验证的完整证据矩阵 |