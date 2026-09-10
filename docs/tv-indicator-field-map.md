# 双指标 TV Pine → 分析卡 字段映射 v1.3

> 所属：棠溪交易驾驶舱 / `tradingview-indicator-analysis`
> 更新：2026年9月10日（上一版 v1.2 = 2026年7月2日）
> 权威来源：两份 v13 生产指标源码 + 2026-09-10 在 `BINANCE:BTCUSDT.P` 上的实盘读数
> **唯一代码定义源**：`scripts/tv_indicator_contract.py`（改字段先改这里）

## 0. 当前生产指标

| 指标 | Pine 文件 | sha256[:24] | 行数 | 分工 |
|---|---|---:|---:|---|
| 主指标 | `SVP_主指标_优化v13_清理死码_20260910.pine` | `98d6338b4cb77e5d4e56e5e4` | 3446 | 结构、位置、IA/FVG/OB、VWAP/EMA/CVD、DMI体制、13 行行动格、唯一执行授权 |
| 副指标 | `AggVol_副指标_优化v13_清理死码_20260910.pine` | `9f71366943a2d773ccb0c1c4` | 921 | 5 所聚合成交、4 所 OI、估计 CVD、LSR、基差、6 行行动格、只确认/降级/否决 |

## 1. v1.2 → v1.3 的实质变化（旧文档已失效的部分）

| 项 | v1.2 记录 | v1.3 实际 | 影响 |
|---|---|---|---|
| 主指标版本 | v5 / 3163 行 | **v13 / 3446 行** | 字段与行名大幅变化 |
| 主指标行动格 | 10 行：结论/方向/进场/止损/目标/确认/风险/磁吸↑/磁吸↓/核对 | **13 行**：位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位 | 旧卡片只吃到 4/13 行 |
| 进场·止损·目标 | 独立三行 | **折进「风控」行**：`入X·止Y·n.nA·标Z·n.nR` | 必须解析「风控」行才能拿到价格 |
| 「风控」行标签 | 固定「风控」 | **动态四态**：风控 / 风控·观察 / 风控·未授权 / 禁做·不出价 | 只认字面「风控」会在观察态漏读 |
| 副指标版本 | v6 / 469 行 | **v13 / 921 行** | — |
| 副指标行动格 | 10 行 | **6 行**：信号/结论/流向/持仓/量能/操作 | 风险/高周/覆盖/爆仓已并入或删除 |
| `OI Total` | 有 | **已不存在** | 旧映射恒空 |
| `Estimated CVD Value` | 有 | **改名为 `CVD Value`** | 旧映射恒空 |
| `MCP CVD Value` | 有 | **已不存在** | 旧映射恒空 |
| `MCP EMA Length 1-4` / `MCP Risk Pack` / `MCP Bull FVG CE` | 有 | **均已不存在** | 旧映射恒空 |
| 主副连接 | 无 | **`Basic Packed Bus`（合同号 22002）** | 主指标必须选源指向它 |
| 配额 | 交易所 20 + 2 + 4 + 1 = 27/40 | **request.\* 8 / 8，input 193 / 38，alert 0** | — |

## 2. 主指标行动格（13 行，权威读法）

| # | 行 | 含义 | 卡片用途 | 授权含义 |
|---:|---|---|---|---|
| 1 | 位置 | 价在 VA 上/下 · VWAP 锚 · 周月偏空/多 · 波N% | 背景定位 | — |
| 2 | 结论 | 副Sx·A禁/不执行 + 冲突/未收线标志 + 等待根数 | **裁决首读** | 决定等级 |
| 3 | 方向 | 主倾向 · 趋势/震荡 · 评分 n/10 | 方向速览 | — |
| 4 | 路径 | 触发链 + `·距n.nA↑/↓`（入场位距现价） | 触发条件 | — |
| 5 | **风控** | 授权等级 + `入X·止Y·n.nA·标Z·n.nR` | 执行三件套 | **风控·观察 / 风控·未授权 / 禁做·不出价** |
| 6 | CVD | 锚定周期 · 方向 · 质量 · `基差±n.nn%` | 订单流确认 | — |
| 7 | OI | 四所 OI 共识 / 未接 | 持仓变化 | — |
| 8 | 协同 | `副Sx…·高周N` | **主副一致性** | — |
| 9 | 结构 | 多/空趋势 · BOS/CHoCH · 守摆高/低 · 扫位 n/m | 结构判定 | — |
| 10 | 磁吸↑ | `↑周N 高/低 价格·n.nA·分N·N★HTF` | 上方目标 | — |
| 11 | 磁吸↓ | 同上（下方） | 下方目标 | — |
| 12 | 前位 | `名称 价格·生命周期·角色·距离·退役时刻` | 前关键位现状 | — |
| 13 | 现位 | `多/空·反抽/回踩 XX·等MSS↑·HH:MM定` | 当前观察位 | — |

**前位行的生命周期与角色**：生命周期 = 已破 / 过期 / 被替代；角色 = 仍撑 / 破转阻 / 仍阻 / 破转撑。

## 3. 副指标行动格（6 行）

| 行 | 源码变量 | 含义 | 卡片用途 |
|---|---|---|---|
| 信号 | `panelStateA` + 共振 n/4 | 🔴S3冲突 / S1支持多 / S2支持空 / S4降权 / S0未接 + `·OI背离` | 订单流状态码 |
| 结论 | `actText` | 实涨可信 / 缩量下跌 / 涨势存疑 / 回补 · 勿追·前N根 | 真假运动 |
| 流向 | `flowPanelTxtA` | 锚定周期 · 采样口径 · `本锚近NK卖/买` · `净N%` · 滚动同向/逆 | CVD 确认/背离 |
| 持仓 | `oiTxtA` | ⚡新空/新多/回补/平仓 · `n.nn%` · `同N%` · `滚NK` | 价仓四象限 |
| 量能 | `volTxtA` | ▲放量/▼缩量/平量 · `xN.N` · `合N%` · `同步放量 n/5` | 能否追 |
| 操作 | `comboTxt` | 不执行 / 不追 / 弱确认 / 仅作参考 / 确认多 / 确认空 | 最终执行建议 |

## 4. Data Window 全量（35 + 27）

### 主指标

`S VWAP` `S VWAP ±Band1` `EMA 9/21/34/55` · `POC Price` `VAH Price` `VAL Price` `nPOC Price` `W VWAP Price` `M VWAP Price` `DO Price`
`MCP Side Code`(1多/-1空/9X/0无) `MCP Grade Code`(3A/2B/1C/-1X/0等待) `MCP Setup Score`(0-10)
`MCP Entry/Stop/Target Price` · `MCP CVD Method Code` · `MCP Quality Code` · `MCP FVG/OB Quality Score`
**v13 新增接进卡片**：`MCP Entry Valid Code` `MCP RR Ratio` `MCP NoTrade Reason Code` `MCP Execution Pack` `MCP Trigger Pack` `MCP Regime Pack` `MCP Contract Pack` `MCP Evidence Pack/Bar Time/Close Time` `MCP StructPack`

### 副指标

`HALDRO Valid Code` `OI Change % (Normalized)` `CVD Value` `CVD Method Code` `CVD Quality Code` `LSR` `Volume Ratio` `Coverage Exchanges/Spot/Perp` `Coverage Feed Mode` `Exchange Dominance %` `Confirm Score` `Composite` `HALDRO Risk Code`
**v13 新增接进卡片**：`Basic Packed Bus` `HALDRO State Pack` `OI Price Direction` `OI Breadth` `OI Agreement %` `HALDRO OI Pack` `OI Dispersion Ratio` `HALDRO Freshness Pack` `Stale Venue Count` `HALDRO Contract Pack` `HALDRO Flow Pack` `CVD Anchor Value`

## 5. 解码器（v13 新增，全在契约文件里）

### `MCP NoTrade Reason Code` — 位掩码，可多位置位（最有价值）

| 位 | 含义 |
|---:|---|
| 1 | HTF 冲突 X |
| 2 | 过热追高 X |
| 4 | 低流动性 |
| 8 | 价格几何不成立 |
| 16 | R:R 不足 |
| 32 | CVD 质量不达标 |
| 64 | ADR 禁追 |
| 128 | 溢折价不允许 |
| 256 | 本根未收线 |
| 512 | 触发不新鲜 |
| 1024 | 副指标冲突/降权 |

**实读样例**：`1976 = 8+16+32+128+256+512+1024` → 七项同时成立，与面板 `副S0未接·A禁 ⚠冲突 ⚠未收线` 自洽。

### 其他

| 字段 | 取值 |
|---|---|
| `MCP Entry Valid Code` | -3 X禁做 / -2 价格几何不成立 / -1 R:R不足 / 0 无方向 / 1 待确认 / 2 可执行(B/C) / 3 可执行(A) |
| `HALDRO State Pack` | 0 S0未接 / 1 S1支持多 / 2 S2支持空 / 3 S3冲突 / 4 S4降权 |
| `MCP RR Ratio` | ≥2.0 过硬闸（A级必需）；≥1.5 仅 B/C 直通；<1.5 不足 |
| `MCP Execution Pack` | `几何*1e6 + 收线*1e5 + 止损ATR*10 + (入场码+3)`；实读 1801 → 几何0/未收线/1.80ATR/入场码-2 |
| `MCP Trigger Pack` | `(触发码+10)*1e5 + 触发年龄*100 + 新鲜*10 + (信号态+1)` |
| `MCP Contract Pack` | `171000 + 市场码*10 + 1`；实读 171011 = BTC/加密 |
| `Basic Packed Bus` | 主副唯一总线；合同号 22002 为加密，22000 非加密 |

## 6. 读取顺序（v13）

```text
①  TV 健康与品种校验：chart_get_state；价格数量级与品种必须匹配
②  主指标 13 行行动格（pine_tables，study-filter SVP）—— 决策首读
③  副指标 6 行行动格（study-filter 副指标名）
④  主指标 DW：先读 Side/Grade/EntryValid/RR/NoTradeReason 五件套
⑤  副指标 DW：State Pack / Valid Code / Confirm / Composite / Coverage
⑥  解码：NoTrade 位掩码 → 原因链；EntryValid → 准入结论；RR → 闸门结论
⑦  外部验证：Binance OI/Funding/Taker/多空比/Depth、F&G、CoinGecko、Jin10/X
⑧  截图：全屏，含价格轴 + 主行动格 + 副行动格/CVD 窗格
⑨  输出：多周期定位 → 关键位矩阵 → 多源交叉验证 → 矛盾点 → 方案 → 评分 → 完成度
```

## 7. 合成裁决（**已落成代码**：`scripts/decision_matrix.py`）

### 7.1 主副九宫格 `synthesis_verdict()`

输入：主指标等级 × 副指标状态 S0-S4 × R:R × 是否加密。
输出：`verdict / authority / sub_role / executable / hard_block / rr / reason`。

| 主指标 | 副指标 | 裁决 | 可执行 |
|---|---|---|---|
| A 多 | S1 支持多 | **A执行** | ✅ |
| A 空 | S2 支持空 | **A执行** | ✅ |
| A | S3 冲突 | **不执行·副冲突** | ❌ 硬阻断，清空三件套 |
| A | S4 降权 | **A降级候选** | ❌ 降为 B 档人工候选 |
| A | S0 / 未接 | **A降级候选** | ❌ 副未接不得假装同意 |
| A | 反向（A多+S2） | **A降级候选** | ❌ |
| B/C | 顺向 + R:R≥1.5 | **B/C人工候选** | ❌ 给触发与候选价，不给执行指令 |
| X | 任意 | **X禁做** | ❌（副指标不覆盖 X） |
| 非加密 | 任意 | **副不参与** | 按主指标，不得被副指标否决 |

**不变量**：全网格扫描（9 等级 × 6 副状态 × 5 R:R = 270 组）证明**合成永不升级** ——
副指标只能确认/降权/否决，任何组合都不可能把 B/C 变成 A。
代码位置 `_apply_matrix_guard()`（auto_card）：在 FinalVerdict 落定后做最后一次保守化，只降不升。

### 7.2 解除条件 `release_plan()` / `format_release()`

回答「现在是 A 禁，那我在等什么」。每个 NoTrade 位置对应一句**可验证**的等待条件：

| 位 | 解除条件 |
|---:|---|
| 1 | 等 HTF 与本级同向 |
| 2 | 等过热回落（回到结构位/ATR 正常范围） |
| 4 | 等流动性窗口（避开低流动时段） |
| 8 | 等价格几何成立（入场与止损顺序正确、贴近结构位） |
| 16 | 等 R:R ≥ 2.0 |
| 32 | 等 CVD 质量达标（采样源恢复） |
| 64 | 等 ADR 空间打开（当日波动耗尽，隔日再看） |
| 128 | 等溢价/折价回到允许侧 |
| 256 | 等本根收线 ★临时 |
| 512 | 等新触发出现（旧触发已过期） ★临时 |
| 1024 | 先修副指标总线 ★临时 |

★ 临时项排在最前 —— 先做能立刻做的。

### 7.3 R:R 档位 `rr_tier()`

`≥2.0` A级（过硬闸）｜`≥1.5` 仅 B/C 直通｜`<1.5` 不足｜缺失 → 不给执行价。
与指标侧 `rrHardOk / bcDirectOk` 同源同阈值。

### 7.4 旧版文字规则（保留供理解）

| 情况 | 裁决 |
|---|---|
| 主A + 副顺向 + 覆盖正常 + R:R≥2.0 | A 机会，可盯执行 |
| 主A + 副 S3 冲突 | **不执行**（硬阻断，不得降级放行） |
| 主A + 副 S4 降权 / S0未接 | 降权为人工候选 |
| 主B/C + 副强 + R:R≥1.5 + 贴关键位/FVG | B/C 人工观察候选 |
| 主X | 不出价；读 NoTrade 掩码写「解除条件」 |
| NoTrade 含 1024 | 先修总线（主指标「免费版唯一总线」未指向副指标 `Basic Packed Bus`） |
| NoTrade 含 256/512 | 等收线 / 等新触发，不得提前挂单 |

## 8. 禁止事项

- 禁止用 v1.2 的 10 行旧行名（进场/止损/目标/确认/核对）解析 v13 面板 —— 会静默丢 9 行。
- 禁止只认字面「风控」行 —— v13 是动态四态标签。
- 禁止把「风控·观察」里的候选价当成 A 级授权价（那是 B/C 人工观察档）。
- 禁止强依赖副指标 `OI Total` / `Estimated CVD Value` —— 已不存在。
- 禁止把副指标加密的 OI/Funding/Spot-Perp 逻辑套到 XAU/外汇/股票。
- 禁止在指标侧改完行名/字段名后不改 `scripts/tv_indicator_contract.py` —— 那是唯一契约源。
