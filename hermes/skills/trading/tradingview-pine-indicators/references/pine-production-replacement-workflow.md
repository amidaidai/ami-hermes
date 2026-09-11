# Pine production replacement workflow

Use this when the user uploads updated main/sub TradingView indicators and says to replace the originals.

## Source of truth

- Treat the freshly uploaded files as authoritative, even if workspace files look newer.
- Preserve the previous production files before overwrite.
- For Tang Xi's current layout, production files commonly live at the repo root:
  - `svp_indicator.txt` = main SVP/ICT/VWAP/CVD overlay
  - `haldro_indicator.txt` = HALDRO/aggregated-volume sub indicator
- Also sync deliverable copies to Desktop as `.txt` because the user can import/paste them manually if TV automation is unstable.

## Replacement steps

1. Create a timestamped evidence directory, e.g. `outputs/pine-replace_<timestamp>/`.
2. Copy current production files to `*.old.txt` in that directory.
3. Copy uploaded main/sub files into the production file names.
4. Copy the new files to Desktop with clear names, e.g. `主指标_最新替换版.txt` and `副指标_最新替换版.txt`.
5. Run static audit before touching TradingView:
   - `request.security` raw count and expanded estimate
   - `request.security_lower_tf` count
   - `plot/fill/bgcolor/table.new` output counts
   - `line.new/box.new/label.new` object creation counts
   - `alertcondition` count
   - action panel preference checks: `：` labels, no `｜`, `磁吸↑` and `磁吸↓` separate
   - HALDRO crypto gate: `syminfo.type == 'crypto'`
6. Use TradingView MCP/CLI to attempt server compile and editor compile, but do not claim failure from transient `fetch failed` or editor-open errors. Record the exact result.
7. Run system linkage after replacement:
   - `python scripts/tv_data_bridge.py` must refresh BTC TV cache with real POC/VAH/VAL.
   - `python scripts/auto_card.py BTCUSDT` must inject TV levels.
   - `python scripts/auto_card.py XAUUSD` must reject BTC cache to avoid 59k/60k contamination.
8. Generate a report with replacement paths, backups, audit counts, TV compile status, and system-linkage evidence.
9. Do not commit or push unless the user explicitly requests it. Passing checks is not authorization to publish Git changes; retain local verified files and the evidence report.

## TradingView automation pitfalls

- `pine check` / server compile may return `fetch failed`; this is an availability/network result, not a Pine compile error. Fall back to editor `pine compile` and offline `pine analyze` when available.
- Pine Editor automation may later return `Could not open Pine Editor` even after a previous set/save succeeded. Do not pretend the second save worked. Leave Desktop files for manual paste and state the exact blocker.
- A compile result with severity `4` can be a warning, not a fatal syntax error. Examples seen:
  - Pine v5 is outdated warning on a valid main indicator.
  - `shorttitle` too long on the HALDRO sub indicator.
- Low-risk warning fix: TradingView short titles must be ≤10 characters. For `Volume Aggregated Spot & Futures`, use `shorttitle='AggVol'`; this changes only display metadata, not trading logic.

## Report must distinguish

- Replaced locally / synced to Desktop / saved to TradingView cloud / compiled on chart.
- A file being valid locally does not mean it is saved in the TV cloud if editor automation failed.
- XAU rejection of BTC TV cache is a success condition, not a warning, after the cache-gating fix.
