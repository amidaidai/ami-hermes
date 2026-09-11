# Pine 绘图上限 71→64 修复（2026-07-09 · SVP_v6）

## 报错

```
脚本创建了太多绘图(71)。限制为64
```

## 根因（与 raw plot() 计数差很大）

TradingView 内部槽位：

```
TV_count ≈ series_color_plot×2 + const_color_plot×1 + fill×(1~2) + bgcolor×(1~2) + table×1
```

- `color=VWAP_COLOR` / `color=POC_COLOR` 等 **`input.color` 变量 = series 色 = 2 槽**
- `color=SHOW_X ? EMA_COLOR : color.new(EMA_COLOR, 100)` 三元色 = series = 2 槽
- `fill` / `bgcolor` 若 color 为 series/三元，也可能按 2 计
- 原始 ~30 个 `plot()` + series 翻倍 + 3 bgcolor + 2 fill + 1 table ≈ **71**

grep 只数到 30 仍会超限——**必须以 series 色翻倍估算**。

## 本会话有效修法（按省槽效率）

### 1. 视觉 plot 色常量化（主因，省最多）

plot 的 `color=` 改成字面 hex（与 input 默认一致），**不要**绑 `input.color` 变量：

```pine
// 坏：series 色 → 2 槽
plot(..., color=VWAP_COLOR)
// 好：const 色 → 1 槽
plot(..., color=#00BCD4)
```

本指标默认对照：

| 元素 | const hex |
|------|-----------|
| S VWAP | `#00BCD4` |
| Band1 | `#4CAF50` |
| Band2 | `#808000` |
| EMA9/21/34/55 | `#00FF6A` / `#009688` / `#2962FF` / `#B71C1C` |
| POC | `#0F0F0F` |
| nPOC | `#787B86` |
| VAH/VAL | `#2962FF` |
| W/M VWAP | `#FF00FF` / `#FF9800` |
| DO | `#673AB7` |

说明：用户在设置里改这些 input 颜色时，**plot 线色不再跟**；`line.new` 对象仍可用 input 色。

### 2. bgcolor 3→1（省 2~4 槽）

```pine
// 先定义，再单条 bgcolor（Pine 单遍，定义必须在引用前）
bool show_macro_bg = SHOW_MACRO and tf_sec_ict <= 900
bool show_sb_bg = SHOW_SILVER_BULLET and tf_sec_ict <= 3600
bool inMacroAm = show_macro_bg and not na(time(timeframe.period, MACRO_AM_TIME, TZ_NY))
bool inSilverBullet = show_sb_bg and (...)
bgcolor(inMacroAm ? color.new(#FFD700, 70) : inSilverBullet ? color.new(#00FFFF, 85) : ictSessionBg)
```

**陷阱**：用 regex 合并 bgcolor 时若误删 `inMacroAm`/`inSilverBullet` 定义 → `Undeclared identifier`。合并后必须 grep 确认定义行号 < bgcolor 行号。

### 3. fill 色尽量 const

```pine
// 仍 series（三元）：fill(..., color=cond ? color.new(#00FF6A,60) : color.new(#E91E63,60))
// 更省：固定一色
fill(pEma1, pEma2, color=showEma12Cloud ? color.new(#00FF6A, 70) : na)
```

云多空变色可牺牲换槽位。

### 4. MCP Data Window 压缩（次要，保 auto_card 字段名）

保留经典名（auto_card 依赖）：

- `MCP Side Code` / `Grade Code` / `Setup Score` / `Entry` / `Stop` / `Target` / `CVD` / `Quality`
- `MCP Bull FVG CE` / `Bear FVG CE`

新增结构压成 1 个：

```pine
// FvgQ*10000 + (OB+1)*100 + (BOS+2)*10 + (LV+1)
// BOS 码：CHoCH 优先 ±2，否则 BOS ±1
int mcpBosCode = chochBull ? 2 : chochBear ? -2 : bosBull ? 1 : bosBear ? -1 : 0
int mcpStructPack = int(nz(mcpFvgQualityCode, 0)) * 10000 + (mcpObCode + 1) * 100 + (mcpBosCode + 2) * 10 + (mcpLvCode + 1)
plot(mcpStructPack, "MCP StructPack (FvgQ*10000+(OB+1)*100+(BOS+2)*10+(LV+1))", display=display.data_window)
```

**压缩时必须保留** `mcpFvgQualityCode` / `mcpNearestFvgIsBull` 等计算定义；只删独立 `plot`，别删赋值。

### 5. 修后目标

- raw plot 调用 < 30
- series 色 plot = 0（视觉线）
- bgcolor = 1
- 乐观估 ~32–40；最坏（全 plot×2）也要 **≤63**

## 验证

```bash
# series 色剩余（应接近 0，除 data_window 无 color 的 plot）
grep -n "plot(.*color=" 主指标.pine | grep -v "color=#" | grep -v "color\\.new(#"

# bgcolor 条数（目标 1）
grep -c "^bgcolor(" 主指标.pine

# 定义顺序
grep -n "bool inMacroAm\\|bool inSilverBullet\\|bgcolor(inMacroAm" 主指标.pine
```

TV Pine Editor 保存挂图为最终验收。

## 连带小修（同会话）

- DO：`line.set_x2(doLine, bar_index + 1)`
- nPOC：创建 `endBar+1`，延展 `bar_index+1`
- BOS/CHoCH 显示/MCP：先 CHoCH 后 BOS（否则 CHoCH 永不显示）
