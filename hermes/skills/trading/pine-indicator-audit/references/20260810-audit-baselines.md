# 2026-08-10 双指标审计快照（SVP_ICT_v2 + AggVol_v2 fix版）

> ⚠ 20260810 定稿复核修正：主指标行尾基线记录有误——交付文件实测为 CRLF（08-09 版 LF 被 patch 工具转 CRLF），非 LF。纯 LF 修复版已交付：桌面/hermes下载文件/指标审计定稿_20260810/SVP_ICT_v2_20260810_fix_LF.pine（diff 确认仅行尾差异）。下表行尾行相应修正为 CRLF。

## Plot 配额计数铁律（官方文档确认）

**每个 `plot()` 调用都计 1 plot count，无论 `display` 参数是什么**（含 `display.data_window`）。
- series-color（color 含 `?`/变量名/`color.XXX`/cGood 等）→ **额外 1 slot = 2 slots 总计**
- 常量 `#hex` 或 `na` → **1 slot**
- **不产生 plot count 的函数**：`hline()`, `line.new()`, `label.new()`, `box.new()`, `table.new()`, `polyline.new()`, `plot()` with `display=display.none`（完全隐藏）
- **最坏式 = Σ(plot slots) + alertcondition + bgcolor + Σ(fill series-color)**

> 来源：TradingView 官方 Pine Script docs "Visuals / Plots" 页 + "Writing / Limitations" 页（2026-08-10 浏览器实测）

## 主指标基线（SVP+ICT+VWAP+CVD, 3082行）

| 维度 | 值 |
|------|-----|
| 行数 | 3082 |
| 字符数 | 219,703 |
| Token估算 | ~51K |
| plot() 总调用 | 39 |
| series-color plots | 10 (slots=11) |
| DW-only plots | 29 (**各计1 slot = 29**) |
| 总 plot slots | **40/64 (余24)** |
| bgcolor | 4 |
| fill | 2 |
| 最坏配额 | **46/64 (余18)** |
| request.security | 8 (静态) |
| request.security_lower_tf | 2 |
| alertcondition | 0 |
| alert() | 1 |
| MCP DW plots | 27 |
| input参数 | 228 |
| 死变量 | 0 |
| 行结尾 | LF（无CRLF） |

### 关键配额变化（vs 08-08基线）

| 维度 | 08-08旧值 | 08-10新值 | 变化 |
|------|----------|----------|------|
| 行数 | 3034 | 3082 | +48 |
| plot总调用 | 41 | 39 | -2 |
| DW-only | 未知 | 29 | 新增认知 |
| 最坏配额 | 51/64 | **46/64** | ✓ 改善 |
| alert() | 3 | 1 | -2 |
| 死变量 | 5 | 0 | ✓ 全清 |

## 副指标基线（AggVol, 704行）

| 维度 | 值 |
|------|-----|
| 行数 | 704 |
| 字符数 | 63,297 |
| Token估算 | ~13K |
| plot() 总调用 | 40 |
| series-color plots | 19 (slots=31) |
| DW-only plots | 21 (**各计1 slot = 21**) |
| 总 plot slots | **52/64 (余12)** |
| bgcolor | 0 |
| fill | 0 |
| 最坏配额 | **52/64 (余12)** |
| request.security | 7 (静态) |
| alertcondition | 0 |
| alert() | 1 |
| HALDRO DW plots | 21 |
| input参数 | 43 |
| table.cell | 34 |
| 死变量 | 0 |
| 行结尾 | LF（无CRLF） |

### 关键配额变化（vs 08-08基线）

| 维度 | 08-08旧值 | 08-10新值 | 变化 |
|------|----------|----------|------|
| 行数 | 656 | 704 | +48 |
| series-color slots | 51 | **52** | +1 |
| DW-only | 未知 | 21 | 新增认知 |
| 最坏配额 | 51/64 | **52/64** | +1 |
| 死变量 | 2 | 0 | ✓ 全清 |

## CVD 锚定一致性矩阵

| 场景 | 主指标 | 副指标 | 一致? |
|------|--------|--------|-------|
| 加密 <1h | D | D | ✓ |
| 加密 1h-4h | W | W | ✓ |
| 加密 4h+ | M | M | ✓ |
| 贵金属 <4h | D | D | ✓ |
| 贵金属 4h+ | W | **M** | ✗ 分叉 |
| 外汇/股票 <4h | D | D | ✓ |
| 外汇/股票 4h+ | W | **M** | ✗ 分叉 |

**发现**：副指标 CVD 锚定缺少市场维度分支——只用纯周期秒数映射（<3600→D, <14400→W, else→M），而主指标对贵金属/外汇/股票在4h+用W而非M。
**影响**：P2（注释差异，不影响加密品种实际运行）

## 市场判定一致性

| 检测项 | 主指标 | 副指标 | 同源? |
|--------|--------|--------|-------|
| 贵金属 | `autoMetal` (L277): XAU/XAG/GOLD/SILVER/GC/SI ticker检测 | `f_is_metal_ticker()` (L78-82): 同关键字 | ✓ |
| 加密门控 | `autoCrypto` (ticker+type混合) | `isCryptoPlot` = `syminfo.type=='crypto' and not f_is_metal_ticker()` | ✓ 功能等价 |
| XAUUSDT.P修复 | 已修 (autoMetal) | 已修 (20260810注释标记) | ✓ |

## 副指标 DW 字段中"估算"字样

L677: `"CVD Value (K线估算)"` — DW标题含"估算"
L678: `"CVD Method Code (1=K线估算)"` — DW标题含"估算"

用户偏好：副指标界面不显示"估算/Estimated"字样。DW标题中的"K线估算"需确认是否违规——DW是开发者调试面板，用户日常不查看；行动格/图表可见区域已无"估算"字样。

## 副指标 OI 方向票逻辑

- L350: `oiBreadthA = oiUpCountA - oiDnCountA`（4所OI升降计数差）
- L667: `oiDirCodeA = oiUpA ? 1 : oiDnA ? -1 : 0`
- L699: `Flow Pack = OI*100 + CVD*10 + SP`（编码包）
- 铁律遵守：OI升=新仓扩张，多空都算票；OI降不算方向票 ✓
