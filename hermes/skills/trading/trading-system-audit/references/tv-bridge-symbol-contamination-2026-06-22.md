# TV Bridge Symbol Contamination Audit Pattern · 2026-06-22

## Trigger
Use this when auditing BTC alerts/cards that depend on TradingView MCP or `btc_tv_data.json`, especially after the user has manually switched the TradingView chart to XAU or another symbol.

## Failure Mode
A zero-token TV bridge can be syntactically healthy and cron-green while writing the wrong asset into the BTC cache. The observed case:

- `btc_tv_data.json` path was correct and fresh.
- Cron status was `ok`.
- TradingView CDP was connected.
- But the active chart was `OANDA:XAUUSD`, so BTC cache contained XAU-scale values like `vwap=4164`.
- Downstream BTC watch levels and alerts would silently use wrong semantic data.

## Audit Rule
Do not stop at `exists + fresh + exit=0` for cache files. Always validate semantic identity:

- `symbol` must equal expected asset, e.g. `BINANCE:BTCUSDT.P` for BTC TV bridge.
- Price-scale sanity must match the symbol, e.g. BTC VWAP should not be a gold-scale `4xxx` value.
- Required indicator fields must be present and non-null: `vwap`, `band2_low`, `poc`, `vah`, `val`, `cvd`, `cvd_slope`.
- Cross-check live TradingView state with MCP if available: `chart_get_state` / quote should show the same symbol.

## Fix Pattern
The bridge script must force and verify the target symbol before writing cache:

1. Read current chart state.
2. If `chart.symbol()` differs, call `chart.setSymbol(TARGET_SYMBOL, callback)`.
3. Wait for chart load.
4. Read active state again.
5. If active symbol still mismatches, fail hard and do not write cache.
6. Only write JSON after quality gates pass.

## Verification Bundle
Run all of these before claiming fixed:

```bash
node --check tools/tradingview-mcp/fetch_tv_data.cjs
python scripts/tv_fetch_bridge.py
python - <<'PY'
import json, pathlib
p = pathlib.Path('C:/Users/Administrator/AppData/Local/hermes/data/btc_tv_data.json')
d = json.loads(p.read_text(encoding='utf-8'))
print({k: d.get(k) for k in ['symbol','resolution','vwap','band2_low','poc','vah','val','cvd','cvd_slope']})
assert d.get('symbol') == 'BINANCE:BTCUSDT.P'
assert float(d.get('vwap') or 0) > 10000
PY
```

Also run the card verification bundle:

```bash
python hermes/scripts/auto_card.py BTCUSDT
python hermes/scripts/auto_card.py XAUUSD
python -m pytest tests/test_card_render_locked.py -q
```

## Reporting Guidance
Classify as P0 when the wrong-symbol cache can drive live BTC alerts or decisions. It is not a cosmetic data issue: it can invert critical levels and suppress or trigger wrong alerts while all process/crons look green.
