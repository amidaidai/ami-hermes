# Pine SVP v6: plot quota, zone labels, loop step (2026-07-09)

Session: desktop `SVP_v6.pine` compile/runtime fixes after v6 OB/BOS/CHoCH/LV merge.

## 1) "脚本创建了太多绘图(71)。限制为64"

### Root cause
TV plot slots ≈ `const_color_plot×1 + series_color_plot×2 + fill×? + bgcolor×? + table`.
`color=INPUT_COLOR` / ternary colors double. Matching formula to 71:
`plots×2 + fills×2 + bgcolors×2 + table ≈ 30×2 + 2×2 + 3×2 + 1 = 71`.

### Fix pattern (preserve auto_card field names)
1. **Visual plots → constant hex** (S VWAP/bands, EMA, axis POC/VAH/VAL/nPOC/W·M VWAP/DO). Inputs still color `line.new` objects; plot series no longer follow input color.
2. **Merge 3 bgcolor → 1** after defining `inMacroAm` / `inSilverBullet` (do not delete defs when merging).
3. **EMA cloud-only**: plot values for `fill`, line color `color.new(#hex, 100)` constant transparent. Do not use `color.new(#hex, SHOW_EMA ? 0 : 100)` (series transparency doubles again).
4. **MCP DW**: keep classic titles `MCP Side/Grade/Setup/Entry/Stop/Target/CVD/Quality` + FVG CE×2; pack OB/BOS/LV (+ optional FvgQ) into one `MCP StructPack`.
5. Target worst-case estimate **≤63** after edit.

### Delivery
Sync Desktop + upload + `SVP_v6_ready.pine` / `.txt`. User must full-replace Pine Editor source and re-add study (old saved script keeps old line numbers).

## 2) Runtime: `'step' in loop must be greater than zero` @ breaker for

### Bad
```pine
if array.size(obList) > 0
    for oi = array.size(obList) - 1 to 0 by -1
```
When `size==1` → `for oi = 0 to 0 by -1` → runtime error (often reported as L2205).

### Good
```pine
int oiBrk = array.size(obList) - 1
while oiBrk >= 0
    ...
    oiBrk -= 1
```

### Related
`maxIndex`: `for i = 1 to array.size(a) - 1` when `size==1` → `1 to 0` → same class of error. Guard `sz<=0 / sz==1 / else loop`.
Panel: `for r = 0 to pnlRowCount - 1` only if `pnlRowCount > 0`.

User still seeing L2205 after fix almost always means **TV still running old source** — verify Editor search `by -1` is empty and `oiBrk` exists.

## 3) Compile: Undeclared `inMacroAm` / `inSilverBullet`

Caused by bgcolor merge regex deleting:
```pine
bool show_macro_bg = ...
bool inMacroAm = ...
bool inSilverBullet = ...
bgcolor(...)
```
and leaving only `bgcolor(inMacroAm ? ...)`. **Always keep defs immediately above the single bgcolor.**

## 4) Zone labels (FVG/OB/BRK/LV) — user preference

- **Language**: English tags `FVG↑/↓`, `OB↑/↓`, `BRK↑/↓`, `LV↑/↓` (not Chinese 缺口/订单块/真空).
- **Position**: **BOTTOM-RIGHT INSIDE the box**, not outside.
  - `x = rightEdge - ZONE_LABEL_X_IN`
  - `y = min(top,bot) + ATR * ZONE_LABEL_Y_ATR` (lift up into box)
  - `style=label.style_label_right` (text to the left of anchor → into box)
- Inputs: `ZONE_LABEL_SIZE`, `ZONE_LABEL_X_IN`, `ZONE_LABEL_Y_ATR`.
- LV = Liquidity Void; settings label may say `Show Liquidity Void (LV)`.
- UDT fields: `FVG.lb`, `OBZone.lb`; delete on expire/shift; maintain x/y/text/size/style each bar.

## 5) Process pitfall: "文件没有改到"

Never claim zone/EMA/plot fixes are done without:
1. Successful write to absolute Desktop path
2. sha/size verify
3. grep for new anchors (`FVG↑`, `ZONE_LABEL_X_IN`, `oiBrk`, transparent EMA color)

Prefer writing a `patch_*.py` script then running it over fragile multi-line shell heredocs on Windows.

## 6) DO / nPOC visibility (same session)

- `line.set_x2(doLine, bar_index + 1)` not `bar_index`
- nPOC create `endBar + 1`; extend `bar_index + 1`
