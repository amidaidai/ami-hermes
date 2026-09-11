# SVP 行数坍缩修复 + MCP Data Window 完整性验证 (2026-07-09)

## 1. SVP 小币种行数坍缩

### 症状
用户报告：一些小币种的 SVP 分布图只显示几行，不像主流币那样显示完整的 70 行。

### 根因定位

`processAndRender` 方法中的桶宽（stepSize）计算链：

```pine
L611: float priceRange = math.max(this.maxProfilePrice - this.minProfilePrice, syminfo.mintick)
L612: float rawStep = priceRange / FINAL_ROWS
L613: float minStep = syminfo.mintick * finalVpMinTickMult    // 默认 mintick × 20
L615: float stepSize = math.max(rawStep, minStep)             // ← 问题核心
L616: stepSize := math.max(stepSize, syminfo.mintick)
L617: stepSize := math.min(stepSize, priceRange / 5.0)       // 至少 5 行兜底
```

**当小币种日内波幅很小时**：
- `priceRange` 很小 → `rawStep` 很小
- `minStep = mintick × 20` 是固定下限
- `stepSize = max(rawStep, minStep)` → `minStep` 胜出
- 实际行数 = `priceRange / stepSize` 远少于 `FINAL_ROWS`
- L617 兜底到 `priceRange / 5` → 只有 5 行

### 数值验证

| 币种 | price | range | mintick | minStep | rawStep | stepSize(前) | 行数(前) | stepSize(后) | 行数(后) |
|------|-------|-------|---------|---------|---------|-------------|---------|-------------|---------|
| BTC | 60000 | 2000 | 0.01 | 0.2 | 28.6 | 28.6 | 70 | 28.6 | 70 |
| 小币A | 0.05 | 0.002 | 0.0001 | 0.002 | 0.0000286 | 0.002 | 5(兜底) | 0.0001 | 20 |
| 极低波幅 | 0.01 | 0.0005 | 0.00001 | 0.0002 | 0.0000071 | 0.0002 | 5(兜底) | 0.0000217 | 23 |

### 修复代码

在 L613 后插入：

```pine
// 自适应最小桶宽：小币种波幅小时，minStep会强制抬高桶宽导致只有几行
// 当 minStep 会导致实际行数不足 minBuckets 时，自动缩小到保证至少 minBuckets 行
int minBuckets = math.max(math.floor(FINAL_ROWS / 3), 20)
minStep := math.min(minStep, priceRange / minBuckets)
```

- 加密 `FINAL_ROWS=70` → `minBuckets = max(23, 20) = 23`
- 其他 `FINAL_ROWS=50` → `minBuckets = max(16, 20) = 20`
- 主流币 `rawStep` 始终 > `minStep`，修复对其无影响

## 2. MCP Data Window 完整性验证

### 背景
用户使用棠溪交易系统的 TV MCP 读取指标 Data Window 值做自动化分析。为降 token 删除代码后，必须确认 MCP 读取的 plot 未被误删。

### 主指标 Data Window plots (11个)

```
MCP Side Code
MCP Grade Code
MCP Setup Score
MCP Entry Price
MCP Stop Price
MCP Target Price
MCP CVD Value
MCP Quality Code
MCP Bull FVG CE
MCP Bear FVG CE
MCP FVG Quality Code
```

### 副指标 Data Window plots (17个)

```
Volume (不导出，主图)
OI Total
Estimated CVD Value
CVD Value
CVD Method Code
CVD Quality Code
LSR
Volume Ratio
Coverage Exchanges
Coverage Spot
Coverage Perp
Coverage Feed Mode
Exchange Dominance %
Confirm Score
HALDRO Risk Code
HALDRO Flow Pack (OI*100+CVD*10+SP)
Composite
```

### 验证结果

本次 token 削减删除的 15 个死变量（`stateText`/`cardLine1-3`/`detailText`/`directionGuideText`/`actionGuideText`/`nowAdviceText`/`treatmentText`/`valueText`/`vwapText`/`emaText`/`valuePosText`/`barConfirmText`/`trendScoreText`/`reversalScoreText` + `valueRange`/`valuePos`）全部是面板显示用的字符串/数值变量，**无一出现在 Data Window plot 中**，MCP 读取链路零影响。

## 3. 本次修复清单

| # | 问题 | 修复 | 影响 |
|---|------|------|------|
| 1 | `cvdBearStars`/`cvdBullStars` 未定义 | 插入 `int cvdBearStars = 0` / `int cvdBullStars = 0` | 编译通过 |
| 2 | Token 超限 81303 > 80000 | 删 15 个死变量 + 空 if/else 链 + 面板三档减两档 | ~77455 tokens |
| 3 | 小币种 SVP 只显示几行 | `minStep` 自适应缩小，保底 20-23 行 | 小币种行数从 5 → 20+ |

### 最终文件
`C:/Users/Administrator/Desktop/SVP_fixed.pine` (180,705 字符, 3077 行)