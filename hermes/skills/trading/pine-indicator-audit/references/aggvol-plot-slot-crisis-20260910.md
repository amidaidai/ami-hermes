# 副指标绘图槽危机：「脚本创建了太多绘图(65)。限制为64」（2026-09-10 实案）

## 1. 报错与误判

```
脚本创建了太多绘图(65)。限制为64
```

**误判**：我按 `plot()` 调用数估配额（`plot 45/64`、`bgcolor 1`、新增 2 → 以为 47/64），
实际 TV 内部口径下 v5 已经 **65**，刚好越线。

## 2. 正确口径（再次确认）

```
TV_count ≈ series_color_plot × 2 + const_color_plot × 1 + fill(1~2) + bgcolor(1~2) + table × 1
```

- `color=` 表达式含**三元 `?`**、**`array.get()`**、或引用 **`input.color` 变量** → **series → 2 槽**
- 字面 hex / `color.green` / `color.new(#XXXXXX, n)` 常量 → 1 槽
- `bgcolor` 的 color 若为 series/三元 → 2 槽
- 每个 `table.new` → 1 槽
- **`plotcandle` / `plotshape` 的 series 色同样翻倍**

**实测反推（口径偏移 +4 稳定，可用于预估）**：

| 版本 | 绘图声明数 | 本地估算 | TV 实测 |
|---|---:|---:|---:|
| v4 | 47 | 59 | **63** ✓（可用） |
| v5 | 49 | 61 | **65** ✗（超限） |
| v6 | 46 | 58 | 预计 **62** ✓ |

> 结论：**估算器 + 4 ≈ TV 实际**。本仓库估算器：`outputs/pine_20260905/plot_budget_20260910.py`
> （或交付副本同名脚本）。**任何新增视觉元素前先跑它，目标 ≤ 59。**

## 3. 省槽手段（按"伤害从小到大"排序）

### 3.1 `line` 对象代替 `bgcolor` / `plotshape`（0 槽，**但坐标量纲必须与本窗格一致**）

> ⚠️ **20260910 真实事故（必读）**：AggVol 锚界曾写成
> `line.new(bar_index, low, bar_index, high, extend=extend.both, ...)`
> —— `low`/`high` 是**价格**量纲（BTC 数万），而副图是**震荡窗格**（Delta/CVD ±数千）。
> TV 把绘图对象纳入窗格自动缩放 → 窗格 Y 轴被撑到价格区间 → **两条累计线一起被压成平线**，
> 用户实测症状：「这两条线丫的好平啊」。
> **结论：省槽不能用「价格量纲的坐标」换。** line/box/label 的 y 必须落在本窗格量纲内
> （或直接退回 `bgcolor`——量纲无关、零缩放风险）。修法见 v7：锚界退回 bgcolor，
> 代价 +1 槽由「复用闲置槽位」和「删零消费者 DW plot」净额抵消。

`line.new` 确实**不吃 64 绘图槽**（只受 `max_lines_count`，默认 50 约束）。
本仓库 `zeroLine` 早就用这个模式（`line.new(bar_index-1, 0, bar_index, 0, ...)`，y=0 量纲安全），
**在震荡窗格里要照抄的是它的 y 取值方式，不是它的对象类型**。

若确实需要用 line 画全高竖线，y 必须取本窗格量纲内的值（如 `-1 .. +1`，靠 `extend.both` 向上下无限延展），
**绝不能传 `low`/`high`/`close`**。本仓库当前选择是保守退回 bgcolor，不再赌 line 的渲染。

```pine
// v7 现行写法（震荡窗格内的锚界标记）：量纲无关
bgcolor(SHOW_ANCHOR_AID and newCvdPeriod and isCryptoPlot ? color.new(chart.fg_color, 80) : na, title='CVD锚界')

// v6 废弃写法（会把窗格 Y 轴撑到价格区间 → 压平所有曲线）
// line.new(bar_index, low, bar_index, high, extend=extend.both, ...)   ← 禁止
```

**自检**：上线前跑 `grep -nE "(line|label|box)\.new\(.*\b(low|high|close|open|hl2|hlc3)\b"`，
副指标里应为**空**（主指标因为挂在价格窗格，价格量纲是合法的）。

### 3.2 复用"同模式闲置"的 plot 槽（0 槽，次选）

同一 pattern 下互斥的 series 可以**合并进一条 plot**，用条件三元分派值 + 条件 style：

```pine
plot( mode == 'Delta' and isCryptoPlot ? Delta : mode == 'Cumulative Delta' and isCryptoPlot and SHOW_ANCHOR_AID ? cumRollQ : na,
      'Delta / 净主动流·整锚',
      style= mode == 'Delta' ? plot.style_columns : plot.style_line,
      color= mode == 'Delta' ? (Delta > 0 ? bull_color : bear_color) : color.new(color.teal, 15) )
```

本文件 EX1..EX5 早就用条件 style（`style=exd ? plot.style_line : plot.style_columns`），**条件 style 可编译**，是既有先例。
合并后槽位数不增（series 色本就是 2 槽），但**省下了"新增一条独立 plot"的 1 槽**。

### 3.3 删"零消费者"的 Data Window plot（−1 槽）

判据（必须全中才删）：
1. 该 plot 标题在 `scripts/`（含 `auto_card.py`、`tv_data_bridge.py`）、`docs/tv-indicator-field-map.md` 中**零命中**；
2. **不是**主指标 `input.source` 指向的那条（主指标只读 `Basic Packed Bus (唯一主副连接)`）；
3. 标题自带 `compatibility only` / `legacy` 之类自我否定语义。

本次删的是 `OI Raw Compatibility Only`（`plot(haldroUsableA and oiOkA ? oiCloseA : na, ...)`），
并在原位置留下"若要恢复，加回这一行"的注释。

**不可删**：`HALDRO Valid Code`（`auto_card.py` 读）、`CVD Quality Code`（`auto_card.py` 读）、
`Coverage Feed Mode`（`auto_card.py` 读）、`Basic Packed Bus`（主指标 input.source）、
`Coverage Exchanges/Spot/Perp`、`Confirm Score`、`Exchange Dominance %`（字段表内）。

### 3.4 视觉 plot 色常量化（−1/条，暂缓）

把 `colEXv1..colEXv5` 这类 `input.color` 换成字面 hex：每条省 1 槽，AggVol 最多 **−5**。
代价：**用户不能再从设置里改这些线色** → 必须事先问，不可静默执行。

### 3.5 Data Window 打包（−2，暂缓）

`Coverage Exchanges/Spot/Perp` 三条合成 1 条：省 2 槽。
代价：改字段名 → 必须同步 `docs/tv-indicator-field-map.md` 与所有读取脚本。

## 4. 副指标槽位现状（2026-09-10 v6 后）

| 项 | 值 |
|---|---:|
| 绘图声明 | 46 |
| 本地估算 | 58 |
| 预计 TV | ≈62 / 64（余量 2） |
| request | 8（六项和 93/254，还有 161 余量） |

**结论：绘图槽是这副指标的第一瓶颈，不是 request、也不是 token。**
下一步任何新增视觉元素（第三条曲线、新标记、新色带）**必须先跑估算器**，
≤59 才动手；否则先做 3.1/3.2/3.3。

主指标同口径估算 ≈41 → 预计 45/64，**余量充足**，不是瓶颈。

## 5. 交付/验证口径（重要）

`translate_light` 服务器端点**不检查 64 绘图上限**，`errors2=[]` **不能**证明没超限 ——
该限制只在 **TV 客户端挂图/保存**时触发。所以：

- 服务器编译只能证明语法/其它 IL 约束；
- **绘图上限的最终判定必须由用户在 TV 客户端挂图**，不得声称"已修复"；
- 交付时必须写明这一条，并附预估槽位与数据来源（估算器 + 实测反推偏移）。
