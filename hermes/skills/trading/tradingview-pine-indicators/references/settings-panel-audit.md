# TradingView Dashboard Settings-Panel Audit

Use this reference after simplifying a Pine dashboard or removing chart/table features.

## Why this matters

TradingView users experience the Inputs panel as part of the product. Dead controls create confusion even if the script still compiles. After removing chart markers, detail rows, or visual modes, audit the inputs panel and delete controls that no longer change behavior.

## Practical audit loop

1. Extract all `input.*` variable definitions.
2. Count references to each input variable across the script.
3. Treat `count == 1` as a strong dead-input signal: it is declared but not used anywhere else.
4. For multiline `input.string(... options=[...])` definitions, delete the continuation line too.
5. Remove helper functions that only supported the deleted setting, such as fixed-width wrapping for a removed detail row.
6. Re-run the scan and require zero unused input variables before reporting the panel as cleaned.
7. Re-check critical behavior after cleanup: table position, opacity defaults, alertcondition lines, price-axis plots, and absence of removed marker calls.

## Example Python scan

```python
from pathlib import Path
import re

p = Path(r"D:/Hermes agent/outputs/SVP_ICT_VWAP_EMA_CVD_Pro_v3.pine")
text = p.read_text(encoding="utf-8")

for i, line in enumerate(text.splitlines(), 1):
    m = re.match(r"\s*(?:bool|string|int|float|color)\s+([A-Z][A-Z0-9_]*)\s*=\s*input\.", line)
    if not m:
        continue
    var = m.group(1)
    count = len(re.findall(r"\b" + re.escape(var) + r"\b", text))
    if count <= 1:
        print(f"UNUSED? {i}: {var} count={count} | {line.strip()}")
```

## Settings that are often safe to remove after simplification

- Marker display toggles after all `plotshape()` / marker code is deleted.
- Detail-row controls after the table no longer renders a detail/description row.
- Visual-clean toggles when the script has already made simplified visuals the default and the toggle no longer branches logic.
- Extra color inputs for states that are no longer used by table cells.
- Threshold inputs declared for an older scoring system but absent from current score conditions.

## Reporting standard

When finished, report the removed settings as a short table and state that an unused-input scan was rerun. Do not claim TradingView syntax success unless the user verifies in Pine Editor.
