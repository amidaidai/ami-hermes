# SVP_production_optimized.pine 深度审计报告 (2026-07-10)

## 文件概况
- **路径**: `D:/Hermes agent/outputs/indicator-audit-20260710/SVP_production_optimized.pine`
- **版本**: Pine v6 / 2813 行 / 191 KB
- **指标标题**: SVP+ICT+VWAP+CVD (含 EMA/VWAP/CVD/FVG/MCP Data Window)
- **编译状态**: ✅ 通过

---

## P1 级：重绘/正确性/阻断性缺陷

### P1-01: HTF FVG/OB 使用 `lookahead=barmerge.lookahead_on` 导致实时重绘 ★★★★★
**证据**: L1954-1955
```pinescript
[hBull, hBear, hTop, hBot] = request.security(syminfo.tickerid, fvgHtfRes, f_htf_fvg(), lookahead=barmerge.lookahead_on, ignore_invalid_symbol=true)
[obHBull, obHBear, obHTop, obHBot] = request.security(syminfo.tickerid, fvgHtfRes, f_htf_ob(), lookahead=barmerge.lookahead_on, ignore_invalid_symbol=true)
```
**问题**: HTF FVG/OB 结构在当前 HTF K 线未收盘时可见，随价格波动反复出现/消失/位移。
**影响链路**: 入场信号(B/C 级依赖 HTF confirm)、OB breaker 判定、FVG HTF align 全链路失真。
**修复**: 移除 `lookahead_on`；仅在 `barstate.isconfirmed` 的 HTF 收盘根上识别结构（消费端 L1957-1958、L1985-1986 已有 `barstate.isconfirmed` 守卫，**但数据源已提前泄露**）。

### P1-02: ADR Daily 计算用 `lookahead_on` 读取「当日已完成」均幅 ★★★★☆
**证据**: L304
```pinescript
float adrDailyRaw = request.security(syminfo.tickerid, "D", ta.sma(high - low, effAdrLen)[1], lookahead=barmerge.lookahead_on, ignore_invalid_symbol=true)
```
**问题**: `[1]` 已取前一日，再加 `lookahead_on` 双重保险 → 实盘当日会提前看到「明日 ADR」数值，或在日内读到**尚未确认的当日 ADR**。触发 `ADR_EXHAUST_PCT`、`ADR_ROOM_ATR` 过滤器时出现**看穿未来**。
**修复**: 去掉 `lookahead_on`，仅用 `ignore_invalid_symbol=true` + `[1]` 保证只读前日收盘确定值。

### P1-03: HTF 趋势确认包同样用 `lookahead_on` ★★★★☆
**证据**: L751
```pinescript
[htfCloseC, htfEmaFastC, htfEmaSlowC, htfSma50C] = request.security(syminfo.tickerid, htfTf, f_htf_trend_confirmed_pack(), lookahead=barmerge.lookahead_on, ignore_invalid_symbol=true)
```
**问题**: `htfBullConfirmed` / `htfBearConfirmed` (L754-755) 直接用于 `htfAllowLong/Short` (L1927-1928)、**A 级门槛** (L2308-2309)、**风控硬阻断** (L2317)。若 HTF 当根未闭合，EMA/SMA 会随价格抖动 → **方向翻转重绘**。
**修复**: 同 P1-01，移除 `lookahead_on`，仅在 HTF `barstate.isconfirmed` 时采样。

---

## P2 级：重要/资源/体验/可维护性

### OB/FVG 质量分级缺失 (3 项)

| 编号 | 问题 | 证据行 | 说明 |
|------|------|--------|------|
| **P2-01** | **无 OB 质量分级 (A/B/C)** | L103-125, L2123-2256 | 仅有 `SHOW_HTF_OB` 布尔、是否 breaker、是否 mitigated。缺：位移确认、体积/成交量、回测胜率、HTF align 强度、距价距离 ATR 倍数等量化评分。建议在 `OBZone` 增加 `int qualityScore` 字段 (0-100)，入列时计算。 |
| **P2-02** | **无 FVG 质量分级** | L84-101, L2001-2121 | `FVG` 结构体仅有 `htfConf` 布尔。缺：位移确认 (`FVG_REQUIRE_DISP` 已有但未入分)、缺口大小、回补深度、HTF align、近因子距离、生存时长。建议同增 `int fvgQuality`。 |
| **P2-03** | **OB/FVG 联动评分缺失** | L2064-2070, L2219-2223 | 仅做 `ob.htfConf := true/false` 简单布尔。建议：OB 与同向 HTF FVG 重叠 → +20 分；OB 内含 FVG CE → +10 分；FVG 内含 OB → +15 分。输出 `mcpStructPack` 可打包更丰富的质量码。 |

### EMA 参数保护 (3 项)

| 编号 | 问题 | 证据行 | 说明 |
|------|------|--------|------|
| **P2-04** | **EMA 长度无强制排序/越界保护** | L148-151 | `EMA_LEN_1..4` 仅 `minval=1, maxval=500`，用户可设 `9, 9, 9, 9` 或 `55, 34, 21, 9` 导致云层反向/重叠异常。建议：`input.int` 加 `tooltip` 提示顺序 + 运行时 `runtime.error` 断言 (Pine v6 支持)。 |
| **P2-05** | **HTF EMA 用 `lookahead_on` 见 P1-03** | L715-716, L751 | 已归入 P1。 |
| **P2-06** | **EMA 云层绘图与参数未联动校验** | L862-867 | `SHOW_EMA_12_CLOUD` / `SHOW_EMA_34_CLOUD` 仅控制 `fill()`，但 `plot()` 仍每根 K 线创建 4 条 plot (L862-865)。若关闭云层仍消耗 plot 配额 (共 24 条 plot，接近 64 上限)。建议：`plot(..., display=showEma12Cloud ? display.all : display.none)` 或合并为 2 条 plot + 动态 color。 |

### FVG/OB 生命周期管理 (4 项)

| 编号 | 问题 | 证据行 | 说明 |
|------|------|--------|------|
| **P2-07** | **FVG `bornBar` 计算偏移 2 根 K** | L2009, L2016 | `box.new(bar_index - 2, ...)` 但 `bornBar := bar_index` → 实际出生在 `bar_index-2`，`bar_index - bornBar` 算出的存活周期少 2 根。导致 `FVG_EXPIRE_BARS` 提前 2 根触发清理。 |
| **P2-08** | **LV (Liquidity Void) 硬编码 100 根过期，无输入参数** | L2275 | `bar_index - lv.bornBar > 100` 硬编码。建议加 `input.int(LV_EXPIRE_BARS, 100, ...)` 并复用 `OB_EXPIRE_BARS` 逻辑。 |
| **P2-09** | **HTF FVG/OB 列表清理条件含 `not fvgHtfValid`** | L1968, L1996 | `if hzFilled or not fvgHtfValid` → 切换 HTF 周期或关闭 `SHOW_HTF_FVG` 时**批量删除所有 HTF 对象**，再开启时需等待下一根 HTF 收盘才重建 → 视觉闪烁。建议仅按 `hzFilled` 清理，`fvgHtfValid` 仅控制**新增**。 |
| **P2-10** | **SVP Completed Profile 渲染时机在 `barstate.islast`** | L1571-1572 | 历史回测时只在最后一根渲染已完成 profile，导致回测回放看不到历史 SVP。实盘无影响。建议：在 `isNewPeriod` 分支 (L1508) 已渲染 `false`，保留；`barstate.islast` 仅补渲染**当前活跃** profile。 |

### 重绘/看穿未来残留 (1 项)

| 编号 | 问题 | 证据行 | 说明 |
|------|------|--------|------|
| **P2-11** | **SVP Completed Profile 渲染时机** | 见 P2-10 | 同上 |

### 对象/Plot/Request/Token 余量 (3 项)

| 编号 | 资源 | 当前用量 | 上限 | 剩余 | 风险 |
|------|------|----------|------|------|------|
| **P2-12** | `max_boxes_count` | ~120 (OB 4 + FVG 3 + LV 5 + HTF FVG 4 + HTF OB 4 + nPOC 1 + VP polyline 2 + session boxes 6 + macro) | 120 (L5) | **≈0** | 任何新增 box (如 Breaker 独立框、SMT box) 即溢出 → 运行时错误。建议：`max_boxes_count=200` 或动态清理旧 box。 |
| **P2-13** | `request.security` 调用 | 12 次/根 K 线 (L304, L612, L729, L750, L751, L960, L963, L969, L974, L980, L1954, L1955 含 lower_tf) | 40 (免费/Pro) / 64 (Ultimate) | 28-52 | 1m/5m 图在免费/低权限账号极易触发「Too many requests」。建议：合并 HTF 请求 (L750/751 可合并)、OI/DXY/VIX 仅在 `barstate.isconfirmed` 请求、SMT 仅在 `SHOW_SMT` 开启时请求。 |
| **P2-14** | `plot()` 调用 | 24 条 (L801-803, L862-865, L2722-2746, L2807-2813) | 64 | 40 | 尚可，但 MCP 数据窗口 plot 占 11 条 (L2722-2746)，若后续扩展会紧张。建议：打包为 `plot(..., display=display.data_window)` 单条 JSON 字符串或移除非必要。 |

### 设置卫生/输入参数规范 (4 项)

| 编号 | 问题 | 证据行 | 说明 |
|------|------|--------|------|
| **P2-15** | **分组常量命名重复/易混** | L6-23 | 19 个 `const string` 组，**但 UI 显示仅 9 大类** (00-09)，中间缺失 10-18，导致设置面板分组跳跃。建议：按 UI 顺序重命名 `G00_MARKET`、`G01_SVP`、`G02_ICT`、`G03_VWAP`、`G04_EMA`、`G05_CVD`、`G06_DMI`、`G07_PRO`、`G08_FUNDING`、`G09_ADR`。 |
| **P2-16** | **Tooltip 超长/含换行/中文标点** | L25, L29, L88, L109 等 | 如 `tooltip="自动会根据 syminfo.type..."` (L25) 超过 200 字符，TradingView 会截断且不换行。建议：≤120 字符，用英文标点，核心信息前置。 |
| **P2-17** | **`inline` 分组不一致** | L148-151 | `EMA_LEN_1/2` 共用 `inline="emalen12"`，`EMA_LEN_3/4` 共用 `inline="emalen34"`，**但 UI 上显示为两组独立行**，视觉上未对齐。建议：统一 `inline="ema_all"` 或拆为 4 个独立行。 |
| **P2-18** | **`minval/maxval` 过宽导致非法组合** | L148-151, L109-112 | EMA 1-500、OB_LOOKBACK 5-200、OB_EXPIRE_BARS 0-1000。用户可设 `EMA_LEN_1=500, EMA_LEN_2=1` → 云层反向。建议加运行时校验或缩小范围 (如 EMA 1-200、OB_LOOKBACK 5-100)。 |

---

## 源码证据行号速查表

| 类别 | 关键行号 | 备注 |
|------|----------|------|
| **HTF lookahead_on** | L304, L751, L1954, L1955 | **P1-01/02/03** |
| **OB/FVG 结构体定义** | L1942-1950 (FVG), L1973-1983 (OBZone) | 缺 `qualityScore` 字段 |
| **OB/FVG 生命周期** | L2040, L2053 (FVG 过期), L2198 (OB 过期), L2275 (LV 硬编码) | P2-07/09/10 |
| **bornBar 计算** | L2012 (`bar_index`), L2019, L2156 (`bar_index-obOffset`), L2168 | P2-07 |
| **HTF 列表清理** | L1968-1969, L1996-1997 | P2-09 |
| **EMA 参数** | L148-151 (输入), L856-859 (计算), L862-867 (绘图) | P2-04/06 |
| **对象限制** | L4-5 (`max_boxes_count=120` 等) | P2-12 |
| **request.security** | L304, L612, L729, L750, L751, L960, L963, L969, L974, L980, L1954, L1955 | P2-13 |
| **plot 计数** | L801-803, L862-865, L2722-2746, L2807-2813 | P2-14 |
| **分组常量** | L6-23 | P2-15 |
| **inline 分组** | L148-151 | P2-17 |
| **SVP completed profile 渲染** | L1508-1512, L1571-1572 | P2-11 |

---

## 建议修复顺序 (ROI 排序)

1. **P1-01 / P1-03** — 移除 HTF `request.security` 的 `lookahead_on` (影响全链路信号正确性)
2. **P1-02** — 修正 ADR daily 请求
3. **P2-01 / P2-02** — 在 `OBZone`/`FVG` 增加 `int qualityScore` 字段 + 计算函数 (为后续 A/B/C 级打分奠基)
4. **P2-12** — `max_boxes_count=200` 或实现 LRU 清理
5. **P2-13** — 合并 HTF 请求、按需请求 OI/DXY/VIX/SMT
6. **P2-04 / P2-06** — EMA 参数运行时校验 + plot 显示联动
7. **P2-07 / P2-09 / P2-10** — bornBar 修正、LV 过期参数化、HTF 列表清理逻辑
8. **P2-15 / P2-16 / P2-17 / P2-18** — 设置面板规范化 (低优，不影响逻辑)

---

## 结语

该指标**架构完整、功能极其丰富**，已通过编译且实盘可用。核心风险集中在 **HTF `lookahead_on` 导致的实时重绘 (P1×3)** 与 **对象池/请求数逼近上限 (P2×3)**。**OB/FVG 质量分级缺失**是下一版本 (v6.1+) 最值得投入的功能增强点，可直接提升 A/B/C 级信号的胜率区分度。建议先修复 P1 重绘，再扩容对象池，最后补齐质量分级体系。