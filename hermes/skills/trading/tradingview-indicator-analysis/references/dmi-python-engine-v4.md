# DMI Decision Engine v4.0 — Pine-to-Python Bridge Architecture

## Context (2026-06-22)

User's `SVP+ICT+VWAP+EMA+CVD` Pine Script indicator (2024 lines) contains a full DMI Decision Table engine:
- Trend score 0-10 + Reversal score 0-10 (dual-track)
- A/B/C/X four-grade system
- DMI (ADX/DI+/DI-) trend confirmation
- CVD 6-state detection (bull confirm / bear confirm / bull div / bear div / absorb / distribute)
- HTF (higher timeframe) filter
- Key level proximity gate (A grade must be within 0.6 ATR of a key level)
- X risk grade (ADX hot > 40 / VWAP extended / structure conflict / HTF conflict)

## Architecture: Dual-Path DMI

```
Path A: TV MCP (for analysis cards via auto_card.py)
  TV → data_get_pine_tables → DMI decision table text → _parse_tv_dmi_table()

Path B: Python Engine (for cron alerting via btc_alert_watch_v3.py)
  TV data bridge (VWAP/bands/EMA/CVD/labels) + Binance OHLCV
  → dmi_decision.py → compute_scores() → A/B/C/X grade
  → Only A grade pushes to Telegram
```

## Key Files

| File | Purpose |
|------|---------|
| `scripts/dmi_decision.py` | DMI computation + trend/reversal scoring + A/B/C/X grading |
| `scripts/btc_alert_watch_v3.py` | Alert detector v4.0 — calls dmi_decision, builds decision card |
| `tools/tradingview-mcp/fetch_tv_data.cjs` | TV data bridge — writes BTCUSDT.P_tv_data.json |

## DMI Computation Details

- **RMA**: Wilder's Running Moving Average (not EMA)
- **DI period**: 10 bars (matches user's `DMI_DI_LEN=10`)
- **ADX smooth**: 10 bars (matches user's `DMI_ADX_SMOOTH=10`)
- **Hot threshold**: ADX ≥ 40
- **Balance**: ADX < 20 OR DI gap ≤ 3.0

## Trend Score Formula (0-10 per side)

```python
trend_long += 2 if price above S VWAP
trend_long += 2 if price above VAH (or +1 if in VA)
trend_long += 2 if EMA bull (9≥21 AND 34≥55)
trend_long += 2 if DMI bull confirm
trend_long += 1 if vol_high AND close_near_high
trend_long += 1 if CVD bull confirm
trend_long -= 1 if CVD bear divergence
```

## Reversal Score Formula (0-10 per side)

```python
reversal_long += 3 if swept_low_reclaimed (ICT sweep)
reversal_long += 2 if val_reclaimed
reversal_long += 2 if vwap_extended_dn
reversal_long += 1 if DMI hot
reversal_long += 1 if vol_high AND NOT close_near_low
reversal_long += 1 if CVD bull divergence
reversal_long += 1 if CVD absorption buy
```

## Grade Thresholds

| Grade | Condition | Push |
|-------|-----------|------|
| A | trend ≥ 8, gap ≥ 2 vs opposing, CVD confirm, acceptance OK, near key level, not hot | ✅ Push |
| B | trend ≥ 6, gap ≥ 2, CVD OK | ❌ Silent |
| C | reversal ≥ 6, gap ≥ 2 | ❌ Silent |
| X | hot / extended / conflict / HTF conflict | ❌ Silent (禁追) |

## Data Flow

```
cron (every 1min)
  ├── btc_alert_watch_v3.py
  │   ├── load_data() → btc_latest.json + BTCUSDT.P_tv_data.json
  │   ├── Fallback: Binance API klines if TV OHLCV missing
  │   ├── compute_dmi(highs, lows, closes)
  │   ├── compute_scores(data, dmi, atr, ohlcv_bars)
  │   ├── Grade check: only A → write btc_pending.txt
  │   └── build_decision_card() → format matching Pine decision table
  │
  └── btc_push_cron.py (every 1min)
      └── reads btc_pending.txt → sends to Telegram:386
```

## Pitfalls

- **TV indicator shows XAU values after symbol switch**: The data window values may remain stale. Python engine uses Pine labels/lines (correct) + Binance OHLCV (correct). Recompile Pine script on TV to fix.
- **ADX hot threshold (40) may be too strict for crypto 15m**: During strong moves, ADX frequently exceeds 40, causing grade X. Consider crypto-specific threshold of 50-55 if A signals are too rare.
- **OHLCV Bridge Gap**: `fetch_tv_data.cjs` doesn't export OHLCV bars. `btc_alert_watch_v3.py` falls back to Binance REST API klines. This works but adds latency.
- **Dual Python environments**: `dmi_decision.py` is used by cron (Python 3.11) and potentially by sandbox (Python 3.12). Changes must work in both.
