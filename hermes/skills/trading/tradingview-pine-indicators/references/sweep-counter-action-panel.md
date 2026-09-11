# Sweep Counter Pattern — Action Panel 结构行 (v10.3+)

Append a compact swept-vs-unswept count to the `结构：` line by iterating the global `levels[]` array.

## ⚠ 术语直白中文铁律（2026-06-26 用户纠正）

用户反馈："扫2存5 近0.8A 这个看着很迷茫"——**禁止单字抽象代号**。最终格式改为：

```
已扫2/剩5
```

下面的旧格式 `5扫/7待`、`扫N存M` 已废弃——保留历史是为了对照，**新实现必须用 `已扫/剩`**。

## Why

行动格结构行原本只显示最新 ICT 事件（如 `ICT 扫周四亚高收回`），交易者看不到全图共有多少流动性池已被扫/未扫。计数器回答"还剩几个流动性池待扫"这一关键问题。

## Implementation

Insert BEFORE `actionStateText`（避免 Pine 单遍扫描前向引用错误）：

```pine
// Sweep counter — how many ICT levels are swept vs waiting
string actionSweepSummary = ""
if SHOW_ICT_LEVELS and array.size(levels) > 0
    int sweptCount = 0
    int unsweptCount = 0
    int levelI = 0
    while levelI < array.size(levels)
        ICTLevel evLvl = array.get(levels, levelI)
        if evLvl.swept
            sweptCount := sweptCount + 1
        else
            unsweptCount := unsweptCount + 1
        levelI := levelI + 1
    actionSweepSummary := "已扫" + str.tostring(sweptCount) + "/剩" + str.tostring(unsweptCount)
```

Then expose as `sweepCountText` and append to `actionLine2`（结构行，加密市场）：

```pine
string sweepCountText = actionSweepSummary  // "已扫2/剩5"
string actionLine2 = marketCrypto ? "结构：" + sweepCountText + magnetText + " · CVD" + actionCvdText + ...
```

## Output

```
结构：已扫2/剩5 磁距0.8A · CVD日买盘 · VWAP上方 · EMA多
```

| Part | Meaning |
|------|---------|
| `已扫2` | 2 ICT levels have been swept (swept = true — price actually crossed the level) |
| `剩5` | 5 levels still intact (swept = false — not yet touched by price) |
| ICT off | Counter not appended (empty string) |

## Semantic Note

Counter uses `evLvl.swept` — **NOT** `evLvl.isActive`. `isActive` is set to `false` when session ends regardless of whether level was touched. Using `isActive` would miscount ended-but-unswept sessions as "swept". `swept` flag is only set `true` when sweep detection loop fires (`high > lvl.price and close < lvl.price` for highs after v10.3 repaint fix). Day/week pool levels are also tracked as `ICTLevel` objects in the same `levels[]` array, so the count includes them transparently.

## Pitfalls

- **Must iterate AFTER the sweep detection loop** — sweep loop sets `swept`, so counter must run after it. Insert counter code before `actionStateText` definition (action panel section).
- **Pine single-pass**: variables defined inside `if` blocks are scoped. Use `:=` to reassign counters in `while` loops — `int sweptCount = 0` outside, `sweptCount := sweptCount + 1` inside.
- **`levels` array must be in scope** — typically a global var at the top of the script. If `levels` is defined in a local block, hoist it to module scope first.
- **Do NOT use `isActive` as a proxy for sweep state**: `isActive` is set to `false` when a session ends (bar closes), not when price crosses the level. Inactive levels may still be unswept — counting by `isActive` inflates the "swept" count.
- **不要回退到 `扫N存M` / `5扫/7待` 等单字代号格式**：棠溪 2026-06-26 明确反馈这种缩写"看着很迷茫"，必须用 `已扫N/剩M` 直白格式。任何新加的代理字段都遵循此规则——参见 SKILL.md「用户偏好—行动面板术语必须直白中文」。

## 历史（已废弃格式，仅供对照）

| 版本 | 格式 | 状态 |
|---|---|---|
| v9.0 | `5扫/7待` | ❌ 废弃 — 颠倒语序，看着像"扫描5次" |
| v10.0 | `扫2存5` | ❌ 废弃 — 单字代号"存"含义不清 |
| v10.3 | `已扫2/剩5` | ✅ 当前 — 直白主动语态 |

## 同时改名的关联字段（同一用户反馈触发的批量修复）

| 旧 | 新 | 含义 |
|---|---|---|
| `近0.8A` | `磁距0.8A` | 离最近磁吸目标0.8个ATR |
| `VWAP 延/延下` | `VWAP上方过远/下方过远` | 价格偏离VWAP过远 |
| `VWAP 上/下/均` | `VWAP上方/下方/贴VWAP` | 价格与VWAP相对位置 |
| `位3/确5/延0` | `位置3/确认5/延展0` | 位置/确认/延伸风险三评分 |
| `止损1.5A` | `止损1.5ATR` | 单位A → ATR |
| `磁78↑` | `磁吸78↑` | 磁吸分数+方向 |
| `位✓/位~/位✗` | `位置✓/位置~/位置✗` | 核对行 |

所有 1-2 字代号改为完整中文词汇，单位 A 显式标 ATR，磁吸前缀一律加"吸"字。