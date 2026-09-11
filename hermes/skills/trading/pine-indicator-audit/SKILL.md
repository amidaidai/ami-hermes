---
name: pine-indicator-audit
description: "Audit/optimize Pine main/sub indicators: correctness, quotas, panels, contracts, client verification."
---

## 核心参考

- 人工决策：`references/pine-manual-decision-dashboard-contract.md`
- 双指标合同：`references/pine-dual-indicator-audit-contracts.md`
- 多市场合同：`references/pine-dual-indicator-multi-market-contracts-20260825.md`
- Basic总线/CE10117：`references/pine-basic-packed-bus-ce10117-20260825.md`
- 免费版路由：`references/pine-free-tier-dual-indicator-routing-and-decision-closure-20260826.md`
- 紧凑主表/副表固定六行：`references/pine-dual-indicator-compact-panels-20260826.md`
- 表格去重、Packed Bus `na` 防护、同级双边 WAIT、信号年龄：`references/pine-dual-indicator-table-and-bus-integrity-20260827.md`
- **主指标路径状态机**（阶段、触发优先级、X优先、路径行与验收）：`references/pine-execution-path-state-machine-20260827.md`
- **路径闭环与执行/观察价格原子隔离**（最近完成→唯一下一步、WAIT/X清空执行字段、B/C只入观察字段）：`references/pine-path-closure-and-atomic-price-contract-20260827.md`
- **行动格决策语义压缩与白话化（当前权威）**（现位保留方向/不追/角色位→MSS/时间链；流向改短线/近期/前周期专业白话）：`references/pine-panel-decision-language-contract-20260827.md`
- 编译端点/跨锚：`references/pine-20260814-cross-anchor-and-compile-endpoint.md`
- request 语义与全量编译：`references/pine-20260814-request-semantics-and-audit.md`
- 2026-09-01 双指标现场审计增量 → `references/dual-indicator-live-audit-findings-20260901.md`
- **客户端 CE10117、源码读回哈希、Basic 双脚本身份与最终证据链** → `references/pine-client-compile-evidence-and-dual-deploy-20260901.md`

- **单边位失效**：破位、swept、生命周期 → `references/pine-20260812-trending-market-key-level-audit.md`
- **结构叙事须图上可核验**：HH/HL/LH/LL真定义、BOS/CHoCH活动标签、异步CE10117验收 → `references/pine-structure-visibility-and-semantic-contract.md`
- **CE10116先扫原文件** → `references/pine-20260810-ce10116-refactor.md`
- **市场判定必须用 ticker 字符串，不能只用 syminfo.type**：TV 上 BINANCE:XAUUSDT.P 的 syminfo.type=='crypto'，副指标曾因此把 XAU 当加密走 5 所聚合（覆盖率恒 1/5 + 误开订单流估算），而主指标 autoMetal 用 XAU/XAG/GOLD/SILVER/GC/SI 字符串检测判贵金属——主副"市场身份"打架。审计双指标时逐行核对市场判定源，主副必须同源。
- **锚定一致性要建 market×timeframe 矩阵逐格核对**：CVD 锚定常缺市场维度（纯按周期秒数映射），而 S VWAP/SVP 有市场分支（metal/forex/stock 4h+→W vs crypto 4h+→M）；1d+ 图 SVP=12M vs CVD/VWAP=M 分叉且注释常自称"一致"。审计"锚定"时输出矩阵表（场景×SVP/S VWAP/CVD/副CVD），逐格标 ✓/✗，注释与实现不符也计 ✗。
- **免费档 2026（2026-08 官方复核）**：64 plot counts 含 Data Window-only；`request.*()` 40（Ultimate 64）；intrabar 100K。`request.footprint()` 仅 Premium/Ultimate，且是 intrabar 分类量、非交易所原生逐笔。详见 references/2026-ecosystem-and-quota.md。
- **静态扫描只做初筛**：脚本应区分 const/input/simple/series 色；不能把所有颜色变量或 `color.xxx` 常量都按 series 计。DW-only 仍计；table=0；bg/barcolor=1；fill 仅 series 色=1。临界值以 TV 编译器报数/逐行注释差值为准。
- **2026 社区共识已内嵌**：CVD 背离必须 confluence（关键位 + 摆动>1.5ATR + 吸收/派发区分），纯 divergence 无 standalone edge（GitHub SoCloseSociety/TradeBobbyTerminal bed5b8b 实测）。

## Purpose

Audit and optimize the user's two TradingView Pine Script indicators. Do not use old assumptions that the main indicator lacks FVG or that MCP Data Window exports were removed.

For decision-assistance upgrades, load `references/dual-indicator-decision-assistance-enhancement-blueprint-2026-08-08.md`; for necessity audits, also load `references/dual-indicator-enhancement-necessity-audit-20260822.md` and `references/community-validated-enhancement-triage-2026-08-22.md`.

When an audit advances into implementation, load `references/pine-decision-integrity-repair-and-verification.md`. It defines the dependency order, SVP compute/render separation, unified sweep state machine, final Entry/Stop/Target protocol, CVD quality gating, non-crypto HALDRO invalidation, and semantic regression checks. Use `references/svp-decision-integrity-audit-patterns-2026-07-19.md` for the matching audit signatures. For adversarial vNext main-indicator audits, also load `references/svp-vnext-adversarial-decision-closure-2026-07-19.md`; it covers hard-risk bypasses, multi-sweep price aliasing, nPOC mode parity, raw-CVD bypasses, atomic FVG/Magnet selection, tick-range coverage, and static-vs-server verification boundaries. For historical-POC mismatches or an action panel that only says “等触发”, load `references/npoc-semantics-state-official-alignment.md`; it covers current POC/pPOC/nPOC semantics, the full physical-removal route when nPOC is rejected, tick-aligned rows, official Periodic VP precision mappings, and scenario-routed `等触发（路径）` states.

**20260810 审计+修复+行动格优化（主 SVP_ICT_v2+副 AggVol_v2）**：见 `references/pine-20260810-full-audit-fixes.md`（含 patch 事故两形态铁律、10行化/位三态/路径闸门一致性模式）。
**20260810 回踩位路径绑定**：等回踩不知道回踩哪里/路径不扎实的修复配方，**后续迭代**：进场×看位去重（进场行=触发链、看位行=位+动作）、行宽治理（KZ倒计时放确认行/波动率放结构行/方向行砍pdShort）、方向行置信度>分数四数字（类型词保留）、KZ 倒计时须 `time_close("D")`、删 input 勿删可见外观参数（副指标零线参数化见修改13）。见 `references/svp-pullback-path-binding-2026-08-10.md`。
**20260810 评分口径**：市场适配分/辅助决策分打分维度表，见 `references/indicator-scoring-rubric-2026-08-10.md`。
**20260810 双指标评分制（市场适配分/辅助决策分）**：市场适配分五维（识别20/自适应25/护栏25/锚定20/SMT10）+ 辅助决策分四维（该不该动40/多远20/多久了20/完整20），基线主92/副85、主84/副78 与 P0→P3 排序，见 `references/dual-indicator-scoring-rubrics-2026-08-10.md`。
**20260809 第三方监测报告核验 + P1 修复教训（主 SVP_ICT_v2 + 副 AggVol_v2，9 处修复）：** 详细核验表与修复模式见 `references/pine-20260809-third-party-report-verification.md`。
(1) **核验第三方 AI 审计报告：逐条落代码证据，不盲信**。外部报告 2 个 P0 全为误报/降级：①「免费档 plot 上限 40」是错的——官方上限 64（所有档位，v5+；40 是 v4 时代旧限制），报告把免费档「0 技术告警/5000 bar」等其他限制混进来了；②「request.security_lower_tf 在局部作用域需验证」——基线已实机编译过的位置，降级为预算注意项（request 条件 false 也照常执行，degrade 只省赋值，100K intrabar 预算内即可）。核验流程：每个声称的 bug → grep 对应行 → 确认分支/条件是否真被拦截 → 分「属实/误报/部分属实」三档，属实才修。
(2) **字符串分支顺序陷阱**（P1 真实 bug）：失效价映射 `str.contains(invalidText,"扫") and str.contains(invalidText,"低") ? ictEventPrice : invalidText == "跌回扫低" ? curVal : ...`——「跌回扫低」同时含「扫」+「低」，contains 分支恒先拦截 → 特判分支死代码 → 双向扫当根失效价=na → priceGeometryOk=false 误杀 A/B 计划。修法：**特判（精确 ==）必须放在 contains（模糊）分支之前**。通用审计点：模糊匹配在前会吞掉所有子串命中的精确分支。
(3) **input.source 接线检测**（P1 真实 bug）：`input.source(close)` 未接线时返回默认 close，价格恒>0 → OI 行显示「▲ 新多 65000.00% ✓一致」假数据。修法：`bool wired = sourcetostring(src) != "close"`——sourcetostring 对未接线 input.source 返回 "close"，对接线返回「指标名: 序列名」。用 wired 区分「未接线 / 接线但 na（如非加密无 OI）」两种文案，杜绝假数据与误报。
(4) **var 首根固化 + table 位置无 setter**（P1）：`var string _posSel = ...` + `var table actionPanel = table.new(_posSel, ...)` → 改位置输入不生效。修法：位置字符串去 var（每根重算）+ `var string _posSelPrev = ""` + `if barstate.isfirst or _posSel != _posSelPrev` 时 `actionPanel := table.new(...)` 重建。
(5) **回放模式 timenow 陷阱**（P2）：`time >= timenow - window` 在 replay 下 timenow 是真实时间 → 回放点所有连线消失。修法：`barstate.isreplay ? true : ...`。
(6) **跨所现货代理后缀**（P2）：spot 代理只 `str.replace(tickerid, ".P", "")` 漏 Coinbase `-PERP` 风格 → 基差恒 0。修法：双层 replace（.P 与 -PERP），无效替换由 ignore_invalid_symbol 兜底为 na。
(7) **patch 工具行尾混用**：patch 会把 \n 行转成 \r\n 造成混用；修完统一行尾（sed -i 's/\r$//' 转 LF 或反之），并复检：plot 计数未增、括号配平（剥离字符串/注释后逐对）、修复点 grep 验证。
(8) 未修决策点：主指标 L918-931 死会话 CVD 链（cvdAsiaSlope/cvdLondonSlope/cvdNYSlope 零消费，6 变量+1 死输入 SHOW_SESSION_CVD）——接回行动格 CVD 行或整删，等用户拍板（20260807 精简只删了消费端）。

**2026-08-09 交付前铁律（Pine 行尾 + 外部报告核验 + 通用陷阱）：**
1. **Pine 源文件必须 LF 行尾**。CRLF（Windows 上传/记事本保存）会让 TV 编译器对行尾运算符续行（跨行三元的 `?`/`:` 结尾行）报 CE10156 "end of line without line continuation"——报错与逻辑无关，纯换行符问题。Hermes patch 工具改写文件时可能把全文件转成 CRLF（含未改行），**每次 patch 后、交付前必须检查行尾**；混用或含 `\r` 一律 `sed -i 's/\r$//'` 转 LF 并复核。跑 `scripts/check_line_endings.py`。
2. **外部审计/监测报告必须逐条落到代码行号核验，不盲信**。2026-08-09 实测：第三方报告 P0-1「免费档 plot 上限 40」是误报——官方 plot 上限 64（所有档位通用），免费档真实硬限制是 5000 历史 bar / 2 指标/图 / 0 技术告警 / 3 价格告警 / 20s 计算 / 100K intrabar / 40 request.security / 64 plot。「数据窗 plot 可合并打包」类建议不要接——破坏 MCP Data Window 解包兼容。
3. **Pine 通用陷阱（本会话实证，详细见 references/pine-crlf-line-endings-and-audit-pitfalls-2026-08-09.md）**：
   - `input.source(close)` 未接线时值是 close（价格恒>0）→ 产生假数据（如 OI 行「▲ 新多 65000.00% ✓一致」）。接线检测：`bool wired = sourcetostring(src) != "close"`，未接显示占位文案。
   - `str.contains(t, "扫") and str.contains(t, "低")` 会拦截更具体的 `t == "跌回扫低"`（两者都含扫+低）→ 该分支成死代码且双向扫当根取值=na。**模糊 contains 分支必须排在精确相等判断之后**。
   - `var string pos = <input 派生三元>` 首根固化 + table 位置无 setter → 改输入不生效。修法：去掉 var + `var table t = na` + `if barstate.isfirst or pos != posPrev` 时 `t := table.new(...)` 重建。
   - `barstate.isreplay` 回放模式下 `timenow` 是真实时间 → 用 timenow 过滤近端连线的逻辑在回放时全部消失；改 `barstate.isreplay ? true : ...`。
   - Coinbase 永续后缀 `-PERP` 不会被 `str.replace(ticker, ".P", "")` 覆盖 → spotTicker 基差恒 0；双替换 `str.replace(str.replace(t, ".P", ""), "-PERP", "")`。

**v2 增强实施教训（2026-08-06 晚）：** (1) `str.tostring(time, format.timestamp)` 在 v6 报 CE10272 Undeclared identifier → 用 `str.tostring(time, "yyyy-MM-dd HH:mm")` 自定义格式。

**2026-08-09 双指标审计修复 + CE10156 排雷教训：**
(1) **CE10156 "end of line without line continuation" 三连报**：TV 编译报 CE10156 + CE10271(Could not find function) + CE10272(Undeclared identifier) 时，后两个几乎必是连带误报——先修语法错误，别去查官方 API。真实案例：`sourcetostring`/`barstate.isreplay` 都是 v6 标准 API，报错元凶是跨行三元。
(2) **Pine v6 行尾续行规则**：只保证行尾 `\`、括号内换行、开放括号/逗号/二元运算符结尾续行；**三元运算符 `?`/`:` 行尾续行不可靠**（Pineify 2026 证实 v6 支持面），跨行三元链（行尾 `:` 下一行继续）在部分 TV 环境报 CE10156。修复 = 机械合并为单行，用 `scripts/merge_multiline_pine.py`（注意：合并脚本内层循环正常 break 后必须 `i = j`（j 已 +1），否则已合并行重复输出）。
(3) **CRLF 行尾是 CE10156 高发元凶**：TV 编译器对 `\r` 残留敏感，行尾运算符续行在 CRLF 下必报错。任何交给 TV 的 .pine 必须纯 LF 无 BOM。上传/修复文件先 `sed -i 's/\r$//'` + 字节检查（`b'\r' not in data`）。
(4) 已验证修复模式（2026-08-09 落地于 SVP_ICT_v2/AggVol_v2）：input.source 未接线检测用 `sourcetostring(src) != "close"`（默认 close 恒>0 会造假数据）；回放模式连线用 `barstate.isreplay ? true : time >= timenow - window`；table 位置输入生效 = 去 var + `if barstate.isfirst or _posSel != _posSelPrev` 重建；str.contains 特判分支必须排在通用 contains 分支之前（"跌回扫低"同时含"扫"+"低"被前置拦截的经典坑）。 (2) `timestamp(timeframe.period, time, 0)` 参数不匹配（CE10265）→ 当前 K 时间直接用 `time / 60000`（毫秒→分钟）。 (3) `if` 块内 tuple 解构到外层 var 变量触发 shadowing 警告 → 用局部名接收再 `:=` 回外层。 (4) `plot` 不能画 string 类型 → 字符串日志用 `label` 显示、Data Window 只导数值。 (5) 新品种方向引用 setup 系列（setupLongA 等在 2400 行后）必须放在 setupX 定义之后，否则前向引用。 (6) ticker 比较用 `ticker.standard()`。 (7) 事件窗口实现：3 事件位（名称+时间输入），`timestamp(tt)` 解析 "YYYY-MM-DD HH:MM"，T-4h~T+1h 窗口并入 setupX 硬闸门，行动格显示倒计时；BTC 大盘风向 +1 request.security("60")，非自身品种才请求，逆势降级；基差极端（basisEma>0.10 禁追多 / <-0.05 禁追空）并入 setupX。

**Audit lessons (2026-08-06):** (1) 副指标 AggVol 20260806 版新增共振度行时引入 P0 前向引用——`color resoColA = ... cGood/cWarn/cBad`（L447）引用 L494-496 才定义的配色块，Pine 自上而下编译必报 `Undeclared identifier`。修复=把配色块（pnlLight/cLabel/cVal/cGood/cBad/cWarn）整块上移到共振度块之前。教训：**新增行引用既有色值时，先确认色值定义行号在引用行之前**；pine_static_scan.py 只查面板三变量，抓不到这种前向引用，必须用 TV 服务器编译（pine-facade translate_light，curl 即可，无需 CDP）实测。 (2) 免费档性能：`EXlist.sum()` 在 for 循环内每 K 重复求和 → 提出循环存常量；`FX_CONV_RATE` 在 USD 默认路径短路为常量 1.0 省 1 个 request.security。 (3) `ta.ema` 等状态函数放三元/条件作用域内会触发官方警告 "should be called on each calculation" → 先无条件算 `basisEmaRaw` 再按条件取用。 (4) 主指标 CVD 行动格行按用户口径去掉 `(估算)` 字样（诚实口径保留在 MCP CVD Method Code 与源码注释）。

**Audit lessons (2026-08-08)：** (1) SVP 主指标继续堆功能前先函数化主执行体（FVG/OB/LV 维护循环、磁吸扫描、行动格构建）；源码字符或历史 token 估算不能证明当前 IL 是否超限，最终只认 TV 服务器编译。 (2) AggVol plot 槽位偏紧时，零线优先用不占 plot count 的可行实现，EX 堆叠 series-color 在不需要模式下应短路；实际计数以 TV 编译为准。 (3) `ta.*` 只有在条件作用域导致并非每K执行时才标 CW10002；三元仅位于函数参数内部、而 `ta.rma()` 本身每K无条件执行时不要误报。 (4) 副指标 OI/LSR/基差请求在非加密品种上仍会预取，应包进 `isCryptoA` 门控以节省 unique context。 (5) 行动格「位置行」把价在VA/ADR余量/就绪度拼成一行会撑宽表格，应拆ADR/就绪到独立行或删除重复信息。 (6) MCP Side 必须让 X 优先于残留 A/B/C 原始方向；X 时执行价格原子清空。 (7) 人工 B/C 候选的界面显示权与 MCP 导出权必须拆开，不能让低于最低 R:R 的候选与 NoTrade 同时导出。 (8) 副指标 OI 空向票必须遵循四象限：价跌+OI涨是新空扩仓；正式评分、共振行、Composite 与告警不得一处用 OI涨、一处用 OI跌。 (9) `barssince(not na(value))` 只能证明非空，不能证明 venue 数据更新；freshness 应按值/源时间变化年龄实现。 (10) 决策辅助增强不应继续堆因子，而应加「就绪度仪表 + 触发路径 + 动作语义 + 主副指标冲突裁决」四件套；具体条目与优先级见 `references/dual-indicator-20-enhancements-2026-08-08.md`。 (11) 用户问"还差什么功能/指标"时，答案分三层：宏观事件层、跨资产联动层、实时执行/复盘层；先补财经日历 overlay、跨资产相关性矩阵、波动率状态机。

**Audit lessons (2026-08-09)：** (1) 判定 input.active 灰化落地不能 grep `input.active`——Pine 写作 `active=SHOW_ADVANCED`（参数名不带 input. 前缀）。用 `grep -n "active=" 主指标.pine`；主指标已对 15+ 高级输入灰化（L218-246，20260809 新增，含 DMI/风控/CVD 微调）。 (2) bgcolor 静态计数陷阱：`box.new(... bgcolor=...)` 的 box 参数不是 `bgcolor()` 函数调用、不计 plot count。正则只匹配 `bgcolor\s*\(`，否则会把主指标真实的 1 个 bgcolor 数成 4（box 的 bgcolor= 全被误算）。 (3) 链式死代码粗扫盲区：「声明1次且引用≤1」只抓叶子；`cvdAsiaAcc`（定义+累加+喂死 Slope）3 处引用但整链死。**任何变量 3 处引用+下游零消费 = 链死**。主指标 L918-931 会话 CVD 链（cvdAsiaBar→Acc→Slope + SHOW_SESSION_CVD 输入）每 K 白算 14 行——20260807 精简删消费端、计算链残留，2026-08-09 审计仍在（每次审计必重 grep cvdAsiaAcc/cvdAsiaSlope）。修法：接回「亚主/伦主/纽主」到 CVD 行（用户偏好）或整条删。 (4) 缺失数据"全绿"陷阱（副指标共振行）：`resoLsrA = not lsrCrowdingRiskA` 在 LSR 为 na 时恒 true → 缺失显示为健康。修法 `not na(lsrA) and not lsrCrowdingRiskA`，缺失标 `✗LSR缺`。审计任何"健康度/数据项"行必须检查缺失（na）路径是否被当成通过，不能只看拥挤方向。 (5) Freshness Pack 语义（副 L465-467）：`barssince(not valid)` = 自上次失效以来的K数，**健康时恒 999**（从未失效），不是数据年龄——解码端别把 999 当"很旧"。掉线兜底靠 sourceDropoutA（EMA 基准+连续3根缺失），两者互补；"所有所返回停滞旧值"盲区仍在（下一步改值变化年龄）。 (6) 删除回退请求后必须同步更新配额总注释：L305 删 USDC.P_OI 回退（4 所×2→4 context）后 L302 注释仍写 32/40，实际 29/40。审计时核对注释里的配额数字 vs 实际展开。 (7) MCP pine_check 传大源码会灌爆上下文：主指标 202KB≈86K tokens 直接传 source 参数不可行；优先本地文件脚本（tv_pine_check_files.mjs）或让用户 TV 实机 Add to chart 拿回执。CDP 未连时如实标「静态未发现 P0」，不写"编译通过"。 (8) 非加密门控仍未落地（2026-08-08 教训(4) 复验）：f_oi×4/lsrA/spotCloseA 无条件预取，XAU 图白占 6 个 context（默认 29/40，注释误写 32）；修法 `isCryptoA ? f_oi(ex) : na`。 (9) HTF FVG/OB 外层 lookahead_off（L1993/1994）+ 函数内 [1]/[3] 确认偏移 = 合法但发布延迟 1 根 HTF 末尾，改 lookahead_on 视觉提前（与 f_htf_trend pack 一致）。 (10) 位置行三合一（posText+adrRoomText+rdyGauge）仍是行动格最宽行——2026-08-08 教训(5) 未落地，下次改版处理。 (11) 20260809 已确认落地：CVD 锚定双指标同步（主 L751 与副 L37 同口径 <1h→D / 1h-4h→W / ≥4h→M）、input.active 灰化、executablePlan rrHardOk、MCP Side X 优先+价格清空、alert() 边沿事件化全部正确——审计别再当未知项重查，直接引用为基线。联网核验 4 条：TV 官方 Visuals/Plots 确认 series color（含 input.color）计 2、SO 佐证；TV 官方 Inputs 文档 input.active；flowly 2026 指南 footprint 仅 Premium；equiti/tradingsim/tradedevils HVN=磁吸/LVN=快速穿越共识。完整会话见 `references/dual-indicator-audit-2026-08-09.md`。

**Audit lessons (2026-08-02):** (1) 行动格 CVD 行回归——`actionCvdText` 赋值多处但表格无消费行时，订单流状态+基差标签全部白算；审计必须核对每个 f_pnl_row 消费端与所有 *_Text 变量。加回一行 `f_pnl_row("CVD", actionCvdText, ...)` 即可恢复。 (2) 时间锚——`ta.change(time("D"))` 是交易所时区日界（加密=UTC日=北京08:00），`dayofweek(time, DISP_TZ)` 星期名用显示时区；默认 DISP_TZ 若为北京时间会与加密 UTC 日界差 8 小时、与 COMEX 美东日界差 13 小时，导致池标签星期错标。默认应"跟随交易所"与日界同源。日/周池与 SVP D/W 锚天然同源（time("D")=D 锚），无需额外对齐；真正要防的是时区输入默认值。 (3) 死代码删除前必须查共享消费链（如 longPlanPrice 被 bcLongPlanPrice 消费、cvdAsiaAcc 被 cvdAsiaSlope 消费），只删叶子变量+唯一消费者函数（f_tf_label/f_fmt_cvd）。删除后全量 grep 残留。

**批量改脚本铁律（2026-08-02 教训，一次会话连踩三次）**：混用 `rm_line`（按行列表 pop）+ `sub`（按字符串 replace）时，rm_line 必须把 pop 后的列表**写回文件**，否则 sub 生效、rm 落空 → 文件编译必错。正确姿势：全部用字符串 `sub` 整块替换（含换行），或 rm 后立即 `open(path,'w').write('\n'.join(lines))`。改完必须全量 grep 残留（排除 options 数组里的合法交易所名，那不算死代码）。

**更隐蔽的坑：`sub` 脚本中间 `assert` 失败会丢弃前面所有已成功的替换。** 典型写法是「读文件→逐个 `sub`（每个带 `assert cnt==1`）→最后写盘」。若第 8 个 `sub` 的 old 字符串因换行符/实际内容差异匹配 0 次 → assert 抛异常 → **前 7 个成功的 `sub` 从未写盘** → 磁盘文件停在第一段状态（比如输入区改了、GetExchange 体没改），表现为「部分改动生效、部分丢失」的编译必错混合态。本会话这种 assert 中途炸掉、改丢失的情况出现了两次（第 8 项 EX 恢复、OI 恢复各一次）。**每次炸掉后磁盘是旧态，下一段从磁盘重读，不是从内存 src 续跑。**

**根治：两阶段「先全部验证、再统一应用」**——第一阶段循环里只 `assert src.count(old)==1`，任何一项失败就整批不动、打印所有失败项；全部通过才进第二阶段逐个 `src.replace(old,new,1)` 并 `open(path,'w')` 写盘。这样要么全改要么全不改，永不产生半改文件：
```python
pairs = [("label", old_str, new_str), ...]
fails = [lbl for lbl,o,n in pairs if src.count(o) != 1]
if fails:
    print("❌ 不执行:", fails)   # 先看实际文件文本，改 old 再重试
else:
    for lbl,o,n in pairs: src = src.replace(o,n,1)
    open(path,'w',encoding='utf-8').write(src)  # 一次性写盘
```
验证用旧文本残留扫描，别用「新文本存在」反推（`EXv4 = EXv3` 存在不等于 EX 4/5 全链恢复——要逐项核对输入/函数体/解构/求和/计数/plot/OI 全消费链，本会话 5 所恢复要 13 项全绿才算完整）。

**CE10295「main body of the script is too long」（2026-08-02 主指标 2957 行触发）**：脚本**主体 IL 超限**的编译期错误，官方解法就是包函数（函数体只编译一次，调用点只留调用指令）。Pine 三个硬约束：(1) 函数**不能改全局变量**，只能读全局、用局部变量累加、返回 tuple、调用处 `[g1,...]=f()` 赋回；(2) 元组上限 **16 值**；(3) 历史引用如 `resPrice[1]` 依赖全局赋值的 series 语义，函数返回赋值**不破坏**，可安全函数化。选块标准：无绘图副作用、无 `var` 持久、无 `barstate.islast`、纯计算读全局。实测把关键位矩阵(64行)/扫线扫描(36行)/评分累加(48行)三个纯计算块函数化，148 行主体 → 3 函数+3 调用，静态扫描全绿。**CE10295 是编译期错误，静态扫描测不到**，必须让用户贴回 TV 实测。若还报，下一个候选是行动格文本构建块(约90行)+磁吸扫描块。完整配方见 `references/pine-ce10295-functionization.md`。

**Current production preference:** For free/Basic performance or quota changes, load `references/free-tier-pine-optimization-playbook.md`. Basic cannot create technical alerts; any `alert()` eventization guidance applies only to a separately maintained paid/upgrade-compatible alert build, never as a Basic workaround. In that paid build, retain two critical pitfalls: (1) never gate `alert()` with `barstate.islast` (it only fires on the realtime bar; islast swallows closed-bar confirms so the alert never fires), and (2) when OR-combining many conditions wrap the whole group in parens (`and` binds tighter than `or`, so unparenthesized trailing branches silently bypass the `alertOkA and haldroUsableA` guard and fire on non-crypto). Also strip `//`, `/* */`, `"..."`, `'...'` before counting bracket balance — Chinese punctuation in Pine comments/strings makes raw `(`/`)` counts report false "unbalanced". Physically delete `pPOC`; keep time-limited `nPOC` levels whose quantity and appearance are user-adjustable. Each nPOC must begin at the right edge of its completed SVP POC (`endBar`) and extend right from that original point—never slide `x1` forward. Default style is dashed. While untouched, advance `x2`; on touch, freeze `x2` at the touch bar and reuse ICT hiding/fading behavior. Expired or over-limit objects are deleted. Only unswept, unexpired nPOCs may feed support/resistance, Magnet, key-level routing, events and the price axis. B/C grades may display an explicit `B/C人工` Entry/Stop/Target candidate for the user’s discretionary judgment even when not promoted to A-grade execution; X/no-trade remains a hard block and must never export executable MCP prices. The action-panel entry row must show `等触发（具体路径）` before Entry/Stop/Target geometry exists.

For mature dual-indicator upgrades, also load `references/dual-indicator-execution-state-oi-consensus.md`. It defines Entry Valid/No-Trade/Trigger contracts, trigger freshness, price-pivot-anchored CVD, cross-exchange OI agreement/dispersion, freshness risk bits, shadow regime fields, plot-budget discipline, and the external `GO-A / GO-B / WAIT / NO-GO` validator. User-facing order-flow wording must stay direct: retain `爆仓` (`空头爆仓偏强 / 多头爆仓偏强 / 无明显爆仓`); do not rename it to literary abstractions such as `杠杆失衡代理`. Technical comments may still disclose that the Pine value is a proxy rather than an exchange liquidation feed.

When the user asks for a broad, multi-dimensional, web-researched audit with "10 optimization suggestions / recommended enhancements / what else is missing / how to help decision-making" and explicitly forbids backtesting/replay, load `references/dual-indicator-20-enhancements-2026-08-08.md`. It contains a decision-oriented 20-item enhancement roadmap (6 panel/execution + 3 cross-indicator verdict + 4 ICT/SMC + 4 data/performance + 3 visualization/new-data) plus community evidence, priority phases, and links to the relevant reference files. Use it to answer directly: which 3 items deliver the fastest decision-quality improvement, and which items are blocked by free/Premium tiers.

## 指标本身的官方＋社区横向研究（2026-08-08增量）

用户要求研究 Pine/SVP/Footprint/CVD/OI/ICT-SMC 且明确“不要回测、不要复盘”时，读取 `references/indicator-only-evidence-benchmark-2026-08-08.md`。若任务进一步要求“先读当前源码→做2025–2026社区横向对标→筛真缺失候选并剔除重复/低价值项”，同时读取 `references/source-gap-community-candidate-filter-2026-08-08.md`；该文件记录四分类裁决法、P/R/O成本口径、iFVG/EQH-EQL/HVN-LVN/前日VP/BPR/OB增强边界、winning-zone原子合同，以及 MB标签、重复评分、LV/CVD重复等排除规则。该证据库补充了：

- 当前 `request.footprint(ticks_per_row, va_percent, imbalance_percent)` 三参数签名、Premium/Ultimate与单请求限制；
- 官方营销博客“exact ask/bid”与当前技术文档“按intrabar价格行为分类”的冲突裁决；
- Footprint内建图表因实时/历史intrabar粒度变化而“repainting by design”的准确适用边界；
- 2026-04 UDT字段排序与2026-08 UDT数组二分查找；只有Profiler证明大型候选数组的线性扫描是热点时才实施；
- Basic 2指标/5K历史K/20秒/0技术告警、1条indicator-on-indicator连接，以及用单个 `input.source()`复用副指标裁决plot的边界；
- 动态request运行时context、series参数plot count的现行验收线；
- OI单位、venue agreement/freshness、源码可验证性分级，以及搜索限流后直抓官方深链接的取证路径。

这类报告必须只筛“指标本体”的数据语义、配额、性能、状态机和面板优化；排除盈利、胜率、回测和复盘主张。矩阵至少含：主张、主/副指标、URL、日期、证据等级、源码可验证性、设计含义、禁止误读。

## 官方现行限额（2026年7月10日；覆盖本文历史快照）

以 TradingView Pine v6 官方 `Writing / Limitations` 当前文档为准：

- 单脚本编译后 IL 上限现为 **100,000 tokens**，不是历史 80,000；导入库合计上限 1,000,000 tokens。
- `request.*()` 默认最多 **40 个 unique calls**；Ultimate 方案最多 64。相同函数且参数完全相同的后续调用通常不算 unique。
- `request.footprint()` 每脚本只允许 1 个 unique call，且仅 Premium / Ultimate 可用。
- plot count 仍为 64；`alertcondition()`、`bgcolor()`、使用 series color 的 `fill()` 也计入，`hline()` 不计入。
- 文中所有“80,000 token”“余量仅几十”“~186,400字符触顶”均为 2026年7月9日历史实案，**不得用于当前审计结论**。当前官方明确说明无法查看 IL token 数，源码字符数/行数不能可靠换算；未影响输出的死代码还会被编译器从 IL 中剔除。最终只能以 TradingView 实际编译为准。

官方来源：https://www.tradingview.com/pine-script-docs/writing/limitations/

## 账号档位约束：免费 Basic 是硬天花板（2026-08-02 官方定价页实测）

**所有 request/plot/token 配额之上，账号档位先卡死一批能力。审计前先确认用户账号档位；免费档（Basic）尤其致命：**

- **免费档技术告警 = 0** → `alertcondition()` 在免费账号既不能被运行告警使用、又各占 1 个 plot count，Basic 构建应物理删除。`alert()`虽不以相同方式占多个plot槽，但也**不能绕过Basic账号的零技术告警权限**；免费档实际通知交给外部 Python 扫描管线。若维护付费兼容版，再把多事件合并为一个事件化 `alert()`，不要把它写成免费绕过方案。
- **历史K = 5,000 根**（5m≈17天/15m≈52天/1h≈208天/4h≈833天；D/W≈20年全量）→ 免费档主战 5m/15m/1h/4h，不追求超长历史。
- **指标/图 = 2** → 主+副正好占满，不能加第三个；Footprint 升级只能做独立脚本在 Premium+ 评估。
- **计算时限 = 20s**（付费 40s）→ 主指标 lower-TF 精度全量重算是最大超时风险。
- **免费档性能第一杠杆：lower-TF 请求加 `calc_bars_count`**（不传则按图表全量K拉取 intrabars；5m挂1m=25,000根、4h挂60m=20,000根，爆 20s）。主指标两处 `security_lower_tf`（SVP 精度 + CVD）都要加。**⚠ 但绝不能硬编码 `calc_bars_count=1000`**——SVP 分布图 D 周期需 1440 根 1m intrabar，1000 会截断 30% 数据使 POC/VAH/VAL 算错。必须动态计算 `max(1000, 完整分布图周期所需)`（`profSec/precSec`），见 `references/multi-market-adaptation-crypto-metals-2026-08-02.md`。

完整对照表、免费档优化序列与取证技术（curl --compressed 抓官方文档、browser_console 提取 JS 定价页）见 `references/tradingview-plan-tier-limits-free-account.md`。

## P0: Pine v6 request unique-context 计数铁律（2026-07-21 官方校正）

**当前 Pine v6 按运行时 unique `request.*()` 调用/数据上下文计限，不是简单的源码静态调用点计数。** v6 默认启用 dynamic requests，允许 request 在条件、循环和函数局部作用域内执行，也允许 series symbol/timeframe。普通账户上限40，Ultimate上限64；完全相同函数与参数通常复用。

- 源码 grep 只能定位调用点，不能直接得出 unique contexts。
- 函数内一个动态 `request.security(Ticker, ...)` 若历史执行中访问20个不同 symbol，可能消耗20个 unique contexts；相反，相同参数重复50次通常只算1个。
- v6 lazy evaluation + dynamic requests 下，未执行的三元/条件分支可以不产生相应运行时请求；因此“input开关永远不省配额”不是通用真理。
- 但实时阶段不能首次请求历史阶段从未访问过的新上下文。所有实时所需 symbol/timeframe/expression 必须在历史执行阶段完成预取。
- 库内 request 即使与主脚本参数相同，也可能单独计数，按官方文档审计。

**审计方法**：
1. grep 所有 request 调用点；
2. 展开每个动态 symbol/timeframe 在默认与最坏输入配置下可能访问的不同上下文；
3. 分别报告“默认运行时 unique 数”和“最坏启用配置 unique 数”；
4. 通过 TradingView 服务器编译/运行验证，不把静态正则结果写成最终配额结论。

**腾配额优先级**：删除无消费请求 → 默认路径短路无关请求（如USD模式不取汇率）→ 去重交易所/币对 → 合并相同上下文 tuple → 拆分脚本。

**非加密品种请求短路（2026-08-08）**：副指标 OI/LSR/基差请求在非加密图表上仍会被历史阶段预取，浪费 unique context。应把 `f_oi()`、`lsrA`、`basisPctA` 等请求包进 `isCryptoA` 门控函数：
```pine
f_oi_safe(string ex) => isCryptoA ? f_oi(ex) : na
```
默认路径下非加密品种的 unique request 数可从 8 降到 2（汇率 + 图表自身）。

官方来源：
- https://www.tradingview.com/pine-script-docs/writing/limitations/#number-of-calls
- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#dynamic-requests

## Pine 编译顺序铁律

**Pine 是自上而下编译，变量必须先定义后引用。** 有两层严重度：

1. **def-before-use 顺序错**：变量存在但声明在使用之后 → 运行时 na 或编译警告
2. **未定义变量引用**（更严重）：变量在表达式中被引用但全文无声明/赋值 → `Undeclared identifier 'X'` → 指标完全无法加载

常见陷阱：panelDirVal 定义在 pdZone 之前，却引用 pdZone → 编译失败。
**修法**：把被引用的变量定义移到引用者之前。

**未定义变量检查**（2026-07-09 实案）：`cvdBearStars`/`cvdBullStars` 在 L2126 被引用但全文零声明 → 致命编译错误。详见 `references/pine-undefined-identifier-audit-2026-07-09.md`。

检证命令：
```bash
grep -n "string pdZone\|string panelDirVal" 主指标.txt
# 输出必须 pdZone 行号 < panelDirVal 行号

# 未定义变量检查：对每个被引用变量，确认有声明
grep -c "VARNAME" 主指标.txt      # 引用次数
grep -c "VARNAME\s*=" 主指标.txt   # 声明次数；=0 → 致命
```

## 重绘安全验证（2026 社区 #1 质量标准，每次必查）

**`request.security(..., lookahead=barmerge.lookahead_on)` 配合已收柱偏移 `[1]`/`[3]` 是正确的非重绘写法，绝不可标 P0。** 只有 `lookahead_on` 不带历史偏移、直接取 HTF 当前未收柱才是未来函数泄漏。

审计时确认三点（任一缺失才是问题）：
- HTF-FVG / ADR 等 HTF 取值用 `lookahead_on + [1]/[[3]` → 非重绘 ✓
- 扫线/FVG/等级识别由 `barstate.isconfirmed` 门控 → 不在 K 内反复变 ✓
- 扫线判定含 `closeReclaim`（收盘回线内=真扫拒绝），非仅 wick 触碰 ✓

**HTF 发布时序检查（2026-07-21）**：先检查 expression 内是否已使用确认偏移，再判断外层 lookahead。当前 `f_htf_fvg()` 使用 `[1]/[3]`，`f_htf_ob()` 的结构突破使用 `close[1]/[2]`，属于确认数据。若外层仍为 `lookahead_off`，主要缺陷是确认结果可能额外延迟到下一根 HTF 末尾，不应误标为未来泄漏；改为 `lookahead_on` 可按官方模式在新 HTF 开始时发布上一根确认结果。消费端 `barstate.isconfirmed` 只确认图表K，不替代 HTF expression 的历史偏移。

检证：
```bash
grep -n "lookahead\|barstate.isconfirmed\|closeReclaim" 主指标.txt
```

**2026-08-08 更新**：`request.security(syminfo.tickerid, fvgHtfRes, f_htf_fvg(), lookahead=barmerge.lookahead_off)` 在 expression 已使用 `[1]/[3]` 确认偏移的情况下，外层 `lookahead_off` 会额外延迟 HTF 确认发布。建议改为 `lookahead=barmerge.lookahead_on`（内部已确认偏移，不会未来泄漏）。

## 告警事件化与快照语义（2026-07-21）

- `alertcondition()` 每个占一个 plot count；`alert()` 不以同样方式消耗独立 alertcondition 槽，并支持动态 message 与显式 `alert.freq_once_per_bar_close`。
- 持续状态不能直接当事件：`finalStrong`、`lowCoverageWarn`、`setupX`、CVD/LSR/OI风险若连续多根为真，会在每根符合频率的实时K重复触发。默认改为进入事件 `state and not state[1]`，或使用带 freshness/trigger-id 的一次性脉冲。
- 保留少量确需在 Create Alert 对话框中独立选择的执行类 `alertcondition()`；信息/风险类优先合并为一个动态 `alert()`，同时释放 plot 预算。
- TradingView 创建运行告警时会保存脚本、inputs、symbol、timeframe 的服务器快照。源码或输入更新后，必须删除并重建已有告警；改图表或脚本不会自动更新旧告警。
- 告警只在 realtime bar 触发。历史图上条件为真不证明运行告警已发出。

官方来源：https://www.tradingview.com/pine-script-docs/concepts/alerts/

## 审计清单（每次必走）

### 0. 程序化静态扫描（先跑 scripts/pine_static_scan.py 再人工细读）
一次性输出：request.security 调用点展开、plot 计数、line/box/label 计数、typed-def 重复、关键变量 def-before-use 顺序、重绘信号。

**陷阱：重复 typed-def 扫描会把函数内局部作用域变量（`i`/`j`/`eFast`/`sec`/`v` 等）报成重复——这是 Pine 合法的，是误报，不是缺陷。** 只有顶层（全局）同名 typed-def 才是真重复。判别：看行号是否落在 `f_xxx() =>` 函数体或 `for` 循环内。

### 0a. TradingView服务器编译（静态扫描后必跑）

优先用 MCP `pine_check(source)`。若宿主机直连 `pine-facade` 报 `fetch failed`，但 TradingView Desktop 的 CDP 已连接，改用浏览器上下文脚本：

```bash
node scripts/tv_pine_check_files.mjs 主指标.txt 副指标.txt
```

该脚本从本地文件读取完整源码，通过 TradingView 页面会话调用 `translate_light`，只返回 errors/warnings，不把20万字符源码灌回对话。输出 `ok:true, status:200, errors:[]` 才算服务器编译通过；warnings必须逐条处理或在报告中明确列出。它不会替代最终“Add/Update on chart”运行态测试。

### 0b. 未定义变量扫描（致命编译错误，人工审查必跑）
**Pine 是自上而下编译，`Undeclared identifier 'X'` 是致命错误，指标完全无法加载。** 常见根因：变量在某行被引用（如三元表达式内），但全文从未声明或赋值。这比 def-before-use 更严重——def-before-use 是顺序问题，未定义是根本不存在。

**检测方法（无需脚本，用 execute_code 快速扫描）**：
```python
# 提取所有被引用的标识符，与所有声明/赋值的标识符交叉比对
import re
code = open('指标文件.txt', encoding='utf-8').read()
# 声明/赋值：var/type/name = ... 或 name := ...
declared = set(re.findall(r'(?:var\s+)?(?:float|int|bool|string|color)\s+(\w+)\s*=', code))
declared |= set(re.findall(r'(\w+)\s*:=', code))
# 引用：变量名出现在表达式中（粗筛，有误报但能抓未定义）
# 关键：找被使用但不在 declared 中的名字
```

**2026-07-09 实案**：主指标 L2126 引用 `cvdBearStars` / `cvdBullStars`（在 `cvdStateText` 赋值的三元表达式内），但全文零声明零赋值 → TradingView 编译 `Undeclared identifier` → 指标无法加载。根因推测：设计了背离星级评分逻辑但只写了消费端没写计算端。**修法**：在 `cvdBearDiv`/`cvdBullDiv` 定义后（如 L974 后）补 `int cvdBearStars = 0` / `int cvdBullStars = 0`，或补完整星级计算。

**审计时必须执行的 grep**（检查未定义变量最常见模式）：
```bash
# 找被引用但 grep 不到声明的变量
grep -n "VARNAME" 指标文件.txt
# 如果只有引用行、没有 "VARNAME =" 或 "VARNAME :=" 声明行 → 致命错误
```

**⚠ 扫描器盲区：静态扫描"未定义变量 none + def-before-use none"不代表 TV 编译通过。** `pine_static_scan.py` 只检查 panelDirVal/panelConclusionVal/panelEntryVal 三变量的依赖，**不覆盖新增行动格行（共振度/就绪度/触发链）引用的共享色值**（如 `cGood/cWarn/cBad`）或辅助变量。2026-08-06 实案：副指标 `color resoColA = ... ? cGood : ...`（引用处）引用配色块 `cGood/cWarn/cBad`（定义在之后）→ 扫描全绿但 TV 编译 `Undeclared identifier`。**新增任何行动格行后，必须手工比对该行每个引用名的声明行号 vs 引用行号**（`grep -n "color cGood\|color cWarn\|color cBad"` 行号必须 < 引用行）。详见「决策就绪度仪表模式」节的前向引用盲区条目。

### 1. 配额检查
- `grep -c "request\\.security"` → 展开计数
- `grep -c "^\\\\s*plot\\\\("` → < 64
- `grep -c "line\\.new\\|box\\.new\\|label\\.new"` → 各 < 500
- **副指标 VAREUR/VARRUB 无条件请求**：grep `VAREUR\\|VARRUB` 副指标.txt，若未用 `coinusd` 条件门控 → 标 P2 配额浪费
- **副指标 plot 槽位估算**：统计 series-color plot 数 × 2 + 常量色 plot 数 + alertcondition + bgcolor + fill(table) + hline，最坏式 ≤ 64。当前 HALDRO ~57/64 偏紧

**快速识别 series-color plot（占 2 个 count）**：源码里 `color=` 右侧出现三元 `?`、颜色变量（如 `VWAP_COLOR`）、或 `color.new(..., 100)` 等动态表达式时，该 plot 计 2。常量 `#hex` 或 `color.green` 计 1。批量扫描脚本：
```python
import re
code = open('指标.pine', encoding='utf-8').read()
for i,l in enumerate(code.splitlines(),1):
    if re.search(r'\bplot\(', l):
        m = re.search(r'color\s*=\s*([^,)]+)', l)
        if m:
            expr = m.group(1).strip()
            is_series = '?' in expr or re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', expr) or 'color.' in expr
            print(f"L{i}: {'SERIES' if is_series else 'CONST'} {l[:100]}")
```
把 series-color 改常量色（如 `#1E88E5`）通常一次能释放 5-8 个 count。

### 2. 代码质量
- [ ] **行动格消费链断裂（P0，2026-08-02 实案）**：显示变量被赋值多次但表格行 `f_pnl_row()`/`table.cell()` 零消费——行动格某行静默消失，连带的 feature 一起白算。审计必须列全表格行消费链：grep 所有 `f_pnl_row(` 调用，把每个表格行标签与它引用的显示变量对齐，逐一确认 `actionCvdText` / `panelDirVal` / `panelConclusionVal` / `panelEntryVal` 等每个 computed 显示变量都至少被一个 table 行消费。只通过编译不算数——`actionCvdText` 编译通过但从未上表，CVD 行从行动格彻底消失。这是"computed-but-unused"的显示端变体，比死代码更隐蔽（计算链看着完整，只是消费端没接线）。**死代码扫描要区分两种**：① 真正零引用的死变量（可删）；② 被计算但不被表格消费的显示变量（需接回表格，不是删）。
- [ ] **时间锚一致性（P1，2026-08-02 实案）**：日/周池用 `ta.change(time("D"))`（交易所时区日界），而星期标签用 `DISP_TZ`（北京）。Binance 加密日界 = UTC 00:00 = 北京 08:00 → 池在北京 08:00 才切换，而非北京 0 点。且高周期不一致：1h 图 SVP 锚=W、4h+ 锚=M，但池永远按 D 滚——两个"日"不是同一个日。**修法**：池锚定跟随 SVP 锚周期（`newDayPool = targetProfileTF=="D" ? isNewPeriod : ta.change(time("D"))!=0`），或加 `POOL_ANCHOR_TZ` 输入用 `time("D","0000-0000",tz)` 切池。审计时 grep 所有 `time("D"/"W"/"M")` 与 `time(targetProfileTF)`，确认日池/SVP/CVD 锚周期同源、时区口径一致。见 `references/svp-action-panel-consumer-chain-audit-2026-08-02.md`。
- [ ] **未定义变量引用**（致命）：变量被引用但全文无声明/赋值 → `Undeclared identifier` 编译失败。2026-07-09 实案：`cvdBearStars`/`cvdBullStars` 在 L2126 被引用但零声明。
- [ ] 死代码：定义但未引用的变量（如 pdZone 在删除引用后仍定义）
- [ ] 变量重复定义：同一变量名定义两次
- [ ] 命名错位：HALDRO 原版 PERP1_*/PERP2_* 命名与后缀不对应（求和正确，勿单独改）
- [ ] 注释与代码不符：tooltip 写"省4配额"但静态计数不省
- [ ] **死风控参数**：`RISK_PER_TRADE_PCT` / `DAILY_MAX_LOSS_PCT` / `WEEKLY_MAX_LOSS_PCT`（L261-263）定义了但全文零引用——用户以为有风控保护实际没有。审计时跑 `grep -n "RISK_PER_TRADE_PCT\\|DAILY_MAX_LOSS_PCT\\|WEEKLY_MAX_LOSS_PCT"` 确认是否仍为死代码；如已写入 Data Window 编码则不算死。
  - [ ] **编译 token 超限**：源码 > ~186,400 字符即可能触顶（80000 tokens）。用 `len(code)/2.33` 快估。削减优先删死变量 → 删空 if/else 链 → 精简面板档位 → 短缩 tooltip。详见上方 §P0b。
- [ ] **tooltip 默认值描述不一致**：`ACTION_PANEL_TRANSP` tooltip 写"默认28"但实际默认50。审计时 grep tooltip 文案中的数字，与 `input.int(默认值,...)` 比对。
- [ ] **narrative card 死代码残留**：`stateText`/`cardLine1-3`/`directionGuideText`/`actionGuideText`/`detailText` 等旧叙事卡变量，被 v2 行动格取代后不再消费。仅 `invalidText`/`watchText` 仍被消费不可删（`invalidText` 驱动止损价推导 L2672-2691，`watchText` 用于面板等待文案）。
  - **安全清理法（2026-07-08 实测，附脚本）**：直接跑 `python scripts/clean_dead_narrative_card.py 主指标.txt`，脚本内置三道护栏——①删除前 grep `table.cell(...VAR)` 确认零消费（有消费则报错退出）；②对 `watchText`/`invalidText` 声明与 `:=` 行强制跳过（误删护栏）；③删除后回扫确认死变量无残留且保留变量仍有声明。手动清理按“变量名 + `:=`”或正则 `^\s*(string\s+VAR\s*=|VAR\s*:=)` 匹配声明与赋值；清理后必须 `grep -c "stateText\|cardLine1\|cardLine2\|cardLine3\|directionGuideText\|actionGuideText\|detailText"` 全为 0，否则残留 `:=` 会直接 Pine 编译失败 `Undeclared identifier`。完整步骤与实测见 `references/haldro-v6-deadcode-cleanup-2026-07-08.md`。
- [ ] **原行动栏保守增强模式**：当用户明确说“原来的行动栏挺好/算了回原版”时，不要再强推 v11 大改。优先在原版上做**零 request、零 plot**的小修：① 修 `gapThrough` 视觉扫线一致性（`touchOrGap = wickPierce or gapThroughLine`）；② 修 tooltip/文案不一致；③ 可用现有变量加一行动态 `解除/等待`，只在 `panelRisk or not executablePlan` 时显示；④ 不加五层固定 MTF、不加 opportunityScore 多 plot、不新增 FVG 框/数组。目标是保住原行动栏手感和编译余量。

### 2b. SVP 行数坍缩检查（小币种/低波幅品种，2026-07-09 实案）

**问题**：小币种 SVP 只显示几行而非完整的 70 行（加密）或 50 行（其他）。

**根因**：`processAndRender` 中桶宽计算：
```pine
float rawStep = priceRange / FINAL_ROWS          // 理想桶宽（70行）
float minStep = syminfo.mintick * finalVpMinTickMult  // 最小桶宽下限（mintick × 20）
float stepSize = math.max(rawStep, minStep)       // 取较大值 ← 问题在这
stepSize := math.min(stepSize, priceRange / 5.0) // 至少5行兜底
```
当小币种日内波幅很小，`priceRange` 小 → `rawStep` 小，但 `minStep = mintick × 20` 是固定下限 → `stepSize` 被 `minStep` 抬高 → 实际行数 = `priceRange / stepSize` 远少于 `FINAL_ROWS` → 只有 5 行。

**举例**：price=0.05, range=0.002, mintick=0.0001 → `minStep=0.002`, `stepSize=0.002`, 行数=1 → 兜底到 5 行。

**修法**：在 `minStep` 定义后插入自适应缩小：
```pine
int minBuckets = math.max(math.floor(FINAL_ROWS / 3), 20)
minStep := math.min(minStep, priceRange / minBuckets)
```
当 `minStep` 会导致行数不足 `minBuckets`（加密 23 行、其他 20 行）时自动缩小。主流币波幅大、`rawStep` 始终 > `minStep`，不受影响。

**审计检查命令**：
```bash
grep -n "minStep\|stepSize\|minBuckets\|FINAL_ROWS" 主指标.txt
# 确认 minStep 有自适应缩小，而非固定 mintick × finalVpMinTickMult
```

### 2c. MCP Data Window 完整性验证（token 削减后必查）

**铁律**：任何为降低 token 而删除代码后，必须确认 `display=display.data_window` 的 plot 一行未动。用户通过 TV MCP `data_get_study_values` 读取这些编码值驱动自动化分析，删错一个 plot 会导致 MCP 读取链断裂。

**检查命令**：
```bash
grep -n "display=display.data_window" 主指标.txt
grep -n "display=display.data_window" 副指标.txt
# 削减前后 plot 名称和数量必须完全一致
```

主指标 Data Window plot 列表（v6+OB/BOS/LV 后 14 个）：MCP Side/Grade/Setup/Entry/Stop/Target/CVD/Quality + FVG CE×2 + FVG Quality + MCP OB Signal + MCP BOS/CHoCH + MCP Liq Void。副指标 17 个（OI/CVD/LSR/Volume Ratio/Coverage×4/Dominance/Confirm/Risk/Flow/Composite）。删除的死变量（`stateText`/`cardLine1-3`/`detailText` 等）不应出现在 Data Window plot 中——若出现则不可删。新增 OB/BOS/LV 功能后 MCP plot 从 11 增至 14，仍远低于 64 上限。

### 3. 颜色可见性（白色主题）
- POC_COLOR #0F0F0F → 白色主题可见 ✓
- 深色值（如 #1A1D23）在白色背景下可见
- 浅色值（如 #F4F5F7）在白色背景下近透明 → 仅作背景色

### 4. 行动格可读性
- [ ] 方向行无重复（如 `偏多 + 顺多` 两个"多"）
- [ ] 每行信息密度适中，不堆砌
- [ ] KillZone/PD/扫位用缩写省空间
- [ ] 均衡区不显示（无增量信息）

### 5. 社区对齐（下单辅助向）
- [ ] CVD 背离标注（价 HH + CVD LH = 卖背离 ⚠）
- [ ] 溢价/折价前置到标准档
- [ ] KillZone 活跃标记前置
- [ ] 扫位计数前置
- [ ] 核对行含位移 ✓/✗

## 双指标协作模式

| 角色 | 主指标 | 副指标 |
|------|--------|--------|
| 功能 | 定位/分级：A/B/C/X + 「风控」行（入/止/标/R:R）+ 磁吸位 | 订单流验证：5所聚合量 + 4所OI + CVD + 覆盖率 |
| CVD | lower_tf子K价格方向估算Delta（粒度较细，仍非真实bid/ask逐笔） | HALDRO影线/实体比例估算（更粗） |
| 适用 | 全市场（加密/金/外汇/股） | 仅加密（`syminfo.type=='crypto'` 门控） |

**生产搭配口径：** AggVol副图默认使用 `Cumulative Delta + Aggregated + USD`。主指标是唯一Entry/Stop/Target与X硬闸门；副指标只作确认，不得把自身信号写成独立开单授权。用户界面统一写 `CVD`，不显示“估算/Estimated”；源码注释/方法码仍须诚实披露其低周期价格行为分类口径，禁止宣传为交易所真实逐笔 bid/ask。主指标行动格不增加“订单流”核对行，也不使用“副驾/副驾驶”。副指标精简行动格保留信号/结论/流向/持仓/风险/操作骨架：流向合并CVD+量能+有效爆仓状态，持仓合并OI四象限+一致率+LSR。

当出现“长期禁追”、磁吸在无计划时全为`--`、社区全面复核或Footprint升级讨论时，必须读取 `references/dual-indicator-panel-rootfix-community-2026-07.md`；其中包含方向化X闸门、磁吸双参考价、同Anchor CVD、告警事件化、逐venue freshness、series-color配额与独立Footprint边界。

**使用铁律**：CVD 背离时以主指标为准，副指标流向只当背景佐证。非加密品种别看副指标。

### 双指标驾驶舱裁决（2026-07-04）

当用户问“能不能依赖这两个指标开单 / 怎么优化驾驶舱 / 怎么适配多市场”时，不要只审计 Pine 本体；必须把两者映射到交易驾驶舱：

- SVP v10 = 主指标：决定结构、方向、关键位、入场、止损、目标、R:R、A/B/C/X。
- HALDRO = 加密副指标：验证 OI、CVD、量能、覆盖率、现货/合约主导、Composite、Confirm Score。
- 黄金/外汇/股票/传统期货不强行套 HALDRO；用各市场对应数据替代副指标。
- 正式加密驾驶舱必须在“多周期定位”前新增“双指标裁决表”，直接说明主副指标共振/冲突/不足与 A/B/C/X 裁决。
- GO/NO-GO 应加入或等价体现 `dual_indicator_conflict`：SVP 与 HALDRO 强冲突时不能输出 A 可执行。

详细协议见 `references/dual-indicator-cockpit-verdict-protocol-2026-07-04.md`。

## 静态扫描 def-before-use（2026年7月10日已修复）

`pine_static_scan.py` 已由历史的线性 `ORDER_CHAIN` 改为真实依赖图 `ORDER_DEPS`：只检查 `panelDirVal`、`panelConclusionVal`、`panelEntryVal` 各自引用的依赖是否先声明，不再把互不依赖的变量按任意顺序比较。当前 `SVP_v6_ready` 基准应输出 `def-before-use 违例: none`；若再出现违例，按报告给出的 `依赖→消费者` 行号人工复核。

## HALDRO 副指标使用注意（2026-07-04 审计确认）

**CVD 质量差异**：HALDRO CVD（`sessCvdA`）使用影线/实体比例估算 Delta；SVP 主指标通过 `request.security_lower_tf` 汇总子K价格方向成交量，粒度更细但仍是**估算**，不是真实 bid/ask 逐笔。两者冲突时以主指标的关键位门控CVD作为优先背景。若账户支持，可在独立 Footprint Pro 版评估单个 `request.footprint()`；它提供更细的低周期分类量、行级失衡与POC/VA，但按官方口径仍不能笼统称为交易所逐笔真Delta。

**LSR 多空拥挤方向检查（2026-07-08 审计新增，2026-07-10 确认仍存在）**：审计 HALDRO 时必须 grep `lsrTxtA`。常见错误是把 `LSR > 1.3` 写成 `空拥挤`、`LSR < 0.8` 写成 `多拥挤`。按常见 Long/Short Ratio 口径应为：`LSR > 1.3` = 多头拥挤，`LSR < 0.8` = 空头拥挤。若当前方向与拥挤同侧，Confirm Score 应扣 1，并在风险行/风险码中标 `⚠LSR拥挤`。只显示 LSR 不参与降级属于 P1 弱确认缺口。

**⚠ LSR 方向反转是确认的反复出现缺陷**：skill 在 2026-07-08 首次记录，2026-07-10 上传源码中仍然写反（`lsrA > 1.3 ? ' · 空拥挤' : lsrA < 0.8 ? ' · 多拥挤'`），说明修复从未写入用户 TV 生产环境。每次审计必须执行此 grep 验证：
```bash
grep -n "lsrTxtA" 副指标.txt
# 正确：lsrA > 1.3 ? ' · 多拥挤' : lsrA < 0.8 ? ' · 空拥挤'
# 错误（仍存在）：lsrA > 1.3 ? ' · 空拥挤' : lsrA < 0.8 ? ' · 多拥挤'
```
同时检查 LSR 是否参与 Confirm Score 降级：grep `confirmScoreA` 确认含 LSR 拥挤扣分项；grep `haldroRiskCodeA` 确认含 LSR 位。若两者均不含 LSR → P1 弱确认缺口（LSR 只显示不降级）。

**汇率请求配额说明（Pine v6 dynamic requests）**：副指标应让 USD/COIN 默认路径直接使用常量换算率，只在 EUR/RUB 分支实际执行换汇请求。v6 默认 dynamic requests 且条件短路，未执行的请求分支可以不形成运行时 unique context；但实时所需上下文必须在历史阶段已访问。审计时同时报告默认输入和最坏启用配置，不再写“条件门控一定不省配额”。

**P1: 副指标 plot 槽位偏紧（2026-08-07 当前版复核）**：当前为 39 个 `plot()`、0 个 `alertcondition()`；Volume、Delta Spot-Perp、Perp-Spot proxy、Delta、CVD、EX1–EX5 共10个 plot 使用 series color，各额外产生 1 个 plot count，静态估计约 **49/64**、余量约15。最终以 TradingView 服务器编译回执为准。新增 plot 前优先复用/打包 Data Window 字段；不得静默删减用户要求的5所成交量或4所OI。

**历史线条首根可见性案例（当前生产版保留DO与限时nPOC）**：DO与nPOC都要求水平线创建与维护具有非零长度并向右多延一根。nPOC只在未触碰且未过期时作为有效候选；触碰后低周期淡化虚线，H1+可按`HIDE_SWEEPS_ON_HTF`隐藏。当前用户已删除pPOC。

**Confirm Score 尺度**：HALDRO Confirm Score 上限 5，SVP 评分上限 10，不能直接比大小或相加。读图标准：
- Confirm Score ≥ 3 → 副指标强确认
- Confirm Score ≤ 2 → 副指标弱确认，须等 SVP 主指标进一步过滤

**v2.1/v2.2 CVD 背离检测 + LSR + 5行精简（按上传源码确认，不能假设已落地）**：审计 HALDRO 副指标时先 grep `cvdBearDivA|cvdBullDivA|LSR|CVD Value`。若缺失，可按以下模式升级：
1. CVD 背离三重过滤（摆动极端 + CVD不确认 + 摆动>1.5×ATR + slope方向），背离时流向行替换为 `CVD ⚠卖背离`/`CVD ⚠买背离`，Confirm Score扣1，`riskWarnA`增加`⚠CVD背离`。用户界面不显示“估算/Estimated”；诚实口径放在源码注释与`CVD Method Code`。
2. 多空比 LSR（`BINANCE:{base}USDT_LSR`，`ignore_invalid_symbol=true`），>1.3 多头拥挤，<0.8 空头拥挤，追加到持仓行后缀；若当前方向与拥挤同侧，Confirm Score扣1并提示`⚠LSR拥挤`。
3. 精简模式建议固定5行（信号/结论/流向/持仓/操作，风险并入结论或固定风险行），不要退回3行，也不要因风险出现让操作行上下跳动。
4. Data Window 只保留 `CVD Value`，另保留 `CVD Method Code`、`CVD Quality Code`、`LSR`、`HALDRO Valid Code`、`HALDRO Risk Code`；**`Estimated CVD Value` 已彻底移除**（历史记录，勿再当现行字段）。
5. 告警标题使用`CVD卖背离`/`CVD买背离`，并事件化为首次进入状态，避免每根收盘K重复触发。
6. 配额必须按TradingView series-color规则计算实际plot count；原始调用数只是最低值，最终以TV服务器编译回执为准。

## AggVol vNext 强制决策完整性检查

成熟副指标除配额和LSR外，每次必须检查：

1. **Freshness不是非空判断**：默认前向填充的`request.security()`值持续非空时，`ta.barssince(valid)`会永久为0；应逐源记录真实更新时间/缺口年龄，掉线状态持续到恢复。
2. **OI四象限语义**：`priceDn + oiUp`是新空扩仓，不得同时标为“OI背离”并扣分；拆分扩仓、平仓、衰竭和跨所分歧。
3. **唯一最终裁决**：Strong、Confirm Score、Composite、Risk Code、行动格和告警必须消费同一`finalDecision`；禁止强共振告警与同向拥挤/关键风险告警同时成立。
4. **多空镜像**：可信空头也必须要求CVD同向确认；HTF票必须与价格方向一致，反向HTF不得反而给共振加分。
5. **CVD Anchor一致**：价格pivot对应CVD与上一pivot比较时必须处于同一anchor，或使用独立连续CVD。
6. **HTF gaps 语义**：确认型HTF序列若供每根低周期K消费，应使用`gaps_off`前向填充最后已确认值；`gaps_on`会令无新HTF值的大多数低周期K返回`na`，使HTF确认/冲突门控间歇失效。
7. **单位维度审计**：变量若已是百分数（ratio×100），转基点只应再×100；再×10000会把bp导出放大100倍。所有MCP字段必须用实测数值做量纲反推。
8. **模式/市场护栏贯穿图形端**：`Single`模式必须进入可用态；非加密护栏不能只保护表格，副图plot与Data Window也应隐藏或明确标为图表源/tick-volume估算。
6. **交易所去重与单位适配**：重复输入槽不得重复加总或虚增coverage；跨所成交量/raw OI不得混合未知合约单位。决策只消费normalized change/breadth/agreement/dispersion。
7. **爆仓代理降权**：保留直白“爆仓”文案，但PERP-SPOT量差代理仅作背景，不得单独改写最终结论。

## P1: R:R 执行显示一致性（2026-07-03，2026-07-04 更新）

审计主指标行动格时，**有两个独立的 RR 门控点**，必须分别检查：

### P1-A：`executablePlan` 本身必须含 `rrHardOk`（2026-07-04 实案）

**错误模式（被实际发现的 bug）**：
```pine
bool executablePlan = displayLongA or displayShortA or bcDirectOk
// ↑ 完全绕过 rrHardOk，replayPlanPrice 会被赋具体值，MCP DW 导出可执行订单
```
结论行虽显示 `X R:R不足`，但 `replayPlanPrice`/`replayInvalidPrice` 有值 → MCP Data Window 导出入场/止损价 → 自动化脚本误读为可执行订单。

**正确写法**：
```pine
bool executablePlan = ((displayLongA or displayShortA) and rrHardOk) or bcDirectOk
```

### P1-B：面板三行必须受 `rrHardBlock` 门控

在 `executablePlan` 正确的前提下，还需确认面板显示同步：
```pine
string panelEntryVal = rrHardBlock ? "不做，R:R不足" : "等触发"
string panelStopVal  = rrHardBlock ? "—" : stopPriceText != "" ? ... : "—"
string panelTgtVal   = rrHardBlock ? "—" : magnetTargetText != "" ? ... : "—"
```

**两个 bug 可以同时存在，也可以只有其中一个。先查 P1-A 再查 P1-B，不可只查面板显示。**

检证命令（两条都要跑）：
```bash
# P1-A
grep -n "executablePlan" 主指标.txt
# 必须看到: ((displayLongA or displayShortA) and rrHardOk) or bcDirectOk

# P1-B
grep -n "panelEntryVal\|panelStopVal\|panelTgtVal" 主指标.txt
# 必须看到三行首次赋值都含 rrHardBlock
```

B/C 直接挂单仍按更低门槛：`R:R >= 1.5` + HTF/CVD/位置/结构触发/流动性/SMT 全部通过；否则显示等待确认。

## 社区驱动的优化知识库

### 2026 ICT/SMC 共识（Medium 30 策略详解 + Reddit + ATAS + Bookmap）

**下单辅助核心要素**（优先级排序）：
1. **方向**（偏多/偏空）—— 最基础
2. **溢价/折价** —— go/no-go 过滤（深溢价不做多）
3. **KillZone** —— 窗口内/外，影响信号权重
4. **位移** —— 2026 #1 质量过滤器，无位移=假突破
5. **CVD 背离** —— 最早反转先导
6. **待扫/已扫位** —— 情境感知，知道等什么

**社区源映射**：
- ICT 2026: Displacement 是 #1 过滤、FVG 需 HTF 结构对齐、Premium/Discount 铁律
- Bookmap: CVD 背离最可靠反转信号、关键位吸筹/派发检测
- Reddit r/Daytrading: Session CVD (亚/伦/纽) + Volume Profile + VWAP 三联核心
- ATAS SMC 模板: Delta + vPOC + 吸收 + 流动性区四件套
- TradingView 社区: 分会话 CVD Divergence 脚本（四类背离自动标）
- Freqtrade/X: ATR 夹层止损、连亏缩仓

### 行动格缩写规范
- KillZone: `⚡亚` `⚡伦` `⚡纽`（完整标保留在联动行；用户要更直白时可写「亚洲/伦敦/纽约开盘」）
- PD 区: `深溢价` `溢价` `深折价` `折价`（均衡不显示）
- 扫位: **禁止** 抽象 `扫3/5`；用户可读优先 → `已扫3/剩5`（或明确未扫口径）
- DMI: 仅显示冲突状态（`过热`/`走弱`/`待定`），`顺多/顺空` 与方向重叠省略

## 生产权威与多文件对照（2026-07-09）

用户问「这个指标怎么样 / Desktop 这份如何」时：

1. **字节权威**：`Desktop/SVP_v6.pine` 应与 `~/.hermes-web-ui/upload/default/SVP_v6.pine` 同 sha；不一致要标明哪份是上传生产。
2. **角色裁决先于功能清单**：
   - `SVP_v6` = 当前生产主驾驶（v6 + OB/Breaker/BOS/CHoCH/LV + MCP 14）
   - `SVP_fixed` = v5 修复基线/回退（无 OB 层；R:R/扫线/minBuckets 等与 v6 同源）
3. **输出顺序**：结论（能否当生产）→ P0/P1/P2 → 与另一版对照 → **直接推荐挂哪份**。禁止只罗列模块不给裁决。
4. **token 余量**：v6 实测 est≈78145/80000，余量薄；再加功能先削。

详见 `references/svp-v6-vs-fixed-audit-2026-07-09.md`。

## P1: BOS/CHoCH 优先级铁律（v6+ 必查）

**`chochBull`/`chochBear` 是 `bosBull`/`bosBear` 的条件子集。**  
若 `bosChochText` / `MCP BOS/CHoCH` **先判 BOS 再判 CHoCH**，则 CHoCH 文案与 MCP 码（±2）几乎永不触发，告警却可能双边同时响。

**正确**：文案与 MCP 均 **先 CHoCH 后 BOS**。

```pine
// 错
bosChochText = bosBull ? "BOS↑" : bosBear ? "BOS↓" : chochBull ? "CHoCH↑" : ...
// 对
bosChochText = chochBull ? "CHoCH↑" : chochBear ? "CHoCH↓" : bosBull ? "BOS↑" : bosBear ? "BOS↓" : ""
// MCP 同理：choch ? ±2 : bos ? ±1 : 0
```

```bash
grep -n "bosChochText\|MCP BOS/CHoCH" 主指标.pine
# choch 三元分支必须在 bos 之前
```

## 历史案例：DO / nPOC 可见性（当前生产版为可调限时nPOC）

- DO：创建与维护均延到`bar_index+1`；
- nPOC：必须从已完成SVP的POC右端`endBar`原点延长，禁止滚动或改写`x1`；数量、过期K数、颜色、线型、宽度可调，默认虚线；未触碰时推进`x2`，触碰后冻结在触碰K线，H1+可隐藏；pPOC已删除。

## P2: CVD 星级算法（2026-07-09 已实现）

`int cvdBearStars = 0` / `cvdBullStars = 0` 原为恒 0 空壳。星级应基于背离强度，并保持事件方向配对正确：
```pine
cvdBearStars := cvdBearDivQualified ? (cvdDistributeSellQualified ? 3 : 2) : cvdBearDiv ? 1 : 0
cvdBullStars := cvdBullDivQualified ? (cvdAbsorbBuyQualified ? 3 : 2) : cvdBullDiv ? 1 : 0
```
确认熊背离+卖方派发=3星；确认牛背离+买方吸收=3星；确认背离=2星；未确认背离=1星；无背离=0。审计时除 grep `:=` 外，还必须核对熊/牛事件没有配反。

## P1: bcDirectRaw 必须含 OB/Breaker 汇合（2026-07-09 修复）

原版 bcLongDirectRaw / bcShortDirectRaw 条件不含 `inBullOB / inBullBreaker / inBearOB / inBearBreaker`，导致价格回踩 OB 时不触发 B/C 级挂单。修复后追加到条件组：
```pine
// 多
...or mssLongOk or acceptanceBullOk or inBullOB or inBullBreaker) and not adrLowRoomLong...
// 空
...or mssShortOk or acceptanceBearOk or inBearOB or inBearBreaker) and not adrLowRoomShort...
```
审计时 grep `or inBullOB or inBullBreaker` 和 `or inBearOB or inBearBreaker` 确认存在。

## P1c: 风控参数 MCP 编码（2026-07-09 新增）

`RISK_PER_TRADE_PCT` / `DAILY_MAX_LOSS_PCT` / `WEEKLY_MAX_LOSS_PCT` 原为死代码（只有声明零引用）。修复为写入 MCP Data Window 供 auto_card 读取：
```pine
int mcpRiskPack = int(nz(RISK_PER_TRADE_PCT, 0) * 10000 + nz(DAILY_MAX_LOSS_PCT, 0) * 100 + nz(WEEKLY_MAX_LOSS_PCT, 0))
plot(mcpRiskPack, "MCP Risk Pack (Risk%*10000+DailyLoss%*100+WeeklyLoss%)", display=display.data_window)  // 历史记录：该 plot 后续版本已移除
```
MCP Data Window 从 11 增至 12 个 plot。
⚠ **该字段后来又被移除（2026-09-11 核实）**：`MCP Risk Pack` 在当前定版不可读，是历史记录而非现行字段。
现行审计口径：按契约 `scripts/tv_indicator_contract.py` 的 `DW_MAIN` 清单比对，不要 grep 这个旧名。

## 注释删除 Token 削减陷阱（2026-07-09 实案）

删独立 `//` 注释行削 token 时，`//@version=6` 也以 `//` 开头会被误删！必须在删除逻辑中排除：
- 保留含 `@version` / `Pine` / `v6` / `非重绘` / `安全` / `compile` 关键字的注释行
- 或在删除后检查第一行是否为 `//@version=6`，缺失则补回
- 写盘后必须 grep `@version=6` 确认存在

## CW10002: ta.* 在条件表达式内（2026-07-09 实案）

TradingView 警告 `CW10002`：`ta.sma()` / `ta.rma()` 等依赖历史状态的函数放在 `or` / `and` / 三元 `?` 条件表达式内时，可能不在每根 bar 执行，导致历史计算不一致。

**检测**：
```python
# 找 ta.xxx( 在含 or/and/? 的行中
grep -n "ta\.\(sma\|rma\|ema\|wma\|stdev\|variance\|atr\|tr\|crossover\|crossunder\|highest\|lowest\|pivothigh\|pivotlow\)" 指标.pine | grep -E "or |and |\?"
```

**修法**：提取到全局变量，条件改为引用变量：
```pine
// 错
bool dispVolOk = not DISP_REQUIRE_VOL or (not na(volume) and volume > ta.sma(volume, 20))
// 对
float volSma20 = ta.sma(volume, 20)
bool dispVolOk = not DISP_REQUIRE_VOL or (not na(volume) and volume > volSma20)
```

注意：`request.security(syminfo.tickerid, "D", ta.sma(high-low, N)[1], lookahead=...)` 中的 `ta.sma` 在 `request.security` 的 expression 参数内，不算 CW10002（它在 HTF 上下文每 bar 执行）。只有主脚本条件表达式内的才算。

## 历史案例：FVG/OB/LV 标签框内定位（已被 2026-07-10 偏好覆盖）

> 仅用于理解 `text.align_right`、box 边界与 label 坐标的历史排错。**当前最终要求是英文缩写标签位于框内右下角**，以文末“FVG/OB/LV 区标签 + EMA 只云”和 `references/svp-zone-controls-community-ranking-2026-07-10.md` 为准。

**当时问题**：`style=label.style_none`（无背景气泡）+ 文字默认 `text.align_center` + x 坐标在框右边界 → 文字一半溢出框右边，标签不在框内。用户两轮反馈：「都没有在那个框里面」→ 修到 `-1` 后「箭头和边框重叠了，标签要左移一点点」。

**根因**：`label.new(x=right_edge, ..., style=label.style_none)` 不带 `textalign` 参数时，TradingView 默认居中对齐文字，文字以 x 为中心向左右展开。x 在框右边界 → 右半文字溢出。`-1` 只缩了 1K，文字仍贴着右边框。

**修法**（6个 label.new + 3个 set_x 维护，全社区共识）：
```pine
// label.new 参数
x = right_edge - 3                    // 向框内缩 3K（用户实测 -1 仍重叠，-3 合适）
textalign = text.align_right           // 文字右对齐，紧贴x向左展开
textcolor = 区域色(非color.white)       // 用 FVG_BULL_COL / OB_BULL_COL 等，不用 white

// label.set_x 维护同步
label.set_x(f.lb, fvgRight - ZONE_LABEL_X_IN - 3)
label.set_x(ob.lb, bar_index + 5 - ZONE_LABEL_X_IN - 3)
label.set_x(lv.lb, bar_index + 5 - ZONE_LABEL_X_IN - 3)
```

**标签左移量调参经验**：`-1` 太近仍与边框重叠 → `-2` 可见但仍贴边 → `-3` 文字完全在框内且不碰边框。不同品种/周期框宽不同（FVG_EXTEND 默认=1 很窄，OB 框 right=bar_index+5 更宽），统一用 `-3` 安全。用户后续要求微调时改 `ZONE_LABEL_X_IN` input 值即可，不用改代码。

**社区依据**：TradingCode.net `label.set_textalign()` 文档确认 `text.align_right` 让文字向右对齐，紧贴 x 坐标点向左展开。`label.style_none` 下 `textalign` 仍然有效。参考：https://www.tradingcode.net/tradingview/set-label-text-align/

## BOS/CHoCH 告警精简与逻辑保留（2026-07-09 实案）

用户说"BOS这些还需要不需要就删掉"。分析依赖链后结论：

| BOS/CHoCH 用途 | 能否删 | 原因 |
|----------------|--------|------|
| OB 触发条件 (`obBullDetected = SHOW_OB and bosBull`) | ❌ 不能删 | 删了 BOS → OB 永不触发 |
| MCP 编码 (`mcpBosCode`) | ❌ 不能删 | auto_card 读取结构信号 |
| 面板确认行 (`bosChochText`) | ❌ 保留 | 行动格确认行显示 BOS/CHoCH |
| 4个 alertcondition | ✅ 可删 | 快进快出不看 BOS/CHoCH 弹窗告警，减噪音 |

**审计铁律**：删除 BOS/CHoCH 前必须 grep 依赖链——`bosBull` / `bosBear` 被 `obBullDetected`、`mcpBosCode`、`bosChochText` 引用，删了会断 OB 检测和 MCP 编码。只删 alertcondition（弹窗告警），不删逻辑骨架。

## execute_code replace 重复匹配陷阱（2026-07-09 实案）

同一 `execute_code` 脚本中 `code.replace(old, new)` 成功后，第二次用同一 `old` 字符串 replace 会报 `❌`——因为已经被改过了，旧字符串不存在了。

**修法**：`execute_code` 的 replace 结果验证不要用「字符串是否仍在」判断，因为第一次改完新字符串不含旧字符串。多步修复时，每步替换后重新 `read_file` 拿最新内容再下一步替换；或在一个脚本内一次性做完所有 replace 后再验证。

## P0: UDT type 定义必须在使用之前（2026-07-09 实案）

**Pine 自上而下编译对 UDT（`type`）同样适用。** `type OBZone` 定义在 L2172，但 `var array<OBZone> htfObList` 在 L2034 引用它 → 编译错误 `"OBZone" is not a valid type keyword`。

**根因**：新增 OB HTF 功能时，在 `type OBZone` 定义之前插入了一行 `var array<OBZone> htfObList`，但 Pine 编译器在到达 `type OBZone` 定义之前不认识这个类型名。

**修法**：把 `type XXX` 定义移到所有引用该类型的行之前。包括 `var array<XXX>`、`XXX.new()`、函数参数 `XXX` 等。

**审计检查**：
```bash
# 找 type 定义行号 vs 最早引用行号
grep -n "type OBZone\|array<OBZone>\|OBZone\." 主指标.pine | head -5
# type 行号必须 < 任何 array<OBZone> / OBZone.new / OBZone 变量声明行号
```

**这是 Pine 编译顺序铁律的第三个子类**：① `=` 声明 def-before-use ② `:=` 赋值引用后声明 ③ `type` UDT 定义后引用。三者都是自上而下编译的体现。

## P0: 函数插入导致 return 行孤儿（2026-07-09 实案）

在两个函数之间插入新函数时，如果操作不慎会把前一个函数的 return 语句推到新函数之后，变成「孤儿行」。

**实案**：`f_htf_fvg()` 的 return `[bull, bear, top, bot]` 在插入 `f_htf_ob()` 时被推到了 `f_htf_ob()` 之后，导致：
1. `f_htf_fvg()` 没有 return → 调用方 `request.security(..., f_htf_fvg())` 的 tuple 赋值报 `Cannot assign a variable to a tuple`
2. 孤儿行 `[bull, bear, top, bot]` 在 `f_htf_ob()` 之后 → `bull`/`bear`/`top`/`bot` 未声明 → `Undeclared identifier`

**修法**：插入新函数时，确认前一个函数的 return 语句紧跟其函数体最后一行。插入点应在 return 行**之后**，不在 return 行**之前**。

**审计检查**：每个 `f_xxx() =>` 函数的最后一行应为 `[...]` tuple return 或单个返回值表达式。grep 函数名后检查紧邻的 return 行：
```bash
grep -n "f_htf_fvg\|f_htf_ob\|f_htf_trend" 主指标.pine
# 每个函数 => 后到最后一个表达式之间不能有另一个函数定义
```

## P0: UDT 新增字段后 OBZone.new 参数不匹配（2026-07-09 实案）

**给 `type` UDT 新增字段后，所有 `.new()` 构造调用必须同步更新参数数量。** 漏掉任何一处 → 后续参数错位 → 类型不匹配编译错误。

**实案**：`type OBZone` 从 8 字段增至 9 字段（新增 `bool htfConf`）。OB 主检测的 2 处 `OBZone.new` 和 HTF OB 的 2 处都更新了（9 参），但 **LV（Liquidity Void）的 2 处 `OBZone.new` 漏改**（仍 8 参）→ `bar_index`（series int）被当作 `htfConf`（series bool）→ 编译错误 `An argument of "series int" type was used but a "series bool" is expected`。

**根因**：LV 复用 `OBZone` 类型存储流动性真空区域，与 OB 检测代码距离远（L2312 vs L2209），手动更新时容易遗漏。

**修法**：新增 UDT 字段后，全文件 grep 所有 `.new()` 调用，逐一确认参数数量：
```bash
grep -n "OBZone.new(" 主指标.pine
# 数每个调用的参数个数，必须等于 type 定义的字段数
# 注意逗号在字符串内的情况（label.new 参数），需人工确认
```

**通用规则**：任何 `type XXX` 新增/删除字段后，全文件 `grep XXX.new(` 逐一核对参数数。常见复用同一 UDT 的功能模块（OB/LV/Breaker 复用 OBZone）距离远，容易漏改。

## P0: `:=` 赋值引用后声明变量（def-before-use 变体，2026-07-09 实案）

**与未定义变量不同：变量已声明（`int cvdBearStars = 0` 在 L825），但 `:=` 重新赋值行引用了在它之后才声明的变量。** Pine 自上而下编译，`:=` 行在 L1786 引用 `cvdAbsorbBuyQualified`（声明在 L1789）→ `Undeclared identifier "cvdAbsorbBuyQualified"` 编译错误。

**根因**：插入星级赋值 `cvdBearStars := cvdBearDivQualified ? (cvdAbsorbBuyQualified ? 3 : 2) : ...` 时，放在了 `cvdAbsorbBuyQualified` / `cvdDistributeSellQualified` 声明之前。

**修法**：把所有 `bool` 声明放前面，`:=` 赋值放最后：
```pine
bool cvdBearDivQualified = ...        // 声明
bool cvdBullDivQualified = ...        // 声明
bool cvdAbsorbBuyQualified = ...      // 声明
bool cvdDistributeSellQualified = ... // 声明
cvdBearStars := cvdBearDivQualified ? (cvdAbsorbBuyQualified ? 3 : 2) : cvdBearDiv ? 1 : 0  // 赋值在最后
cvdBullStars := cvdBullDivQualified ? (cvdDistributeSellQualified ? 3 : 2) : cvdBullDiv ? 1 : 0
```

**审计时检查**：对每个 `:=` 赋值行，确认其引用的所有变量在该行之前已有 `bool/float/int/string` 声明或前序 `:=` 赋值。grep `:=` 行号 vs 声明行号。这是 Pine 编译顺序铁律的一个子类——不只是 `=` 声明有顺序要求，`:=` 重新赋值同样受 def-before-use 约束。

## CW10002: ta.* 函数在条件表达式内（2026-07-09 实案）

**TradingView 警告**：`The "ta.sma()" call inside the conditional expression might not execute on every bar, which can cause inconsistent calculations because the function depends on historical results.`

**根因**：`ta.sma()` / `ta.rma()` / `ta.ema()` / `ta.crossover()` / `ta.crossunder()` / `ta.highest()` / `ta.lowest()` 等依赖历史结果的函数放在三元条件、`or` / `and` 条件或 `if` 块内时，条件为 false 的 bar 上不执行 → 内部状态断链 → 后续 bar 计算结果不一致。

**修法**：把 `ta.*` 调用提取到全局变量，条件表达式只引用结果：
```pine
// 错
float x = cond ? ta.sma(close, 14) : na
bool y = not na(sVwap) and ta.crossover(close, sVwap)
bool z = not na(curVah) and ta.lowest(close, N) > curVah
// 对
float smaVal = ta.sma(close, 14)
float x = cond ? smaVal : na
bool xoverS = ta.crossover(close, sVwap)
bool y = not na(sVwap) and xoverS
float lowN = ta.lowest(close, N)
bool z = not na(curVah) and lowN > curVah
```

**审计时 grep**：`ta.sma\|ta.rma\|ta.ema\|ta.wma\|ta.crossover\|ta.crossunder\|ta.highest\|ta.lowest` 出现在含 `or` / `and` / `?` 三元或 `if` 块内的行。常见于 ADR / CVD / DMI / VWAP acceptance / displacement 相关的条件取值。

**批量检测脚本**（execute_code）：
```python
import re
code = open('指标.pine', encoding='utf-8').read()
for i, l in enumerate(code.split('\n')):
    if re.search(r'ta\.(sma|rma|ema|wma|crossover|crossunder|highest|lowest|atr|tr|pivothigh|pivotlow)\s*\(', l):
        if re.search(r'(or|and|\?|if\b)', l.strip()):
            print(f"L{i+1}: {l.strip()[:150]}")
```

**注意**：`request.security(syminfo.tickerid, "D", ta.sma(high-low, N)[1], lookahead=...)` 中的 `ta.sma` 在 `request.security` 的 expression 参数内，不算 CW10002（它在 HTF 上下文每 bar 执行）。只有主脚本条件表达式内的才算。

**修复顺序**：CW10002 警告需逐个排查。同一轮修复中可能出现多个 CW10002（ta.sma → ta.crossover → ta.highest/ta.lowest），每个新编译错误都要继续提取全局变量直到无警告。

## 历史案例：FVG/OB 标签框内坐标审计（当前勿照抄）

> 本节保留坐标边界检查方法；**当前标签目标位置为框内右下角**。审计时检查 x/y 落在 box 边界内，并用 TV 全屏截图确认不遮挡价格轴、区域框或 CVD 副窗。

**历史反馈**：FVG/OB 标签曾“都没有在那个框里面”，因此当时检查 label x/y 是否落在 box 范围内。

当前定位逻辑（FVG L2070 等）：
```pine
label.new(bar_index + FVG_EXTEND - ZONE_LABEL_X_IN, math.min(t, b) + nz(currATR, syminfo.mintick) * ZONE_LABEL_Y_ATR, ...)
```
- x = 框右边缘 `bar_index + FVG_EXTEND` 减去 inset
- y = 框底部 `math.min(t, b)` 加上 ATR 抬升

**可能问题**：
1. `FVG_EXTEND` 默认=1，框很窄，标签 x 在框右边缘可能超出框体
2. `ZONE_LABEL_Y_ATR` 默认=0.05，ATR 抬升太小，标签可能贴在框底线下方而非框内
3. `label.style_none` 不限制标签位置，标签会自动偏移避免重叠
4. box 的 right 坐标随 `box.set_right` 每bar更新，但 label 的 x 也在更新——需确认两者同步

**审计时检查**：标签 x 是否在 `[box_left, box_right]` 范围内，y 是否在 `[box_bottom, box_top]` 范围内。用 TV 截图肉眼验证。

## 静态扫描脚本注意

`scripts/pine_static_scan.py` 已于 2026-07-10 修复三类历史问题：CRLF/`\\n` 双重转义导致整文件被读成少数行、`pEma = plot(...)` 赋值形式漏计 plot、字符串/成员名/函数参数被误报为未定义变量。当时基准（对已退役的 `SVP_v6_ready.pine`）应输出：2859 行、request 12、plot 28、未定义变量 none —— 历史基准值，勿套用到定版指标。若以后结果偏离，先用 TradingView 实际编译与独立正则扫描交叉验证，不要把扫描器异常当成指标缺陷。

## 审计后产出格式

纯纵向、无装饰分隔线；可用短对照表。
P0（编译失败/配额超限） → P1（核心功能缺陷） → P2（死代码/注释误导）
每条：问题 → 证据（行号/命令） → 修法。
用户问「怎么样」时末尾必须给 **直接推荐**（挂 v6 / 回退 fixed / 先修哪几条）。

审计收尾：必须跑 `grep` 确认配额、变量唯一定义、无死代码引用。

## 扫线 gapThrough 视觉一致性检查（2026-07-05 发现）

**问题模式**：扫线评分检测有两条路径——`sameBarTouch`（影线触碰）和 `gapThrough`（跳空穿透）。L2033-2045 的评分逻辑正确处理了两者（`sweptHighRejected` 看 `close < price` 对两种路径都成立）。但 L1671-1677 的**线条变虚逻辑只检测 `wickPierce`，不检测 `gapThrough`**——跳空穿过时评分系统标记了扫线，但图上线条仍为实线，视觉与逻辑不一致。

**检查命令**：
```bash
grep -n "wickPierce\|gapThrough\|isSwept.*:=" 主指标.txt
```
如果 `isSwept` 赋值行只引用 `wickPierce` 不引用 `gapThrough`，线条变虚逻辑有缺口。

**修法**：在 L1675 区域加 `gapThrough` 判定并并入 `touchOrGap`，让 `isSwept` 同时覆盖两种路径。

## P0c: 绘图 64 上限急救（2026-07-09 实案 71→≤63）

**报错**：`脚本创建了太多绘图(N)。限制为64`。与 security 40 / token 80000 是另一维约束。

- series 色（`input.color` / 三元 color）→ 该 plot **计 2**；常量 `#hex` → 计 1
- 用户报 71 时勿只算「series×2」。**最坏式**（本轮命中 71）：
  `worst = plots*2 + fills*2 + bgs*2 + table` → 目标 **≤63**
- 修法优先级：① 视觉/轴标 plot 色常量化（最大收益）② bgcolor 合并为 1 ③ fill 固定色 ④ MCP 只打包新结构字段为 `MCP StructPack`（历史记录：当时曾用长名 `MCP StructPack (FvgQ*10000+…)`，现已改回短名），**保留** classic auto_card 名（`MCP Side Code` 空侧 **-1**）⑤ 仍超再砍 Band2/云 fill
- 打包时必须保留 `mcpFvgQualityCode = ...` 赋值（可删 plot 不可删定义）
- 桌面 + upload `SVP_v6.pine` 双写对齐；TV 编译为准
- 详见 `references/svp-v6-plot-limit-and-audit-2026-07-09.md`

### 2c 口径更新（DW 急救后）
经典名：Side/Grade/Setup/Entry/Stop/Target/CVD/Quality + FVG CE×2 + StructPack + RiskPack = **12 个** Data Window plot（2026-07-09 全量审计确认）。结构用 StructPack（CHoCH 优先于 BOS）。勿再假设独立 `MCP OB Signal` / `MCP BOS/CHoCH` / `MCP Liq Void` 三 plot 仍在——已打包进 StructPack。RiskPack 编码 `Risk%*10000+DailyLoss%*100+WeeklyLoss%`。

**Token 实测**：v6_ready 削减后 78,017/80,000，余量 1,983。削减了 7 项（5死函数+银弹窗+Band2+EMA单线input+精简标准模式+降级提示+性能模式 = ~1,905 tokens）。

## 历史案例：编译 token 80,000 上限时期（2026-07-09，当前勿沿用）

> 本节只保留旧版实案的清理方法。当前官方 IL 上限已为 **100,000 tokens**，且官方明确说明无法从源码字符数可靠推算 IL token；未影响输出的死代码会被编译器剔除。审计当前脚本时不得使用下述80K阈值、字符/2.33或186,400字符作为P0结论，最终只认 TradingView 编译回执。

当时 TradingView 编译后代码 token 上限为80000，超过会报 `Compiled code contains too many tokens`。这与 request/plot/object 配额是不同维度。

### 历史粗估（仅复盘，不用于当前验收）

Pine 代码的 token 密度约为 **2.33 字符/token**（2026-07-09 实测：189,427 字符 → 81,303 tokens）。快速估算：
```
est_tokens = source_chars / 2.33
```
源码超过 ~186,400 字符即可能触顶，需提前规划削减。

### token 削减策略（按效率排序）

1. **删除死变量（最高效）**：变量只赋值从未被读取 = 纯死代码。每个死变量的声明 + 全部赋值行（含 if/else 链内的 `:=`）都可整条删除。2026-07-09 实案：删 15 个死变量（`stateText`/`cardLine1-3`/`detailText`/`directionGuideText`/`actionGuideText`/`nowAdviceText`/`treatmentText`/`valueText`/`vwapText`/`emaText`/`valuePosText`/`barConfirmText`/`trendScoreText`/`reversalScoreText` + 连带 `valueRange`/`valuePos`）省 8,949 字符 / ~3,848 tokens。

2. **删除空 if/else 链**：死变量的赋值被删后，其 if/else 链可能变空（条件还在但分支体为空）→ 整条删除。2026-07-09 实案：`nowAdviceText` 的 6 分支 if/else 链赋值全删后链变空，连头带尾删 6 行。

3. **精简面板档位**：`ACTION_PANEL_DETAIL` 从三档（精简/标准/完整）减到两档（精简/标准），删 `panelDetailFull` 变量及 `完整` 档独有代码路径（指标行、计划行、独立风险行）。

4. **短缩 tooltip**：input tooltip 长字符串占大量 token，可精简文案。

5. **删注释**：注释也占 token，但效率低于删代码（注释通常比代码短）。

### 死变量检测方法（execute_code 批量扫描）

```python
# 提取所有声明/赋值的变量名
import re
code = open('指标.txt', encoding='utf-8').read()
declared = set(re.findall(r'(?:var\s+)?(?:float|int|bool|string|color)\s+(\w+)\s*=', code))
declared |= set(re.findall(r'(\w+)\s*:=', code))
# 对每个声明变量，检查是否有"读取"（出现在非赋值行的表达式中）
for var in sorted(declared):
    reads = [i+1 for i, line in enumerate(code.split('\n'))
             if re.search(r'\b' + re.escape(var) + r'\b', line)
             and not line.strip().startswith(var + ' :=')
             and not line.strip().startswith(('string ', 'float ', 'int ', 'bool ', 'color ')) + var + ' =')
             and not line.strip().startswith('//')]
    if len(reads) == 0:
        print(f"  DEAD: {var} (0 reads)")
```

### 死函数检测（2026-07-09 实案，比死变量更大的 token 回收）

**死函数 = 定义了但全文零调用的函数。** 比死变量回收更大：一个函数体可能 10+ 行。

**检测方法（execute_code 批量）**：
```python
import re
code = open('指标.pine', encoding='utf-8').read()
lines = code.split('\n')
# 找所有 f_xxx() => 定义
funcs = [(i+1, re.search(r'(\w+)\s*\(', l).group(1), l) for i, l in enumerate(lines)
         if '=>' in l and '(' in l and not l.strip().startswith('//')]
for ln, fname, line in funcs:
    # 调用 = 行中有 fname 但没有 => 且不是定义行
    calls = sum(1 for l in lines if fname in l and '=>' not in l and not l.strip().startswith('//'))
    if calls == 0:
        print(f"  DEAD: {fname} (0 calls, defined at L{ln})")
```

**2026-07-09 实案**：5 个死函数（`f_dist_text` 192 tokens / `f_score_text` 42 / `f_strength_text` 40 / `f_price_text` 48 / `f_level_short` 30）= 352 tokens 纯回收。**注意 `f_near` 同名搜索误报为死——有 9 处调用，需人工确认。**

**2026-07-10 实测更新**：当前上传源码中 `f_rebuild_polyline`（L351）也是死函数（0 调用），死函数总数为 6 个（`f_rebuild_polyline` + `f_dist_text` + `f_score_text` + `f_strength_text` + `f_price_text` + `f_level_short`），约 ~400 tokens 可回收。这 6 个在 SVP_v6 生产版本中可能已被删除——审计新上传文件时重新 grep 确认是否仍在。

**安全删除**：死函数零依赖，可直接删定义行+函数体。删后 grep 函数名确认无残留。

### Token 模块化审计方法（2026-07-09 实案）

全量审计时不仅要看总 token，还要按模块拆分定位「哪些段最贵」。这样削减能精准打击。

**方法**：把文件按逻辑分段（input声明 / VolumeProfile / ICT / CVD / 评分 / 行动格 / MCP plots），逐段计算 `len(chunk)/2.33`，输出占比表。同时按 input group 统计每组消耗。

**实案 token 分布**（79957 总量）：
| 模块 | Token | 占比 |
|------|-------|------|
| 头部+input(252个) | 14,412 | 18.0% |
| ICT函数(扫线/标签/会话) | 8,909 | 11.1% |
| 关键位/文本函数 | 9,047 | 11.3% |
| 评分/行动格/方案 | 12,822 | 16.0% |
| VolumeProfileEngine | 5,788 | 7.2% |
| CVD delta+计算 | 5,111 | 6.4% |
| OB/BOS/CHoCH | 3,571 | 4.5% |
| FVG检测/绘制 | 2,611 | 3.3% |

**input 组 token TOP5**：DMI(1737) > ICT_STYLE(1473) > SESSIONS(1370) > VP_ELEMENTS(1157) > EMA(888)。

**削减启示**：input 占 18% 但大部分是用户可调参数不可删。真正能削的是死代码 + 默认关功能的完整代码块。

### 可删项分级矩阵（2026-07-09 实案，token 余量极薄时决策工具）

当 token 余量 < 500 且用户问「建议删哪些」时，按以下分级给出选项：

| 级别 | 删什么 | 释放 | 余量 | 说明 |
|------|--------|------|------|------|
| 保守 | 死代码+默认关小功能 | ~1,200 | ~1,250 | 零依赖删除+默认false功能 |
| 中等 | 保守+默认关大功能 | ~1,800 | ~1,850 | +EMA单线/LV等 |
| 激进 | 中等+耦合功能 | ~3,000 | ~3,000 | +需同步改MCP解析的功能 |

**评估维度**：默认值 / 依赖链 / MCP编码耦合 / 删后影响。
**关键原则**：先列清单不删，让用户选。MCP编码耦合项（如LV→StructPack位）标注「删后auto_card需同步改」。

### 削减后验证

- `est_tokens = len(code) / 2.33 < 80000` → 安全
- 确认削减未破坏活变量：grep 活变量仍有声明 + 赋值 + 读取
- 确认无空 if/else 分支残留
- 确认 MCP Data Window plots / alertcondition / request.security 数量不变

### 削减执行三大陷阱（2026-07-09 实案，删 7 项 ~1,905 tokens）

删 input 变量 + 删 if 分支 + 删功能模块时，以下三个陷阱各至少触发一次：

**陷阱1：残留引用 — 删了 input 但代码里还在用**

删 `SHOW_EMA_1`/`EMA_1_LEN` 等 input 后，`ta.ema(close, EMA_1_LEN)` 仍引用已删变量 → 编译 `Undeclared identifier`。同理 `proLightMode`、`showDegradeWarn` 等。

**修法**：删 input 后立即 grep 全文找残留，逐一替换：
- `EMA_1_LEN` → `9`（硬编码默认值）
- `proLightMode` → `false`（默认非轻量）
- `showDegradeWarn` → `degrade`（用底层变量直接替代）
- `showSpanWarn` → `spanTooLongForDrawing`

**陷阱2：缩进错位 — 删了 `if` 行但保留 body，body 多了一层缩进**

删 `if panelDetailStd\n` 后，body 行保留了 12 空格缩进（原在 if 内多缩 4 空格），但同层 `bool spanTooLongForDrawing` 只有 4 空格 → Pine 报 `Mismatched input "string" expecting "end of line without line continuation"`。

**修法**：删 `if` 行后，手动将 body 每行减 4 空格缩进。或更安全：不删 `if` 行，改为 `if true`（但浪费 1 行 token）。推荐用 patch 工具逐行修缩进。

**陷阱3：多行 replace 匹配失败 — 原始字符串含 `\\n` 转义**

Pine 字符串中的 `\\n`（换行文本）在 Python `code.replace(old, new)` 时，`old` 中的 `\\\\n` 与实际文件中的 `\\n` 不匹配 → 静默不替换。

**修法**：多行 replace 失败时改用逐行 `lines[i] = 'new content'` 修改，再 `'\n'.join(lines)` 重组。

**削减后完整验证流程**：
```python
# 1. 残留检查 — 所有被删变量名 grep 全文
residuals = ['SHOW_EMA_1', 'EMA_1_LEN', 'proLightMode', 'showDegradeWarn', ...]
for r in residuals:
    if r in code:
        print(f"❌ {r}: {code.count(r)}处残留")

# 2. 编译关键串检查
# 关键串用**当前**字段名（`MCP Risk Pack` 已废止，会永久报缺失）
for s in ['@version=6', 'dynamic_requests=true', 'f_htf_ob()', 'MCP Quality Code']:
    if s not in code:
        print(f"❌ 关键串缺失: {s}")

# 3. Token 确认
print(f"Token: {len(code)/2.33:.0f}/80000")
```

## v5→v6 迁移与新增 ICT 功能（2026-07-09 实案）

### v5→v6 迁移检查清单

1. **`@version=5` → `@version=6`**
2. **添加 `dynamic_requests=true`** 到 `indicator()` 声明（允许 `request.security()` 用动态 symbol）
3. **`fixnan()` 不再接受 bool 参数**——但 `fixnan(float_expr)` 仍然合法。grep `fixnan(` 确认参数是 float 不是 bool
4. **`na()`/`nz()` 不再接受 bool 参数**——扫描所有 bool 变量的 `na()`/`nz()` 调用
5. **UDT field 不能直接用 `[]` 取历史**——`myUDT.field[1]` 需先存到变量再取历史
6. **`na` 不能替代内置常量**——如 `style=na` 不再合法
7. **整数除法返回 float**——`1/2` 返回 `0.5` 而非 `0`，需 `int()` 显式截断
8. **`for ... by -1` v6 合法但生产禁用**——size=1 时 `0 to 0 by -1` 报 `step must be greater than zero`。倒序一律 `while`。另：`for i=1 to size-1` 在 size=1、`for r=0 to n-1` 在 n=0 同样炸

### v6 迁移常见编译错误（2026-07-09 实案追踪）

迁移后用户在 TradingView 遇到的 3 个编译错误及修复：

**错误1：`dynamic_requests` 重复参数**
```
错误于 6:23 Two or more arguments are passed to the "dynamic_requests" parameter.
```
根因：`code.replace()` 在 `indicator()` 第一行后插入 `dynamic_requests=true,`，但原始声明的闭合括号行已有另一个 `dynamic_requests=true)`（replace 产生的重复）。结果 L3 和 L6 各有一个。
修法：grep `dynamic_requests` 确认只有一处。用 `patch` 工具直接删多余行比 execute_code replace 更可靠。

**错误2&3：`na(series bool)` from request.security tuple**
```
错误于 2029:108 Cannot call "na" with argument "x"="call "operator SQBR" (series bool)".
An argument of "series bool" type was used but a "simple float" is expected.
```
根因：`request.security()` 返回的 tuple 中 bool 字段（如 `hBull`/`hBear`）是 `series bool`。v6 中 `na()` 不接受 bool，但 `hBull[1]` 取历史值时在 v5 合法的 `na(hBull[1])` 在 v6 报错。
修法：`na(hBull[1])` → `not hBull[1]`（v6 bool 不可为 na，"不存在或为假"合并为 `not`）。
注意：原写法 `na(hBull[1]) or not hBull[1]` 简化后变成 `not hBull[1] or not hBull[1]`，需去重为 `not hBull[1]`。

**迁移后必跑的 v6 编译检查清单**：
```bash
# 1. dynamic_requests 只出现一次
grep -c "dynamic_requests" 主指标.pine  # 必须 = 1

# 2. request.security 返回的 bool 字段无 na() 调用
grep -n "na(hBull\|na(hBear\|na(hBull\[\|na(hBear\[" 主指标.pine  # 必须为空

# 3. 所有 na() 调用的参数不是 bool 变量（需人工确认变量类型）
```

**迁移前必须跑的 breaking change 扫描**（用 execute_code 批量检测）：
```python
# 1. na(bool) / nz(bool) 检测
# 2. fixnan(bool) 检测
# 3. UDT field[] 检测
# 4. if floatVar 检测（v6 需显式比较 if floatVar != 0）
# 5. style=na 检测
```
2026-07-09 实案扫描结果：主指标无任何 breaking change（fixnan 两处均在 float 表达式上，合法），迁移只需版本号+dynamic_requests 两行改动。

### 新增 ICT 功能集成模式

添加 Order Block / Breaker Block / BOS/CHoCH / Liquidity Void 时的标准集成点：

| 集成层 | 插入位置 | 做什么 |
|--------|----------|--------|
| **输入参数** | ICT_STYLE_GROUP 输入末尾 | 新增 `OB_GROUP` 常量 + `SHOW_OB`/`SHOW_BREAKER`/`SHOW_BOS_CHOCH`/`SHOW_LIQ_VOID` 开关 + 颜色/过期参数 |
| **检测逻辑** | FVG section 之后、PD section 之前 | 新增 `type OBZone` + swing 检测 + OB/Breaker 缓解跟踪 + LV 填充检测 |
| **面板确认行** | `ckSweep` 定义之后 | 新增 `ckOb` 字符串变量 + 更新 `panelCheckText` 拼接 |
| **MCP Data Window** | 最后一个 MCP plot 之后 | 新增 `MCP OB Signal` / `MCP BOS/CHoCH` / `MCP Liq Void` 编码 plot |
| **alertcondition** | 最后一个现有 alert 之后 | 新增 BOS↑/↓、CHoCH↑/↓、OB 缓解告警 |
| **confirmScore** | confirmScore 定义行 | 追加 OB 汇合加分 `+ ((inBullOB and activeLongPlan) or (inBearOB and activeShortPlan) ? 1 : 0)` |
| **bcDirectRaw** | B/C 级挂价条件 | 追加 `(inBullOB or inBullBreaker or nearAKeyLevel)` 汇合条件 |

### OB HTF 确认缺失（2026-07-09 用户反馈）

用户指出「ob的设置和fvg差不多，高周期可以确认低周期」——当前 OB 没有 HTF 确认逻辑，而 FVG 有完整的 HTF 确认链。审计时必须检查 OB 是否有 HTF 确认。

**FVG 的 HTF 确认链（参考实现）**：
1. `f_htf_fvg()` 函数在 HTF 上下文检测 FVG，返回 `[bull, bear, top, bot]` tuple
2. `request.security(syminfo.tickerid, fvgHtfRes, f_htf_fvg(), lookahead=barmerge.lookahead_on)` 取 HTF FVG
3. HTF FVG 存入 `htfFvgList` 数组，维护填充/过期
4. 本级 FVG 维护循环中遍历 `htfFvgList`，检查重叠：`hz.isBull == f.isBull and f.top >= hz.bot and f.bot <= hz.top` → `htfConf = true`
5. `f.htfConf := htfConf` 写入 FVG UDT，影响标签文案（`"FVG↑ HTF"`）和 MCP 质量码

**OB HTF 确认实现模式（2026-07-09 实装，仿照 FVG HTF 完整链）**：

1. **`f_htf_ob()` 函数**：在 HTF 上下文检测 OB（pivothigh/pivotlow → BOS → 找最后反向K → 前一根 = OB），返回 `[obBull, obBear, obTop, obBot]` tuple
2. **新增 `request.security`**：`[obHBull, obHBear, obHTop, obHBot] = request.security(syminfo.tickerid, fvgHtfRes, f_htf_ob(), lookahead=barmerge.lookahead_on)` — 复用 FVG 的 `fvgHtfRes` 周期，+1 配额
3. **`htfObList` 数组**：维护 HTF OB 的填充/过期清理，与 `htfFvgList` 同构
4. **`SHOW_HTF_OB` 输入开关**：独立控制 OB HTF 确认；`fvgHtfValid` 改为 `(SHOW_HTF_FVG and SHOW_FVG) or (SHOW_HTF_OB and SHOW_OB) and timeframe > curTfSec`
5. **OBZone UDT 新增 `bool htfConf` 字段**：OBZone.new 从 8 参变 9 参（多一个 htfConf=false）
6. **本级 OB 维护循环中检查重叠**：`ohz.isBull == ob.isBull and ob.top >= ohz.bot and ob.bot <= ohz.top → ob.htfConf := true`
7. **标签加 `" HTF"` 后缀**：`obTag + (ob.htfConf ? " HTF" : "")`
8. **`inBullObHtf` / `inBearObHtf` 变量**：仿照 `inBullFvgHtf`，在 OB 维护中 `inBullObHtf := inBullObHtf or ob.htfConf`
9. **confirmScore 额外加分**：`+ ((inBullObHtf and activeLongPlan) or (inBearObHtf and activeShortPlan) ? 1 : 0)`
10. **bcDirectRaw 补 OB HTF 汇合**：`or inBullObHtf) and not adrLowRoomLong` / `or inBearObHtf) and not adrLowRoomShort`

**Token 预算管理（新增功能时）**：OB HTF 新增约 1,400 tokens。本轮从 79,380 → 80,731 超限，需削回 < 80,000。削减优先级：tooltip 截短（25→40字符省~200 tokens）→ 精简新增函数（合并 bull/bear 分支）→ 内联确认循环（`for` 替代 `while`）→ 删行内注释。**写盘前必须确认 `len(code)/2.33 < 79500` 留余量**。

**审计检查命令**：
```bash
grep -n "htfOb\|obHtf\|SHOW_HTF_OB\|ob.*htfConf\|inBullObHtf\|f_htf_ob" 主指标.pine
# 无输出 → OB 缺少 HTF 确认，应对齐 FVG 的 HTF 确认链
# 有输出 → 确认 f_htf_ob 函数 + htfObList + ob.htfConf + inBullObHtf + confirmScore 全链完整
```

## OB 检测算法（Pine v6 实测通过）

```
Bullish OB = BOS↑ 后往回找最后一根阴线（位移K），它前面那根阳线 = OB
Bearish OB = BOS↓ 后往回找最后一根阳线，它前面那根阴线 = OB
Breaker = OB 被反向突破（close 跌破 bull OB bot / 突破 bear OB top）→ 变色标记
缓解 = 价格回踩 OB 区（low ≤ OB top for bull / high ≥ OB bot for bear）→ 淡化
```

### 添加功能时的 token 预算管理

新增功能必然增加 token，需要同步削减以保持 < 80000：
1. **先加功能再削 token**：功能代码写完后重算 `len(code)/2.33`，超 80000 再削
2. **削减优先级**：删独立注释行（最高效，~1 token/行）→ 删空行 → 短缩 tooltip → 精简 string 拼接
3. **OB 代码本身约 3500 字符 / ~1500 tokens**：含 type 定义+检测+维护+LV

### execute_code 变量不持久陷阱

**重要**：`execute_code` 的 Python 变量在不同调用之间不持久。多步文件修改（如先插入代码、再修改面板、再加 MCP plot）**必须在同一个 execute_code 脚本中完成全部操作**。分步执行会导致后续步骤找不到前面步骤的 `lines` 变量，静默失败（插入不生效但无报错）。

**正确模式**：在一个脚本内完成 读取→修改→写入 的完整闭环。如果修改步骤太多，可以分多个脚本，但每个脚本必须独立读文件→改→写文件。

### patch 工具 vs execute_code replace 可靠性对比

**`patch` 工具（skill_manage action=patch 或独立 patch 工具）比 execute_code 内的 `code.replace()` 更可靠**，因为：
- patch 直接操作文件，不经过 Python 变量
- patch 有 fuzzy matching，容忍细微空白差异
- patch 返回 unified diff，可立即确认改动生效

**execute_code `code.replace()` 的陷阱**：
- 如果 `old_string` 在文件中出现多次，`replace()` 会全部替换（非预期）
- 如果 `old_string` 因编码/换行符差异匹配失败，**静默不替换但无报错**
- 多行 `old_string` 跨平台换行符（`\r\n` vs `\n`）可能导致匹配失败

**推荐流程**：大段插入用 execute_code（一次读完→改→写），小修正（1-3行）用 patch 工具。

### 桌面文件同步 + 「文件没有改到」交付铁律（2026-07-09）

**文件交付命名铁律（2026-08-02 用户两次纠正）**：改完指标文件后，修改日期写进**文件名**，不是 indicator 标题。正确：改完复制成 `SVP主指标_免费档优化版_20260806.txt`（今天日期），旧日期文件保留作历史。`indicator("...")` 内部标题保持原样，绝不在里面加日期（用户明确纠正过「不是哦，是在外面的文件标题」）。记忆已存短版；此处为可执行规则。

**根目录整洁铁律（同会话用户反馈「感觉有点乱」）**：指标文件散落 120 个在 `hermes下载文件/` 根目录 → 建 `历史版本/` 子文件夹，根目录**只留当前两个生产文件**（主+副最新版），其余全部 `mv` 进 `历史版本/`。交付时根目录一眼可辨该用哪个，历史版仍可回退。

**修改源文件后必须同步桌面**，否则用户拿到旧版。实案：`shutil.copy2` 失败 → 桌面未更新。

**更严重**：口头声称「已修好 FVG 标签/EMA 只云」却**未写盘** → 用户「文件没有改到」。默认=上轮交付失败。

**闭环（同一回合）**：① 写源（优先 Desktop `patch_*.py`+python，避 bash heredoc 截断）② 同步 `SVP_v6.pine` + `SVP_v6_ready.pine` + upload ③ sha 一致 + grep 关键串（`FVG↑`/`oiBrk`/`color.new(#00FF6A, 100)`）④ 再声称已修好。

### FVG/OB/LV 区标签 + EMA 只云（用户偏好 2026-07-10 最终）

**标签使用必要英文缩写**：`FVG↑/↓`、`OB↑/↓`、`BRK↑/↓`、`LV↑/↓`、`HTF`。这些是交易图面标准术语，用户明确允许必要英文；不要再强制改成“缺口/订单块/破坏块/真空/高周”。  
**位置：框内右下角**：禁止再用独立 `label.new()` 模拟框内文字——label 的锚点、样式切换与像素宽高会导致 `OB C`、`FVG A HTF` 等长文本部分越过 box 边界，而且维护循环可能把创建时的 `style_none` 覆盖回 `style_label_left`。必须将区域文字直接写进 box：`box.set_text(bx, txt)` + `box.set_text_halign(bx, text.align_right)` + `box.set_text_valign(bx, text.align_bottom)`，并设置 `box.set_text_color/size`。FVG、OB、BRK、LV 的创建与每根维护都使用 box 内建文字；对应 UDT 的 label 字段传 `na`。这样文字由 box 自身裁定在框内右下角，框天然包住文字。修改后 grep 必须满足：区域 `label.new(...FVG|OB|BRK|LV)` 为 0，旧 `ZONE_LABEL_X/Y` 坐标控制为 0，box 右下对齐调用覆盖四类区域。

**主执行体长度铁律**：上述五个 `box.set_text*()` 操作禁止在 FVG多空、OB多空、BRK、LV及维护循环中重复展开。必须封装成单一辅助函数（如 `f_set_zone_box_text(box,string,color,string)`）后调用，否则即使静态扫描通过，TradingView 仍可能报 `The main body of the script is too long. Use functions to reduce its size.`。静态扫描抓不到该限制；用户要求自己做视觉验证时，也不能把静态扫描通过说成 TradingView 编译通过。详见 `references/pine-zone-box-text-and-main-body-limit.md`。  

**P0 图面回归检查——创建正确不等于运行时正确（历史 label 实现，现已弃用）**：过去曾出现创建时 `style_none + align_right`，但维护循环每根K线又执行 `label.set_style(..., label.style_label_left)`，导致长文本重新越界。此案例说明创建路径与维护路径必须同时审计；但当前生产规则不再修补独立 label，而是统一迁移到 box 内建文字。若仍发现 FVG/OB/BRK/LV 的 `label.new`、`label.set_x/y/style/textalign`，视为待清理的旧实现，不得继续通过“左移几根K线”调参。  

**按用户指定验证边界执行**：用户明确说“只修改指标，验证我来”时，只做源码修改、静态扫描、同步与哈希核验；不要擅自更新 TradingView 图表实例、截图或做运行态部署。交付时直接给已同步文件和本次根因，避免把时间花在用户已接手的验证环节。  
**EMA 只云但周期必须可调**：EMA 线可用 `color.new(...,100)` 隐藏，只保留 fill；但 `EMA_LEN_1..4` 输入不能为削 token 而删除或硬编码。四个周期输入必须同时驱动主图 `ta.ema()`、HTF trend pack 与趋势裁决。云颜色 input 必须被 `fill()` 实际消费，禁止设置面板有颜色项而 fill 仍写死 hex。为 TV MCP 精确获知用户改后的周期，分别导出四个小整数 Data Window 字段，不要打包成会被 TradingView 缩写为 B/M 而丢位的大整数。  
**交付闭环**：真写盘 → 同步 upload/desktop → SHA 一致 → TV 云端重开比对 → 重载图表 study → 截图确认标签与 CVD 副窗。  
详见 `references/tv-cloud-chart-deployment-and-dual-indicator-audit-2026-07-10.md`。

## 决策就绪度仪表模式（2026-08-06 实案，用户「总感觉不怎么能让我下决策」时用）

当用户反馈"指标信息都看懂了但还是下不了决策"，根因几乎不是缺信息，而是**等待态太多 + 多因子堆叠没有一个收敛的决策数字**。行动格大量 `等触发（...）`、`等确认`、触发链 9 环节，用户不知道"现在几成把握、还差什么"。社区证据同指向此结论：CVD 背离无独立 edge、多因子堆叠 ≠ 可执行决策（Bookmap/TradeBobbyTerminal）。

**当前解法 = 先收敛成可解释的路径进度与唯一缺口，不是继续堆因子或制造伪精确百分比**：优先显示 `扫位✓ → MSS○ → 回踩○（1/3）`、事件年龄、剩余有效K数和 blocker。只有在分母随开关动态调整、方向完全对齐、且X/R:R/几何/新鲜度能强制归零时，旧式就绪百分比才可作为次要显示；不得把启发式百分比写成胜率、概率或A级授权。

以下“就绪度大字行”是历史实现模式，仅在满足上述合同后参考：

1. **就绪度大字行**（行动格顶部）：对触发因子计数 → 映射百分比 → 配色。实测 7 因子（扫位/MSS/位移/FVG/OB/CVD/上级），映射 `可做100% / 就绪85% / 接近55% / 等待25% / 禁做0%`（executablePlan=100、setupX=0）。一眼回答"做不做"。
2. **触发链清单行**：`触发 ✓扫位 ✗MSS ✗位移 ✗FVG ✓OB ✓CVD ✗上级` 勾选式。回答"还差什么"。
3. **置信度追加**：方向行加 `置信X%`（由 setupTotalScore×10 映射）。回答"敢不敢"。

**副指标共振度必须方向对齐（2026-08-07 逻辑反例修正）**：不得把“CVD有方向、OI有变化、放量或缩量、HTF有方向、未触发LSR风险、未触发低覆盖”简单相加后称为共振；这只是状态/健康项数量，可能出现“强确认多”同时 CVD 向下或 HTF 向空。真正共振票必须按当前价格方向逐项镜像：多向只计 `cvdUp`、OI扩张且一致、`volUp`、`htfBull`；空向只计 `cvdDn`、OI扩张且一致、`volUp`、`htfBear`。缺失 LSR/覆盖数据不得自动得分。若保留原存在性计数，行名必须改为“数据项/健康度”，不能叫“共振”。`finalStrong` 与 `htfConflict` 也必须直接按方向硬门控，不能仅在 `vGood/vBad` 已成立时才检查高周期反向。

**插入位置**：就绪度/触发链定义必须放在 `f_pnl_row` 定义之后、第一个 `f_pnl_row(...)` 调用之前；引用的全局（executablePlan/setupX/setupTotalScore/mssLongOk 等）必须已在其前定义。表格行序（定版 2026-09-11）= 位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位；入场/止损/目标/R:R 已折进「风控」行，不再单列。

**Pine 陷阱**：副指标插入共振度行后，表格后续所有行的行号要整体 +1（table.cell 的 row 索引、table.clear 范围、opRow 计算），且 `resoXxxA` 变量命名注意拼写（`resoLsraA`→`resoLsrA` 曾写错）。改完静态扫描确认 def-before-use none。

**P0 前向引用盲区（2026-08-06 副指标实案，pine_static_scan.py 抓不到）**：新增共振度行时写了 `color resoColA = resoCountA >= 5 ? cGood : resoCountA >= 3 ? cWarn : cBad`（L447），但 `cGood/cWarn/cBad` 在 **L494-496 之后**才定义（配色块在行动格渲染块之前）。Pine 自上而下编译 → `Undeclared identifier` → 副指标挂不上图。**关键：静态扫描器只检查 panelDirVal/panelConclusionVal/panelEntryVal 三变量，完全不覆盖新增的共振度/就绪度行引用的共享色值或辅助变量**——报 `未定义变量 none`、`def-before-use none` 全绿，但 TV 编译必炸。审计任何新加行动格行（共振度/就绪度/触发链）时，必须**手工核对新行引用的每个变量名（尤其 color cGood/cWarn/cBad、cLabel/cVal 这类配色块成员）的声明行号是否在引用行号之前**。通用命令：`grep -n "color cGood\|color cWarn\|color cBad" 副指标.txt` 与引用行对比行号；或用 execute_code 粗扫「引用行 < 声明行」的全量前向引用（注意单遍脚本可能漏报声明在后的名字，需两遍：先收集所有声明+引用行号再比对）。修法：把配色块（cLabel/cVal/cGood/cBad/cWarn 五行）整块上移到共振度块之前即可。

**就绪度行别和确认行功能重复**（2026-08-06 实案，用户「行动格太多行」时先查这个）：新增的 `触发 ✓扫位 ✗MSS...` 勾选清单行，与**已有的确认行**（`panelCheckText`，HTF✓/CVD✓/位置✓/MSS/FVG/扫位/位移/PD/ADR/SMT 10 因子勾选，且带警告色）是同一类信息的两种拷贝——触发行只有 7 因子、无警告色，纯冗余，删掉不丢信息。**加任何勾选式/清单行前，先 grep 是否已有 `panelCheckText` 之类更全的确认行**；若有，别再新增。

**「结论+解除」两行可合并**（同会话）：结论行说"为什么不能做"（`X R:R不足`），解除行说"等什么"（`等更好价，R:R≥2R`）——同一等待的两种表述。合并为 `actionStateText + " · " + panelUnlockText`（只在 `panelNeedUnlock` 时拼接），信息零丢失，11→10 行。合并时 `panelUnlockText` 定义必须移到 `panelConclusionVal` 之前（def-before-use）。

**移动变量定义的重复定义陷阱（2026-08-06 实案，静态扫描没抓到）**：用「删除旧定义 + 插入新定义」挪动一个变量（如 panelConclusionVal）时，若删除用的 old 字符串与文件实际内容有细微差异（旧版无拼接、新版带拼接，子串互相包含），`src.replace(old,'')` 可能没删掉旧定义 → 磁盘上**新旧两个定义并存** → Pine 重复定义编译错误。静态扫描的"可疑引用"能抓到"引用无定义"，但**抓不到"定义重复"**（它报的是未定义，不是重复）。修法：挪动定义后必须 `src.count("string VARNAME") == 1` 验证唯一；且新旧两版子串互相包含时，删除用**带上下文前缀的完整行**（含 `string VARNAME =` 开头到行尾）精确匹配，不用可能撞到新定义的短子串。

## 「一直等方向」静态默认文案陷阱（2026-08-06 实案，用户「一直等方向怎么办」时用）

**症状**：行动格进场行永远显示 `等触发（等方向）`，用户觉得指标"不让我下决策"。

**根因**：`expectedTriggerPath` 初始值 = `"等方向"`，但**只在 `if planSideLong` / `else if planSideShort` 分支内被覆盖**。当指标没给任何 A/B/C 计划（`planSideLong/Short` 均为 false）时，文案永远停在初始值——不是市场没方向，是文案逻辑只服务"有计划"场景，无计划时就是空话。**这是"静态默认文案只在特定状态分支更新"的通用陷阱**：审计任何行动格/面板文案时，若某行长期显示初始值，先查它是否只在 `if <计划/状态>` 内被 `:=` 覆盖，无该状态时是否永远停在初始值。

**修法**：无计划时也按市场实际状态给具体等待路径（优先级从高到低）：
```pine
string expectedTriggerPath = "观望 等方向明确"
if planSideLong
    expectedTriggerPath := sweptLowReclaimed ? "已扫低→等MSS↑" : ...   // 原有路径不变
else if planSideShort
    expectedTriggerPath := sweptHighRejected ? "已扫高→等MSS↓" : ...
else if trendLongScore >= trendShortScore + 2
    expectedTriggerPath := adrExhausted ? "趋势偏多·ADR耗尽 等回踩" : "趋势偏多 等回踩→MSS↑"
else if trendShortScore >= trendLongScore + 2
    expectedTriggerPath := adrExhausted ? "趋势偏空·ADR耗尽 等反抽" : "趋势偏空 等反抽→MSS↓"
else if priceInVA
    expectedTriggerPath := "价在价值区 等出区→扫位/位移"
else if dmiTrendWeak
    expectedTriggerPath := "DMI走弱 等趋势重启"
else
    expectedTriggerPath := "观望 等扫位/关键位反应"
```
效果：无计划时也显示 `等触发（趋势偏多 等回踩→MSS↑）`，告诉用户市场状态 + 具体等什么动作，而非干巴巴的"等方向"。依赖变量（trendLongScore/priceInVA/adrExhausted/dmiTrendWeak）必须定义在 expectedTriggerPath 之前（本实案都在 L2586 前，安全）。

**⚠ 两层嵌套陷阱（同会话，用户两连报「还是一样 等方向」）**：只改 `expectedTriggerPath` 远远不够——**行动格真正显示的是 `panelEntryVal`，而它有自己的硬编码初始值 `"等触发（等方向）"`，且只在 `if panelLongSide or panelShortSide` 分支内被 `:=` 覆盖**。无计划时 `panelEntryVal` 永远停在初始值，哪怕 `expectedTriggerPath` 已加市场状态分支也不会被调用。这是「静态默认文案只在特定状态分支更新」陷阱的**第二层**：诊断任何「改了一处还是没变」的文案问题，必须顺消费链往下查——修的是 `expectedTriggerPath`（中间变量），显示的是 `panelEntryVal`（行动格变量），中间还隔一层 if。修法：把 `panelEntryVal` 初始值改为**无条件引用** `expectedTriggerPath`，拆掉 if 包装：
```pine
string panelEntryVal = triggerCode == 0 ? "等触发（" + expectedTriggerPath + "）" : not triggerFresh ? ... : ...
```
（原来 `panelEntryVal :=` 整块在 `if panelLongSide or panelShortSide` 内，拆掉外层 if 后无条件更新。）**审计文案类 bug 铁律：永远查「哪个变量喂给 table.cell/f_pnl_row」，不是改你第一眼以为的变量。** 修完 `src.count("string panelEntryVal")==1` 确认无重复定义。

## Pine 表格宽度 = 最宽单元格文本（2026-08-06 实案，用户「表格有点宽了」时用）

**Pine 表格（table）单元格不换行、不缩列，整表宽度由最宽的单元格文本决定。** 用户反馈表格变宽时，不是布局设置问题，而是某行文本过长撑宽。诊断：逐行动态文本算显示宽度（中文≈2px/字、英文≈1px/字，`sum(2 if ord(c)>127 else 1 for c in text)`），找出最宽行。主/副指标行动格最宽行 = 撑宽元凶。

**撑宽根因几乎总是「重复信息拼接」，不是单个信息本身**——本例两处：
1. **确认行**：`panelConfirmText = panelCheckText + " · FVG " + panelFvgShort`——`ckFvg` 里已有 `FVG✓` 勾选，又额外拼 `· FVG A·85` 分数。分数不进决策（警告判定只看 `✗` 和 `C级`），纯冗余。删掉 `· FVG A·85` 拼接 + `panelFvgShort` 死变量，宽度大降。
2. **方向行**：`偏多 6/10 置信60%`——同一个分数显示两遍（`setupTotalText` 的 `6/10` 和 `confPct` 的 `置信60%`）。删 `6/10`（`panelScoreVal` + `setupTotalText`），保留 `置信60%`。

瘦身 = 删重复片段，**不动决策逻辑**。删冗余变量后必须全量 grep 残留（本例 `panelScoreVal`/`setupTotalText` 删除时两次未写盘，需重读磁盘再删，见下方铁律）。

**删变量连带修引用时「两次未写盘」陷阱（同会话连踩）**：`src.replace()` 在内存修改成功但中间 `assert` 失败就丢弃所有未写盘改动。修复 panelDirVal 引用已删变量时，第一段 `replace` 未 `open(...,'w')` 写盘、第二段只删了定义没删引用 → 磁盘停在「定义已删、引用残留」态。每段改完必须 `open(path,'w').write(src)` 落盘，再验证 `src.count("VARNAME")==0`。表格瘦身多段替换时，每段独立「读→改→写→grep 残留」，不要一个脚本里多个 `sub` 最后才写盘。

## 社区 2025-2026 前沿研究（2026-07-09 扫描）

### Pine v6 新能力（社区尚未广泛使用）
- **`request.footprint()`**（2026 初上线，需 Premium/Ultimate）：获取 TradingView 按低周期价格行为分类的 buy/sell volume、delta、POC、VAH/VAL 与逐行失衡；比单根OHLC估算更细，但不可笼统称为交易所逐笔 bid/ask 真Delta。通用生产版不直接依赖，宜另做 Footprint Pro。
- **`dynamic_requests=true`**：`request.security()` 可用 `series string` 动态切换 symbol，放入循环/条件
- **`log.info()`/`log.warning()`**：运行时日志调试
- **`bid`/`ask` 变量**：仅 1T tick 图可用
- **无 scope 数量限制**：v6 移除了 550 scope 上限

### ICT 社区 2026 共识（Top 30 策略文章）
- 基础5件套：Market Structure / Liquidity / FVG / KillZone / Displacement
- Block 6 种：OB / Breaker / Mitigation / Rejection / Propulsion / IFVG（Inversion FVG）
- 高级概念：Volume Imbalance / Liquidity Void / BPR / Immediate Rebalance
- 模型：2022 Model / Unicorn / MMXM / ICT Execution 1-2-3
- **你已有**：FVG+HTF确认 / 扫流动性 / MSS / VWAP / CVD / OI / KillZone / Macro
- **本次新增**：OB / Breaker / BOS / CHoCH / Liquidity Void
- **仍缺**：Mitigation Block / Rejection Block / IFVG / Volume Imbalance / Inducement(IDM) / NWOG/NDOG

### 性能优化（LuxAlgo 社区共识）
- 自定义循环比内建函数慢 18-100x：用 `ta.highest()` 替代手写循环
- 合并 `request.security()` 为 tuple 调用：9→1 可从 340ms 降到 228ms
- Pine v6 request 配额按运行时 unique context 计：条件分支未执行时可不形成请求；但同一动态调用若访问多个不同 symbol/timeframe，会按不同上下文累计，且实时不得首次访问历史阶段未预取的新上下文
- `memory.log()` 监控实际内存用量（v6 新增）
- 预分配数组大小比动态 push 更高效

## TradingView 三层部署闭环（编辑器 / 云端 / 图表实例）

完成 Pine 修复后必须分别验证三层，禁止把“编辑器编译通过”误报为生产部署完成：

1. **编辑器缓冲区**：`pine set` 只证明 Monaco 中已写入。
2. **云端原生产脚本**：点击 Pine 自己的“保存脚本”，切到别的脚本后重新打开目标；统一 CRLF/LF 后与交付文件做字节或 SHA256 比对。
3. **图表 study 实例**：旧实例可能继续运行旧版。新增 Data Window plot 后，移除旧 entity，再从已确认的原生产脚本重新“添加到图表”。

部署后必须同时满足：

- `chart_get_state` 中主、副指标各只有一个实例；
- 主指标 Data Window 出现 `MCP CVD Method Code...`；
- 副指标出现 `OI Change % (Normalized)`、`HALDRO Risk Code`、`HALDRO Valid Code`；
- 5m/15m/1h/4h/D 五周期均能读取；
- 临时优化副本只能用于中转验证，最终图表必须回到原生产脚本身份。

完整 UI 切换、保存、重开、换行归一、实体重载步骤见 `references/tv-cloud-chart-deployment-and-dual-indicator-audit-2026-07-10.md`。

### P0：多 Monaco 编辑器选择与云端保存

TradingView Desktop 可能同时保留叠加层、分割视图和隐藏旧脚本的多个 Monaco editor。任何客户端若固定使用 `monacoEnv.editor.getEditors()[0]`，可能把主指标名称下的云端源码覆盖成副指标，或让 `pine get` 读到隐藏模型。

部署前必须检查每个 editor 的 DOM rect，选择 `width>0 && height>0` 的当前可见编辑器；不得默认 `[0]`。`pine set success` 只表示某个 model 被写入；若保存按钮仍 disabled，TradingView 没有进入 dirty 状态，`Ctrl+S` 不能证明云端已保存。最终证据只能是：切到另一脚本→重开目标→可见 editor 源码完整→CRLF/LF归一后SHA与本地一致→真实编译无错。

脚本列表 `name/title` 错配、主脚本重开后只有约529行、或源码头出现 `@HALDRO Project`，均按P0云端身份污染处理，立即停止继续保存并以本地权威文件恢复。详细诊断、选择器和Unicode陷阱见 `references/tradingview-multi-monaco-cloud-save-safety.md`。

## HALDRO 跨所 OI 与真实 HTF 新准则

- 不同交易所及 USDⓈ-M/COIN-M 原始 OI 单位可能不同；跨所方向和背离不得使用 raw OI 直接求和。
- 每所先计算 OI 百分比变化，再对有效交易所等权或显式权重聚合。**`OI Total` 已废止**（当前字段是 `OI Change % (Normalized)` + `OI Breadth` + `OI Agreement %`）。
- 用 `ACT_LB*6` 回看当前周期不算 HTF；必须使用真实 `request.security()` 请求下一层周期，并采用确认值。
- HALDRO Risk Code 统一位图：`1低覆盖 / 2单所主导 / 4上级冲突 / 8 OI背离 / 16 CVD背离 / 32非加密 / 64 LSR拥挤`。下游必须按位解码，并将 `4/8/16/64` 纳入 A 级降级或 X 禁做门控。

## vNext 决策正确性审计（2026-07-10 新增）

审计不应止于编译、配额和图面；以下四项会直接改变交易裁决：

1. **CVD过滤消费链**：若已定义摆动幅度门控（如 `cvdDivSwingOk`），必须确认正式 `Qualified` 背离实际引用；同时核对熊背离 `cvdSlope < 0`、牛背离 `cvdSlope > 0`。
2. **背离强化事件配对**：熊背离配卖方派发，牛背离配买方吸收；反配会错误升为3星。
3. **ADX过热语义一致**：不得一边仅将“过热+远离”列为X，一边却在A级无条件 `not dmiHot`。只禁沿交易方向追价，高质量回踩可保留。
4. **Magnet原子选择**：name/price/dist/score 必须在同一候选分支一起更新，禁止最近位与全局最高分错配。

**主副职责铁律**：主指标内仅通向死文本、且已由 Python 资产路由或 HALDRO 覆盖的 DXY/VIX/永续溢价/重复OI请求，应物理删除；不得删除 HALDRO 的聚合OI、LSR、Valid Code、Risk Code。

详细复现、代码模式与安全清理流程见 `references/pine-v16-1-decision-correctness-2026-07-10.md`。

## 决策完整性增量检查（2026-07-19）

大型 SVP/ICT/CVD 指标即使编译、request、plot 全部过关，也必须追加以下逐链检查：

1. **当前 Profile 历史/实时同构**：若 `processAndRender()` 或 POC/VAH/VAL 数值计算只在 `barstate.islast` 执行，而历史K只存储数据，则实时行动格、重载历史、回放和 MCP 历史值不一致。数值计算须每根K确定性执行；仅对象绘制可留在 `barstate.islast`。
2. **Value Area 官方口径**：以 TradingView 当前官方文档为准——比较 POC 上下候选桶；若加入候选桶会超过剩余目标量，则停止，不纳入该桶。若代码无加桶前阈值检查而直接累加，会让 VAH/VAL 相对官方口径偏宽。其他平台采用“首次达到/超过”时必须标为自定义算法。
3. **R:R 方向几何**：`abs(entry-stop)` / `abs(target-entry)` 会掩盖方向错误。执行前强制多单 `stop < entry < target`、空单 `target < entry < stop`；止损 ATR 距离按 entry，不按当前 close。
4. **唯一执行价格源**：行动格、MCP、提醒、回放必须共享同一 `finalEntry/finalStop/finalTarget`。若行动格显示 FVG CE/扫线价/VA边，而 R:R 用另一 candidate price，标 P1。
5. **扫线单状态机**：绘图端与决策端必须共同消费 `SWEEP_MARK_MODE + confirmed + reclaim/accept`；事件扫描要排除已扫水平，避免图线未扫但评分已扫、或重复扫线。
6. **CVD门控全消费链**：定义 Qualified 信号后，继续检查 `cvdLongOk/cvdShortOk`、结构、B/C、直接挂单、冲突、提醒和 MCP 是否仍消费 raw divergence/absorption。低质量时应中性退化。
7. **Magnet目标原子绑定**：目标 name/price/score/dist/HTF 必须来自同一方向候选。提醒不得读取“最近位分数”去代表“方向目标分数”，且目标方向要相对最终 entry 校验。
8. **跨资产识别与成交量单位**：ticker 任意子串（如含 `GC`）不可直接判贵金属；使用 `syminfo.type/root/exchange` 精确路由。`volume*price` 不可无条件用于反向合约/张数期货硬门控。
9. **验证措辞**：没有 TradingView 服务器回执时，只能写“静态未发现 P0”，不得写“编译通过”。

完整复现模式、价格口径表和审计示例见 `references/svp-decision-integrity-audit-patterns-2026-07-19.md`。

**v2 基线（2026-08-08 上传版）**：主指标 SVP+ICT+VWAP+CVD v2 = 3,033 行 / 199KB / 9 request(7+2 ltf) / 37 plot(27 DW) / 0 alertcondition / 0 死函数 / 0 死变量。副指标 AggVol v2 = 655 行 / 49KB / 7 request / 40 plot(22 DW) / 0 alertcondition / 2 死变量(maxValidExchangeSeenA/maxOiVenueSeenA)。两指标均 `//@version=6` + `dynamic_requests=true`，alertcondition 已全部事件化为 `alert()`。详见 `references/decision-support-gap-analysis-2026-08-08.md`。

**v2 基线（2026-08-09 上传版，最新）**：主指标 = 3,065 行 / 202KB / est≈86.7K tokens / 8 request（6 security+2 lower_tf，默认≈8 unique/40）/ 43 plot（7 series：4 EMA+3 VWAP_COLOR 变量色）/ 最坏 **55/64 余 9**（50 plot + fill 2×2 + bgcolor 1）/ 29 DW / 0 alertcondition / 2 alert() 事件化 / 死变量 6 个+1 死输入（会话 CVD 链）。副指标 = 686 行 / 52KB / 7 request（GetExchange 展开 20 + OI4 + LSR1 + spot1 + oiSingle1 + HTF1 = **29/40 默认**，EUR/RUB 最坏 +1）/ 41 plot（12 series：Volume/SPOT/PERP/DeltaSP/PerpSpot/Delta/CumDelta/EX×5）/ 最坏 **53/64 余 11** / 23 DW / 0 alertcondition / 0 死变量。20260809 新增：CVD 锚定双指标同步（主 L751 与副 L37 同口径）、input.active 灰化 15+ 输入。

**v16.1 本地生产验收基线（2026-07-11）**：主指标 2835 行、`request.*=8`、plot 33、fill 2、bgcolor 1、alertcondition 16、最低绘图估算 52/64、def-before-use=0、未定义变量=0；本地权威 SHA256 `4e9abbbe6130522ac08f78c2dcf5810ffff60fcc46c04b07ce275b210a6d46ac`。副指标 529 行、展开请求约32/40、最低绘图估算44/64；本地权威 SHA256 `2af4a1ae085cfc820ad552423a705375e1a26a3aaac171f677020c70d2807fee`。主指标已物理删除DXY/VIX/重复OI/永续溢价4条外部确认链，由Python/HALDRO承接。**云端是否一致必须每次按“重开脚本→选择可见 Monaco→归一化SHA”重新验证，不能沿用历史成功结论。** BTC与XAU五周期 Data Window 曾实读成功，但旧图表实例正常不等于云端源码正确。

## SVP/ICT v2 深审新增必查项（2026-08-07，2026-08-10 精简）

大型主指标即使服务器编译与普通静态扫描通过，也必须补做敌对场景：

1. 单 K Profile：数值计算不得因 `endBar > startBar` 绘图条件被跳过。
2. B/C 人工候选：测试 R:R=1.2/1.5/2.0，低于下限不得导出完整 Entry/Stop/Target。
3. 最终合同：X 优先方向，NoTrade/EntryValid/Side 不得互相矛盾。
4. nPOC：触碰前冻结 approachSide；数量上限按 active 对象治理。
5. CVD pivot：两个 pivot 必须同 anchor，并保存各自 method/sample/quality。
6. mintick：Entry/Stop/Target 量化后重验几何和 R:R。
7. readiness/路径：几何、R:R、新鲜度、收线覆盖就绪度；已挂单不再写“等 MSS/回踩”。
8. 假功能：显示输入、PERP→spot、风险 pack 必须区分 Pine 内执行与外部元数据。
9. 性能：未跑 Profiler/Add-to-chart 只能标风险，不得断言通过或超时。
10. 市场/告警/MCP/配额：资产类别与交易时制拆分；每事件独立边沿；方法码/单位真实；plot 扫描不得漏 `p=plot(...)`，死代码须含 UDT 字段。

基础矩阵见 `references/svp-v2-static-decision-contract-audit-2026-08-07.md`；2026-08-10 增量边界见 `references/svp-main-targeted-audit-edge-cases-2026-08-10.md`。

## 参考支持文件

- `references/dual-indicator-audit-2026-08-09.md` — 2026-08-09 联网审计实录：P1 全项通过核对表（executablePlan rrHardOk / MCP Side X 优先 / X 价格清空 / panelEntryVal 无条件 / LSR 方向 / 共振票镜像 / OI 四象限 / alert 事件化 / HTF 死请求已删 / CVD 锚定同步 / input.active 灰化）、会话 CVD 死链（L918-931）拍板项、pending P2 清单（非加密门控/resoLsrA 缺失全绿/freshness 值变化年龄/lookahead_off 延迟/位置行撑宽）、联网核验 4 条 URL。
- `references/dual-indicator-v2-source-audit-signatures-2026-08-08.md` — 双指标能编译后仍需追查的执行合同与数据质量签名：X/MCP优先级、人工候选与机器导出分离、单K Profile、nPOC触碰快照、OB原子Entry、mintick量化、真实freshness、OI空向四象限、非加密请求短路及TV服务器编译闭环。
- `references/svp-v2-static-decision-contract-audit-2026-08-07.md` — 单K Profile、B/C RR旁路、X/Side/NoTrade合同、nPOC触碰、OB原子价格、CVD跨锚质量、mintick、readiness、基差/风控消费链与Basic性能的深审签名。
- `scripts/pine_static_scan.py` — 审计第0步：一键输出配额展开/plot/对象计数/重复def/def顺序/重绘信号。`python pine_static_scan.py 主指标.txt 副指标.txt`（注意：正则双重转义可能导致 re.error，失败时改手工 grep）
- `scripts/clean_dead_narrative_card.py` — 安全批量删旧叙事卡死代码，内置三道护栏（消费检查/误删跳过/残留回扫），删完自动跑前需人工复核配额。
- `references/svp-v6-vs-fixed-audit-2026-07-09.md` — 2026-07-09：Desktop fixed vs v6 vs 上传权威字节对照、BOS/CHoCH 优先级 bug、DO/nPOC set_x2、MCP 对照、token 余量、生产选用口径。
- `references/svp-v6-plot-limit-and-audit-2026-07-09.md` — 2026-07-09：TV「绘图71/64」急救（series 色常量化 + bgcolor 合并 + MCP StructPack）+ 最坏计数公式 + auto_card 字段兼容。
- `references/svp-v6-plot-limit-loop-fvgob-2026-07-09.md` — 2026-07-09：写盘交付、for step、EMA 只云、bgcolor 定义序。
- `references/pine-plot-quota-zone-labels-loop-step-2026-07-09.md` — 2026-07-09 汇总：71/64、step 循环、区标签**英文+框内右下角**、EMA 只云、写盘闭环。
- `references/haldro-v6-deadcode-cleanup-2026-07-08.md` — 2026-07-08 实案：HALDRO v6 `ta.highest/ta.lowest` 内联条件→全局赋值修复（防 has_errors 挂图失败）+ 主指标叙事卡死代码清理协议 + 风控参数死代码改标注不删。
- `references/pine-undefined-identifier-audit-2026-07-09.md` — 2026-07-09 实案：主指标 `cvdBearStars`/`cvdBullStars` 未定义引用致致命编译错误。检测方法、修复模式、未定义变量与 def-before-use 的区别。
- `references/pine-token-limit-reduction-2026-07-09.md` — 2026-07-09 实案：主指标 81303→77455 tokens 削减全流程。死变量批量检测脚本、空 if/else 链清理、面板档位精简、token 密度基准 2.33 字符/token。
- `references/svp-row-collapse-mcp-integrity-2026-07-09.md` — 2026-07-09 实案：小币种 SVP 行数坍缩根因（minStep 固定下限）+ 自适应修复（minBuckets 保底 20-23 行）+ token 削减后 MCP Data Window 11+17 plot 完整性验证。
- `references/pine-security-quota-reference.md` — Pine security 配额静态计数详细规则 + 社区源
- `references/community-optimization-checklist-2026.md` — 六社区 2026 下单辅助优化清单
- `references/npoc-semantics-state-official-alignment.md` — POC/pPOC/nPOC语义、官方Periodic VP精度对齐与行动格触发路径。
- `references/single-timed-npoc-lifecycle.md` — 当前生产版单一限时nPOC：固定1个、8根K短虚线、触碰冻结、ICT隐藏联动、消费端与回归断言。
- `references/dual-indicator-lsr-gonogo-lessons-2026-07-06.md` — SVP/HALDRO 双指标迭代记录：主指标 gapThrough 视觉修复、副指标 LSR 多空拥挤、auto_card LSR 桥接、GO/NO-GO 8闸门一致性。
- `references/svp-v6-ready-fix-session-2026-07-09.md` — 2026-07-09：SVP_v6_ready.pine 全量修复（Token超限/BOS-CHoCH优先级/OB汇合/风控MCP编码/CVD星级/def-before-use/CW10002/FVG标签定位）。
- `references/svp-v6-full-audit-2026-07-09.md` — 2026-07-09：SVP_v6_ready.pine 编译通过后全量审计。Token模块分布、FVG/OB/LV逻辑链、评分体系、重绘审计、5个死函数(352 tokens)、可删项分级矩阵(保守/中等/激进)、社区对标结论。
- `references/svp-v6-token-reduction-deletion-2026-07-09.md` — 2026-07-09：删7项(~1,905 tokens)执行实录。三大执行陷阱(残留引用/缩进错位/多行replace失败)、EMA单线input删后plot条件修改、删后保留功能清单。
- `references/dual-indicator-full-audit-2026-07-10-session2.md` — 2026-07-10 第二轮：上传源码实测基准、全项通过清单、LSR方向仍反转、6死函数(含f_rebuild_polyline)、VAREUR/VARRUB配额浪费、副指标plot槽偏紧57/64、推荐修复优先级。
- `references/dual-indicator-decision-closure-audit-2026-07-10.md` — 成熟主/副指标+TV MCP+Python裁决的闭环审计：computed-but-unused过滤、字段映射未消费、Valid Code门控、final_verdict硬覆盖、体制实盘/回测一致、置信校准与同构回放。
- `references/dual-indicator-execution-state-oi-consensus.md` — vNext执行状态机与用户偏好：Entry Valid/No-Trade/Trigger码、触发时效、价格枢轴锚定CVD、跨所OI一致性/离散度、数据新鲜度、影子体制、plot预算、外部裁决验证器，以及行动格保留直白“爆仓”文案。
- `references/dual-indicator-community-official-evidence-2025-2026.md` — 2025–2026联网证据库：TradingView官方Footprint与Pine限额、社区聚合CVD/OI诚实口径、Bookmap/ATAS经验、GitHub freshness/回测架构，以及双指标真正值得新增/删减的裁决规则。做“最新社区与官方标准”研究时优先读取。
- `references/dual-indicator-evidence-benchmark-2026-08-07.md` — 2026-08-07增量核验：官方Footprint博客与技术文档措辞冲突、Basic实时档位、Bybit OI单位/真爆仓接口、Setup≠Edge、主副指标对标线、消融/WFO/OOS/PBO/DSR最低验收。做双指标证据对标或诚实口径审计时，与上一份证据库一起读取。
- `references/svp-zone-controls-community-ranking-2026-07-10.md` — 最终图面规则（英文标签框内、FVG/OB数量与延伸、EMA可调）、HTF开关串线/BOS显示语义审计、死设置扫描、OB/FVG社区质量排名与Footprint Pro策略。
- `references/fvg-ob-label-runtime-style-regression-2026-07-10.md` — FVG/OB 创建样式正确却被维护循环 `set_style` 覆盖的历史复现；当前应迁移 box 内建文字，不再继续修补独立 label。
- `references/pine-zone-box-text-and-main-body-limit.md` — 区域文字真正内嵌 box 的标准实现、最长标签验收、OB HTF链，以及重复展开 `box.set_text*()` 导致 Pine 主执行体过长的函数化修法。
- `references/pine-v6-official-constraints-dual-indicator-audit-2026-07-21.md` — TradingView官方最新约束增量：Pine v6动态request unique-context语义、HTF确认发布时序、LTF intrabar/calc_bars_count、告警快照与事件化、Footprint单调用边界，以及当前双指标59/64与约58/64绘图预算复核。
- `references/tradingview-plan-tier-limits-free-account.md` — 2026-08-02：官方定价页逐档限额实测（免费Basic=0脚本告警/5000历史K/20s计算/2指标·图）。免费账号下 alertcondition 纯死重、lower-TF 必须加 calc_bars_count。审计前必读，尤其是用户为免费账号时。
- `references/free-tier-pine-optimization-playbook.md` — 免费档三刀手术全实录：alertcondition→事件化alert()（释放plot count，免费档0技术告警）、lower_tf加calc_bars_count降intrabar、and/or优先级与islast门控两大坑、剥离注释/字符串后数括号平衡、免费档数据规划与诚实告知边界。
- `references/free-tier-performance-squeeze-2026-08-06.md` — 免费档性能榨干社区研究+双指标实测：Pine Profiler/LuxAlgo 5成因/calc_bars_count/动态request 官方证据；**已落地**优化（histogram 数组移入 renderProfileObjects 门控、FX_CONV_RATE USD短路、EXlist.sum 提循环）+ 未落地候选（合并 request tuple）。做「榨干免费档性能」或「指标太慢」研究时读取；改前先看哪些已实施，别重复应用。
- `references/multi-market-adaptation-crypto-metals-2026-08-02.md` — 多市场自适应（加密+贵金属重点）：calc_bars_count 硬编码截断 SVP 分布图数据的 P0 回归与动态修复、注入变量 def-before-use 陷阱、贵金属现货 CVD 诚实化（`现货无逐笔`）、SMT 期货/现货分流（GC1!→COMEX:SI1!）、funding 代理（现货-永续基差，Pine无funding API）与市场隔离铁律。
- `references/svp-action-panel-consumer-chain-audit-2026-08-02.md` — 2026-08-02 全量审计：P0 行动格 CVD 行静默消失、P1 时间锚 3 处不一致、23+7 死代码清单、模块保留裁决。审计前必读——尤其行动格消费链检查方法。
- `references/pine-ce10295-functionization.md` — CE10295 函数化配方：函数不能改全局（→局部+tuple返回）、元组16上限；选块标准；三块模板；静态扫描测不到必须贴TV实测。
- `references/module-value-classification-audit-2026-08-02.md` — 内嵌模块价值分类审计（用户问「哪个小指标有用哪个没用」时用）：按 input 分组盘点→逐模块追踪决策消费链→分三桶（决策核心/纯展示/无用）→结合交易逻辑给建议。附 12 模块实测权重表与「有消费端≠模块有用」陷阱。
- `references/multi-search-backend-fallback-pine-2026-08-02.md` — 多搜索后端回退取证：Firecrawl 被 ban 时 Tavily/Exa/Brave 直连轮换、Reddit 403 用 Tavily include_raw_content 绕、web_search 改 .env 需重启。
- `references/tradingview-multi-monaco-cloud-save-safety.md` — TradingView同时存在可见/隐藏Monaco模型时的安全选择器、dirty保存判定、重开SHA闭环、脚本身份错配与Unicode粘贴陷阱。
- `references/comprehensive-audit-deliverable-format.md` — 全方位多维度 Pine 审计（"10 条建议/推荐增强/不要回测"模式）的 8 段交付骨架、量化扫描脚本、2026 社区 Top SMC 基准脚本对比表、增量优化候选矩阵、避坑清单。
- `references/dual-indicator-20-enhancements-2026-08-08.md` — 双指标 20 条决策向增强/强化路线图（决策辅助 10 条 + 主副协同 3 条 + ICT/SMC 4 条 + 数据/性能 4 条 + 可视化 3 条）+ 社区证据与优先级路线图。做"10 条建议 / 推荐增强 / 怎么优化决策 / 还差什么功能"研究时读取。
- `references/decision-support-gap-analysis-2026-08-08.md` — 决策辅助审计三原语（多远/多久了/该不该现在动）+ 功能缺口分析方法论（覆盖度图谱→社区对标→零成本增强识别）+ v2 基线 + 10 项缺失功能（Taker Ratio/OI动量/波动率分位/费率极端/HVN-LVN/锚定VWAP/清算级位/BTC风向/会话VP/复合VP共振）。做"还差什么功能/怎么辅助决策/缺什么指标"研究时读取。

## 全方位多维度审计交付格式（"10 条建议 / 推荐增强" 模式，2026-08-08）

**触发条件**：用户说"全方位审计 / 联网社区全面查 / 10 条优化建议 / 推荐增强 / 需要优化吗 / 指标本身优化"，且明确**不要回测/复盘**，只看指标本身。

### 8 段输出骨架（缺一段不算合格审计）

1. **量化基线表**：行数 / 字符数 / token 估算 ÷ 2.33 / request 静态调用点 / plot 总数 / series-color plot / alertcondition / alert() 事件化 / fill / bgcolor / line / label / box / polyline / MCP Data Window plot 字段数 / 死变量精确数 / type 前向引用 / UDT 字段 vs .new() 实参数对齐
2. **P0 致命级**：编译失败 / 重绘 / 可执行性。**每条含：问题 → 行号命令证据 → 修法**
3. **P1 决策完整性**：核心功能缺口。**每条标社区证据标签**（官方事实 / 平台教学 / 社区实现 / 开源架构）
4. **P2 性能 / UX / 可读性**：不致命可选
5. **联网社区 2026 新增能力清单**：增量候选表，列 来源 / 实施成本 / 决策价值 / 推荐星标 ⭐⭐⭐
6. **10 条优化建议**：按优先级排序，**每条标 P0/P1/P2 + 一句话修法 + 涉及行号**
7. **推荐增强**（不只是修复）：A/B/C/D/E/F 真正能涨决策质量的增量
8. **决策（直接推荐）**：立刻落地哪几条 / 不推荐做的（带原因）/ 指标本身已多扎实

**用户开放追问陷阱**：用户问"还有你看看有什么需要优化的吗"是开放追问，必须在末段主动给出"额外观察点"，不能仅复述已列条目。

### 2026 社区 Top SMC 基准脚本（"我有什么 / 缺什么" 对比表）

| 脚本 | URL 关键词 | 差异化卖点 | 当前主指标缺口 |
|---|---|---|---|
| Quant SMC Pro [JOAT] | `ugOBLSa3-Quant-SMC-Pro-JOAT` | 自适应 ATR pivot + iFVG + Mitigation Rule/Tag + EQL + AVWAP PD + Confluence Score 0-100 | 真缺 iFVG / EQL / Adaptive Pivot；**MB标签不构成缺口**：当前 OB 本来只在 BOS/CHoCH break 后创建，重标 MB 几乎无区分度 |
| Unicorn ICT Signals [TradingFinder] | `9uGRHvXH-Unicorn-ICT-Signals` | Breaker Block + FVG Zones + Mitigation Level FVG | 已有 BRK 变色；只需增强 mitigation 深度/close-through 语义，不再加同义标签 |
| ICT Sessions + SMT Divergence | `rGyFTcVW-ICT-SMC-Sessions-SMT-Divergence` | RTH Gap + 25/50/75% quartile + 实时 SMT + DST 锚定 | 缺 RTH Gap（仅股票/RTH用户条件候选） |
| Order Block Detector [SMC ChartSense] | `1ORCJ6hv-Order-Block-Detector-SMC-ChartSense` | structural-extreme OB、FVG gate、wick/close mitigation | 当前 OB 只取10根内第一根反向K；应升级锚点和缓解模式 |
| Swing Reversal Auto Targets | `CKpLwLIZ-Swing-Reversal-Auto-Targets-JPT-Module-1` | 自适应 Swing HH/HL/LH/LL + 动态 S/R + 非重绘 pivot | Adaptive Pivot 有价值；独立 HH/HL 标签图面价值低 |

**用法**：不得把社区功能名直接当源码缺口。先沿当前检测→状态→评分→面板/MCP消费链判定“真缺失/部分实现/重复/低价值”。本生产架构优先候选为 iFVG、EQH/EQL、HVN/LVN、前日VP、OB结构源锚定与缓解模式；MB重标签、额外总分、重复 first-touch 不进入最终候选。

### series-color plot 计数最坏式（免费档 plot 余量评估铁律）

```
worst_plot_count = Σ(每 plot：color 含 ? / color.XXX / cGood 等变量 → 计 2；常量 #hex → 计 1)
                + alertcondition_count                         // 每个计 1
                + bgcolor_count                                 // 每个计 1
                + Σ(每 fill：series-color ? 2 : 1)
```

**series-color 判定正则**：`color\s*=\s*[^,)\n]*[?:]|color\.\w+|cGood|cBad|cWarn|cLabel|cVal|PNL_\w+`

**批量扫描脚本**（execute_code）：
```python
import re
def worst_plot_count(src):
    worst = 0
    for i, line in enumerate(src.split("\n")):
        if not re.search(r'(?:^|\s|;)plot\s*\(', line): continue
        m = re.search(r'color\s*=\s*([^,)\n\)]+)', line)
        col_expr = m.group(1).strip() if m else ""
        is_series = ("?" in col_expr or any(k in col_expr for k in ["color.","cGood","cBad","cWarn","cLabel","cVal","PNL_"]))
        worst += 2 if is_series else 1
    return worst
```

**免费档双指标实测基线（2026-08-09 复核，替代 08-08 口径）**：
- 主指标 43 plot（7 series：4 EMA 三元 + 3 S VWAP 的 `VWAP_COLOR` input 变量色，均计 2）+ 0 alertcondition + **1** bgcolor + 2 fill（EMA 云，三元 series 色） = 50 + 0 + 1 + 4 = **55/64**（余 9）
- 副指标 41 plot（12 series：Volume/SPOT/PERP/DeltaSP/PerpSpot/Delta/CumDelta/EX×5 用三元或 bull_color/bear_color 变量，计 2）+ Zero Line 常量 1 + 0 alertcondition + 0 bgcolor + 0 fill = **53/64**（余 11）
- ⚠ 计数口径修正（2026-08-09 实案）：① box 的 `bgcolor=` 参数不计 plot count，只数 `bgcolor()` 函数调用；② input.color 变量（如 VWAP_COLOR/bull_color）按 series 计 2——08-08 基线把这两类算错（主 4 bgcolor、副 62/64 均为误报）。

**铁律**：副指标余量 ≤ 2 时，**新增 plot 必须先合并打包 MCP 字段**，不得静默删 5 所成交量或 4 所 OI 减负；主指标余量 11 可加 1 个 iFVG（box + box.set_text，不计 plot）。

### HTF `lookahead_on` vs `lookahead_off` 区分铁律（2026-08-08 修订）

| 组合 | 性质 | 视觉表现 | 修法 |
|---|---|---|---|
| `lookahead_off` + expression 已收柱 `[1]/[3]` | 合法非重绘 | 结果延迟 1 根 HTF 末尾才发布 | 改 `lookahead_on` 视觉提前 1 K（不是修 bug，是优化） |
| `lookahead_on` + expression 已收柱 `[1]` | 标准非重绘 | 新 HTF 开始时即发布上一根确认结果 | ✓ 不动 |
| `lookahead_off` + expression **无**偏移 | **未来函数泄漏 P0 致命** | 当前未收柱直接取 | 必须加 expression 偏移或改 `lookahead_on` |

**审计时不要把 `lookahead_off + 已收柱偏移` 误标为"重绘"**，正确标签是"延迟"。证据：TradingView `concepts/repainting/#repainting-requestsecurity-calls` 官方文档。

### 副指标共振 / 同向票铁律（P1 反复出现陷阱，2026-08-07 修正）

**陷阱**：把"CVD 有方向 + OI 有变化 + 放量 + HTF 有方向"简单相加得 4/4 共振，**实际是状态 / 健康项数量，不是方向票**。可能"强确认多"同时 CVD 向下或 HTF 向空。

**修法**：方向票必须按价格方向解释订单流，并让 OI 四象限在所有消费者中保持一致
- 多向：`cvdUpA && oiUpA && volUpA && htfBullA` 各算 1 票（价涨+OI涨=新多扩仓）
- 空向：`cvdDnA && oiUpA && volUpA && htfBearA` 各算 1 票（价跌+OI涨=新空扩仓）
- `oiDnA` 在价涨时是空回补、价跌时是多平仓/去杠杆，只作状态说明，不算“新空确认”票
- 缺失 LSR / 覆盖数据 → 不得自动得分
- 若保留原存在性计数，行名必须改为"数据项 / 健康度"，**不能叫"共振"**
- Confirm Score、共振行、Composite、行动格和告警必须复用同一 OI 语义；不得正式评分用 OI涨、共振行却对空使用 OI跌
- `finalStrong` 与 `htfConflict` 必须直接按方向硬门控，不能仅在 `vGood/vBad` 已成立时才检查高周期反向

证据：GitHub SoCloseSociety/TradeBobbyTerminal 2026-07-10 commit `bed5b8b`：实测 CVD divergence 无 standalone edge，仅 confluence lens；Bookmap 2026-01 CVD 教学同口径。

### 2026 Pine 官方增量能力（增量优化候选必查表）

| 能力 | 来源 | 适用条件 | 推荐 |
|---|---|---|---|
| `request.footprint()` 低周期分类 Footprint | Pine v6 2026-01 release notes + 当前技术文档 | 仅 Premium/Ultimate、每脚本最多1个 unique call、可能返回 na；不可宣传为交易所原生逐笔 bid/ask tape | ⭐⭐⭐ 独立 Footprint Pro 脚本，不进 Basic 通用生产双指标 |
| `input.active` 依赖输入灰化 | Pine v6 2025-07 release notes | 所有 `input.*()` 新增 `active` 参数；false 时输入灰化不可改。主指标 60+ 输入面板的 UI 减负神器 | ⭐⭐⭐ 免费档纯 UI 层，零 request/plot 成本。`SHOW_NPOC=false` 灰化 `NPOC_LIMIT`、`AUTO_PROFILE_TF=true` 灰化 `MANUAL_PROFILE_TF` |
| 多行字符串 `"""..."""` | Pine v6 2026-04 release notes | 跨行字面量自动含换行，免 `\n` 转义 | ⭐⭐ 长 tooltip / 面板文案可读性 |
| UDT 集合排序/二分 `array.sort`/`array.binary_search` | Pine v6 2026-04/08 release notes | 可按 UDT 字段排序/搜索（`sort_field` 参数） | ⭐⭐ 磁吸候选/FVG 列表按 score 排序可替代手写冒泡 |
| `syminfo.isin` | Pine v6 2025-11 release notes | 12 位 ISIN，跨交易所识别同一标的 | ⭐ 跨所 SMT/相关性识别 |
| `time()`/`time_close()` `timeframe_bars_back` | Pine v6 2025-10 release notes | 在指定周期上按 bar 偏移算时间戳 | ⭐ 事件窗口/会话锚定更精确 |
| `plot()` `linestyle` 参数 | Pine v6 2025-09 release notes | plot 直接画虚线/点线，免 `plot.style_*` 变体 | ⭐ 前日 VP 投影虚线可直接 plot |
| 字符串上限 40960 字符 | Pine v6 2025-08 release notes | 原 4096 → 40960 | ⭐ 长面板文案不再受限 |
| `calc_on_every_history_tick` | Pine v6 2026-07 release notes | 历史每 tick 执行，减少 lookahead bias | 仅 Premium/Ultimate，免费档不可用 |
| `request.security_lower_tf` `calc_bars_count` 动态化 | TV 官方文档 | 免费档必备，避免 100K intrabar 超限 | ✓ 已落地硬编码 `1000` 必败（5m 图 D 分布图需 1440 根 1m） |
| Inversion FVG (iFVG) | Quant SMC Pro / Unicorn ICT 2026 共识 | box + box.set_text，0 新 plot cost | ⭐⭐ 免费档可加 |
| OB mitigation 深度/失效模式 | Quant SMC Pro / SMC ChartSense 2026 | 当前已有 `mitigated`，增强 proximal/50%/wick-through/close-through/full-fill；**不单列 MB 标签**，因为当前 OB 仅在结构 break 后创建，重标签无区分度 | ⭐⭐⭐ 零 request/plot，直接提高区生命周期质量 |
| Adaptive ZigZag ATR pivot | Quant SMC Pro 2026 | 重写 OB 检测逻辑 | 一致性收益（中等） |
| Per-venue freshness 真实时间戳 | HyperData Terminal 2026-07 | 替换 `ta.barssince(not na(v))` 为值变化检测 | � 副指标必改 |
| EQL / Equal High/Low 检测 | Quant SMC Pro 2026 | ATR tolerance + 扫描深度 | ⭐⭐⭐ 社区扫线 #1 增强 |
| RTH Gap + 25/50/75% quartile | ICT Sessions Pro 2026-03 | 独立脚本 + DST 自动锚定 | ⭐⭐ 股票用户升级后做 |

**审计时**：每项列出现在"未做"列时按 ⭐⭐⭐ 优先级建议加；不要全做，按用户决策风格与预算挑选。

### 静态扫描必备脚本（execute_code 模板）

```python
import re
src = open('指标文件.txt', encoding='utf-8').read()
lines = src.split("\n")
# 1. request / plot / alertcondition 静态计数
# 2. series-color plot 精确定位（按 color= 后 ? / 变量名 判定计 2）
# 3. 死变量精确扫描（声明次数 ≥ 1 且 读取次数 = 0，排除局部变量/形参/Pine 内置）
# 4. type 前向引用（type 定义行号必须 < 最早引用行号）
# 5. UDT 字段数 vs .new() 实参数一致性（按逗号顶层深度数）
# 6. 关键消费链（f_pnl_row("X") 必须消费 panelXxxVal）
# 7. 死 alertcondition（免费档 = 0 才能用）
# 8. HTF lookahead 模式 + expression 偏移审计
# 9. OBZone / FVG UDT .new() 实参数对齐
```

完整模板与"消费链 = 0 误报"陷阱（panelConclusionVal 是 `=` 不是 `:=`，静态扫描脚本要把两种定义方式都识别）见 `references/comprehensive-audit-deliverable-format.md`。

## 消费链死代码 + 死请求 + 回退双求值（2026-08-08 双指标全量审计新增）

**「消费者被删、计算链残留」是最隐蔽的死代码形态**：某次"精简"只删了表格消费端（`table.cell`/`f_pnl_row`），没删喂给它的整条计算链 → 每根 K 白算一整串变量，且静态扫描（只查 panelDirVal/panelConclusionVal/panelEntryVal 三变量）抓不到。审计任何注释写着"已精简/已删"的变量，必须顺消费链往下查：**grep 该变量的消费端，若零消费则整条上游链都是死代码**。

**实案（主指标）**：`cvdAsiaBar→cvdAsiaAcc→cvdAsiaSlope→cvdLeadAbs→cvdLeadSession→cvdSessionSuffix` 全链每 K 计算，但 `cvdSessionSuffix` 零消费（L2690 注释"20260807 精简：删会话主导/基差"只删了消费端）。修法二选一：① 整条删（省 token+计算）；② 把"亚主/伦主/纽主"接回行动格 CVD 行（会话资金流信号，快进快出有用，推荐）。

**死 HTF 请求（白占 request 配额）**：`[htfClose, htfEmaFast, htfEmaSlow, htfSma50] = request.security(...)` 只喂给 `htfBull/htfBear`，而这两个变量全文零消费（真正被消费的是带 [1] 偏移的 `htfBullConfirmed/htfBearConfirmed`）。grep 确认 `htfBull\b` 只有定义行 → 整条请求+函数（`f_htf_trend_pack`）可删，省 1 配额+1 函数+token，行为零变化。**审计每个 request.security 时，必须确认其解构出的每个变量都有消费端**，否则该请求是死请求。

**`nz(request.security(A), request.security(B))` 双参数都求值（配额陷阱）**：`nz` 的两个参数都会求值，回退请求永远占 unique context。副指标 `f_oi()` 用 `nz(USDT.P_OI, USDC.P_OI)` → 4 所 × 2 = 8 个 OI context 全占。修法：改 if/else 结构（主源 na 才请求回退），v6 dynamic requests 下未执行分支不占 unique context。**审计回退型请求时，`nz(req1, req2)` 是配额浪费信号**。

**重复计算**：`volMa = ta.sma(volume,20)` 与 `volSma20 = ta.sma(volume,20)` 同值算两遍 → 合并。grep 同名不同变量算同一表达式。

**`isH1 == 3600` 硬编码**：`updateLabel` 里 `bool isH1 = timeframe.in_seconds() == 3600` 只认 1h，4h/D 图不缩写"亚/伦/纽"标签 → 改 `>= 3600` 与 `isH1OrHigher` 口径一致。

**每 K 全量重算 O(N²) 性能风险**：`processAndRender(currentProfileStart, bar_index, true, barstate.islast)` 每根 K 执行，函数内 `for i=0 to count-1` 遍历全部 hPrices（上限 95000）重算分布。5m 图挂 D 分布图+高精度是免费档 20s 超时最大风险。修法：历史 K 增量更新（新 bar 只累加进对应桶），`barstate.islast` 才全量重算+渲染；数值同构性不受影响。

## 决策辅助审计模式（2026-08-08 新增，用户问"怎么优化辅助决策 / 还差什么功能"时用）

当用户从"代码审计"视角升级到"决策辅助"视角时，审计目标从"指标是否正确"变成"指标是否帮助用户更快更准做决策"。读取 `references/decision-support-gap-analysis-2026-08-08.md` 获取完整方法论。

### 决策辅助三原语

用户反馈"信息都看懂了但还是下不了决策"时，根因不是缺信息，而是缺三个即时感知原语：

| 原语 | 含义 | 审计检查 | 实现方式 |
|------|------|----------|----------|
| **多远** | 当前价距入场价多远 | 进场行是否有 "距X ATR" 后缀 | `math.abs(close - replayPlanPrice) / currATR` |
| **多久了** | 信号存活多久 / KillZone剩多少分钟 | 就绪度是否有年龄后缀、KillZone是否有剩余时间 | `triggerAge` 已有变量追加 "·3K"；`math.round((sessEnd - time)/60000)` |
| **该不该现在动** | 所有信息汇总后的一个动作词 | 方向行末尾是否有 →进/等/退/禁 | executablePlan/rdyPct/regime 组合 |

### 功能缺口分析方法

1. **覆盖度图谱**：用 execute_code 批量扫描两指标 30+ 功能关键词，输出已覆盖 vs 缺失
2. **社区对标**：对比 2026 ICT/SMC + 订单流 + VP + 趋势 + 风控前沿
3. **零成本增强识别**：最大缺口不是缺指标，而是已有数据没提取二阶导数

**核心洞察**：已有一阶数据（oiAggA/currATR/basisEma/volume/cvdAgg）都有对应的零配额二阶导数（OI动量/ATR分位/费率极端/Taker Ratio/CVD加速度），全部 0 request 成本。

### v2 指标基线（2026-08-08 上传版）

主指标 SVP+ICT+VWAP+CVD v2：3,033 行 / 199KB / 9 request / 37 plot / 27 DW / 0 死函数 / 0 死变量
副指标 AggVol v2：655 行 / 49KB / 7 request / 40 plot / 22 DW / 0 死函数 / 2 死变量（maxValidExchangeSeenA/maxOiVenueSeenA）

### 10 项缺失功能优先级

必加（零配额）：Taker Buy/Sell Ratio · OI动量变化率 · 波动率分位数 · 资金费率极端检测
高（零或低成本）：HVN/LVN标记 · 锚定VWAP · 清算级位
中（+1 request）：BTC大盘风向 · 会话VP · 复合VP共振区

## 2026 社区 VP 增强对标（2026-08-08 联网扫描）

| 增强 | 社区依据 | 价值 | 成本 |
|------|---------|------|------|
| HVN/LVN 节点 | Rogue VP Pro / Volume Profile XL / F3s SVP | 高量节点=磁吸位，低量节点=快速穿越区 | 主指标内加检测（局部最大/最小桶+阈值），~40 行 |
| 前日 VP 投影 | Previous Day Volume Profile / Rogue VP Pro | 前日 POC/VAH/VAL 投影到当日，比前日高低点信息量大 | 复用现有 profileEngine，存前日 lastPoc/Vah/Val |
| VA 偏差扩展（±0.25/±1/±2 VA） | Rogue VP Pro | 作目标/耗尽区，与 ADR 投影互补 | ~15 行 |
| Volume Delta 分色直方图 | Volume Profile XL Split Up/Down | 与主、副指标现有估算 CVD 共源；普通 OHLC/LTF 方向法不是 aggressor tape | **不进入通用候选**；除非独立 Footprint Pro 且诚实标口径 |
| POC 首次触碰事件 | Fib-Weighted VP / Liquidity Atlas 2026 | 当前 nPOC 已有 touch/gap/sweep，FVG/OB 已有 touchCount | **只扩展**到前日VP/HVN-LVN/EQH-EQL；不重复造 nPOC first-touch |

**`request.footprint()` 免费档不可用**：只有 Premium/Ultimate 用户可以运行调用它的脚本；Basic 通用源码不能靠关闭分支或把结果当作“每 bar 返回 `na`”来兼容。`na`表示有调用资格时某根K无可用Footprint数据。升级后再评估独立 Footprint Pro 脚本。
