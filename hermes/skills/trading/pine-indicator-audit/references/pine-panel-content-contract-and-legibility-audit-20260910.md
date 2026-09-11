# 行动格「内容 + 解析契约」审计（2026-09-10 v9 实案 · 同日第九轮）

> 触发：用户用过一阵之后问「表格有什么优化的吗？」。
> 此时**宽度与跨行重复已不是瓶颈**（v3 已用最坏行宽 + 跨行重复两把尺子治过），必须换尺子，
> 否则只会把已经压过的宽度再压一遍，伤自足性却拿不到收益。

## 1. 第三把尺子：视觉权重（决策权重最高的格子有没有语义色？）

**实案**：副表六行里，**唯一没有语义色的格子是「操作」行**——它固定 `cVal` 中性灰。
而它恰恰是"放不放行"的闸门；灯行（信号）反而有整行底纹抢眼。
→ **视觉权重与实际决策权重反了**，并且与"先看闸门、再看灯"的教读顺序自相矛盾。

**修法**（0 绘图槽 / 0 input / 文本零改动）：

```pine
color opCol = str.startswith(comboTxt, '确认') ? cGood : str.startswith(comboTxt, '不执行') or str.startswith(comboTxt, '不追') ? cBad : str.startswith(comboTxt, '仅作参考') ? cVal : cWarn
color opBg  = color.new(opCol, math.max(ACT_TRANSP - 25, 0))
// 与灯行同强度底纹，形成「灯 + 闸门」两个重点、中间四行中性的视觉层级
```

**要点**：用 `str.startswith(既有语义文本)` 派生颜色 → 不动文本、不动解析、不动判定链。

> ⚠️ **20260910 用户回退（必读 · 与本段结论相反）**：上面这套闸门配色**被用户明确要求撤回**，原话
> 「颜色不太行，改回去，**是内容要优化**」。同批的"爆仓行改黄"（§3）也一并回退，并已提交 `v10` 去掉。
> **结论：视觉权重这把尺子可以用来诊断，但不要擅自改颜色交付。**
> 用户对配色的容忍度很低，改配色=引入他可能反感的风险；他要的是**信息缺口**被补上（见 §9）。
> 只保留其中的**内容**修复（爆仓分支补 `⚠主导`、`table.new` 尺寸 2×10→2×6），那两条用户没反对。
> 若确实想改颜色：先问，或至少交付时明说"这处只改颜色、可一键回退"。

## 2. 第四把尺子：声明尺寸 vs 填充行数

`table.new(pos, 2, 10, border_width=1, frame_width=1, …)` 但只 `table.cell` 填了 6 行
→ **外框仍按 10 行画**，表格底部挂着一片空框（用户观感就是"有点难看"，且很难自己说清）。

- 声明行数必须 == 实际填充行数；`table.clear(actT, 0, 0, 1, N-1)` 的范围要同步。
- 面板从 10 行瘦到 6 行这类历史重构，**最容易漏掉 `table.new` 的尺寸参数**。
- 这是纯静态可查的：数一遍 `table.cell(actT, 1, k)` 的 max k，和声明行数比。

## 3. 「整行替换」是内容缺口的常见来源

```pine
// 病灶：爆仓分支整行替换 volTxtA
string volPanelTxtA = shortLiqA or longLiqA ? '▲放量·' + liqTxtA + (…streak…OI…) : volTxtA
```

进入爆仓分支就把 `volTxtA` 整行丢掉 → 连带吞掉 `⚠单所主导`、`合N%`。
而**去杠杆/轧空那几根恰恰是成交量最集中、单所主导风险最高的时刻**——最该看到这个警告时它没了。

修法：爆仓分支尾部**补回**风险词 `+ (perpDomA ? '⚠主导' : '')`。

**连带配色矛盾**：爆仓时量能行走"放量"分支变**绿**，而结论行同时写着 `涨势衰竭·空头回补` /
`去杠杆·防反弹` → 一行绿一行黄，语气自相矛盾。爆仓是"事发"不是"健康放量" → 改警示色：

```pine
text_color = perpDomA or shortLiqA or longLiqA ? cWarn : volUpA ? cGood : volDnA ? cWarn : cVal
```

**通用规则**：任何 `cond ? A : B` 的整行替换分支，都要问一句——
**A 丢掉了 B 独有的风险/质量字段吗？** 丢了就补回最风险的那一个（不是全补，避免行过长）。

## 4. 解析契约（改面板前必查）

- `scripts/auto_card.py`：`sub_keys = ["信号","结论","风险","高周","持仓","流向","覆盖","量能","爆仓","操作"]`
  **按行标签**解析副表 → **行标签一律不许改名、不许调序**。缺行可容忍（列表是超集：当前只填 6 行，
  风险/高周/覆盖/爆仓 已折叠进其它行）。
- 主指标行动格同理（13 行标签）。
- `comboTxt` 的取值文本（`确认多/确认空/弱确认/不升级/不执行/不追/仅候选/仅作参考/去杠杆/改USD/…`）
  是语义契约：**改颜色安全，改字要先查消费者**。
- `sub_keys` 的超集容忍**不是删行的许可证**——删行会丢信息且不可逆。
- 想改行序（例如把「操作」提到「信号」下面以贴合读表顺序）→ **不要做**，用颜色解决视觉权重即可。

## 5. 删/改 Data Window 字段前的消费者扫描法

对每个 plot 标题逐个在 `scripts/`（`auto_card.py` / `tv_data_bridge.py`）+ `docs/tv-indicator-field-map.md` 里查：

| 判定 | 实案 |
|---|---|
| 零命中 → **可删** | `OI Raw Compatibility Only`（标题自带 compatibility-only，全仓零消费者） |
| 有 Python 命中 → **不可删** | `HALDRO Valid Code` / `CVD Quality Code` / `Coverage Feed Mode`（auto_card 消费） |
| 无 Python 命中但 **TV 自身消费** → **不可删** | `Basic Packed Bus (唯一主副连接)`（主指标唯一 `input.source`）；`HALDRO State/Contract Pack` 经总线被解码 |

**"无 Python 消费者" ≠ "可删"** —— 必须同时排除 `input.source` 链路。删字段时在原位置留一行
"若要恢复，加回这一行"的注释。

## 6. 机械坑（本轮又踩一次，已固化）

**片段文件是整行时，锚点也必须含到行尾。**

驱动里把锚点写成**完整行常量**（含 `bgcolor = …)`），不要写半行（只到 `cVal,`）：

```python
# ✗ 半行锚点：片段自带行尾 ')'，原行尾又留一个 ')' → 双右括号 CE10016
rep(a, "        table.cell(actT, 1, 4, volPanelTxtA, text_color = perpDomA ? cWarn :…: cVal,", frag_new)
# ✓ 完整行锚点
VOLCOL_OLD = ("        table.cell(actT, 1, 4, volPanelTxtA, … : cVal,"
              " bgcolor = cBg1, text_size = actSizeSel, text_halign = text.align_left)")
rep(a, VOLCOL_OLD, frag("v9volcol_new.txt"))
```

好消息：这类**语法错由 `translate_light` 服务器编译就能抓到**（CE10016），不需要客户端。

## 7. 交付与验证（v9 = 33 项断言）

新增断言至少覆盖：

1. 闸门四态映射就位 + `opCol/opBg` 定义在 `comboTxt` 链**之后**（无前向引用）；
2. 操作行不再固定 `cVal`；非加密分支未动；
3. 爆仓分支含补回的 `⚠主导`；爆仓配色已改黄；常态配色未变；
4. `table.new(…, 2, 6,)` 两处 + `table.clear(…, 1, 5)`，已无 `2, 10` 残留；
5. **行标签顺序未变**（正则取 `table.cell(actT, 0, k, '<标签>')` 逐位比对）；
6. **`comboTxt` 十个关键字逐个 `in` 断言文本未改**（"文本零改动"要钉死，不能靠人眼）；
7. 绘图声明数、input、request 均未增；六项和、五所四所、总线合同未变。

## 8. 一句话总结

> 表格审计有四把尺子，按顺序用：**最坏行宽 → 跨行重复 → 视觉权重 → 声明尺寸 vs 填充行数**；
> 再加上两条硬约束：**行标签/闸门文本是解析契约（禁改名调序）**、**整行替换分支必须查丢字段**。
> （⚠ 按 §1 的回退记录，"视觉权重"只用于诊断，不要据此改颜色交付 —— 见 §12 更新后的总结。）

## 9. 第五把尺子：内容完备性（用户说"是内容要优化"时的正解 · 同日第十轮）

**触发**：用户说「颜色不太行…是内容要优化」，或就某一行问「这里只有 X，我想知道 Y」。

**方法：computed-but-unrendered 可达性扫描**（不是"数读取次数"的死变量启发式）。
把脚本里所有赋值（`=` 与 `:=`，含 `var` 前缀）建成"变量 → 它引用了谁"的图，以**渲染点**为根反向可达，
不可达者即"算了但用户看不到"。可直接跑 `scripts/pine_gap_scan.py`（见 §11 登记）。

**根集合必须同时覆盖两套面板写法** —— 这是首次扫漏 `lastWatchSide` 的直接原因：

| 面板 | 渲染点 | 漏掉的后果 |
|---|---|---|
| 副指标 | `table.cell(...)` | — |
| 主指标 | `array.push(rowVals, X)` / `array.push(rowLabs, X)` | 整条 `prevCompactText` 链被判"死"，结论失去意义 |

外加 `plot*/plotshape/plotcandle/bgcolor/hline/fill/alertcondition`。
**声明形态也要覆盖 `var`**：`var int lastWatchSide = 0` 用 `^\s*(?:string|bool|float|int|color)\s+` 是抓不到的。

**输出必然有噪声**（UDT 方法体、循环局部量、`this.xxx`、input 常量）。按"用户可见的一行/一格"过滤，
**先自己筛一遍再给用户**，不要把几百条候选原样倒出去。

### 9.1 本轮真正抓到并补上的三处（可作模板）

| 缺口 | 症状 | 补法 |
|---|---|---|
| **只有方向、没有强度** | `▲放量 / 缩量` 是二值（门槛 `volMaA×1.2`），1.2× 和 5× 在表里一模一样 | 补相对均量倍数 `' x' + str.tostring(Volume / volMaA, '#.1')`；分母**复用判定用的同一个 `volMaA`**，零新增计算 |
| **只有方向、没有量级** | 流向行 `本锚近10K买` 不说买得多狠 | 补净额占同期量比 `math.sum(Delta, N) / math.sum(volume, N)`。**分子分母必须同源**（都用当前图自身成交量；混进聚合五所量会系统性低估 5 倍）。符号已由"买/卖"表达 → 只给幅度 `·净18%` |
| **只显示"第一张缺票"** | `compactNeed` 用嵌套三元，共振 2/4 时另一张缺的票看不见 | 按固定顺序拼全部缺失再去尾 `+`：`'·缺' + str.substring(missingAllA, 0, str.length(missingAllA) - 1)` |

**通则**：补数字优先挑"已有分母 / 已有窗口"的现成量（`volMaA`、`ACT_LB`、`currATR`），
**不要为了一行新信息新造第二套口径**；一句话能说清的信息尽量塞进已有一行，不新增行。

## 10. 用户问"某一行只有 X，我想知道 Y"＝ 那一行的 Y 大概率已经算着没渲染

**实案（第十一轮）**：用户问主指标「前位」行"只有『被替代』，我想知道到了这个位置**是支持现位还是不支持**"。
源码里 `lastWatchSide`（1=原支撑 / −1=原阻力）**一直存在且从未渲染** —— 答案早就在脚本里，
只是缺一条渲染链。**这类提问不要凭常识设计新指标，先去源码找那个变量。**

补法＝角色判定 + 空间关系两类信息：

```pine
string prevRoleText = lastWatchSide == 1 ? (lastWatchReason == 1 ? "破转阻" : "仍撑") : lastWatchSide == -1 ? (lastWatchReason == 1 ? "破转撑" : "仍阻") : ""
bool   prevRelOk = not na(lastWatchPrice) and not na(pullbackLevelPrice) and not na(currATR) and currATR > 0
string prevRelText = prevRelOk ? "·" + (lastWatchPrice >= pullbackLevelPrice ? "↑" : "↓") + str.tostring(math.abs(lastWatchPrice - pullbackLevelPrice) / currATR, "#.1") + "A" : ""
```

**交付时必须给这张"到那个位置该怎么办"对照表**（用户要的是动作，不是字段说明）：

| 显示 | 含义 | 动作 |
|---|---|---|
| `仍撑` | 原支撑、未破（被更好位替代或过期） | **支持**，回踩仍有承接 |
| `破转阻` | 原支撑、已破 | **不支持**，回踩被挡 |
| `仍阻` | 原阻力、未破 | **不支持上涨** |
| `破转撑` | 原阻力、已破 | **支持**，回抽可接 |

**已破 → 角色翻转**（`lastWatchReason == 1`）是这一行最有价值的信息。
参考基准价用**该行自己写的那个位**（现位行用 `pullbackLevelPrice`，前位行就用它算距离），别另找行情价。

## 11. 往面板插代码：三个新语法坑（本轮各踩一次）

1. **多行三元续行 → `CE10013 Mismatched input`**。Pine 把 `string x = cond` 当作语句结束，
   下一行 `? A : B` 直接报错。**本指标族全部用单行三元**，跟随文件既有写法；
   不要为了可读性折行，也不要指望缩进续行（那是 `and/or` 这类长布尔的用法）。
2. **片段自带缩进 + 驱动自动缩进 → 二次缩进 `CE10013`**。片段文件里**不要写前导空格**，
   由驱动按"原行缩进"统一补：

   ```python
   def rep_line(t: str, prefix: str, new_block: str) -> str:
       """整行锚替换（忽略缩进匹配；新块自动沿用原行缩进）。"""
       line = next((l for l in t.split("\n") if l.strip().startswith(prefix.strip())), None)
       assert line is not None, f"找不到以 {prefix!r} 开头的行"
       assert t.count(line) == 1, f"该行出现 {t.count(line)} 次"
       indent = line[: len(line) - len(line.lstrip())]
       return t.replace(line, "\n".join((indent + l if l.strip() else l) for l in new_block.split("\n")))
   ```

   注意 `prefix.strip()`：面板内的行是缩进过的，拿带缩进的前缀去比会**匹配失败**。
3. **半行锚点（前缀锚）→ 原行尾巴残留**（本轮又犯，落在 `string cvdNowTextA = …`、
   `string volTxtA  = …`、`string compactNeed = …` 三处，报 `CE10156 Syntax error at input`）。
   §6 已写过，此处再钉一次：**一律用 `rep_line` 的整行锚，永远不要拿半个表达式当锚** ——
   片段是整行时，替换后原行尾会留在新片段后面，拼出一行语法垃圾。

## 12. 一句话总结（更新 · 以用户回退为准）

> 用户用过一阵之后再问"表格怎么优化"，答案**不在宽度**（v3 已压过），而在：
> **内容缺口（算了没渲染） > 声明尺寸 vs 填充行数 > 跨行重复 > 视觉权重（仅供诊断，不要擅自改颜色）**。
> 用户原话：**「颜色不太行，改回去，是内容要优化。」**
> 外加两条硬约束永远成立：**行标签/闸门文本是解析契约（禁改名调序）**、**整行替换分支必须查丢字段**。
