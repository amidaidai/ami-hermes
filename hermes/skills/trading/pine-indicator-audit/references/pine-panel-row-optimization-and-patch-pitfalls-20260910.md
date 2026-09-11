# 行动格「表格内容优化」+ 大文件插入坑 + 锚定/连续裁定（2026-09-10 第三~五轮）

> 前置：`references/comprehensive-audit-deliverable-format.md`（八段骨架、避坑清单）与
> `references/pine-fix-delivery-and-verification-20260910.md`（删 vs 接回、交付闭环）。
> 本文记该次会话后续三轮新增的东西：**表格内容怎么审 + 怎么改**、**往 3000+ 行面板里插代码的坑**、
> **锚定 vs 连续的最终裁定与其落地实现（含 pane 量级可比规则）**、**批准净增配额时的回归放行做法**。

## 一、用户问「表格内容要优化一下吗」时的审法

不要凭感觉说"有点宽"。用**最坏行宽 + 跨行重复**两把尺子，逐行从源码枚举。

### 1.1 最坏行宽枚举

对每一行，把它所有分支的字面量取最长组合，算出「最坏字符数」。主表 13 行的实测排序（SVP）：
`结论 36 > 磁吸↑/↓ 30 > 风控 30 > 结构 29 > 现位 28 > 位置 27 > 协同 26 > 路径 22`。
**宽度瓶颈在结论行与磁吸行，不在你以为的路径行**。改之前先量，改完再量一次。

### 1.2 跨行重复（这次抓到 3 处，全部是「自己定的合同没落实」）

| 现象 | 证据 | 合同出处 |
|---|---|---|
| **阻断原因在结论行与风控行各打印一次** | 结论行 `actionStateText + " ⚠" + panelRiskOne`；风控行 `+ "·阻:" + panelRiskOne` | 20260827 逐行职责：风控行「若结论已显示阻断原因，不再重复 `阻:`」 |
| **协同行与结论行逐字同句** | `副S3冲突·不执行` / `副S4降权·仅B/C` / `副S0未接·A禁` 两行都有 | 协同行职责＝S0–S4 + 主副关系 + 高周 + 时机，动作词归结论行 |
| **副表流向行机械拼接三段** | `cvdMemoryTextA = cvdNowTextA + '·' + cvdRollTextA + '·' + cvdPrevTextA`，最坏≈40字 | 20260827：流向优先「同向/冲突/样本不足」，**前锚只有冲突时才值得占宽** |

**教训**："合同写了但代码没落实"是这类指标最高产的 P1 来源。审表格时不要只看宽度，要**逐条把合同条款回代到源码**。

### 1.3 修法：互斥消费，而不是删信息

阻断原因不能在风控行直接删（有状态时结论行也不显示，会丢信息）。正确做法是先抽一个共享标志，两行互斥消费：

```pine
bool riskInConclusion = panelRiskOne != "" and not str.contains(actionStateText, panelRiskOne)
// 结论行：(riskInConclusion ? actionStateText + " ⚠" + panelRiskOne : actionStateText)
// 风控行：riskValText + (panelRiskOne != "" and not riskInConclusion ? "·阻:" + panelRiskOne : "")
```

两种情况下原因都恰好出现一次：`contains=true` 时它已在 `actionStateText` 里；`contains=false` 时走结论行。

### 1.4 副表流向行：冲突优先，同向合并

```pine
bool cvdRollConflictA = (cvdUpA and cvdRollingDnA) or (cvdDnA and cvdRollingUpA)
bool cvdPrevConflictA = not na(prevAnchorCvdA) and ((cvdUpA and prevAnchorDirA < 0) or (cvdDnA and prevAnchorDirA > 0))
string cvdRollTagA = na(cvdRollingA) ? '' : cvdRollConflictA ? '·滚动逆⚠' : cvdRollingUpA or cvdRollingDnA ? '·滚动同向' : ''
string cvdPrevTagA = cvdPrevConflictA ? '·前锚逆⚠' : ''
string cvdMemoryTextA = cvdNowTextA + cvdRollTagA + cvdPrevTagA
```

⚠ 别把"同向"写成 `·滚动买·前锚买`——同向用一个词合并，否则比原来更宽。
**"同向"用状态词（同向/逆），不要用方向词（买/卖）复读**。

## 二、授权等级写进「行标签」，价格包在「值」里（可复用模式）

原有设计把"能不能做"编进**值**（`未授权·止…` / `禁做·不出价`），结果同一件事有四五种值格式，还和结论行打架。
改成：**值永远是同一个价格三件套，授权等级由行标签承载**。

| 行标签 | 触发条件 | 值 |
|---|---|---|
| `风控` | A 已可执行 / B/C 人工候选 | `入<价>·止<价>·x.xA·标<价>·x.xR` |
| `风控·观察` | 计划已成立但未确认（新增态） | 同上，尚未授权执行 |
| `风控·未授权` | 副 S3 冲突 | 同上，B/C 观察价未授权 |
| `风控` | X | `禁做·不出价`（唯一不出价态） |

```pine
string riskLabelText = setupX ? "风控" : aggGateConflict ? "风控·未授权" : pendingPlan ? "风控·观察" : "风控"
array.push(rowLabs, riskLabelText)
```

收益：新增状态只加一个标签分支，值格式不膨胀；用户扫一眼标签就知道"这个价能不能动"。

### 2.1 待确认态（`pendingPlan`）的边界

```pine
bool pendingPlan = (activeLongPlan or activeShortPlan) and not executablePlan and not setupX
   and not ((displayLongA or displayShortA) and not rrHardOk)   // ← rrHardBlock 原式内联，见 3.1
   and not lowLiquiditySession and priceGeometryOk and not na(finalEntryCandidate)
bool panelPlanVisible = visiblePlan or pendingPlan
```

- `replayPlanPrice / replayInvalidPrice / replayTargetPrice`（MCP 执行字段）**仍只在 `executablePlan` 有值**——观察价不得进入执行导出；
- `panelUnlockText` 仍用**严格** `visiblePlan`，所以待确认态照样提示"等收线/等新触发"；
- X 与 R:R不足 一律不出价。

### 2.2 同一价位不许两行重复

入场价原来在路径行（`条件齐✓→A执行 <价>`）和风控行各一次。定稿：**价格只由风控行输出**，
路径行只留"还要走多远"：`FVG承接✓→等收线·距0.8A↓`（负=入场位在下方）。
距离用 `(finalEntryCandidate − close) / ATR`，只在 `pendingPlan` 时追加。

## 三、往 3000+ 行面板里插代码：四个必踩坑

### 3.1 前向引用（Pine 自上而下）

`rrHardBlock` 定义在 `pendingPlan` 之后 → 编译 `CE10272 Undeclared identifier`。
**修法：按原式内联**（`not ((displayLongA or displayShortA) and not rrHardOk)`），不要靠挪行——
上下游都可能有依赖。

### 3.2 `array.push(rowLabs, X)` 之前必须先声明 X

把标签变量声明写在**原 push 位置**，而不是原值计算处（值计算在 push 之后）：

```pine
    string riskLabelText = ...          // ← 声明提前到这里
    array.push(rowLabs, riskLabelText)
    ...                                 // 原来的注释与值计算留在原位
    string riskPriceText = ...
    string riskValText = setupX ? "禁做·不出价" : riskPriceText
    array.push(rowVals, riskValText + ...)
    array.push(rowCols, pal.val)
```

### 3.3 rowLabs / rowVals / rowCols 必须索引对齐

两行之间的插入只能有**声明与注释**，不能有别的 push。改完必须断言：

```python
assert svp.count("array.push(rowLabs,") == svp.count("array.push(rowVals,") == svp.count("array.push(rowCols,") == 13
```

### 3.4 注释与代码一起改

`pathPanelText` 的旧注释写着"在路径行尾部补「入<价>·距…」"，价格移走后注释成了假话。
**改语义的补丁必须同时改相邻注释**，否则下一轮审计会把注释当规格，得出错误结论。

## 四、片段文件法：绕开 Python/JSON 转义（本次踩了 3 次）

往变换脚本里内联"同时含 `'` 与 `"` 的 Pine 片段"会被写盘/JSON 层反复吞掉转义，
症状是 `SyntaxError: unterminated string literal`，且 `read_file` 显示的内容与磁盘不一致。
**不要再试转义**——把片段落到独立 `.txt`：

```
v4_frag/n1_risk_old.txt   ← 逐字放老片段
v4_frag/n1_risk_new.txt   ← 逐字放新片段
```

```python
FRAG = BASE / "v4_frag"
def frag(name): return (FRAG / name).read_text(encoding="utf-8").rstrip("\n")

def rep(text, old, new, expect=1):
    n = text.count(old)
    assert n == expect, f"命中 {n} 次（应为 {expect}）: {old[:120]!r}"
    return text.replace(old, new)
```

无引号、无 `'` 的短替换可以内联；**只要片段里同时出现两种引号，一律走片段文件**。
需要构造含引号的针时用 `Q = chr(34)`，例如 `"    array.push(rowLabs, " + Q + "风控" + Q + ")"`。

### 4.1 括号/反斜杠敏感的字面量：用变量拼；并断言「生成的语义」

第八轮实测两个坑，**都发生在同一份变换脚本里**：

1. `.replace("input.bool(true", "input.bool(false)")` 里的**替换串被转义层补了一个 `)`**，
   实际生成 `SHOW_ROLL_BG = input.bool(false),` → 服务器编译报 `CE10016 Extra closing parenthesis`。
2. 同一个新开关从 `head` 派生时**漏改 `true`** → 默认值错成 ON。**这不报编译错**，
   只有断言能抓到；属于"会直接发错版本给用户"的静默错误。

两条做法，缺一不可：

```python
# 1) 派生新串优先「从已正确的新串派生」，不要各自从老串重解析
B_TRUE, B_FALSE = "input.bool(true", "input.bool(" + "false"   # ← 绝不要直接打字面 input.bool(false)
new2 = (new1.replace("SHOW_ANCHOR_MARK", "SHOW_ROLL_BG").replace(B_TRUE, B_FALSE)
        .replace(ES + "锚界竖带", ES + "连续净流背景线").replace(TIP_MARK, TIP_ROLL))

# 2) 断言「生成的语义」，不只是「替换发生过了」
assert B_FALSE in new2, "背景线开关必须默认关"     # 默认值是对用户的承诺，不能靠肉眼
assert B_TRUE  in new1, "锚界开关必须默认开"
assert ES + "连续净流背景线" in new2 and TIP_ROLL in new2    # 标签与 tooltip 都换过了
```

**推广**：任何「按模板生成代码」的变换，断言对象是**生成结果的性质**，不是替换动作本身。
凡涉及**语义极性**的字段 —— 默认值（true/false）、开关方向、单位、方向箭头（↑/↓）、
阈值正负 —— 全部要写断言钉住。

服务器编译是**第二道闸门**（它抓到了第 1 处），但**不能替代断言**：第 2 处编译完全通过。
两道闸门都要有。

## 五、LF 写盘（Pine 交付硬约束）

`Path.write_text()` 在 Windows 上会把 `\n` 翻成 `\r\n`，于是"LF 无 BOM"的交付承诺被破坏，
且校验脚本算的 SHA256 与磁盘字节对不上（文本模式读回会把 CRLF 归一成 LF）。**永远写字节**：

```python
DST.write_bytes(stage.replace("\r\n", "\n").encode("utf-8"))
```

交付脚本统一用 `read_bytes()` → `replace(b"\r\n", b"\n")` → `write_bytes()`，并打印 `len(bytes)` 与 `sha256(bytes)`。

## 六、验证脚本要「版本容忍」

同一个 `verify_*.py` 要能同时验 vN 与 vN+1（否则每改一版就废一套断言）。把断言写成接受两种合法写法：

```python
check("待确认态标志已定义（v3:planPending / v4:pendingPlan）",
      "bool planPending = ..." in sc or "bool pendingPlan = ..." in sc)
check("entryDistTag 已定义",
      "string entryDistTag = planPending" in sc or "string entryDistTag = pendingPlan" in sc)
```

**代际回归**：新版本的验证脚本应先 `subprocess.run` 上一版的 `verify_*.py`（传新文件路径），
再跑本版新增断言。本次 125 项 = v2 53 + v3 38 + v4 34，且 v2/v3 在 v4 上全量通过才算合格。

统计类断言别用 `count(...) == N` 粗对（同一行出现两次会算成 2）。用"出现该标识符的行是否都在允许集合内"：

```python
check("价格只由风控行输出",
      all(("string entryPriceText" in l or "string riskPriceText" in l)
          for l in sc.split("\n") if "entryPriceText" in l))
```

## 七、锚定 vs 连续：最终裁定（用户问「副指标怎么每日重置」）

### 7.1 先给源码事实表，再给判断

| 项 | 是否重置 | 源码 |
|---|---|---|
| 累计 CVD `CumDelta` | **重置**（锚定周期） | `newCvdPeriod = ta.change(time(cvdAnchorEff)) != 0` → `CumDelta := newCvdPeriod ? Delta : nz(CumDelta[1]) + Delta` |
| OI 变化率 `oiPctChgA` | **不重置**，滚动 `ACT_LB` 根 | `f_oi_pct(v, lb) = (v / v[lb] − 1) × 100` |
| 四所 OI 聚合 | **不重置**，各所滚动百分比等权平均 | `(nz(Bin)+nz(Byb)+nz(Okx)+nz(Bg)) / oiAggValidA` |
| OI Change Candles | **不重置**，每根相对前一根的差分 | `f_oi_bar_pct(o,h,l,c,p)` |
| Volume / SPOT / PERP | **不重置**，每根独立 | `GetExchange / EditVolume` |

### 7.2 裁定

- **累计量（流量累计）必须锚定**：没有起点就没有意义，且不同人图表加载时间不同→不可复现。
- **存量/水平量（OI、Volume）不能锚定**：加重置只会制造假跳变。
  社区 OI 看着"连续/像 K 线"是因为 **OI Change Candles 是水平量的差分**，差分天然连续；
  这不是"别人不重置 CVD"，是**两类量本来就该分开处理**。
- ❌ 不要把**执行锚**改成连续累计：无起点不可复现；且 `max_bars_back` 有限，连续累计在大周期图会被截断成错误值。
- ❌ 不要拿"今日累计 CVD"与"滚动 N 根 OI%"比大小：时间域不同，只能各自看方向。

### 7.3 诚实标注：锚初期两个数字不可比（已落地）

锚刚重置的头几根，CVD 只有 N 个样本（表格显示"本锚样本3/10"），而 OI 滚动仍有完整 10 根。
修法：在持仓行显式写滚动窗长 `oiOkA ? '·滚' + str.tostring(ACT_LB) + 'K' : ''`，
与流向行的 `'本锚近' + str.tostring(ACT_LB) + 'K'` 区分开。**不要写死 10**，跟随 `ACT_LB`。

### 7.4 落地方案（第五轮已实现，用户说"按照你的建议来做"）

两项都进副指标，**主指标一字未动**（逐字节相同）。

**① 锚界标记** —— 只描锚的**第一根**，1 根宽的淡色竖带：

```pine
bgcolor(SHOW_ANCHOR_AID and newCvdPeriod and isCryptoPlot ? color.new(chart.fg_color, 80) : na, title='CVD锚界')
```

- 用 `chart.fg_color` **自适应明暗主题**；
- **不要铺满整个锚区间**（整屏染色反而看不清）；日锚在 15m 图约每 96 根一次，1 根宽足够看清"线从哪断"；
- `bgcolor` 占 **draw 预算**，**不占六项和（254）** —— 配额记账时别混。

**② 连续背景线** —— 关键设计：窗口取「一个锚周期的根数」，**不是无限累计**：

```pine
int   barsPerAnchorQ = math.max(1, int(timeframe.in_seconds(cvdAnchorEff) / math.max(timeframe.in_seconds(timeframe.period), 1)))
float cumRollQ       = math.sum(Delta, math.min(barsPerAnchorQ, 2000))   // 2000 = 该脚本 max_bars_back 上限
plot(mode == 'Cumulative Delta' and isCryptoPlot and SHOW_ANCHOR_AID ? cumRollQ : na,
     '净主动流·整锚(不重置)', color=color.new(color.teal, 15), style=plot.style_line, linewidth=1)
```

### 7.5 pane 量级可比规则（本次最重要的设计判断，可迁移）

**为什么不能用"从加载点开始的无限累计"做背景线**：

1. **它会压平主线**：无限累计随历史线性增长（几千根 vs 本锚几十根），而 pane 只有**一条线性轴** ——
   把锚内 `CumDelta` 变成贴零平线，两条线根本没法同框看。**量级差 1~2 个数量级的同类曲线不能直接叠加**；
2. 它随"图表加载点"漂移，同一段行情不同人看到不同值。

取「一个锚长度」的滚动窗口后：量级与本锚 CumDelta **可比**；是滚动量，**不依赖加载点、不漂移**；
语义干净（锚内线＝本节至今净主动流，背景线＝上一个完整同长度窗口的净主动流）；随周期自动适配（15m→96 根，1h 自动切周锚→168 根）。

> **通用规则**：要在同一 pane 里叠加第二条同类曲线，先让它与主线**量级可比**；
> 否则改用归一化、改窗口、或干脆把结论放进表格 —— 不要硬画。

**诚实标注**：锚刚重置的头几根，本锚 CumDelta 还小、背景线已近满值 —— **此时不要比大小**
（写进 tooltip 与源码注释，不能只写在交付说明里）。

## 八、交付与验收（本轮补充）

- 目录 `hermes下载文件/双指标优化v4_20260910/`：两份 `.pine` + 三个 `verify_*.py` + 说明 md。
- 每轮交付都重跑：服务器编译（translate_light）→ 代际回归 → 配额不变量 → 表结构完整性。
- 配额不变量核对：`request 8/8`、`plot 31/45`、`input 193/37`、`alert 0/0`、六项和 `237/254` 与 `91/254`。
  第三、四轮优化**没有**新增任何 input/plot/request/alert——纯文本分支 + 一个 gating 布尔。
  （**第五轮例外**：经用户批准净增 +1 input +1 plot，见 §9.1。）
- 边界现状写进报告：主指标六项和余量只剩 17，**任何新增强先算六项和**；新功能优先放副指标（余量 163）。
- 说明 md 里必须写明"不接受这个宽度代价就删哪一行"，让用户能自己回退。

## 九、附加型改动（净增配额与新增视觉）的三条做法（第五轮新增）

### 9.1 净增配额时的记账与回归放行

本族指标第一次允许净增（+1 input + 1 plot，副指标六项和 91→93/254）。做法：

- **只加一个开关**（`SHOW_ANCHOR_AID`，与 CVD 锚定周期同排），一次管住 ②③ 两个新增视觉；
- 第二个新视觉**复用已有门控**（`mode == 'Cumulative Delta'`）而不是再加一个 input——少一个 input、多一层语义；
- 旧版 `verify_*.py` 的"配额不变"断言会因净增而**整套失败**，必须在旧脚本里加**放行表**：

```python
ALLOW = {"SVP": {}, "AggVol": {"inp": 1, "plot": 1}}   # 只在"批准的净增"时填，且必须写清用途
for k in a:
    hi = a[k] + al.get(k, 0)
    check(f"{nm}.{k} 不超预算 ({a[k]}" + (f"+{al[k]}→{hi})" if hi != a[k] else ")"),
          a[k] <= b[k] <= hi, f"{a[k]} -> {b[k]}")
```

**放行表不是万能橡皮**：填它等于声明"这次净增是批准的"，必须在交付说明里写明净增了什么、为什么。

### 9.1b 反向情形：新版**减少**配额时（第六轮补充）

当新版合并/删除绘图导致配额**下降**时，§9.1 的 `a[k] <= b[k] <= hi` 会因 `b < a` 而整套失败。
把语义改成真正的「不超预算」，**只卡上界**（代码块内用单引号，避免写盘转义层再吞引号）：

```python
hi = a[k] + al.get(k, 0)
check(f'{nm}.{k} 不超预算 ({a[k]}' + (f'+{al[k]}->{hi})' if hi != a[k] else ')'),
      b[k] <= hi, f'{a[k]} -> {b[k]}（超预算）')
```

减少是好事、不需要放行；**功能有没有被削由专项断言兜底**
（五所成交量 `GetExchange(` == 5、四所 OI、表格行数、总线合同号、锚内 CVD 不连新锚首值），
**不要靠配额计数去证明功能没丢**——两者是正交的。

### 9.2 最强不变量：抽掉新增行后逐行比对

"其余一字未动"用计数断言证明不了。**抽掉本次新增的行，再与上一版逐行 diff（忽略空行）**：

```python
def strip_new(t):   # 去掉本次新增的声明/plot/bgcolor/开关行
    return "\n".join(l for l in t.split("\n")
                     if not any(k in l for k in ("barsPerAnchorQ", "cumRollQ", "CVD锚界", "SHOW_ANCHOR_AID")))

check("除新增 5 处外，逐行与上一版一致（忽略空行）",
      [l for l in strip_new(c5).split(chr(10)) if l.strip()]
      == [l for l in c4.split(chr(10)) if l.strip()])
```

两个坑：
- `code_only()` 去注释后，新插入的**注释行会变成空行**，比对**必须过滤空行**，否则看到"+7 空行"的假 diff；
- 脚本里写 `chr(10)` 而不是 `"\n"`，避免转义层再次吞掉反斜杠（§4 已踩过）；
- **逐行等值断言只对「纯增量」版本成立**。一旦新版**重构了旧行**（`bgcolor` 改 `line` 对象、两条 plot 合并成一条、删掉一条 plot），
  等值断言必然失败，而这是**预期**的。不要为让它变绿而放松断言 —— 加一个**旁路标志**，
  只跳过结构性重构的那一代，并把该代的不变量交给专项断言：

```python
check('除新增处外，逐行与上一版一致（忽略空行；重构版另有专项断言）',
      'cvdAnchorLines' in c5                    # ← 结构性重构代的旁路标志
      or [l for l in strip_new(c5).split(chr(10)) if l.strip()]
         == [l for l in c4.split(chr(10)) if l.strip()])
```

  同理，旧脚本里描述**外观实现**的断言（例如「锚界用 bgcolor」）要预先写成 **vN/vN+1 双写法容忍**，
  否则每换一代都要回去改旧脚本 —— 而改旧的验证脚本会削弱「历史修改未回退」的证据力。

### 9.3 input 标签里的 EN SPACE（U+2002）

该指标族的 input 标签前用的是 **EN SPACE（U+2002）**，不是普通空格。片段文件里若写普通空格，
`rep()` 会报 `命中 0 次`，而 `read_file` 显示出来**肉眼完全看不出差别**（本次靠逐字符 diff 才定位：`diff at 49`）。
匹配前先归一：

```python
ES = chr(0x2002)
def norm_es(t):
    return (t.replace("' 锚定辅助'", "'" + ES + "锚定辅助'")
             .replace("' CVD锚定自动'", "'" + ES + "CVD锚定自动'"))
agg = rep(agg, norm_es(frag("a35_old.txt")), norm_es(frag("a35_new.txt")))
```
