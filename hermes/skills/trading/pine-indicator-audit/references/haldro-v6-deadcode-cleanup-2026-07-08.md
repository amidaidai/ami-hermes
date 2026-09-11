# HALDRO v6 重绘隐患 + 主指标叙事卡死代码清理（2026-07-08 实案）

## 1. HALDRO v6 ta.highest/ta.lowest warning→has_errors 修复

**根因**：v6 smart_compile 把 `ta.highest/ta.lowest` 直接写在 `and` 条件内的写法标 warning，
若用户把 warning 视为 has_errors，图表重新加载时副指标会挂不上，TV MCP 加密验证层直接断。

**病代码（副指标 ~L337-338）**：
```pine
float cvdSwingMagA = ta.highest(high, cvdDivLenA) - ta.lowest(low, cvdDivLenA)
bool cvdBearDivRawA = high >= ta.highest(high, cvdDivLenA)[1] and sessCvdA < ta.highest(sessCvdA, cvdDivLenA)[1]
bool cvdBullDivRawA = low <= ta.lowest(low, cvdDivLenA)[1] and sessCvdA > ta.lowest(sessCvdA, cvdDivLenA)[1]
```

**修法（先无条件全局赋值，再条件引用）**：
```pine
// HALDRO v6 warning fix: ta.highest/ta.lowest 必须先赋值给无条件全局变量，再被条件消费者引用
float hH_A = ta.highest(high, cvdDivLenA)
float hC_A = ta.highest(sessCvdA, cvdDivLenA)
float lL_A = ta.lowest(low, cvdDivLenA)
float lC_A = ta.lowest(sessCvdA, cvdDivLenA)
float cvdSwingMagA = hH_A - lL_A
bool cvdBearDivRawA = high >= hH_A[1] and sessCvdA < hC_A[1]
bool cvdBullDivRawA = low <= lL_A[1] and sessCvdA > lC_A[1]
```

**验证**：grep 确认无 `and ta.highest` / `and ta.lowest` 残留；跑 pine_static_scan.py 看重绘信号数与 plot 计数未破。

## 2. 主指标叙事卡死代码安全清理

**死变量（v2 行动格取代，0 处 table.cell 消费）**：
`stateText` / `cardLine1-3` / `directionGuideText` / `actionGuideText` / `detailText`
—— 含声明行（如 `string stateText = "等待结构"`）与整条 if/else 链内所有 `:=` 赋值。

**保留变量（仍被消费，绝不可删）**：`watchText`、`invalidText`
—— `invalidText` 在 L2672-2691 驱动止损价推导，`watchText` 在面板等待文案 L2910/L3047 使用。

**三道护栏（务必执行）**：
1. 删除前 `grep -n "table.cell(.*VAR"` 确认死变量零消费；有消费则停手。
2. 删除行扫描对 `watchText`/`invalidText` 的声明与 `:=` 行强制跳过（误删护栏）。
3. 删除后回扫：死变量无声明/赋值残留，且 `watchText`/`invalidText` 仍有声明。

**实测结果（本会话）**：删 126 行（3210→3084），无残留，配额/def 顺序未破。
脚本化见 `scripts/clean_dead_narrative_card.py`（自带三道护栏，跑完再跑 pine_static_scan.py 复核）。

## 3. 风控参数死代码处理（不删，改标注）

主指标 L261-263 的 `RISK_PER_TRADE_PCT` / `DAILY_MAX_LOSS_PCT` / `WEEKLY_MAX_LOSS_PCT`
全文仅定义、零引用 —— 用户易误以为有自动风控保护。
正确处置：**不删**（删了改变输入面板语义），改为 input 标题加「展示用未联动」+ tooltip 注明
"当前未接入 R:R/风控脚本，不自动缩仓/禁单/降频"。避免误导而非消除变量。

## 4. 改完收尾铁律

任何 Pine 改写后必须：
- 跑 `python scripts/pine_static_scan.py 主指标.txt 副指标.txt` 复核配额(<40)、plot(<64)、对象(<500)、def 顺序。
- 副指标改完上 TV 重加前，先确认 v6 是否真报 has_errors；触发才需上面第1节修法。
- 驾驶舱双指标定位/CVD 冲突铁律不变（冲突以主指标真逐笔 Delta 为准）。
