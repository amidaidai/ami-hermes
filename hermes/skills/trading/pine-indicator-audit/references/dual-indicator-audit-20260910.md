# 双指标全面审计增量（2026-09-10）

对象：`SVP_token_fixed.pine`（3419 行 / 241438 B / SHA `fdbcdf73…ca8044`）+ `AggVol_anchor_fixed.pine`（876 行 / 78382 B / SHA `0cf4feb0…20c45d6`）。
实跑产物：`scripts/pine_static_audit_scan.py`、`scripts/pine_cloud_compile_check.py`、`scripts/pine_packed_bus_roundtrip.py`（结果落 `D:/Hermes agent/outputs/pine_20260905/`）。

## 0. 审计执行边界（本轮确立，后续沿用）

- 只读三层可直做：静态扫描、`translate_light` 服务器编译、合同反例复现。
- 挂 study 到用户图表 / 改 Pine 编辑器 = 外部状态写入 → **先要授权**；授权后一次挂载 → 读 `pine_get_errors` + Pine Console + `data_get_pine_tables` → 验完移除 study、还原编辑器源码。
- 报告必须三行分写：服务器编译 / 客户端编译 / 图表真实实体。没做写"未复验"。
- 现场事实（本轮）：`OANDA:XAUUSD 15m` 只挂内置 Volume，无任何 SVP/AggVol 实体；TV 云端保存的 SVP 源码 SHA `d5ad89e9…` 与本候选 `candidate_match:false` → **候选从未在 TV 上编译过**。

## 1. 量化基线

| 项 | SVP | AggVol |
|---|---:|---:|
| 行/字符/字节 | 3419 / 220768 / 241438 | 876 / 64581 / 78382 |
| request 调用点（唯一上下文最坏） | 8（≈6） | 8（≈30） |
| plot（series-color / DW / 价格轴） | 31（8 / 21 / 7），最坏预算 44/64 | 45（8 / 24 / 0），最坏预算 53/64 |
| input 总数 | 193 | 37 |
| **TV 六项和** | **237/254（余量 17 ⚠）** | **91/254（余量 163 ✓）** |
| type / UDF / method | 8 / 64 / 10 | 0 / 18 / 0 |
| 表格 | 1 个 2×18，实填 13 行 | 2 个互斥分支，各固定 6 行 ✓ |
| 死变量 | 15 | 6 |
| alertcondition / alert() | 0 / 0 | 0 / 0 |

## 2. P0：CE10117 未闭环

真实现场报错 `Compiled code contains too many tokens: 100488. The limit is 100256`。`translate_light` 返回 0 错 0 警但**不校验 IL**；候选从未客户端编译。
IL 削减杠杆（都是仍进入编译的字符串/分支，不是注释）：`panelEntryVal`(L3091)、`rdyGauge`(L3043)、`sweepCntText`(L3184)、`guidePrevRowText`(L3188-93)、`replayStopDistance/replayStopAtr`(L2913-14)、`aggContractSource`(L232)、`perpSpotBasisPct`(L797-801)、`atrPctile`、`bosChochText`、`chartTfSec`(L3029)、`magnetTargetScore/Text`、`long/shortInvalidText`(L2669-70)、`PRO_GROUP`(L22)。

## 3. 新发现（本轮相对 20260901/20260907 增量的新增项）

### P1-5 SVP 高周期 FVG/OB 读到未收线 HTF 值
- L2175 / L2185 `request.security(…, fvgHtfRaw, …, lookahead=barmerge.lookahead_off)` **无已收线偏移**；L2170-2173 注释却写 "HTF zones are published only after the source HTF candle closes"。
- 官方语义：`lookahead_off` 只是不含未来数据，读到的是**正在形成**的 HTF K → 随其走完而变化（重绘）。非重绘 = `lookahead_off`+`[1]` 或 `lookahead_on`+`[1]`（TV 官方 Other timeframes and data；PineCoders "Higher-timeframe requests"）。
- 同脚本 L812 的 HTF 趋势已是 `lookahead_on`+`[1]` Confirmed 版 → 同图两套 HTF 口径分叉。
- 影响：标 ★HTF 的 FVG/OB 可能在 HTF 收线后不存在。

### P1-6 SVP 信号年龄用原始 setup 驱动，不是唯一仲裁方向
- L2675-76 `signalNowLong = displayLongA or setupLongB or setupLongC`；唯一方向来自 L2693-98 的等级仲裁（同级双边直接 `C等待`）。
- 多空原始 setup 同时成立（= `prePlanTie` 场景）时，结论行显示"…C等待"同时挂"·新"，把从未被仲裁选中的方向当新信号。
- 与 AggVol F10（强多直接转强空沿用上一方向年龄）同类。修法：事件身份含仲裁后方向，方向翻转强制重计时。

### P1-7 副总线第 10 位解码后无消费者
- AggVol L500 `cvdBgCodeA`(0-4) 编在总线个位（L855）；SVP L220 `cvdBgDecoded` **全文件仅此一次**（grep 确认）。
- 编码/位宽/往返都正确，是**消费端缺口**：CVD 当前锚 vs 滚动 vs 前锚背景进不了主指标协同行。要么接进协同行，要么从合同去掉省 1 位。

### P2 新增
- P2-1 `SHOW_SPOT_PERP_BASIS` + `perpSpotBasisPct` 算完从不显示 → 基差(funding 代理)功能实际不存在。社区 StrixEDGE 用同一 `(Perp−Spot)/Spot/3` 代理。
- P2-2 `replayStopDistance = visiblePlan ? |replayPlanPrice − replayInvalidPrice| : na` —— 条件用 `visiblePlan`（含 B/C）、取值用 `replayPlanPrice`（仅 A 级有值）→ B/C 恒 na；正确应取 `panelPlanPrice/panelInvalidPrice`。
- P2-3 副 S3 冲突下 `manualBcCandidate` 不受闸门约束 → `visiblePlan` 为真，风控行打印"止…·标…"而结论行写"副S3冲突·不执行"。
- P2-4 AggVol `liqOIDropA`（去杠杆强度 OI 收缩幅度，20260814 新加）从未渲染；`coverageRowA`/`htfTxtA`/`signalA`/`volume_buy`/`volume_sell` 同样算而不用。
- P2-5 AggVol Exchange Domination 画的是每根重排后的序列（第1名→第1名），不是同一交易所时间序列；图名仍叫 EX1…EX5。
- P2-6 AggVol 非美元报价只归一化到报价货币就当 USD 加总；后缀未去重（SPOT1=SPOT2 双计）；OI 单源回退首段无比较基点。
- P2-7 注释漂移：SVP L2926 声称的 `aggStateSource != close` 守卫不存在（已由 `aggBasicValid` 合同校验替代）；L2170-73 见 P1-5。

## 4. 本轮复现的既有缺陷（沿用 20260907 F01-F12 编号）

| 编号 | 实测反例（`contract_repro` 脚本 B/C/D 段） | 结论 |
|---|---|---|
| F01 | 价涨+OI升且共识+放量+高周多+**CVD 反向** → 票数=3, finalStrong=True, S=1 | 副表同屏"S1支持多"+"流向：卖"；SVP `aggAllowLongA` 只看 `aggStateCodeV==1` → **A 级授权照样成立** |
| F01'（htfConflict） | 价涨+高周空+CVD 反向 → `htfConflict=False`（应 True） | `htfConflict=(vGood and htfBearA) or …` 含 CVD 项 → 逆高周告警静默丢失。修法：改按 `dirUpA/dirDnA` |
| F02 | `oiOk=False, oiUp=False`，价涨+CVD买 → vGood=True | 仍输出"价涨+OI升 · 新多扩仓"；非加密复用同一 actText |
| F03/F04 | `cvdSampleReadyA = not na(cvdSlopeA)` 需满 ACT_LB → 日锚 5m 图前 9 根误报"⚠数据缺" | 锚点预热被当掉线 |
| F12 | `oiAccelA = oiPctChgA − nz(oiPctChgA[5])` | 缺历史补 0 基点，凭空"加速/减速" |

**均已由 `AggVol_display_fixed.pine`（09-07 15:52）修好** —— 副指标交付版应用它，`AggVol_anchor_fixed.pine` 停在审计版。

## 5. 通过项（有实测证据）

- **Packed Bus 22002 往返**：22600 组（全边界 + 13600 随机）失败 0；最大 2200242299199994 < 2^53；旧合同 22000 正确判 invalid；位段无进位（`agree·1e5 + oiPctEnc ≤ 9919999 < 1e7`）。
- `oiAgreementPct` 为 na 时编码端已 `nz(…,0)`（L853）→ 总线不会整条变 na 被下游误判 S0。
- OI Pack 负向解码 `(100−|x|%100)%100` 与编码端一致，含"100% 压 99"边界。
- **A 级唯一授权**：`executablePlan` 要求 `selectedCurrentAValid`（`displayLongA + setupLongA + aggAllowLongA` 三者同时）→ 副 S1/S2 之外不可能出 A。
- 执行/观察价格原子隔离；X/WAIT 时 MCP 三件套为空（L2907-12）。
- 同级双边不猜方向：`prePlanTie → "C等待"`（L2607/2618/2696）。
- 表格：AggVol 两分支各恰好 6 行；SVP `table.clear(0,0,1,17)` 与 `table.new(2,18)` 索引一致（不再 end_row 越界）。
- 五所成交量 + 四所 OI 未削减，非加密/关后缀/重复所只在 `request.security()` 前短路。
- 多市场：`autoMetal` 按 ticker（XAU/XAG/GOLD/SILVER/GC/SI/COMEX）判定；金属现货/外汇 CVD 权重 0 并输出"tick量估算·不计A级票"；AggVol 非加密降为合同 22000，SVP 只认 22002。
- 主副锚定矩阵逐格一致（加密 <1h→D / 1h-4h→W / 4h+→M；非加密 <4h→D / 4h+→W）。

## 6. 社区对标要点（2026）

社区同类（StrixEDGE Funding Rate & OI Radar / QuantAlgo OI Suite / HYPR-run OI Context / NoveltyTrade OI Aggregated）共性：多所 OI 聚合 + 归一化（Z-score / % / USD）、价×OI 上下文分类、**强信号必须所有维度全对齐才触发**、非重绘 HTF 一律 `lookahead_on`+`[1]`；并明示"25 个 request.security 远低于 40 上限"。
结论：本双指标在**数据源完整度 + 估算诚实性**上更强，差距恰好落在**资格规则（反向流不得授权）**与**已收线语义**两点。
