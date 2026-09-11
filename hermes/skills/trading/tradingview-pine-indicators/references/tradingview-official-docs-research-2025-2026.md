# TradingView 官方文档与社区脚本研究 2025-2026

## 研究会话日期：2025-07-10 (初版) / 2026-07-11 (全面更新)

> **P0 CORRECTION — 2026-07-21 official recheck:** This file contains older claims that `request.footprint()` provides “交易所原始 Tick 级买卖量”, “真实 CVD 增量”, or “逐笔匹配、无误差”. Those claims are **superseded and must not be reused**. Current TradingView documentation says footprint data categorizes lower-timeframe volume as “buy” or “sell” from intrabar price action; it is not documented as exchange-native bid/ask aggressor tape. Label it estimated/categorized flow and see `orderflow-community-evidence-2026-07-21.md`. Also, the stable confirmed-HTF pattern is an offset expression such as `close[1]` with `lookahead_on`; do not reuse this file's blanket `lookahead_off + close[1]` recommendation. Treat non-repainting and data accuracy as separate questions.

---

## 1. TradingView 官方文档核心发现

### 1.1 `request.footprint()` / Volume Footprint (Pine Script v6 新特性)

**权威来源**：
- TradingView 官方博客：https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/ (2025-03-02 发布)
- 官方文档 - Release Notes：https://www.tradingview.com/pine-script-docs/release-notes/
- 官方文档 - Concepts / Other timeframes and data：https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/

**核心主张**：
- `request.footprint(ticksPerRow, valueAreaPct)` 返回当前 K 线的成交量足迹对象
- 需要 TradingView Premium 或 Ultimate 计划
- 数据结构两层：
  - **Footprint Object**：整根 K 线级指标 → `buy_volume()`, `sell_volume()`, `delta()`, `total_volume()`, `poc()`, `vah()`, `val()`
  - **Volume_row Object**：具体价格行级指标 → `up_price()`, `down_price()`, `buy_volume()`, `sell_volume()`, `delta()`, `imbalance()`

**关键代码模式**：
```pine
//@version=6
indicator("Footprint Demo", overlay=true)
footprint reqFootprint = request.footprint(100, 70)  // 100 ticks/行, 70% Value Area
if not na(reqFootprint)
    float totalBuy = reqFootprint.buy_volume()
    float totalSell = reqFootprint.sell_volume()
    float delta = reqFootprint.delta()
    volume_row pocRow = reqFootprint.poc()
    float pocHigh = pocRow.up_price()
    float pocLow = pocRow.down_price()
```

**适用性评估**：
- ✅ **SVP 融合**：直接获取 POC/VAH/VAL，无需本地近似计算，精度提升显著
- ✅ **CVD 增强**：逐行买卖量差值 (delta) 可替代/校准 `request.security_lower_tf()` 估算的 CVD
- ✅ **FVG/OB 质量过滤**：足迹内的 `imbalance()` 与 `delta()` 可量化 FVG/OB 形成时的真实买卖力度
- ⚠️ **配额限制**：仅 Premium+ 可用；实盘需回退方案（降级到 security_lower_tf 估算）
- ⚠️ **历史深度**：仅当前实时 K 线可用；回测时足迹数据可能缺失或不完整

### 1.2 Pine Script v6 性能分析与优化官方指南

**权威来源**：https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/

**核心主张**：
- **Pine Profiler**：v6 新增内置性能分析器，编辑器右上角 "More" → "Profiler mode" 开启
- 显示每行/代码块的近似运行时间百分比与条形图
- 自动识别热点：循环、大数组操作、重复 `request.*` 调用、复杂 UDT 操作

**官方优化模式**：
| 优化手段 | 适用场景 | 预期收益 |
|----------|----------|----------|
| 将重复计算提取为函数/变量 | 多处引用同一表达式 | 编译期去重 + 运行期复用 |
| `var` 关键字缓存跨 K 线状态 | 只需计算一次的昂贵操作 | 避免每根 K 线重复计算 |
| `request.security` 元组打包 | 同一 symbol/timeframe 多个指标 | 1 次调用返回 7 值，节省配额 |
| 避免在循环内 `request.*` | 多品种/多周期批量查询 | 编译期静态计数不超 40，运行期不超时 |
| `max_bars_back` / `max_lines_count` / `max_boxes_count` 显式声明 | 大型仪表盘指标 | 防止 "exceeded max lines/boxes" 运行时错误 |

**硬性限制（官方文档）：https://www.tradingview.com/pine-script-docs/writing/limitations/**
- 编译时间 ≤ 2 分钟（连续 3 次超时 → 1 小时封禁）
- 执行时间：Basic 20s / 其他 40s（全数据集）
- 单循环单 K 线 ≤ 500 ms
- **Plot 计数 ≤ 64**（含 `plot*`, `plotarrow`, `plotbar`, `plotcandle`, `plotchar`, `plotshape`, `alertcondition`, `bgcolor`, `barcolor`, `fill`）
- **Series-color plot 计为 2 个槽位**（关键坑点，已在技能库记录）
- 绘图对象：`max_lines_count=500`, `max_boxes_count=50`, `max_labels_count=100` 可通过 indicator() 参数调大

### 1.3 非重绘 官方定义与最佳实践

**权威来源**：https://www.tradingview.com/pine-script-docs/concepts/repainting/

**核心主张**：
- **Repainting 定义**：脚本在历史 K 线上显示的信号/数值，与实时跑完那根 K 线当时看到的不一致
- 三大来源：
  1. `request.security(..., lookahead=barmerge.lookahead_on)` —— 显式引入未来数据
  2. 实时 K 线内部逐 tick 计算 (`calc_on_every_tick=true`) 与历史 K 线仅收盘计算一次的差异
  3. 基于 `request.security_lower_tf()` 的低周期数据，在历史回测时取「已完成」低周期 K 线，实时时取「正在形成」低周期 K 线

**官方规避清单**：
- 所有 `request.security` 显式 `lookahead=barmerge.lookahead_off`（默认即 off，但建议显式写上）
- 实时/历史一致性：用 `barstate.isrealtime` 分支仅做视觉渲染（标签/线延伸），**绝不**做信号判定
- FVG/OB 检测：仅在 `barstate.isconfirmed` 为 true 的 K 线上确认形态；实时 K 线只能显示「潜在」状态
- 显式声明：`force_overlay=true` + `calc_on_every_tick=false`（默认），除非有明确逐 tick 需求并接受非重绘风险

---

## 2. 社区开源脚本模式调研（SVP + VWAP + EMA + ICT FVG/OB + CVD）

### 2.1 代表性高星脚本及其架构模式

| 脚本 | 链接 | 核心模式 | 关键技术债/亮点 |
|------|------|----------|-----------------|
| **Prism Orderflow Detector [JOAT]** | https://www.tradingview.com/script/EOgSNjkf-Prism-Orderflow-Detector-JOAT/ | 8 模块融合：Liquidity Pool + OB + FVG + Breaker Block + Market Structure + Liquidity Heatmap + Volume Delta + Orderflow Strength | v6 原生；`max_bars_back=500`；`max_lines_count=500`；显式 `request.security_lower_tf` 做 Volume Delta；FVG/OB 用 3-K 形态 + ATR 强度门槛 |
| **TradeOS** | https://www.tradingview.com/script/rkgX2Tvx-TradeOS/ | 10 因子评分 0-10：Structure + OB + FVG + Liquidity Sweep + RSI Div + Trend/Vol Bands + Continuation + Displacement + CVD + VWAP | 评分制而非布尔触发；VWAP 作为做多/做空分界；CVD 仅作确认不作方向源；有 Performance Tracker 模块 |
| **Market Structure Dashboard [Flux Charts]** | https://www.tradingview.com/script/vXui7vrm-Market-Structure-Dashboard-Flux-Charts/ | EMA 趋势 + Swing BOS/CHoCH + OB + FVG + Liquidity + CVD | 模块化开关；强调「不重绘」宣称 |
| **SMC Elemental [Cythos]** | https://es.tradingview.com/script/BcFSaAPY/ | FVG + Liquidity Sweep + OB 三核心；标注成交量 delta | 简洁、教学向 |
| **Pinnacle Structure Cipher [JOAT]** | https://cn.tradingview.com/script/DlR9mrqG-Pinnacle-Structure-Cipher-JOAT/ | OB + FVG + CVD Divergence | 明确写出 CVD 背离逻辑：价格新高 + CVD 低位 = 顶背离 |

### 2.2 社区共识的「成熟仪表盘」核心组件清单（2025-2026）

| 维度 | 社区标配做法 | 反模式/避坑 |
|------|--------------|-------------|
| **SVP/VP** | 官方 `request.footprint()` 优先；降级用 `request.security_lower_tf` 重建近似 VP | 别在 overlay 里 `plot` 大量 VP 槽位 → 压扁价格轴 |
| **VWAP** | Session/Anchored VWAP 必带；多锚点（日/周/月/波段） | 别用 `ta.vwap()` 做 HTF 偏见（日内重置导致噪音），改 `ta.sma(hlc3,50)` |
| **EMA** | 21/55/200 三线制；EMA 距离/斜率/穿越打分 | 别在主图叠太多 EMA → 视觉噪音；用表格/Data Window 暴露数值 |
| **FVG** | 3-K 定义：`low[1] > high[3]` (多) / `high[1] < low[3]` (空)；最小尺寸 % 过滤；缓解/填补追踪 | 实时 K 线「潜在 FVG」必须灰显/虚线，仅 `barstate.isconfirmed` 实体化 |
| **Order Block** | 最后一根反向 K 线 + 突破确认 + ATR/成交量强度门槛；延伸右侧；失效自动清理 | 别把所有反向 K 线都画成 OB → 图表爆炸；必须要「冲动波确认」 |
| **CVD** | `request.security_lower_tf` 逐 tick 买卖量累积；锚点 D/W/M 重置；吸收/派发/背离三态 | 别把 CVD 当方向源头；只在关键位（POC/VAH/VAL/VWAP/OB/FVG）做确认/背离 |
| **非重绘** | 所有信号判定在 `barstate.isconfirmed` 分支；实时分支仅渲染「预览」 | 任何 `calc_on_every_tick=true` 的策略/指标默认视为重绘风险 |
| **性能** | `max_bars_back`/`max_lines_count`/`max_boxes_count` 显式设大；Plot 合并编码（Data Window 元组）；Profiler 定期跑 | 不设上限 → 运行时崩；64 plot 槽位耗尽 → 编译报错 |

### 2.3 FVG/OB 质量过滤的社区量化指标

| 质量维度 | 量化公式/阈值 | 来源脚本 |
|----------|---------------|----------|
| **FVG 尺寸** | `((low[1]-high[3])/close)*100 >= minSizePct` (默认 0.1%-0.3%) | Prism, TradeOS |
| **FVG 成交量支撑** | FVG 形成那根 K 线的 `volume > avg(volume,20)*1.5` | TradeOS |
| **OB 强度** | `(high[1]-low[1]) > atr(14)*mult` (mult=2-3) + 突破 K 线实体 > 前一根实体 | Prism, TradeOS |
| **OB 缓解追踪** | 价格重回 OB 区间 50% 视为部分缓解，100% 视为完全失效 | TradeOS, Flux |
| **CVD 吸收/派发** | 价格创新高/新低 + CVD 未创新高/新低 + 摆动幅度 > 1.5*ATR(14) | NikaQuant, Pinnacle |
| **SMT 背离** | 正相关对（BTC/ETH, ES/NQ, EUR/GBP）价格新高 + 参考标的未创新高；负相关对（BTC/DXY, XAU/DXY）价格新高 + 参考标的同创新高 | ICT 标准对照表 |

---

## 3. 可落地的 2025-2026 优化清单（按优先级）

### P0 - 必须做（编译不过/重绘/配额爆炸）

1. **迁移到 `request.footprint()` 获取 POC/VAH/VAL/Delta/Imbalance**（需 Premium+，提供降级分支）
   - 替代本地 VP 近似计算，精度↑、代码量↓
   - 降级：`request.security_lower_tf` + 自建 VP 桶（兼容免费/Pro）

2. **全脚本 `request.security` 显式 `lookahead=barmerge.lookahead_off` + `gaps=barmerge.gaps_on`**
   - 消除隐性重绘风险

3. **FVG/OB 判定强制 `if barstate.isconfirmed` 分支**
   - 实时 K 线仅渲染「潜在」虚线/半透明盒子

4. **Plot 槽位压缩：Data Window 诊断值统一元组编码**
   - 目标：raw plot 调用 < 40，TV 计数 < 60（留冗余）
   - 编码例：`plot(magnetPrice*1e6 + magnetDistAtr*1e3 + ictSweptCount, "Mag+ICT")`

5. **声明 `indicator(..., max_bars_back=500, max_lines_count=500, max_boxes_count=50, max_labels_count=100)`**
   - 防大周期/长历史跑崩

### P1 - 强烈建议（显著提升信号质量/可读性）

6. **CVD 关键位门控**：仅在 `near(POC/VAH/VAL/VWAP/OB/FVG, atr*0.5)` 时让 CVD 吸收/派发/背离参与评分
   - 变量：`cvdKeyLevelGate = nearAnyKeyLevel and cvdQualityOk`

7. **FVG/OB 质量三重门槛**：尺寸% + 成交量倍数 + ATR 强度倍数；三者全过才入池
   - 可暴露为输入组 `FVG_QUALITY_GROUP` / `OB_QUALITY_GROUP`

8. **SMT 标准相关性对照表 + 正/负相关分支逻辑**（见技能库 `references/ict-smt-standard-pairs.md`）
   - 别再硬编码 `BINANCE:BTCUSDT`；用 `f_is_btc_pair()` + 交易所前缀自动检测

9. **Action Panel v9.6 审计 HUD 单格模式**（见 `references/action-panel-v96-audit-hud.md`）
   - 6 行：层级→结论→结构→确认→关键→评估→计划
   - 中文冒号 `：`；模块前缀去重；颜色按等级 A/B/C 透明度分级

10. **Pine Profiler 例行化**：每次大改动后跑一次，截图留存热点 Top 5

### P2 - 可选增强（锦上添花）

11. **Multi-timeframe 联动执行卡**（见 `references/action-panel-mtf-linked-plan.md`）
    - 执行层（5m/15m）：给具体入场/止损/目标
    - 结构层（1h/4h）：给双向路线图 + 移交执行层条件
    - 背景层（1D+）：仅给偏好方向 + 等待结构层确认

12. **Magnet Score 三因子 0-100**（距离 40% + 新鲜度 30% + 优先级 30%）
    - 最近未缓解流动性池自动标注「磁吸目标」

13. **市场自适应参数矩阵**（Crypto/Forex/Metal/Stock/Index 分表）
    - VP 桶宽、ADX 阈值、KillZone 时间、CVD 通道数、VWAP 锚点

14. **社区对标自动化**：`firecrawl` 定期抓取 TradingView 脚本库同类 Top 20，提取参数/逻辑差异生成对比表

---

## 4. 验证清单（交付前自检）

- [ ] `request.footprint` 分支 + 降级分支均通过 TradingView 编译器
- [ ] 所有 `request.security` 显式 `lookahead_off`
- [ ] FVG/OB/CVD 信号判定均在 `barstate.isconfirmed` 分支
- [ ] Plot 计数（含 series-color×2）≤ 60
- [ ] `max_bars_back/lines/boxes/labels` 显式声明且够大
- [ ] Action Panel 单格 6 行，中文冒号，无模块前缀重复，等级色分级
- [ ] SMT 使用 `f_is_btc_pair()`/`f_is_xau_pair()` + 交易所前缀自动检测
- [ ] CVD 关键位门控生效（Data Window 导出 `CVD KeyGate (OK*100+Samples)`）
- [ ] Pine Profiler 热点 Top 5 无明显低垂果实（循环/重复 security/大数组拷贝）
- [ ] 输入面板无死控件（`grep -c` 每个 input 变量引用数 > 0）

---

## 5. 参考链接汇总（可直接点击验证）

| 类别 | URL | 说明 |
|------|-----|------|
| 官方 Volume Footprint 发布博客 | https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/ | 2025-03-02，核心 API 说明 |
| 官方 Release Notes (含 footprint) | https://www.tradingview.com/pine-script-docs/release-notes/ | 搜索 "footprint" 定位 |
| 官方 Concepts: Other timeframes and data | https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/ | request.* 全族谱 |
| 官方 Profiling and Optimization | https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/ | Profiler 用法 + 优化模式 |
| 官方 Limitations | https://www.tradingview.com/pine-script-docs/writing/limitations/ | 64 plot / 20-40s / 500ms 硬限制 |
| 官方 Repainting 定义与规避 | https://www.tradingview.com/pine-script-docs/concepts/repainting/ | 非重绘金标准 |
| Prism Orderflow Detector [JOAT] | https://www.tradingview.com/script/EOgSNjkf-Prism-Orderflow-Detector-JOAT/ | v6 开源，8 模块融合参考 |
| TradeOS | https://www.tradingview.com/script/rkgX2Tvx-TradeOS/ | 10 因子评分制参考 |
| Market Structure Dashboard [Flux] | https://www.tradingview.com/script/vXui7vrm-Market-Structure-Dashboard-Flux-Charts/ | 模块化开关参考 |
| SMC Elemental [Cythos] | https://es.tradingview.com/script/BcFSaAPY/ | 三核心极简教学版 |
| Pinnacle Structure Cipher [JOAT] | https://cn.tradingview.com/script/DlR9mrqG-Pinnacle-Structure-Cipher-JOAT/ | CVD 背离显式逻辑参考 |

---\n\n## 6. 后续跟进建议\n\n1. **实盘验证 `request.footprint()` 降级逻辑**：在免费/Pro 账号上跑通 security_lower_tf 近似 VP 分支\n2. **社区脚本定期抓取**：建立月度 `firecrawl` 任务，监控同类 Top 50 脚本的参数/逻辑演进\n3. **Pine v6 迁移评估**：当前主指标为 v5，评估整体迁移收益（footprint/multiline/enums/UDT 增强）vs 成本\n4. **多市场回测框架接入**：将优化后的评分/面板输出接入 `backtesting-suite` 做 Walk-Forward 验证\n\n---\n\n## 7. 2026-07-11 全面联网调研增补（本次会话核心产出）\n\n### 7.1 官方 Limitations 页面完整逐字抓取结果\n\n**权威来源**：https://www.tradingview.com/pine-script-docs/writing/limitations/\n\n**完整硬性限制表（v6 当前版本）**：\n\n| 限制类别 | 具体数值 | 备注 |\n|----------|----------|------|\n| **编译时间** | ≤ 2 分钟 | 连续 3 次超时 → 1 小时编译封禁 |\n| **脚本执行时间** | Basic 20s / 其他 40s | 全数据集累计 |\n| **单循环单 Bar** | ≤ 500 ms | 嵌套循环以外层为准 |\n| **Plot 计数** | **≤ 64** | `plot*()/plotarrow/plotbar/plotcandle/plotchar/plotshape/alertcondition/bgcolor/barcolor/fill(series色)` 计数；`hline()/line.new()/label.new()/box.new()/table.new()` **不计数** |\n| **Series-color plot** | **每个计 2 槽位** | 动态/输入色 → 双倍消耗 |\n| **单函数调用最多** | 7 个 plot counts | `plotcandle()` 全参数系列色可达 7 |\n| **request.*() 唯一调用数** | 非 Ultimate 40 / Ultimate 64 | 相同参数重复调用不重复计数；库内调用也计入总数 |\n| **request.footprint()** | **单脚本仅 1 次唯一调用** | 仅 Premium/Ultimate 可用；返回 `na` 表示无数据 |\n| **Intrabar/低周期 Bar 数** | Basic/Essential/Plus/Premium 100K / Expert 125K / Ultimate 200K | `calc_bars_count` 可显式限制回溯 |\n| **Tuple 元素总数** | 所有 request.* 合计 ≤ 127 | 超限改用 UDT 打包 |\n| **编译后 IL Token** | 单脚本 ≤ 100K / 含库 ≤ 1M | 无法本地查看，仅编译报错时发现 |\n| **每作用域变量数** | ≤ 1,000 | 全局 + 每个局部块分别计算 |\n| **编译请求体积** | ≤ 5 MB | 含源码+库，未优化前计算 |\n| **集合元素上限** | 数组/矩阵 100K / Map 50K 键值对 | |\n| **历史引用缓冲** | 普通 series 5K / OHLC/time 10K | `max_bars_back()` 可扩大 |\n| **绘图对象前向** | ≤ 500 Bar | `xloc.bar_index` |\n| **图表历史 Bar 数** | Ultimate 40K / Expert 25K / Premium 20K / Essential+Plus 10K / 其他 5K | 账户等级决定 |\n| **回测订单数** | 普通 9,000 / Deep Backtesting 1,000,000 | |\n\n**关键新增（v6）**：\n- `calc_bars_count` 参数现已在 `request.security()`、`request.security_lower_tf()`、`indicator()`、`strategy()` 中可用，显式限制回溯/执行 Bar 数\n- Dynamic requests（动态请求）v6 默认开启，允许 `series string` timeframe 参数\n- `request.footprint()` 纳入 request.* 配额但有**独立单调用限制**\n\n### 7.2 `request.footprint()` 官方完整规范（2026-01 发布，2026-03 博客）\n\n**权威来源**：\n- https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/ (2026-03-02)\n- https://blog.traderspost.io/article/pine-script-footprint-requests (2026-01, 2026-07-10 更新)\n- https://blog.traderspost.io/article/pine-script-footprint-volume-row-functions (2026-03-09, 2026-07-10 更新)\n\n**函数签名**：\n```pine\nrequest.footprint(ticks_per_row, va_percent) → footprint | na\n```\n- `ticks_per_row` (const int ≥ 1)：每价格行的 tick 数（粒度）\n- `va_percent` (const int 1-100)：Value Area 占总成交量百分比（常用 70%）\n- **返回**：当前 Bar 的 `footprint` 对象 ID，**无数据时返回 `na`**\n- **账户限制**：仅 **Premium / Ultimate** 可用；低阶计划脚本报错\n- **唯一调用限制**：全脚本**仅允许 1 个唯一 `request.footprint()` 调用**\n\n**Footprint 对象方法（Bar 级聚合）**：\n| 方法 | 返回 | 说明 |\n|------|------|------|\n| `buy_volume()` | `float` | 全 Bar 主动买入量 |\n| `sell_volume()` | `float` | 全 Bar 主动卖出量 |\n| `delta()` | `float` | `buy - sell`（真实 CVD 增量） |\n| `total_volume()` | `float` | 全 Bar 总成交量 |\n| `poc()` | `volume_row` | Point of Control 行 |\n| `vah()` | `volume_row` | Value Area High 行 |\n| `val()` | `volume_row` | Value Area Low 行 |\n| `rows()` | `array<volume_row>` | 所有价格行数组 |\n| `get_row_by_price(price)` | `volume_row` | 指定价格对应的行 |\n\n**Volume_row 对象方法（逐价位）**：\n| 方法 | 返回 | 说明 |\n|------|------|------|\n| `up_price()` / `down_price()` | `float` | 该行上/下边界价格 |\n| `buy_volume()` / `sell_volume()` | `float` | 该行买/卖量 |\n| `total_volume()` | `float` | 该行总量 |\n| `delta()` | `float` | 该行净买卖差 |\n| `has_buy_imbalance()` / `has_sell_imbalance()` | `bool` | 买/卖失衡标识 |\n\n**标准使用模式（官方示例）**：\n```pine\n//@version=6\nindicator(\"Footprint CVD\", overlay=false)\nint ticksInput = input.int(100, \"Ticks per row\", minval=1)\nint vaInput = input.int(70, \"Value Area %\", minval=1, maxval=100)\n\nfootprint fp = request.footprint(ticksInput, vaInput)\n\nvar float cvd = 0.0\nif not na(fp) and barstate.isconfirmed\n    cvd := cvd + fp.delta()\n\nplot(cvd, \"CVD\", color=color.yellow)\n```\n\n**降级方案（免费/Pro 账号）**：\n- 使用 `request.security_lower_tf(symbol, timeframe, expression)` 获取低周期数组，本地重建近似 VP\n- 精度损失：无法获得真实主动买卖分离，只能用 `close > open ? volume : -volume` 估算 Delta\n- 兼容性：`request.footprint` 分支用 `if not na(fp)` 守卫，降级分支用 `request.security_lower_tf`\n\n### 7.3 非重绘 HTF 官方最佳实践（2025-2026 社区共识）\n\n**权威来源**：\n- https://www.tradingview.com/pine-script-docs/concepts/repainting/\n- https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/ (PineCoders 官方示范, 2024-03)\n- https://www.tradingview.com/pine-script-docs/faq/other-data-and-timeframes/\n\n**核心原则**：\n1. **永远 `lookahead=barmerge.lookahead_off`** —— 默认虽为 off 但显式写上消除歧义\n2. **HTF 表达式内部用 `[1]` 偏移** —— 仅读取「上一根已收盘 HTF Bar」\n3. **实时 Bar 锁定值**：配合 `barstate.isconfirmed` 或 `barstate.islastconfirmedhistory` 仅在 HTF 收盘后更新\n4. **`calc_bars_count` 限制回溯** —— 如仅需最近 500 根 HTF Bar：`request.security(..., calc_bars_count=500)`\n5. **避免在 `request.security` 内部做复杂循环** —— 易触发 500ms/Bar 循环限制\n\n**标准非重绘模板**：\n```pine\n//@version=6\nhtfClose = request.security(syminfo.tickerid, \"4H\", close[1], lookahead=barmerge.lookahead_off, calc_bars_count=500)\n// close[1] = 上一根已确认 HTF Bar；lookahead_off 禁止前瞻\n```\n\n**错误模式（会重绘）**：\n```pine\n// ❌ 实时 HTF Bar 未收盘时会波动\nhtfClose_bad = request.security(syminfo.tickerid, \"4H\", close, lookahead=barmerge.lookahead_on)\n// ❌ 无 [1] 偏移，读取正在形成的 HTF Bar\nhtfClose_bad2 = request.security(syminfo.tickerid, \"4H\", close, lookahead=barmerge.lookahead_off)\n```\n\n### 7.4 Plot Count 64 限制详细规则与计数方法\n\n**权威来源**：https://www.tradingview.com/pine-script-docs/visuals/overview/、https://www.tradingview.com/pine-script-docs/visuals/plots/\n\n**计数函数**（每个调用消耗 1 个 plot count，除非系列色）：\n| 函数 | 固定色 | 系列/动态色 |\n|------|--------|-------------|\n| `plot()` / `plotarrow()` / `plotchar()` / `plotshape()` | 1 | **2** |\n| `plotbar()` / `plotcandle()` | 4 (OHLC) | 5-7 (含 color/wickcolor/bordercolor 系列) |\n| `alertcondition()` | 1 | — |\n| `bgcolor()` / `barcolor()` | 1 | **2** |\n| `fill()` | 1 (常量色) | **2** (系列色) |\n| `hline()` / `line.new()` / `label.new()` / `box.new()` / `table.new()` | **0** | **0** |\n\n**实测计数公式（社区验证）**：\n- 乐观估计：`const_plots + series_plots + fills + bgcolors`（系列色按 1 算）\n- **最坏估计（TV 实际执行）**：`const_plots + series_plots*2 + fills*2 + bgcolors*2`\n- **SVP_v6 实测**：raw 71 调用 → 乐观 ~53 → 最坏 **71+（超限）**，需压缩到最坏 ≤ 63\n\n**压缩策略（已验证有效）**：\n1. 视觉/轴线 plot 全部改 `const color` (十六进制)\n2. `bgcolor()` 合并为单一调用，用 `if/else` 链内部决定颜色\n3. `fill()` 固定色或移除\n4. Data Window 诊断值用**元组编码**压缩：`val1*1e6 + val2*1e3 + val3` 并在标题文档化解码公式\n5. 目标：raw plot 调用 < 40，最坏 TV 计数 < 60\n\n### 7.5 Monaco 多编辑器自动化现状（2025-2026）\n\n**权威来源**：\n- https://www.tradingview.com/blog/en/new-vsc-style-pine-script-editor-34159/\n- https://www.reddit.com/r/TradingView/comments/1kb0qps/can_you_add_the_ability_to_open_more_than_one/\n- https://www.youtube.com/watch?v=9b28aBiH-wI\n\n**现状总结**：\n| 能力 | 支持情况 | 备注 |\n|------|----------|------|\n| **多编辑器窗口** | ✅ 原生支持 | 编辑器空白处右键 → \"New Window\"，可拖出多标签/多窗口 |\n| **Monaco 多实例** | ✅ 每窗口独立实例 | 语法高亮、IntelliSense、格式化各自独立 |\n| **官方 REST API / CLI** | ❌ 无 | 无法通过脚本自动推送/拉取代码 |\n| **本地同步工具** | ❌ 无官方 | 社区方案：Git + 手动复制、Pineify、Pine Script Language Server |\n| **自动化测试/部署** | ❌ 无 Headless Runner | 无 CI/CD 集成 |\n\n**实用工作流建议**：\n1. **主策略/库分文件**：`main.pine` + `lib_svp.pine` + `lib_cvd.pine` → 用 `import` 引用（v6 支持）\n2. **多窗口并行开发**：主图窗口跑主策略、副窗口调库函数、第三窗口写测试脚本\n3. **版本控制**：本地 Git 管理 `.pine` 文件，**手动同步到编辑器**（目前无更好方案）\n4. **性能分析**：编辑器内置 **Pine Profiler**（v6 新增），可按函数/行查看执行耗时，定位 500ms 循环瓶颈\n\n### 7.6 安全 CVD/OI 计算：基于 `request.footprint()` 的原生方案\n\n**核心优势**：无需 `request.security_lower_tf()` 降采样、无需估算买卖方向，**交易所原始 Tick 级买卖量直接可得**。\n\n**标准 CVD 累积模板（非重绘、可实盘）**：\n```pine\n//@version=6\nindicator(\"Native CVD (Footprint)\", overlay=false)\nint ticksPerRow = input.int(100, \"Ticks/Row\", minval=1)\nint vaPct       = input.int(70,  \"Value Area %\", minval=1, maxval=100)\n\nfootprint fp = request.footprint(ticksPerRow, vaPct)\n\nvar float cvd = 0.0\nif not na(fp) and barstate.isconfirmed\n    cvd := cvd + fp.delta()   // 真实买卖量差值\n\nplot(cvd, \"CVD\", color=color.yellow)\n```\n\n**Open Interest (OI) 安全获取**：\n- **Pine Script v6 目前无原生 `request.open_interest()`**\n- **社区方案**：`request.security(\"BINANCE:BTCUSDT.P\", \"1D\", open_interest, lookahead=barmerge.lookahead_off)` —— 仅限提供 OI 的数据源（Binance、Bybit 等）\n- **Footprint 替代**：`fp.buy_volume() + fp.sell_volume()` 近似当 Bar 成交量，**不可替代 OI**，但可作 Delta/Volume Profile 分析\n\n**避坑指南**：\n| 误区 | 正确做法 |\n|------|----------|\n| 用 `close > open ? volume : -volume` 估算 Delta | **直接用 `fp.delta()`** —— 交易所逐笔匹配，无误差 |\n| `request.security_lower_tf` 循环聚合 CVD | **用 `request.footprint()` 逐 Bar 累加** —— 无 Intrabar 循环、无 500ms 限制 |\n| 实时 Bar 累加 CVD 导致重绘 | **仅 `barstate.isconfirmed` 时累加**，或用 `varip` 仅显示实时未确认值 |\n\n### 7.7 对本系统（SVP + ICT + VWAP + CVD / AggVol）的直接落地建议\n\n| 模块 | 现状风险 | 立即可落地的 v6 最佳实践 | 官方/社区来源 |\n|------|----------|---------------------------|---------------|\n| **HTF 结构 (SVP/ICT)** | `request.security` 可能重绘 | 统一改为 `lookahead_off + close[1]` 模式；加 `calc_bars_count=500` 限制回溯 | [PineCoders HTF](https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/) |\n| **CVD 计算** | 估算 Delta（close>open?）、低周期聚合慢 | **全面迁移 `request.footprint()`**：`fp.delta()` 逐 Bar 累加，仅 `barstate.isconfirmed` 提交 | [TV Blog 2026](https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/) |\n| **AggVol / Footprint** | 依赖 `security_lower_tf` 数组循环 | 用 `fp.rows()` 直接拿全行 `volume_row`，配合 `has_buy_imbalance()` 做失衡检测 | [TradersPost Ref](https://blog.traderspost.io/article/pine-script-footprint-volume-row-functions) |\n| **Plot 计数超限 (64)** | SVP+VWAP+CVD+信号=易超 64 | 1) 合并 `plot()` 系列；2) 非关键视觉改 `line.new()/label.new()/box.new()`（不计 plot count）；3) `fill()` 仅用 `const color` | [Limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/) |\n| **执行时间超限 (20/40s)** | 多 `request.security` + 循环 | 1) 开启 `calc_bars_count`；2) 将重计算移入 `request.security` 内部表达式（HTF 上下文跑）；3) 用 Profiler 定位热点 | [Profiling](https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/) |\n| **多编辑器协作** | 单窗口切换低效 | 利用原生“New Window”多 Monaco 实例并行开发；本地 Git 管理源码 | [TV Blog Editor](https://www.tradingview.com/blog/en/new-vsc-style-pine-script-editor-34159/) |\n| **OI 数据** | 无原生支持 | 继续用 `request.security(..., \"open_interest\", lookahead_off)`，仅限支持交易所；Footprint 无法替代 | 社区共识 |\n\n### 7.8 关键官方 URL 速查表（本次调研新增）\n\n| 主题 | 官方链接 |\n|------|----------|\n| **Limitations (v6 完整限制表)** | <https://www.tradingview.com/pine-script-docs/writing/limitations/> |\n| **request.* 命名空间 & `request.footprint`** | <https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/> |\n| **Repainting 官方定义与对策** | <https://www.tradingview.com/pine-script-docs/concepts/repainting/> |\n| **PineCoders 非重绘 HTF 权威示范** | <https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/> |\n| **Footprint 发布博客 (2026.03)** | <https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/> |\n| **Footprint API 完整参考 (TradersPost)** | <https://blog.traderspost.io/article/pine-script-footprint-volume-row-functions> |\n| **Release Notes (v6 所有变更)** | <https://www.tradingview.com/pine-script-docs/release-notes/> |\n| **Pine Profiler 性能分析** | <https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/> |\n| **Monaco 编辑器发布公告** | <https://www.tradingview.com/blog/en/new-vsc-style-pine-script-editor-34159/> |