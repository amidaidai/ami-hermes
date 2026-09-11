# Pro Dashboard v3 Lessons

Session-specific lessons from iterating a TradingView SVP/ICT/VWAP/EMA/CVD dashboard into a practical real-time panel.

## User-facing table design

- Default the table to a compact execution panel, not a research panel.
- Preferred compact rows: `等级`, `处理`, `高周`, `结构`, `量能`, `CVD`, `计划`, `失效`.
- Keep a `详细` mode for `状态`, `市场`, `趋势`, `事件`, `倾向` when the user is debugging why a grade appears.
- Split `量能`, `事件`, and `CVD`; combined rows with abbreviations were hard to read in live trading.
- Avoid cryptic labels like `C多`, `C空`, `量↑强`; use short natural Chinese like `顺多确认`, `放量上收`, `下方吸收`.
- `计划` must name the exact level: `破VAH`, `破VAL`, `破POC`, `破VWAP`, or a pullback level like `VWAP`, `POC`, `VAL`.
- For this user, chart markers are noise. Remove marker code or keep it opt-in and disabled; do not default to `A多/A空/顶D/底D/!` labels on the chart.
- If table opacity is requested, make header/cell defaults and dynamic state colors fully opaque.
- Put the compact table in the lower-left by default for this user's TradingView layout.

## Accuracy-improvement sequence

Prefer false-positive reduction before adding new indicators:

1. HTF bias filter (`高周`) with readable timeframe labels (`1h`, `4h`, `1D`, not `60`, `240`).
2. Acceptance confirmation (`接受确认K数`) before allowing high-confidence breakouts.
3. CVD divergence qualification only near key levels.
4. A-grade gating: `A多/A空` only near VAH/VAL/POC/VWAP/VWAP bands/nPOC/session sweep levels.
5. Grade stability: upgrades require consecutive confirmation bars; `X` risk remains immediate.

## Pine implementation notes

- Use a helper like `f_tf_label()` to convert TradingView timeframes to readable labels in tables.
- Use a helper like `f_near_level(level, atrMult)` and intermediate booleans for key-level proximity; avoid very long OR chains.
- If TradingView throws syntax errors near `alertcondition`, simplify to positional calls with short ASCII titles/messages.
- Audit dead inputs after removing features; e.g. remove `SHOW_SETUP_MARKERS` if all `plotshape()` calls were deleted.
- When making table cells opaque, search for leftover `color.new(..., 35)` highlight colors.
