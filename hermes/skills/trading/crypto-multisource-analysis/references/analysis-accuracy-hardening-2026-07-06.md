# Analysis Accuracy Hardening · 2026年7月6日

## Scope
Session hardening for 棠溪 multi-asset analysis cards and GO/NO-GO gates. Use this as the regression checklist when changing `auto_card.py`, `go_nogo_gate.py`, `render_v8.py`, `行情守望.py`, or freshness watchdogs.

## Durable lessons

| Area | Rule | Why |
|---|---|---|
| Snapshot freshness | `auto_card()` must refresh/mark `source_snapshot_{symbol}.json` before GO/NO-GO and write real `_snapshot_age_h` | Data freshness gates must not depend on a default 24h assumption |
| Daemon snapshot refresh | `行情守望.py` must refresh SourceSnapshot even when active monitor levels are missing/expired | Expired levels must not stop BTC/XAU data from staying fresh |
| R:R gate | GO/NO-GO must use the primary plan `rr_a/rr1`, not `max(rr_a, rr_b)` | A good reverse plan must not make the current primary plan executable |
| Cross-asset sentiment | Non-crypto cards must not ingest BTC/crypto CoinGecko community, BTC Polymarket, or BTC x_sent caches | XAU/forex/stocks need their own macro/hotspot/COT/rates context |
| Windows output safety | Renderer stdout/stderr reconfigure must catch `OSError`/`ValueError` | Piped cron/terminal handles may reject reconfiguration and should not break card rendering |

## Regression commands

```bash
cd "D:/Hermes agent"
python -m py_compile scripts/auto_card.py scripts/render_v8.py scripts/行情守望.py scripts/data_freshness_watchdog.py scripts/watchdog.py scripts/pipeline_router.py scripts/go_nogo_gate.py
python -m pytest -q
python scripts/data_freshness_watchdog.py
python scripts/tv_live_dump.py --verbose
python scripts/auto_card.py BTCUSDT
python scripts/auto_card.py XAUUSD
```

## Expected probes

- BTC full card: 10-step route; if `rr1 < 2.0`, output must be `NO-GO · rr_ratio`.
- XAU full card: 8-step route; output must explicitly skip BTC/crypto Polymarket, BTC x_sent cache, and CoinGecko crypto community panel.
- `data_freshness_watchdog.py`: no stale `source_snapshot_BTCUSDT.json`, `source_snapshot_XAUUSD.json`, or `tv_live.json` after refresh.
- `render_v8.py`: safe `_safe_reconfigure()` wrapper exists around stdout/stderr encoding changes.
