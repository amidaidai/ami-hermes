# TV Data Bridge Windows Debug Recipe

Use this when BTC analysis says TV data is abnormal even though TradingView is open.

## Symptom

- TV Desktop is open and TradingView MCP health checks pass.
- `btc_tv_data.json` is stale, has empty `symbol`, or has comma-formatted strings such as `"64,212.7"` instead of numeric values.
- Alerts or pipeline decisions look inconsistent with the visible TV chart.

## Root Cause Pattern

The chart can be healthy while the file bridge is unhealthy. Common causes:

1. The cron is an LLM job with only `terminal/file` toolsets, so it cannot actually access TV MCP data.
2. The script bridge writes bad/empty fields and overwrites the last good cache.
3. Node on Windows receives a malformed path string. Prefer `C:/Users/...` paths; incorrectly escaped `C:\Users\...` literals can be interpreted with escape sequences like `\b` and write/read a different path than intended.
4. Windows Python reading `/c/Users/...` can resolve to a repo-local `D:/c/...` path, producing a misleading stale cache. Use `C:/Users/...` for Python verification on native Windows.

## Correct Runtime Shape

- Cron name: `BTC TV 数据桥`
- Schedule: `*/2 8-23 * * *`
- `no_agent=true`
- `deliver=local`
- Script: `tv_fetch_bridge.py`
- Workdir: `D:/Hermes agent/tools/tradingview-mcp`
- Success stdout: empty
- Failure stdout: ASCII-only diagnostic, non-zero exit

## Quality Gate

The bridge must write `C:/Users/Administrator/AppData/Local/hermes/data/btc_tv_data.json` only after these pass:

- Required non-empty fields: `symbol`, `resolution`, `vwap`, `ema9`, `cvd`, `poc`, `vah`, `val`
- `symbol == BINANCE:BTCUSDT.P` for BTC dedicated bridge
- `resolution == 15`
- Numeric fields are actual JSON numbers: `vwap`, `band1_high`, `band1_low`, `poc`, `vah`, `val`, `cvd`, `cvd_slope`
- If labels/data-window cannot provide levels, exit non-zero and keep the last good cache.

## Verification Commands

Run from repo root in Git Bash:

```bash
node --check tools/tradingview-mcp/fetch_tv_data.cjs
cd tools/tradingview-mcp && node fetch_tv_data.cjs
python C:/Users/Administrator/AppData/Local/hermes/scripts/tv_fetch_bridge.py >/tmp/tv_wrapper.out 2>&1; echo rc=$?; wc -c /tmp/tv_wrapper.out
python - <<'PY'
import json, pathlib
p = pathlib.Path('C:/Users/Administrator/AppData/Local/hermes/data/btc_tv_data.json')
d = json.loads(p.read_text(encoding='utf-8'))
keys = ['timestamp','symbol','resolution','vwap','band1_high','band1_low','poc','vah','val','cvd','cvd_slope']
print({k: d.get(k) for k in keys})
print({k: type(d.get(k)).__name__ for k in keys})
assert d['symbol'] == 'BINANCE:BTCUSDT.P'
assert d['resolution'] == '15'
for k in ['vwap','band1_high','band1_low','poc','vah','val','cvd','cvd_slope']:
    assert isinstance(d[k], (int, float)), (k, d[k], type(d[k]))
PY
```

Then run the pipeline:

```bash
cd D:/Hermes\ agent/scripts
python pipeline_integration.py
```

## Diagnostic Order

1. Check TV MCP health/chart state first, but do not kill TradingView.
2. Check cron config: `no_agent`, `deliver=local`, bridge script, correct workdir.
3. Run Node syntax check.
4. Run direct Node fetch.
5. Run wrapper and assert empty stdout.
6. Inspect the real cache using `C:/Users/...`, not `/c/...` inside Windows Python.
7. Delete any accidental repo-local `D:/c/...` cache if it exists; it is diagnostic noise.
8. Run `pipeline_integration.py` and confirm it reads the same real cache.
