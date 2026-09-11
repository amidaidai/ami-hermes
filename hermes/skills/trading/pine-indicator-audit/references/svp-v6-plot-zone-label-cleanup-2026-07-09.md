# SVP v6 plot quota + zone label cleanup (2026-07-09)

Session: Desktop `SVP_v6.pine` compile/runtime fixes + chart declutter for 棠溪 fast scalp style.

## Plot limit: too many plots (71). Limit 64

### Root cause
TV counts **series-color plots as 2 slots**. `color=INPUT_COLOR` from `input.color()` is series. Conditional ternary colors also series.

Matching formula seen in session (~71):
```
approx = plot_count*2 + fill*2 + bgcolor*2 + table
```

### Fix pattern (preserve auto_card MCP titles)
1. Visual plots: use **constant hex** `color=#00BCD4` / `color.new(#00FF6A, 100)` — not `color=VWAP_COLOR`.
2. Merge multiple `bgcolor()` into **one** call (still define booleans first).
3. Keep classic MCP names: `MCP Side Code`, `Grade`, `Setup`, `Entry`, `Stop`, `Target`, `CVD`, `Quality`, FVG CE×2.
4. Pack only new OB/BOS/LV into `MCP StructPack` if needed for margin.
5. EMA cloud-only: plot values for `fill()` but line color fully transparent constant `color.new(#hex, 100)`.

### Declaration order trap
When merging bgcolor, do **not** delete `inMacroAm` / `inSilverBullet` definitions. Define before use:
```
bool show_macro_bg = ...
bool inMacroAm = ...
bool inSilverBullet = ...
bgcolor(inMacroAm ? ... : inSilverBullet ? ... : ictSessionBg)
```

## Runtime: 'step' in loop must be greater than zero

### Cause A — `for i = N to 0 by -1`
When `array.size==1` → `for i = 0 to 0 by -1` throws on some Pine builds.

**Fix:** `while` reverse:
```
int i = array.size(arr) - 1
while i >= 0
    ...
    i -= 1
```
Never use Pine `continue` (not supported).

### Cause B — `for i = 1 to size-1` when size==1
`maxIndex`: size 1 → `for i = 1 to 0` with default +step fails.

**Fix:**
```
if sz <= 0 → na
else if sz == 1 → 0
else for i = 1 to sz - 1
```

### Cause C — `for i = 0 to count-1` when count==0
Guard: `if count > 0` / `if pnlRowCount > 0` before loop.

## Zone declutter defaults (棠溪快进快出)

| Feature | Default | Why |
|---------|---------|-----|
| FVG boxes+labels | ON, max ~3 | Highest entry value (CE) |
| Unmitigated OB | ON, max ~4 | A-grade confluence |
| Mitigated OB boxes | **DELETE** (`REMOVE_MITIGATED_OB=true`) | Faded boxes = noise |
| BRK text | Label as **OB** text; box may recolor | Avoid BRK/FVG/OB text clash |
| LV | **OFF** | Low scalp value |
| Label style | `label.style_none` | Plain text, no pointer bubble |
| Label language | **English** FVG↑/OB↑/BRK↑/LV↑ | User preference |
| Label position | Bottom-right **INSIDE** box | `x=right-inset`, `y=bot+ATR*lift`, `style_none` |
| S VWAP bands | **±1σ only**; ±2σ default OFF | Community: ±1σ = value area |

### OB mitigate rule (this codebase)
- Bull OB mitigated: `low <= ob.top`
- Bear OB mitigated: `high >= ob.bot`
- On mitigate + `REMOVE_MITIGATED_OB`: delete box+label+remove array entry (no `continue`)

### FVG fill rule
- Bull filled: `low <= bot`; bear: `high >= top` → delete box/CE/label

### HTF FVG
Validation only (`htfConf` / quality) — do not draw HTF boxes on LTF chart.

## Delivery discipline (user: 文件没有改到)
1. Actually write Desktop + upload + `SVP_v6_ready.pine/.txt`
2. Verify with sha + grep markers before claiming done
3. On Windows Hermes bash: prefer `write_file` + `python script.py` — long `python - <<'PY'` heredocs break on quoting

## Files after session
- Production path pattern: `Desktop/SVP_v6.pine` + `.hermes-web-ui/upload/default/SVP_v6.pine`
- Deliver ready copy: `Desktop/SVP_v6_ready.pine`
