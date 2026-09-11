# BTC Daemon Zone Calculation Formula

## Data Sources

From TV MCP `study_values` (SVP+ICT+VWAP+CVD study):
- `S VWAP` → `vwap` (session VWAP)
- `VAH Price` → `vah` (Value Area High)
- `VAL Price` → `val` (Value Area Low)
- `POC Price` → `poc` (Point of Control)
- `W VWAP Price` → `w_vwap` (weekly VWAP)
- `DO Price` → `do` (Day Open)

From `data_get_ohlcv(count=100)`:
- `recent_low` = min(low) from last 100 bars
- `recent_high` = max(high) from last 100 bars

## Zone Calculation

```python
LEVELS = OrderedDict([
    ("大底",       {"lo": recent_low - 250,    "hi": recent_low + 50,     "prio": 1}),
    ("前低已破",   {"lo": recent_low + 51,     "hi": int(val),            "prio": 2}),
    ("VAL折价区", {"lo": int(val) + 1,         "hi": int(vwap),           "prio": 3}),
    ("VWAP测试区",{"lo": int(vwap) + 1,        "hi": int(vwap) + 120,     "prio": 2}),
    ("VWAP上运行", {"lo": int(vwap) + 121,      "hi": int(vah),            "prio": 3}),
    ("周VWAP测试", {"lo": int(w_vwap) - 75,     "hi": int(w_vwap) + 75,    "prio": 2}),
    ("周VWAP上方", {"lo": int(w_vwap) + 76,     "hi": 99999,               "prio": 4}),
])
```

## Zone Weights

```python
ZONE_WEIGHT = {
    "大底": 3,        # highest signal
    "VWAP测试区": 2,   # high signal
    "周VWAP测试": 2,   # high signal  
    "前低已破": 1,     # medium
    "VAL折价区": 1,   # medium
    "VWAP上运行": 1,   # medium
    "周VWAP上方": 1,   # low
}
```

## First-Time Alignment Procedure

1. TV MCP: `chart_set_symbol BINANCE:BTCUSDT.P` → `chart_set_timeframe 15` → wait 8s
2. `data_get_study_values` → extract vwap/val/vah/poc/do/w_vwap
3. `data_get_ohlcv(count=100)` → find recent_high, recent_low
4. Calculate zones using formula above
5. Write `btc_ref_levels.json` to both:
   - `C:/Users/Administrator/AppData/Local/hermes/data/btc_ref_levels.json`
   - `D:/Hermes agent/data/btc_ref_levels.json`
6. Update daemon hardcoded fallback values
7. Start daemon (background, no notify_on_complete)

## Auto-Update Mechanism

- Agent cron: `0 */4 * * *` — every 4 hours, reads TV → writes JSON
- Daemon: each 15s loop checks JSON mtime → hot-reloads zones
- Fallback: if JSON missing, uses hardcoded values from last alignment

## 2026-06-28 Alignment (Current)

| Field | Value |
|-------|-------|
| vwap | 60,028.5 |
| val | 59,920.3 |
| vah | 60,254.4 |
| poc | 60,147.3 |
| do | 60,000.4 |
| w_vwap | 61,075.1 |
| recent_low | 59,714 |
| recent_high | 60,925 |

Resulting zones:
- 大底: 59,500–59,760
- 前低已破: 59,761–59,920
- VAL折价区: 59,921–60,028 (BTC was here at alignment time)
- VWAP测试区: 60,029–60,150
- VWAP上运行: 60,151–60,254
- 周VWAP测试: 61,000–61,150
- 周VWAP上方: 61,151+
