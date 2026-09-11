# 20260810 全方位审计 + 修复记录（主 SVP_ICT_v2 + 副 AggVol_v2，14 处）

审计触发：用户"全方位审计（锚定/表格/设置/内部模块/源码/决策）+ 联网核对"。

## 量化基线（修复后）
- 主：3051行 / 201534字符 / token≈86500 / plot43(series5) / 最坏51/64余13 / req静态6+ltf2 / input228 / alert()1 / 死变量0
- 副：695行 / 52834字符 / token≈22700 / plot41(series16) / 最坏57/64余7 / req静态7（运行时29路径/40）/ 死变量0

## P0 修复（会误导决策）
1. **副指标市场判定漏 XAUUSDT.P**：`syminfo.type=='crypto'` 对 BINANCE:XAUUSDT.P 为 true → 黄金被当加密聚合5所（仅币安有数据）+订单流估算误导，且与主指标 marketMetal 判定相反。
   修复：新增 `f_is_metal_ticker()`（ticker 字符串检测，与主指标 autoMetal 同源：XAU/XAG/GOLD/SILVER + root GC/SI + COMEX:GC/SI），isCryptoPlot 与 isCryptoA 均加 `and not f_is_metal_ticker()`。
   **教训：TV 市场判定一律用 ticker 字符串，syminfo.type 对交易所贵金属标的不可靠。**

## 锚定分叉修复（用户点名重点）
2. **CVD 锚定缺市场维度**：原 `tf_sec<3600?D : <14400?W : M` 不分市场 → 外汇/金属 4h+ 图 CVD=月 vs S VWAP=周 分叉。
   修复：`((marketMetal or marketForex or marketStock or marketOption) ? (tf_sec<14400?"D":"W") : (tf_sec<3600?"D":tf_sec<14400?"W":"M"))`——与 autoSvwByMarket 完全同源。
3. **SVP 1d+ → 12M vs CVD/VWAP → M**：保留 12M（年度分布有意），修正错误注释（原注释谎称"与 S VWAP/CVD 一致"）。
   锚定矩阵：加密 1h↓=D / 1h-4h=W / 4h+=M；非加密 4h↓=D / 4h+=W；SVP 分布图 1d+=12M 除外。

## P1 修复
4. 主副 CVD 估算口径互标：主指标行动格 CVD 行低周期聚合时加"·低周期"（副指标流向行恒为影线估算、文本自带"估"字）。
5. metalSpot 时 cvdActionWord 置空（原输出"现货无逐笔·买力回升"自相矛盾）。
6. 副指标单源模式隐藏 syncVolTxt（`datatype=='Aggregated'` 门控）。
7. mcpRiskPack 假数据：硬编码 10900 → `const int MCP_RISK_CONFIG_PACK` + 准确注释（静态配置编码，非实时）。
8. 副指标 exd 模式颜色错位：值用排序后 percform、色用未排序 EXcolors → `(col or exd) ? sortedEXcolors.get(i)`。

## P2 修复
9. metalSpot 不再拉 CVD lower_tf（省 intrabar 预算）。
10. 行动格 `f_render_action_panel()` 包 `if barstate.islast`（省历史 K 每根 20+ 字符串拼接）。
11. xHtfConflict 硬编码 7 → effTrendAThreshold（对齐 A 级门槛）。
12. cvdCalcBarsA1 上限 20000→50000（月锚+1m=43240 全覆盖；1S 秒级极端仍截断属预期）。
13. 死代码：主 basisEmaRaw/basisEma；副 BITMEX XBT 替换分支；entryValidCode/signalStateCode 冗余末三元。
14. 副指标 GetTicker 简化（删除死分支，直接返回表达式）。

## 2026 社区联网核对结论
- Pine v6 仍当前版本（无 v7）；64 plots / 40 requests / 100K intrabar 限制未变。
- **request.footprint() 2026-01 发布、03 上线，Premium/Ultimate 专属**——免费档脚本含此调用无法编译；升级后可用真实 bid/ask 替换全部 CVD 估算。
- CVD 背离 confluence 共识（GitHub bed5b8b）与指标现有关键位/摆动/吸收派发过滤一致。
- 记忆铁律更新：OI 方向票=OI升（新仓扩张）对多空都算票（20260808 代码已改，20260807 记忆"空向要求 oiDn"已过期）。

## 复核方法
- 静态扫描脚本：workspace/audit_20260809/static_scan.py（plot计数含 series-color 规则、req、input、table、死变量粗查、TF字符串）
- 括号平衡粗查（去字符串字面量后数括号，Pine 无本地编译器的替代手段）
- 交付路径：桌面/hermes下载文件/指标审计修复_20260810/（旧版 20260809 原文件保留在上传目录）

## ⚠ patch 截断事故（CE10156 教训，20260810 实发）
给 Pine 大文件做 patch 时，`old_string` **绝不能以变量名+`=` 结尾**（如 `int mcpQualityCode =`）——模糊匹配会把整行替换并把 `=` 后的表达式吞掉，文件里留下孤立的 `int mcpQualityCode =`，TV 编译报 CE10156。
铁律：
1. old_string 必须写完整行（含 `=` 后的全部表达式），或至少写到行内唯一边界。
2. 每轮批量 patch 后**必须 `diff` 原始文件 vs 修改文件**，逐行核对每个 `<`/`>` 差异完整（防静默截断），再做括号平衡复检。
3. 交付前最后读一遍被改行原文。

## 第二轮修复（用户反馈驱动，+8 处）
用户反馈：①"看位行太宽，把东西移到短行，看看其他行是不是也这样"；②"排序有问题吗"。

### 行动格宽度治理（用户偏好：紧凑、手机可读、宽行拆到短行）
看位行原构成 ~32 字符（最宽）：关键位+价格+KZ标记+·结构X+·高周X+·VWAPX。拆法（语义就近）：
- 看位行只留：关键位+价格+KillZone标记（~15）
- 结构方向 → 结构行：去"·结构"前缀（表头即"结构"）；无计划分支删 bosChochText（panelStructText 已含，防重复）
- 高周方向 → 确认行（保留"·高周X"前缀作分隔）
- VWAP锚定标签 → 位置行（最短行）
- 磁吸行去"分NN"（与距离A冗余，距离更直观）；方向行分数尾注"趋势偏多"→"趋势"（方向词已由行动词承载）
改后各行收敛 ~15-17 字符。

### 排序索引一致性审计模式（真 bug：值/颜色/图例错位）
副指标 Exchange Domination：`array.sort_indices(percform, order.descending)` 后构造 sortedEXlist/sortedPercents/sortedEXcolors 同序，但 exd 画线用了未排序的 `percform.get(i)` → EX1 显示第1配置所的占比而非最大占比所；sortedPercents 成死数组。
审计模式：sort_indices 之后**所有消费方必须用排序索引数组**；逐 plot 检查是否误用原数组；sorted* 配套数组未被消费 = 死数组漏用信号。

### 文本移动前查依赖（pitfall）
f_pnl_row 行颜色用 `str.contains(文本)` 判断——把文本从一行移到另一行前，必须检查被移动文本是否被其他逻辑消费（颜色判断/计数）。本次确认行颜色判断用 panelConfirmText（不含 guideHtfText），移动后语义安全。

## 第三轮修复（用户反馈驱动，副指标）
用户反馈：①零线"是线形图"要改点虚线；②信号行太宽；③"整个表格的内容是不是缺少了什么"。

### 零线真虚线（Pine 绘图技巧）
`plot.style_circles` 圆点连续、观感如实线；`line.style_dashed` 才是真点虚线。实现模式：
```
var line zeroLine = na
bool zeroLineOn = mode != 'OBV' and mode != 'MFI' and isCryptoPlot
if zeroLineOn
    if na(zeroLine)
        zeroLine := line.new(bar_index - 1, 0, bar_index, 0, color=color.new(color.gray, 0), style=line.style_dashed, width=1)
    line.set_x2(zeroLine, bar_index)
else if not na(zeroLine)
    line.delete(zeroLine)
    zeroLine := na
```
要点：var 单对象不累积；每根K set_x2 使线贯穿全图（回放也 OK）；Mode 切换删除重建；不占 plot 配额（最坏式 57→56）。

### 副指标信号行瘦身（~30 → ~15 字符）
原 signalA = 灯+方向强度+' · 共振N/4'+'·✗LSR ✗覆盖'+' · 数据可信'。拆法（信息零丢失）：
- `✗覆盖` → 覆盖行已有 ⚠低覆盖（重复项，直接删）
- `✗LSR缺` → 风险行新增 `⚠LSR缺失`（`na(lsrA)` 判定；拥挤仍走 ⚠LSR拥挤）
- `数据可信/降权` → 覆盖行尾常驻
- 连带删除死链 resoLsrA/resoCovA/resoMissA（唯一消费方是 signalA）

### 表格补缺审查（对比主指标行动格找副指标缺口）
副指标行动格对比主指标缺三样，已补：
1. **流向行无 CVD 锚定周期**（主指标 CVD 行有"日/周/月"）→ flowPanelTxtA 加 `(mode=='Cumulative Delta' or mode=='Delta' ? (cvdAnchorEff=='D'?'日':cvdAnchorEff=='W'?'周':'月') : '')` 前缀 → "月▲估买占优"
2. **数据可信状态仅降权时可见**（正常态看不到）→ 覆盖行尾常驻 `' · ' + dataTrustA`
3. **LSR 缺失静默** → 风险行 `⚠LSR缺失`
pitfall：coverageRowA(L424) 定义早于 dataTrustA(L512)——跨行文本拼接必须在表格渲染处（islast 块）做，不能在字符串定义处前向引用。

### 本轮基线
副指标 plot 40（零线改 line 不占配额）、最坏式 56/64 余 8、死变量 0。

## ⚠ patch 事故第二形态：死变量清理误删相邻行（20260810 实发）
清理磁吸死变量（magnetAboveHtf/magnetBelowHtf）时 old_string 范围写大，把相邻的 `float bestAboveScore = -1 / bestBelowScore = -1`（磁吸评分循环的比较基准，仍在使用）一起匹配删除——当场靠 diff 发现多删、立即补回。
补充铁律：
1. 死变量清理的 old_string **精确到目标行本身，禁止捎带相邻行**；删整段前先读上下文确认每行用途。
2. 删完 grep 双向验证：被删变量 0 残留（注释除外）+ 相邻被保留变量仍被引用。
3. 多轮迭代时 `diff` 对比**上一交付版**（而非原始上传版）——本轮正是靠它定位多删行。

## 10行化合并模式（用户偏好：不减少信息、不撑宽、行数少）
主指标行动格 12→10 行（位置/结论/方向/进场/风控/CVD/OI/确认/结构/磁吸/看位）：
- **合并同来源行**：CVD+OI → 一行 "CVD/OI"（值 `actionCvdText + " " + oiRowText`；颜色优先级 CVD 警示色 > OI 一致/分歧色）。
- **合并同概念行**：磁吸↑↓ → "磁吸"，每侧压缩格式 `↑名称价格·距离A`（去价格空格、去 ★HTF——HTF 确认已在确认行；去分NN——与距离冗余）。
- 表格容量（table.new 18 行）远大于实际行数，容量无需改；f_pnl_row push 次数即行数，改完用 grep 数 `f_pnl_row("` 验证。
- **"不宽"基准**：合并后最宽行 ≤ 方向行宽度（BTC 档 ~24-27 字符）。

## 位类行语义前缀三态（看位行"怎么看"的答案）
行动格"位"类行必须带类型前缀，否则用户分不清是支撑阻力还是触发位：
- `回踩XXX`（多单计划）= 入场观察位：价格回踩到位 + 触发信号（MSS↑/FVG承接/OB承接）才可入场，到位≠买入
- `反抽XXX`（空单计划）= 同上，空单等反抽
- `磁吸XXX`（无计划）= 触发观察位：当前最活跃 ICT 级别，靠近可能出扫位/位移，是"行情下一步去哪"的预报
支撑阻力职责由图上 VA/POC/S VWAP/前高低线承担，不放进看位行。

## 路径与闸门一致性审计点（用户指出的矛盾）
无计划路径原只按趋势分数 → 高周偏空时仍显示"趋势偏多 等回踩→MSS↑"，与 htfAllowLong 闸门（禁多）自相矛盾。
修复模式：无计划路径 = **结构方向 × 高周方向**组合——同向给顺势路径（"结构高周同多 等回踩→MSS↑"）、逆向给"等高周转同"路径（"结构多·高周空 等高周转多再回踩"）、单侧待给"等确认"路径、全待退回趋势分/价值区/DMI 分支。
通用审计点：**行动格任何"建议/路径"文本必须与同级闸门一致**——出现"路径教你做多、闸门禁做多"即 P1 级矛盾。

## 最终形态：用户否决 10 行化，恢复 12 行原布局（20260810 第5-6轮，定稿）

用户："磁吸分开吧，12行就12行"。**10行化方案被推翻**——磁吸↑↓拆回两行后仍差 1 行，CVD/OI 也拆回独立行。最终定稿 12 行：
`位置 / 结论 / 方向 / 进场 / 风控 / CVD / OI / 确认 / 结构 / 磁吸↑ / 磁吸↓ / 看位`

本轮两次"恢复"动作暴露的偏好铁律：
1. **合并行会被要求拆回**——压行数前先问合并哪两对，或默认只瘦身不合并。上一节"10行化合并模式"的合并方案仅适用于用户明确要求压行时，且合并对象须同概念（CVD/OI 同源、磁吸同概念）；该用户对主指标最终偏好是**信息完整优先于行数**。
2. **不要擅自删用户已习惯的字段**——磁吸行"去分NN/去★HTF"被要求"恢复原格式"（`↑前日高 12345.6 分88★HTF 0.8A`）。magnetAboveHtf/magnetBelowHtf 声明+4处赋值随之恢复。删字段前必须问。
3. **看位行必须自带决策指引**——用户："要告诉我是准备多还是空、到这里了应该怎么办"。定稿格式（在上一节三态前缀基础上加方向+行动词）：
   - 多计划：`多·回踩前日高12345.6·到位等MSS↑`
   - 空计划：`空·反抽前日低12300·到位等MSS↓`
   - 无计划：`待·磁吸前日高12345.6·盯扫位/位移`
   实现：guideLookText 加 `多·/空·/待·` 前缀 + 新增 `guideActionWord`（planSideLong→"到位等MSS↑"、planSideShort→"到位等MSS↓"、无计划→"盯扫位/位移"），看位行 push = `guideLookText + "·" + guideActionWord + kzShort`。

行动格迭代方法论小结（本会话 6 轮打磨出的完整模式）：宽行拆段到语义归宿行（零丢失）→ 排序数组同源检查 → 表格补缺对照主指标职责 → 路径与闸门一致性 → 行数压缩先问用户 → 字段删除先问用户 → 看位/位类行带方向+行动指引。

## 参数微调（用户口头给值，直接改默认值）
用户："周月vwap的atr为5" → `VWAP_ATR_MULT` 8.0→5.0（周/月 VWAP 智能隐藏阈值，距价 >N×ATR 隐藏连线）。模式：
- 用户给"某参数=X"时直接改 input 默认值 + 注释标注日期与旧值，不做多余解释。
- 交付时提醒：TV 上已保存的设置不会被指标更新后的新默认值覆盖，需手动改或重置该参数。
- 改参数不涉及结构，patch 后括号复检即可，不用 diff 全文件。

## AggVol 深审新增边界（20260810）

1. **收盘确认告警的边沿状态不得被盘中重置**：错误模式是 `anyNow = barstate.isconfirmed and rawState` 后每次执行 `prev := anyNow`；新K盘中 `isconfirmed=false` 会把 `prev` 清零，持续状态因而每根收盘重复提醒。只在确认时更新 `prev`，或对不含确认门的 raw state 做跨收盘边沿。
2. **OI 单源不等于跨所一致 100%**：`oiAggValid==1` 时不得显示“跨所一致100%”，也不得同时标“跨所分歧”。应标“单源/覆盖不足”；只有有效源≥2时才展示 Agreement，并将数据不足/离散过高（State 4降权）与明确方向冲突（State 3）分开编码。
3. **后缀也必须去重**：交易所槽位去重不等于数据源去重；SPOT1/SPOT2 或 PERP1/PERP2（含自定义覆盖）若解析成同一最终后缀，同一成交量会被重复相加。聚合前按最终 symbol/suffix 去重，coverage 与成交量必须使用同一有效源集合。

## 第三方审计报告二次核验（20260810 终轮，逐条裁决模式）

用户发来多份外部审计报告（含行情推荐）要求验证真伪。裁决三档：**属实 / 部分属实 / 误报**。新发现：

1. **配额数字必须用官方口径复核**：外部报告 series-color 计数严重低估（主 17/64、副 31/64 vs 真实 51/64、55/64）——它只数 series-color 槽，漏掉**每个 plot 至少 1 count** 的基础计数（TV 规则：plot 基础 1 + series-color 追加 1 + bgcolor/fill 各 1）。验证第三方配额表：先数 `plot(` 总数，再加 series 与 bgcolor/fill，不信对方的汇总数字。
2. **CRLF 溯源必须对比原始上传文件**：报告称"08-10 patch 工具把主指标转成 CRLF"，实测**原始上传文件就是 CRLF**（3041 个），非工具引入；且 TV 完全兼容 CRLF，不是 P0。行尾问题验证顺序：原始文件行尾 → 当前文件行尾 → 才谈得上"引入"。
3. **request.* 条件门控不省配额（TV 硬规则）**：报告建议"非加密图给 f_oi×4+LSR+基差加 if 门控省 6 个 context"——**无效**。TV 文档明确 request.* 在运行时条件 false 时也照常执行，静态配额按唯一调用计数、不随条件减少；XAU 图上这些请求靠 `ignore_invalid_symbol=true` 返回 na，功能无害。这类"看起来能省、实际省不了"的修复建议直接否掉。
4. **CVD 锚定分叉的场景要查准**：报告举例"1D+ 加密图主→W vs 副→M"是**错的**（加密 1D+ 主副都是 M，一致）；真实分叉在**非加密 4h+**（金属/外汇/股票）。裁决分叉类问题必须把市场×周期矩阵列全再下结论。
5. **外部报告行情推荐一律标注未核实**：BTC $64,800 等价格/推荐是另一模型联网生成，不引用为事实；要走标准加密分析管线重新出。
6. **第三方建议与用户既定偏好冲突时以用户偏好为准**：报告建议副指标流向行加"·K线估算"——用户偏好"副指标界面不显示估算字样"，直接不采纳；同理 DW 字段名去"(K线估算)"（用户拍板，保留"K线"替代词）。

## 终轮定稿（第 6-7 轮）：dirRef 参考位 + 灰化扩展 + 功能冻结决策

### dirRef 参考位模式（"等回踩不知道回踩哪里"的根治）
用户痛点：表格常出现"等回踩"但没说回踩哪；无计划时看位行显示磁吸位（与"等回踩"方向无关），两行位置对不上。
根因：路径行与看位行各给一套位置。
修复模式（可复用）：
```
bool biasLongDir = planSideLong or trendLongScore >= trendShortScore + 2
bool biasShortDir = planSideShort or trendShortScore >= trendLongScore + 2
float dirRefPrice = na
string dirRefName = ""
if biasLongDir and not planSideShort      // 多头看下方：磁吸↓ > VAL > VWAP
else if biasShortDir and not planSideLong // 空头看上方：磁吸↑ > VAH > VWAP
string dirRefTag = not na(dirRefPrice) ? dirRefName + f_fmt_price(dirRefPrice) : ""
```
- **路径行与看位行共用同一 dirRef**——"等回踩/等反抽"后面永远跟着具体位（`趋势偏多 等回踩前日低→MSS↑` / 看位 `偏多·回踩前日低·到位等MSS↑`），两行同位不再打架。
- 看位行三态升级：多计划 `多·回踩{支撑位}`、空计划 `空·反抽{阻力位}`、无计划偏多/偏空 `偏多·回踩{dirRef位}`/`偏空·反抽{dirRef位}`、纯无向 `待·磁吸{位}·盯扫位/位移`。
- 计划内路径"站回VWAP/VAL"改用 `pullbackLevelName`/`reboundLevelName`（na 时回退 "VWAP/VAL"）与看位行同一位。
- 位置层级说明（用户问"不知道看哪一个位置"的标准答案）：**看位行=唯一要盯的位**（方向+位置+到位行动）；进场行=实际挂单价（有计划时）；磁吸↑↓=上下方活跃级别背景；位置行=当前价在 VA 的哪里（背景）。

### 输入面板灰化扩展（SHOW_ADVANCED 14 → 27 参数）
模式：`active=SHOW_ADVANCED` 加在 input 的 group= 后。灰化对象 = 微调数值/颜色/阈值（OB 回看/个数/延伸/过期/全部颜色/填充透明度、SMT 手动品种、FVG 过期K数、DEGRADE_THRESHOLD、CVD slope/divergence/absorb/weight——CVD 微调早已灰化）；**保留可见** = 所有开关类 + 周期选择类（SHOW_*、锚定、低周期、对照品种、EMA、KillZone、行动格外观、分布图行数/宽度）。
注意：SHOW_ADVANCED 定义必须在所有使用点之前（L29，所有 input 之前）；灰化不影响用户已保存的设置值。

### ⛔ 功能冻结决策（20260810 用户拍板，重要）
用户对"2026 社区决策增强推荐"（OB回测标记/bid-ask价差检测/footprint 等）明确回复：**"ABCDEF 这些这些东西都不要"**。
- 指标功能**到此为止**，不再推荐任何新功能；后续只做用户点名的修正。
- 攒配额等升 Premium/Ultimate 接 `request.footprint()` 是唯一保留的升级路径，但**只在用户主动提时才说**。
- 决策辅助能力已完整（方向/时机/位置/风控/证据/禁做六问全覆盖），用户要的是"用指标执行纪律"而不是"继续改指标"。

1. **副指标 CVD 锚定补市场维度（终案）**：`f_is_metal_ticker()` 函数定义**上移至 CVD 锚定区（L37 前）**供两处复用（锚定 + isCryptoPlot 门控），新增 `nonCryptoAnchorA = f_is_metal_ticker() or syminfo.type in (forex/stock/index/futures/warrant/right)` → 非加密 4h 以下→D、4h+→W；加密保持 1h↓→D/1h-4h→W/4h+→M。与主指标 `cvdAnchorTf` 完全同源。pitfall：函数上移后**必须删除原位置定义**，否则"函数重复定义"编译错误。
2. **DW 字段名去"估算"字样**：`CVD Value (K线估算)`→`CVD Value`、`CVD Method Code (1=K线估算)`→`CVD Method Code (1=K线)`。
3. **POC 轴标双主题可见**：`#0F0F0F`（深色主题隐形）→`#5B6470`（浅色=深灰/深色=中灰，且与 nPOC `#787B86` 保持区分度）。颜色选择模式：price_scale 上的轴标色必须双主题可见，用中灰系折中，同族线（POC vs nPOC）保持明度差。

## 最终基线（全部修复后）
- 主：3083行 / 203581字符 / token≈87373 / plot43(series5) / **最坏51/64余13** / req静态6+ltf2 / input228 / 死变量0 / **LF 行尾**
- 副：703行 / 53521字符 / plot40(series15) / **最坏55/64余9** / req静态7 / 死变量0 / LF
- 主指标 203K 字符逼近大脚本红线（CE10295）——功能上加不动了，这是约束不是缺陷。

## 2026 社区决策增强推荐（联网验证，免费档内最后两块）
- **A. OB/FVG 回测确认标记**：社区 2026 热门（ChoCh Identifier/BigBeluga 系）——OB 回测+放量自动打"回测成功"标记；你的引擎已有触发布尔（bullObTradeOk 等），加图上 ✔ 标记成本 ~10 行、不占 plot 配额。
- **B. bid/ask 价差流动性检测**：Pine v6 2025-2026 新增 bid/ask 变量（免费可用），spread > N×mintick 实时判定薄流动性，增强 lowLiquidityAsset（现靠 volume 代理）。
- 已对齐社区无需做的：Sweep+Retracement 组合（你的扫低收回/扫高拒绝即是）、12 行行动格面板（超 Liquidity Matrix 类）。
- 唯一真实升级路径：Premium/Ultimate 接 `request.footprint()` 换真实 bid/ask delta。

## ⚠ CE10116 函数外部元素超限（20260810 最后两轮，双函数拆解）
TV 报错模板**不含函数名**——第一次误判修了行动格函数（f_render_action_panel 227 外部元素，拆 15 函数后仍报错），真凶是评分函数 `f_score_setup()`（加权 84 > 60）。铁律：报 CE10116 先跑 `scripts/pine_external_elements_scan.py <file.pine>` 全量扫所有函数，一次性修全部 >= 60 的，不猜。拆法（子函数按逻辑子集返回元组 / type 对象打包调色板）与陷阱（勿搬回全局防 CE10295 复现、组装代码包 islast）详见 `references/pine-20260810-ce10116-refactor.md`。
