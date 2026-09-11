# 双指标全面审计增量（2026年7月10日 第二轮）

适用：用户上传的主指标 `cd9be80b7fa45f04.txt`（SVP+ICT+VWAP+CVD v6）+ 副指标 `d89106062ce7ef49.txt`（AggVol）。

## 实测基准（本轮确认）

| 维度 | 主指标 | 副指标 |
|------|--------|--------|
| 行数 | 2,860 | 503 |
| 字符数 | 186,300 | 37,793 |
| Token 估算 | ~79,957 / 100,000 | ~16,220 / 100,000 |
| @version | v6 ✅ | v6 ✅ |
| dynamic_requests | true ✅ | 不需要 |
| request.security 展开 | 12 / 40 ✅ | 32 / 40 ✅ |
| plot 槽（含 alert/bgcolor/fill） | ~47 / 64 ✅ | ~57 / 64 ⚠️偏紧 |
| Data Window plot | 12 ✅ | 17 ✅ |
| alertcondition | 16 | 8 |

## 全项通过清单（本轮确认无问题）

- 未定义变量：无（死叙事卡变量 stateText/cardLine1-3/detailText 等全文 0 残留）
- def-before-use：cvdBearStars(L830) 在赋值(L1828)之前 ✅
- UDT type 定义顺序：type OBZone(L2034) 在所有引用之前 ✅
- OBZone.new 参数匹配：6 处全部 9 参 ✅
- 重绘安全：HTF lookahead_on + [1]/[3] 偏移 + barstate.isconfirmed 门控 + f_htf_fvg 用 low[1]>high[3] ✅
- R:R 执行门控：executablePlan 含 rrHardOk(L2522)；panelEntryVal/StopVal/TgtVal 三行 rrHardBlock 门控(L2712/2718/2719) ✅
- BOS/CHoCH 优先级：CHoCH 先于 BOS(L2195/L2787) ✅
- DO 可见性：创建 bar_index+1，维护 set_x2 bar_index+1(L897) ✅
- nPOC 可见性：创建 endBar+1(L1565)，维护 set_x2 bar_index+1(L1607/1610) ✅
- CVD 星级：cvdBearStars := 背离+吸收=3星/背离=2/未确认=1/无=0(L1828-1829) ✅
- minBuckets 小币修复：L517-518 ✅
- MCP Data Window：12 plots 主 + 17 plots 副 ✅
- 风控参数 MCP 编码：mcpRiskPack(L2791-2792) ✅
- OB HTF 全链：f_htf_ob(L725) → request.security(L2016) → htfObList(L2044) → inBullObHtf(L2293) → confirmScore(L2439) → bcDirectRaw(L2429) ✅
- bcDirectRaw OB 汇合：含 inBullOB/inBullBreaker/inBullObHtf(L2429-2430) ✅
- FVG/OB/LV 标签定位：textalign=text.align_right + 框内缩-3 + textcolor=区域色 ✅
- EMA 只云：color.new(#hex, 100) 全透明 plot + fill(L910-913) ✅
- gapThrough 视觉一致：touchOrGap = wickPierce or gapThroughLine(L1428) ✅
- CW10002：主 L1634 ta.rma 在 ternary 参数内但无条件门控；副 L140 ta.ema 条件为 simple bool ✅
- ACTION_PANEL_TRANSP tooltip：写「默认50」，input.int 默认 50，一致 ✅

## 本轮发现的缺陷

### P1-A：副指标 LSR 方向反转（仍存在）

副指标 L309：
```pine
string lsrTxtA = na(lsrA) ? '' : lsrA > 1.3 ? ' · 空拥挤' : lsrA < 0.8 ? ' · 多拥挤' : ' · 多空均衡'
```
正确应为：`lsrA > 1.3 ? ' · 多拥挤' : lsrA < 0.8 ? ' · 空拥挤'`

此缺陷在 skill 中首次记录于 2026-07-08，本次上传源码中仍写反。说明修复从未写入用户 TV 生产环境。

### P1-B：副指标 LSR 未参与 Confirm Score 降级

LSR 只在表格持仓行显示文本(L445/L453)，不参与 confirmScoreA(L390)、riskWarnA(L391)、haldroRiskCodeA(L481) 任何降级机制。当方向与 LSR 拥挤同侧时应扣 1 分并标 ⚠LSR拥挤。

### P2-A：主指标 6 个死函数

| 函数 | 定义行 | 说明 |
|------|--------|------|
| f_rebuild_polyline | L351 | 折线重建，0 调用 |
| f_dist_text | L367 | 距离文本，0 调用 |
| f_level_short | L1677 | 等级简称，0 调用 |
| f_score_text | L1922 | 评分文本，0 调用 |
| f_price_text | L1924 | 价格文本，0 调用 |
| f_strength_text | L1928 | 强度文本，0 调用 |

约 ~400 tokens 可回收。token 余量约 20,000（79,957/100,000），不紧急。

### P2-B：副指标 VAREUR/VARRUB 无条件请求

L65-66 无论 coinusd 是否为 EUR/RUB 始终执行 request.security。默认 USD 时浪费 2 配额。当前 32/40 安全，但扩展 OI 聚合后可能逼近 40。

### P2-C：副指标 plot 槽位偏紧

34 个 plot 中约 15 个使用 series color（每个计 2 槽），最坏约 57/64。新增 plot 前需先评估。

## 推荐修复优先级

1. P1-A LSR 方向反转（1 行改，影响实盘判断）
2. P1-B LSR 参与评分（约 5 行加）
3. P2 可选，不紧急