# 双指标联网审计实录 2026-08-09（SVP_ICT_v2_fix + AggVol_v2_fix）

上传文件：`~/.hermes-web-ui/upload/default/fc5080a3e56f6763.pine`（主）、`7a8c983eb6cd089d.pine`（副）。
TV 服务器编译本次不可用（pine_check 报 `CDP connection failed: fetch failed`，TradingView Desktop 未运行）——结论为「静态未发现 P0」，最终以 TV 实机 Add to chart 回执为准。

## 量化基线（与 SKILL.md「v2 基线 2026-08-09 上传版」同步）

| 维度 | 主 | 副 |
|---|---|---|
| 行/字符 | 3065 / 202,026 | 686 / 51,978 |
| est tokens (÷2.33) | ≈86.7K / 100K | ≈22.3K |
| request 静态/展开 unique | 8 / ≈8 | 7 / 展开 29（20 所×后缀 + OI4 + LSR1 + spot1 + oiSingle1 + HTF1） |
| plot / 最坏 | 43 / 55/64 余 9 | 41 / 53/64 余 11 |
| alertcondition / alert() | 0 / 2（边沿事件化） | 0 / 2 |
| DW plot | 29 | 23 |
| 死代码 | 6 变量 + SHOW_SESSION_CVD 输入 | 0 |
| type UDT | 7 | 0 |
| 对象 | line16/box6/label9/polyline4 | 0 |

最坏式口径（2026-08-09 修正）：box 的 `bgcolor=` 参数不计；`bgcolor()` 函数调用每 1；input.color 变量（VWAP_COLOR/bull_color/bear_color/数组 get 色）按 series 计 2。主：50 plot（7 series=14 + 36 const）+ fill2×2 + bgcolor1 = 55。副：12 series=24 + 28 const + Zero1 = 53。

## P1 全项通过核对表（2026-08-09 版本，下次审计直接引用为基线，不再当未知项重查）

- executablePlan = `not setupX and ((displayLongA or displayShortA) and rrHardOk) or bcDirectOk ...` → L2647-2648 ✓（rrHardOk≥2.0，bcDirectOk≥1.5）
- manualBcCandidate = bcDirectRaw and priceGeometryOk and **not setupX**（L2646）；visiblePlan 两路都含 not setupX → X 时 MCP Entry=na 原子清空 ✓
- replayGradeCode 含 `setupX ? -1` 分支（L2486）；MCP Side Code = `setupX ? 9 : ...`（L2961）X 优先 ✓
- panelEntryVal 无条件更新（L2843），expectedTriggerPath 在 f_pnl_row 消费端拼接（L2898）✓
- 副 LSR：`lsrA > 1.3 ? ' · 多拥挤' : lsrA < 0.8 ? ' · 空拥挤'`（L313）✓ 且参与降级（L455-456 + L531 riskWarnA + L643 alert）
- 副共振票：resoCvdA/resoHtfA 方向镜像（L513/519），resoOiA=oiUpA and oiConsensusOkA（L516，空向=新空扩仓），4 票=resoCvd/resoOi/resoVol/resoHtf ✓
- 副 OI 四象限：vGood/vDiv/vBad/vDelev/vExh（L487-491）+ oiTxtA 新多/新空语义（L359）+ 扩仓 vs 爆仓（L427-433）✓
- alert()：`if alertFire`（anyAlertNow and not anyAlertPrev，var 边沿）包裹，无 islast 门控（L3020-3042 / L630-646）✓
- HTF 死请求已删：f_htf_trend_confirmed_pack 返回 [close[1], eFast[1], eSlow[1], v[1]]，htfBullConfirmed/BearConfirmed 全消费（L788-792）✓
- 行动格消费链：主 13 行 f_pnl_row 全有消费（L2894-2927，CVD 行含星级/吸收/派发）✓
- CVD 锚定双指标同步：主 L751 `tf_sec<3600→D / <14400→W / else M`，副 L37 同口径（20260809 新增）✓
- input.active 灰化：主 L218-246 `active=SHOW_ADVANCED` 覆盖 15+ 输入（20260809 新增）✓
- 副指标不越权：操作行='请看主指标判定'（L596）✓

## P2 pending 清单（2026-08-09 仍未修复）

1. **会话 CVD 死链（主 L918-931 + 输入 L248）**：cvdAsiaBar→cvdAsiaAcc→cvdAsiaSlope 全链每 K 计算，Slope 零消费；SHOW_SESSION_CVD 输入只喂死链。修法二选一：接回「亚主/伦主/纽主」到 CVD 行（推荐）或整条删（省 ~560 tokens）。**待用户拍板。**
2. 非加密门控未落地：副 f_oi×4 / lsrA / spotCloseA 无条件预取，XAU 图白占 6 个 context。修法 `isCryptoA ? f_oi(ex) : na`。副 L302 注释「32/40」过时，实际 29/40（USDC.P_OI 回退已删但总数未更新）。
3. resoLsrA 缺失全绿：`resoLsrA = not lsrCrowdingRiskA`（副 L520）在 LSR=na 时恒 true。修法 `not na(lsrA) and not lsrCrowdingRiskA`，缺失标 `✗LSR缺`。
4. freshness 残余盲区：`barssince(not coverageNowValidA)`（副 L465-467）= 自上次失效以来K数，健康时恒 999（语义是"失效年龄"不是数据年龄，解码端别把 999 当很旧）；sourceDropoutA（EMA50+连续3根）兜底掉线；"所有所返回停滞旧值"盲区仍在，下一步改值变化年龄。
5. HTF FVG/OB 外层 lookahead_off（主 L1993/1994）+ 函数内 [1]/[3] → 合法但延迟发布 1 根 HTF；改 lookahead_on 与 trend pack 一致（优化非修 bug）。
6. 位置行三合一 `posText + adrRoomText + "·" + rdyGauge`（主 L2894）仍是最宽行。

## 2026-08-09 已确认落地（下次不用重查）

CVD 锚定同步、input.active 灰化、executablePlan rrHardOk、MCP Side X 优先 + X 价格清空、alert() 边沿事件化、HTF 死请求删除（f_htf_trend_confirmed_pack [1] 确认）、LSR 方向正确 + 参与降级、共振票方向镜像、OI 四象限一致。

## 联网核验（2026-08-09 增量，均有 URL）

- TV 官方 Visuals/Plots：series color（含 input.color）的 plot 计 2，const color 计 1。https://www.tradingview.com/pine-script-docs/visuals/plots/ （SO 佐证：https://stackoverflow.com/questions/75614138）
- TV 官方 Concepts/Inputs：`active` 参数接受 input bool，依赖其他输入灰化。https://www.tradingview.com/pine-script-docs/concepts/inputs/
- request.footprint 仅 Premium/Ultimate：TV 官方博客 https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/ + flowly 2026 指南（Premium $59/月）https://www.flowly.tools/tradingview-volume-footprint
- HVN=磁吸/支撑阻力、LVN=真空快速穿越/突破：equiti / tradingsim（2026-07 版）/ tradedevils 2026 共识，与 skill「2026 社区 VP 增强对标」一致。

## 交付要点

8 段审计骨架（量化基线→P0 无→P1 全通过表→P2 清单→联网增量→10 条建议→推荐增强 A-F→直接推荐）已验证有效；P1 段用"核对表"方式呈现比逐条解释更高效。改版文件名带 `_20260809` 日期后缀（如 `SVP主指标_20260809.txt`），旧日期文件保留。
