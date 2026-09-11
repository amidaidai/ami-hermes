# 20260809 第三方监测报告核验 + P1 修复记录（主 SVP_ICT_v2 + 副 AggVol_v2）

## 背景
用户贴入一份外部 AI 监测报告（5 节：总体评价/P0×2/P1×3/P2×6/排查确认项），要求核验并修复。本次产出：逐条核验 → 9 处修复 → 双文件修订版（文件名带 20260809 日期，旧版保留）。

## 第三方报告核验表（结论 → 证据）

| 报告项 | 结论 | 证据/说明 |
|---|---|---|
| P0-1 plot 超上限「免费 40」 | ❌ 误报 | 官方 plot 上限 64（所有档位，v5+；40 是 v4 旧限制）。免费档真实硬限制：5000 bar、2 指标/图、0 技术告警、3 价格告警、20s 计算、100K intrabar、40 request.security、64 plot。「数据窗 plot 合并打包」不采纳（破坏 MCP 解包兼容）。联网证据：TradingView Visuals/Plots 官方文档 + StackOverflow（series color 多占 1 slot） |
| P0-2 lower_tf 局部作用域 | ⚠️ 非编译风险 | L644/L759 是 2026-08-08 基线已有代码且已实机编译通过。「条件 false request 照常执行、degrade 只省赋值」属实 → 预算注意项（intrabar 100K 内） |
| P1-3 失效价映射死分支 | ✅ 属实 | L2463/2464：「跌回扫低」含「扫」+「低」被 contains 分支先拦截；该文本只在 na(ictEventPrice)（高低同根双向扫）时设置 → 失效价=na → priceGeometryOk=false 误杀 A/B 计划 |
| P1-4 OI 行假数据 | ✅ 属实 | L213 input.source(close) 未接线时 close>0 恒真 → 「▲ 新多 65000.00% ✓一致」 |
| P1-5 位置输入不生效 | ✅ 属实 | var 首根固化 + table 位置无 setter |
| P2-9 spotTicker 只替换 .P | ✅ 属实 | Coinbase -PERP 风格基差恒 0 |
| P2-10 非加密 OI 行误报「未接副指标」 | ✅ 属实 | 接线但 na 与未接线文案混淆 |
| P2-11 showRecentChartLine timenow | ✅ 属实 | 回放模式连线消失 |
| P2-6/7 分布渲染 | ⚠️ 部分属实 | 已完成分布在周期边界渲染一次（非每根），对象被上限约束，维持现状 |
| P2-8 CurrentVolume ÷close | ⚠️ 继承原版 | 方向/比率不受影响，改动风险>收益，不动 |

## 9 处修复清单

### 主指标（3078 行，+13）
1. L2469/2470 失效价分支调换：「跌回扫低」→curVal、「收回扫高」→curVah 特判前移到 contains 之前
2. L218 加 `bool oiSourceWired = sourcetostring(oiSource) != "close"` 与 `bool aggStateWired = sourcetostring(aggStateSource) != "close"`
3. L2912-2921 OI 行三态：接线有值→数据；未接线→「OI 未接副指标」；接线但 na→「非加密无OI」
4. L2672 `if SHOW_AGG_SYNC and aggStateWired and not na(aggStateSource)`
5. L2834 `_posSel` 去 var
6. L2938-2942 位置变化重建 actionPanel（var _posSelPrev + `if barstate.isfirst or _posSel != _posSelPrev`）
7. L779 spotTicker 双层 replace（.P + -PERP）
8. L300 `barstate.isreplay ? true : time >= timenow - chartLineWindowMs`

### 副指标（689 行，+3）
9. L578-581 actPosSel 去 var + `if na(actT) or actPosSel != actPosSelPrev` 重建 actT

## 修复模式代码片段

```pine
// input.source 接线检测（P1）
bool oiSourceWired = sourcetostring(oiSource) != "close"   // 未接线→"close"；接线→"指标名: 序列名"

// 字符串分支顺序：精确特判必须在 contains 模糊分支之前（P1）
float longInvalidRaw = invalidText == "跌回VWAP" ? sVwap
                     : invalidText == "跌回扫低" ? curVal        // ← 先特判
                     : str.contains(invalidText, "扫") and str.contains(invalidText, "低") ? ictEventPrice
                     : na

// table 位置输入生效：去 var + 位置变化重建（P1）
string _posSel = ACTION_PANEL_POS == "右上" ? position.top_right : ...
var string _posSelPrev = ""
var table actionPanel = na
if barstate.isfirst or _posSel != _posSelPrev
    actionPanel := table.new(_posSel, 2, 18, ...)
    _posSelPrev := _posSel

// 回放模式 timenow（P2）
bool showRecentChartLine = barstate.isreplay ? true : time >= timenow - chartLineWindowMs

// 跨所现货后缀（P2）
string spotTicker = marketCrypto and isPerp ? str.replace(str.replace(syminfo.tickerid, ".P", ""), "-PERP", "") : ""
```

## 复检流程（修完必跑）
1. 修复点逐条 grep 验证（正则注意转义 `?`）
2. 括号配平：剥离 `"..."`/`'...'`/`//` 后逐对统计 () [] {}
3. plot 调用点计数未增（`(?:^|\s|;)plot\s*\(`）
4. 行尾统一：patch 会混入 \r\n；`python -c` 统计 CRLF/裸 LF，sed 统一
5. TV 服务器编译（pine_check）在 Desktop 未运行时不可用 → 如实标注「静态未发现 P0，编译待实机」，不写「编译通过」

## 未修决策点
- 主指标 L918-931 死会话 CVD 链：cvdAsiaBar→cvdAsiaAcc→cvdAsiaSlope 全链零消费（6 变量 + SHOW_SESSION_CVD 输入死）。选项：①接回「亚主/伦主/纽主」到行动格 CVD 行（会话资金流增量信息）；②整链删除（省 ~560 tokens/每 K 计算）。等用户拍板。
- 副指标非加密请求预取：f_oi×4 / lsrA / spotCloseA 未包 isCryptoA 门控，XAU 图白占 6 个 context（29/40 → 可降到 23/40）。skill 2026-08-08 教训(4) 未落地。
- resoLsrA 缺失自动全绿：`not lsrCrowdingRiskA` 在 LSR na 时=true → 建议 `not na(lsrA) and not lsrCrowdingRiskA`，缺失标 ✗LSR缺。

## 基线对照（2026-08-08 → 2026-08-09）
- 主：3033→3065→3078 行；plot 最坏 51→55/64（口径：series 色含 input.color 变量名/三元计 2）
- 副：656→686→689 行；plot 最坏 53/64
- 本次修复 0 plot 新增；alertcondition 0 / alert() 2（事件化）不变
