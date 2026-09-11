# 静态审计扫描器的三类误报（20260910 实测）

> 审计 Pine 指标时，扫描器给出的"发现"必须先自证不是误报，再写进报告。
> 本节三个误报都在 20260910 复审里真踩过，误报率见各条。

## ① lookahead 重绘误报（误报率 3/4）

**错法**：只扫 `request.security(...)` 那一行有没有 `[1]`，一见 `lookahead_on` 无偏移就报"重绘/未来泄漏"。

**真相**：收盘偏移常写在 **UDF 内部**。实测 SVP 4 个 `lookahead_on` 请求，3 个的 `[1]` 在 UDF 里：

```pine
f_htf_trend_confirmed_pack() =>
    [close[1], eFast[1], eSlow[1], v[1]]     // ← 偏移在这
[htfCloseC, ...] = request.security(syminfo.tickerid, htfTf,
                    f_htf_trend_confirmed_pack(), lookahead=barmerge.lookahead_on, ...)
```

**正确判据**：`lookahead_on` + 满足二者之一 —— 请求行有 `)[1]`，或**被调 UDF 的返回表达式含 `x[1]`**。
扫描器要能把 UDF 体打开（按函数名定位 `name(...) =>` 起始行，读后续 ~15 行找 `[1]`）。

非重绘只有两种合法写法：`lookahead_off + [1]`，或 `lookahead_on + [1]`（偏移在 UDF 里也算）。
同一脚本内所有 HTF 请求必须同口径，否则「高周趋势」与「高周 FVG/OB」会打架。

## ② 除零扫描在 Pine 里没有意义（不要做这个维度）

两个理由：

1. **Pine 除法遇 0/na 返回 `na`，不崩、不画错**，不是 P0/P1；
2. 正则 `/` 会命中**字符串字面量里的斜杠**与 input label：`"VAH/VAL"`、`"BTC/USDT"`、`"GBP/USD"`、
   `"Asia/Shanghai"`……实测刷出 65 条"风险"，全是垃圾。

真要查只查一类：真实运算里的 `x / y`（y 是变量）且同行无守卫，且只当 P2 提示。

## ③ "失效开关"传递闭包误报（误报率 13/16）

**错法**：判断一个 `input` 是否失效时，从它出发做引用可达性，看能不能摸到「绘制 sink」
（`plot` / `label.new` / `table.cell` / …）。摸不到就报"摆设开关"。

**真相**：**守卫一整个块的开关全部误判**：

```pine
if SHOW_ACTION_PANEL          // 这行没有 sink
    ...                        // 真正的 table.cell 在块里，行号离得很远
    table.cell(actT, ...)
```

实测 SVP 16 个被报的开关里 13 个是这种误报（`SHOW_ACTION_PANEL`、`BACKGROUND_COLOR`、`EXTEND_POC`、
`SHOW_PROFILE_HIST`、`DISPLAY_TZ` 全是真在用的）。

**正确判据只有两条**（都精确、可复现）：

1. 该 input **零引用**（声明行之外一次都没出现）→ 铁板钉钉的摆设开关；
2. 该 input 的**全部引用行**都只出现在「定义某个已死变量」的那一行上。

其余一律不报。

## 可靠的死码判据

变量声明后**全文零引用**（词边界正则，排除声明行本身）。

解析器注意 —— 要同时吃两种声明形态，否则漏报：

```pine
float oiCloseA = ...            // 带类型关键字
calctype = input.string('SUM')  // 老脚本常见，无类型关键字
```

但正则放松后又会把 `dynamic_requests=true,` 这种**续行**误当声明 →
用类型关键字白名单 + 行首缩进严格约束，输出前人工过一眼。

## 报告口径

死码清单必须给：**行号 + 变量名 + 是否带内嵌字符串**。
带内嵌常量字符串的才是 CE10117 的 IL 杠杆（官方口径：缩短内嵌常量字符串是省 IL 的主要手段）；
纯 bool/float 死码只省一个声明。

删之前先确认它**没有"本该渲染"的语义**：

- `entrySideHtfOk` / `entryDispOk` —— 取侧闸门包装，闸门本体已在 `setupLongA` / `badDisp` 生效 →
  **删包装零行为变更**（但要在报告里写清"这是冗余不是缺口"，否则用户以为闸门丢了）；
- `magnetTargetName` / `longBreakName` 这类看着像"本该显示在表格里"的 → **先问用户**再删。
