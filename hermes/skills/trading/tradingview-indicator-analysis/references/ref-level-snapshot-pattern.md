# Reference Level Snapshot Pattern

> A lightweight TV MCP data-collection workflow for pulling key reference levels without the full analysis pipeline. Designed for no_agent cron jobs and fast checks where only the structural benchmarks are needed.

## When to use

- Cron-based periodic level updates (e.g. `btc_ref_levels.json`)
- Quick sanity check before a full analysis
- no_agent scripts that need VWAP/VAH/VAL/POC/W_VWAP as inputs
- Lightweight monitoring that tracks distance from key levels

## When NOT to use

- User asks for full analysis / trading card → use multi-TF protocol
- DMI grade / action panel needed → need `pine_tables` not just `study_values`
- Need CVD data from the indicator → study_values doesn't expose CVD; need pine_labels/lines or external K-line calculation

## Tool chain

```
① tv_health_check() → confirm cdp_connected + correct symbol
② (optionally data_get_ohlcv(count=100, summary=true) → for recent_high/recent_low)
③ data_get_study_values() → extract key fields
④ [FALLBACK] data_get_pine_labels(study_filter="SVP+ICT+VWAP+CVD") → get VAH/VAL/POC if study_values missing them
⑤ data_get_pine_lines(study_filter="SVP+ICT+VWAP+CVD") → horizontal levels for additional reference
⑥ write JSON → structured file for downstream consumption
⑦ [SILENT] on success
```

## Key fields from SVP+ICT+VWAP+CVD indicator

> ⚠ **Important**: VAH/VAL/POC may appear in EITHER `study_values` OR `pine_labels` depending on SVP indicator version and timeframe. Do NOT rely solely on study_values. Always check both data sources.

### From study_values

| JSON key | study_values field | Status |
|----------|-------------------|--------|
| `vwap` | `S VWAP` | Always present |
| `val` | `VAL Price` | ⚠ Variable — may be absent on some timeframes/versions. Fallback to `pine_labels` (label text `"VAL: ..."`). |
| `vah` | `VAH Price` | ⚠ Variable — same caveat as VAL. Fallback to `pine_labels` (label text `"VAH: ..."`). |
| `poc` | `POC Price` | ⚠ Variable — same caveat. Fallback to `pine_labels` (label text `"POC: ..."`). |
| `w_vwap` | `W VWAP Price` | ⚠ Variable — often absent on lower TFs (15m). Check pine_labels or higher TF. |
| `do` | (Daily Open / DO) | Variable — confirmed present on 2026-06-29 (`60,000.4`). May depend on SVP indicator version on TV. Always handle null gracefully. |
| `recent_low` | OHLCV summary `low` | From data_get_ohlcv(summary=true) |
| `recent_high` | OHLCV summary `high` | From data_get_ohlcv(summary=true) |

### From pine_labels (fallback when study_values missing)

When `study_values` lacks VAH/VAL/POC (observed on 15m BTC, 2026-07-01), read `data_get_pine_labels(study_filter="SVP+ICT+VWAP+CVD")` and extract label text patterns:

| Pattern in label text | Price field | Action |
|----------------------|-------------|--------|
| `"VAH: {price}"` | VAH | Parse `price` from text after `"VAH: "` or use label's `price` field |
| `"VAL: {price}"` | VAL | Same approach |
| `"POC: {price}"` | POC | Same approach |

## Observed field availability (2026-07-01, verified VAH/VAL/POC in pine_labels not study_values)

From live data of BINANCE:BTCUSDT.P on 15m (2026-07-01, BTC ~$58,392 close):
- **study_values showed**: `S VWAP` (59,774), bands, EMA 9/21/34/55 — but NO VAH/VAL/POC/W_VWAP/DO
- **pine_labels showed**: `"VAH: 59294.6"`, `"VAL: 58189.9"`, `"POC: 58563.1"` + ICT session labels
- **pine_lines showed**: 19 horizontal levels including all key SVP levels
- **OHLCV (100 bars)**: high=60,267.6, low=58,160.0, range=$2,107.6
- **Conclusion**: VAH/VAL/POC migrated from study_values to pine_labels (vs 2026-06-29 snapshot where they were in study_values). The data source for these fields has changed. Always read both.

## Parsing notes

Values come as comma-formatted strings (e.g. `"60,134.6"`). Strip commas before parsing to float:
```python
vwap = float(val.replace(",", "")) if val else None
```

## Output JSON structure

```json
{
  "vwap": 60104.9,
  "val": 59904.2,
  "vah": 60271.1,
  "poc": 60099.5,
  "do": 60000.4,
  "w_vwap": 61051.6,
  "recent_low": 59714.8,
  "recent_high": 60924.7,
  "updated_at": "2026-06-29T00:09:56+08:00"
}
```

## Pitfalls

- **DO_Price is variable — no longer always null**: Previously the SVP indicator's Data Window encoding export was absent. As of 2026-06-29, `DO Price` returned `60,000.4` in study_values. Always code defensively: treat DO as nullable, but check before assuming null. If present, include it in output JSON.
- **TV session may already have the right symbol**: `tv_health_check` often returns the previously-set symbol from a daemon or prior session. If it's correct, skip `chart_set_symbol` and go straight to data reads. This saves 5-10s.
- **No need for wait/retry on a connected session**: If `tv_health_check` shows `api_available: true` and the symbol/period are correct, study_values returns immediately. The wait+retry cycle is only needed after `chart_set_timeframe` changes.
- **Comma-formatted floats**: Parse carefully — `float("60,134.6")` raises ValueError. Strip commas first.
- **OHLCV summary vs full bars**: For recent_high/recent_low, `summary=true` is sufficient. Don't request 100 raw bars unless you need bar-by-bar analysis.
- **Don't call this pattern "analysis"**: This is data collection, not analysis. If a downstream consumer treats it as an analysis result, it will miss CVD, DMI grades, action panel data, and multi-TF structure. Label clearly.
- **VAH/VAL/POC may only be in pine_labels, not study_values** (2026-07-01): On 15m BTC, study_values only exposed S VWAP + EMA bands. VAH/VAL/POC were only found in `pine_labels` (`"VAH: 59294.6"`, `"VAL: 58189.9"`, `"POC: 58563.1"`). Always include a `pine_labels` fallback read — do not assume study_values has everything.
- **W_VWAP and DO may be absent on lower TFs** (2026-07-01): On 15m BTC, neither W_VWAP nor DO appeared in study_values or pine_labels. They may only render on higher timeframes (1h/4h). Handle gracefully as null.
- **Heuristic validation after each read**: Compare the price range of values against the expected symbol (BTC ~$58-60K). If VWAP shows ~$4K (XAU range) or ~$72 (SOL range), the indicator hasn't refreshed — force a chart_set_timeframe cycle.
