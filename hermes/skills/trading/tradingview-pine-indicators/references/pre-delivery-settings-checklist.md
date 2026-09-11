# Pre-Delivery Settings & Visibility Checklist

Run this checklist before delivering a Pine Script indicator to the user's desktop. It catches the most common visibility failures that make a new install look broken.

## Run this audit

```bash
# 1. Count all input.bool defaults
grep -n 'input\.bool(' indicator.pine | grep -v '^#' 
```

## Check every default against expected behavior

| Input | Expected Default | Why |
|---|---|---|
| `SHOW_POC` | `true` | POC is the primary structural reference — must be visible |
| `SHOW_VAH_VAL` | `true` | Value area levels are core to the SVP system |
| `SHOW_NPOC` | `true` | Naked POC is a key level |
| `SHOW_VAH_VAL_LINES` | `false` | Lines clutter the chart; labels + axis are enough |
| `SHOW_OPEN_ONLY_ACTIVE` | `false` | Users expect active session labels to be visible |
| `SHOW_DO_LINE` | `true` | Daily open is a commonly-used structural reference |
| `SHOW_EMA_FILTER` | `true` | EMA trend filtering is a core decision input |
| `SHOW_VWAP` | `true` | VWAP is a primary fair-value reference |
| `SHOW_VWAP_BANDS` | `true` | SD bands add context |
| `SHOW_ICT_LEVELS` | `true` | ICT session levels are core to the system |
| `SHOW_KILLZONE` | `true` | KillZone windows are essential context |
| `SHOW_CVD_CONFIRM` | `true` | CVD is the confirmation layer |
| `SHOW_SESSION_CVD` | `true` | Session CVD adds directional context |
| `SHOW_SMT` | `true` | Cross-instrument divergence is a validation layer |
| `SHOW_ACTION_PANEL` | `true` | The action panel IS the dashboard |
| `SHOW_BACKGROUND` | `true` | VA background adds visual context |
| `SHOW_PROFILE_HIST` | `true` | Profile histogram is the SVP view |
| `SHOW_SVP_EXTREMES` | `true` | SVP extreme sweep lines are structural |

## Check all input.color defaults

```bash
grep -n 'input\.color(' indicator.pine
```

Any color below `#3A3A3A` will be invisible on TradingView's dark theme (`#131722`). Common offenders:
- `#0F0F0F` → invisible (near-black on dark bg)
- `#1A1A1A` → nearly invisible
- `#2A2A2A` → barely visible

**Safe minimum on dark**: `#4A4A4A` (minimum contrast). **Recommended visible mid-tones**: `#78909C` (blue-grey), `#607D8B`, or `#FFD700` (gold).

## Check for banned visual features

```bash
grep -c 'bgcolor(' indicator.pine     # Session bgcolor may be intentional; KillZone/Silver Bullet/Macro bgcolors should be reviewed and usually avoided if they overlap session context
grep -c 'plotshape(' indicator.pine   # Should be 0 — no chart markers
```

For Tangxi's current SVP dashboard, active ICT session background coloring can be preserved when already present because it helps distinguish Asia/London/NY sessions. Do not blanket-fail every `bgcolor()` occurrence; inspect whether it is session context (allowed) or extra KillZone/marker highlighting (usually rejected unless explicitly requested).

## Check for dead inputs

```bash
# For each input variable name, count references
for var in $(grep -oP 'input\.\w+\(\w+,\s*"(\w+)"' indicator.pine | grep -oP '"\w+"' | tr -d '"'); do
  count=$(grep -c "\b$var\b" indicator.pine)
  echo "$var: $count refs"
done
```

Any input with exactly 1 reference (= its own declaration) is dead — remove it.

## Check label price duplication

```bash
# Labels created with price in the name AND updateLabel() appends price = duplication
grep -n 'f_make_liquidity_level.*str\.tostring' indicator.pine
```

If `updateLabel()` uses `label.set_text(lb, dispName + ": " + str.tostring(price, ...))`, then `f_make_liquidity_level()` calls must NOT include `str.tostring(price, ...)` in the label name. A hit on the grep above means the label will show `周三 高 2345.6: 2345.6` (duplicated price). Fix: create with just `"周三 高"` and let `updateLabel()` add the price.

## Check label size defaults

| Input | Expected Default | Why |
|---|---|---|
| `DAY_LIQUIDITY_LABEL_SIZE` | `size.small` | Day pools are structural references — must be readable |
| `WEEK_LIQUIDITY_LABEL_SIZE` | `size.small` | Week pools are structural references — must be readable |
| `ICT_SWEPT_LABEL_SIZE` | `size.small` | Swept liquidity lines are important — `size.tiny` is too small |
| `ICT_UNSWEPT_LABEL_SIZE` | `size.small` | Unswept labels must be readable at a glance |

Also verify `updateLabel()` routes day/week pools to their own size inputs, not the generic ICT size. Detection pattern: `isDayPool = str.contains(name, " 高") or str.contains(name, " 低")` → `DAY_LIQUIDITY_LABEL_SIZE`; `str.contains(name, "上周")` → `WEEK_LIQUIDITY_LABEL_SIZE`.
