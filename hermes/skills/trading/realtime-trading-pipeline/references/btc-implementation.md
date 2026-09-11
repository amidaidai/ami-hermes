# BTC Implementation Reference (v10)

> Historical record (2026-08-31): legacy implementation reference; do not use as the current runtime entrypoint.

## File Structure

```
~/AppData/Local/hermes/
├─ scripts/
│  ├─ btc_vwap_daemon.py    # v10: 10s watcher daemon (multi-factor signals)
│  ├─ btc_collector.py      # 1m data collector (no_agent)
│  └─ btc_push_cron.py      # 1m push cron (no_agent)
└─ data/
   ├─ btc_latest.json        # Current snapshot (written by collector)
   ├─ btc_history.jsonl      # Rolling 2000 lines (written by collector)
   ├─ btc_pending.txt        # All events bridge (daemon→push cron→386)
   ├─ btc_priority.txt       # ⭐ events only (daemon→event analysis cron→386)
   └─ btc_state.json         # Daemon state persistence (block dedup, last taker, last price)
```

## Cron Jobs Registered

| Name | Schedule | Type | Deliver | Toolsets |
|---|---|---|---|---|
| BTC全数据采集 | `* * * * *` | no_agent, btc_collector.py | local | — |
| BTC告警推送 | `* * * * *` | no_agent, btc_push_cron.py | TG 386 | — |
| BTC MTF分析 | `*/15 8-23 * * *` | LLM cron | origin | terminal,file,vision,web,search |
| BTC高胜率事件 | `*/2 8-23 * * *` | LLM cron | origin | terminal,file,vision,search,web |
| 持仓与信号 | `*/5 8-23 * * *` | no_agent (existing) | TG 416 | — |

## Event Analysis Cron (BTC高胜率事件)

Created 2026-06-22 after user requested high-probability setup capture.

**Prompt structure:**
1. Read priority file: `cat /c/Users/Administrator/AppData/Local/hermes/data/btc_priority.txt`
2. TRUNCATE IT: `cat > /c/Users/Administrator/AppData/Local/hermes/data/btc_priority.txt`
3. If file empty → exit (zero output = silent, no Telegram delivery)
4. If content → read collector JSON + TV data + screenshot → full ⭐ analysis card

## Daemon Event Rules (btc_vwap_daemon.py v10)

Reference levels from SVP indicator (update after each session):
- VAL = 63,886
- VAH = 64,490
- DO = 63,312

### Level Events (5-min block dedup per type)
- `0 < VWAP-价 ≤ $60` → 📊 VWAP测试
- `价 > VWAP` → 🟢 站回VWAP
- `价 < VAL` → 🔴 破VAL
- `价 > VAL` (after break) → 🟡 站回VAL
- `价 > VAH` → 🟠 破VAH

### Advanced signals (need cnt>5 — ~60s heatup)
- `VWAP-价 > $200` + Taker flip >0.5 → ⭐ 反转信号(多/空)
- `VWAP-价 > $200` + Taker <0.4 → ⭐ 空头延续
- `价-VWAP > $200` + Taker >1.6 → ⭐ 多头延续
- `>0.3% change in 30s` → 📉 快速波动
- `VWAP-价 > $200` or `价-VWAP > $200` → 📊 VWAP偏离

### Taker flip detection
Reads `btc_latest.json` every 10s. Compares current taker_ratio against `state["last_taker"]`.
Threshold: `abs(taker - last_taker) > 0.5`. This catches sudden order flow changes.

### Price velocity tracking
Uses `deque(maxlen=5)` for rolling 30s window (10s per sample, 5 samples = ~40-50s effective).
Threshold: `>0.3%` change in the window. Direction is inferred from sign.

## Collector Data Fields (btc_latest.json)

```json
{
  "ts": "2026-06-22 16:52",
  "price": 64146.85,
  "vwap": 64259.75,
  "vol24": 10975.0,
  "oi": 99644.0,
  "funding": 2.6e-05,
  "ls_ratio": 1.6947,
  "taker_ratio": 0.3737
}
```

Note: `funding` field may time out sometimes. The per-field try/except isolates this.

## MTF Analysis Cron Prompt Structure

1. Read: `cat /c/Users/Administrator/AppData/Local/hermes/data/btc_latest.json`
2. Read TV: chart_get_state → chart_set_timeframe("15") if needed → data_get_study_values → data_get_pine_lines → data_get_pine_labels → data_get_ohlcv(summary=true)
3. Screenshot: capture_screenshot(region="full")
4. Generate compressed analysis card (format: 方向→关键位→现价数据→入场条件→核对清单→预案A/B)
5. Auto-deliver to origin (Telegram 386 topic)

## Token Cost Estimate

- MTF Analysis (60 runs/day): ~1M tokens/day → ~$0.43/day (DeepSeek Flash)
- Event Analysis (~5-10 runs/day): ~0.2M tokens/day → ~$0.10/day
- Total: ~$0.53/day, ~$16/month

## Watching in Background

```bash
# Start daemon
cd ~/AppData/Local/hermes/scripts && python btc_vwap_daemon.py &
# (via terminal(background=true))

# Kill daemon
taskkill //F //PID <n>

# Check latest data
cat ~/AppData/Local/hermes/data/btc_latest.json

# Check pending events
cat ~/AppData/Local/hermes/data/btc_pending.txt

# Check priority events
cat ~/AppData/Local/hermes/data/btc_priority.txt

# Verify daemon process
tasklist //FI "PID eq <n>" | grep python
```
