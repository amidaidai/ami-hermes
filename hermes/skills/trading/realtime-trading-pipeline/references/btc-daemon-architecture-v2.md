# BTC Daemon v2 Architecture (2026-06-23)

## Overview

Single background Python daemon (15s polling) + 1m watchdog cron. Zero LLM tokens. Multi-factor scoring gate replaces zone-entry alerts.

## File Locations

| Path | Role |
|------|------|
| `D:/Hermes agent/scripts/monitor/btc_daemon.py` | Source (git-tracked) |
| `~/.hermes/scripts/btc_daemon.py` | Runtime copy (must sync after edits) |
| `D:/Hermes agent/scripts/monitor/btc_card_gen.py` | Card generator (TV MCP subprocess) |
| `D:/Hermes agent/scripts/monitor/btc_watchdog.py` | Watchdog cron script |
| `D:/Hermes agent/scripts/dmi_decision.py` | Python DMI engine (aligned to user's 2024-line Pine Script) |
| `D:/Hermes agent/data/.btc_daemon_heartbeat.json` | Heartbeat (every 15s) |
| `D:/Hermes agent/data/.btc_daemon_state.json` | Persistent state (zone, last push, cooldown) |
| `D:/Hermes agent/data/btc_signal.json` | Trigger signal for card generator |

## 7 Price Zones

```python
LEVELS = OrderedDict([
    ("大底",       {"lo": 62172, "hi": 62472, "prio": 1}),
    ("前低已破",   {"lo": 62473, "hi": 63370, "prio": 2}),
    ("VAL折价区", {"lo": 63371, "hi": 63850, "prio": 3}),
    ("VWAP测试区",{"lo": 63851, "hi": 64250, "prio": 2}),
    ("VWAP上运行", {"lo": 64251, "hi": 64507, "prio": 3}),
    ("周VWAP测试", {"lo": 64507, "hi": 64750, "prio": 2}),
    ("周VWAP上方", {"lo": 64751, "hi": 99999, "prio": 4}),
])
```

## Daemon Main Loop

```
while True (every 15s):
  1. Binance API → price + 15m klines
  2. detect_zone(price) → current zone
  3. score = score_opportunity(price, zone, bars) → 0-10
  4. write_heartbeat(zone, score)

  5. Every 60th second (deep cycle):
     a. Run dmi_decision.py as subprocess → trend/reversal scores
     b. Fetch F&G from alternative.me
     c. Compute confidence: trend_score(3) + CVD_confirm(2) + near_key_level(2) + not_X(1) + FnG_extreme(2) = /10
     d. If confidence ≥ 8 AND same-direction cooldown < 30min:
        → write btc_signal.json with status=pending
        → run btc_card_gen.py (TV MCP subprocess, full analysis)
        → push card to TG:386 (telegram_direct.py)
        → update state: last_push_dir, last_push_ts

  6. save_state()
  7. sleep(15)
```

## Score Factors (0-10)

| Factor | Max | Conditions |
|--------|:---:|-----------|
| Zone importance | 3 | 大底=3, VWAP测试区/周VWAP=2, others=1 |
| 15m trend | 2 | Trending toward zone +2, neutral +1 |
| Volume | 2 | >1.5x avg + trending +2, >1.2x +1 |
| Distance from bottom | 2 | <100 from 大底 +2, <200 +1 |
| Volatility | 1 | >300 range in key zone +1 |

**Push threshold: ≥ 8.** Cooldown: 30min same direction.

## Direction Logic (5-factor vote, NOT TV grade)

```python
bear_votes = 0; bull_votes = 0
if price < VWAP: bear += 1 else: bull += 1
if CVD < -2000: bear += 1 elif CVD > 2000: bull += 1
if EMA9 < EMA21: bear += 1 else: bull += 1
if "空" in structure_bias: bear += 1 elif "多" in structure_bias: bull += 1
if near_VAL: bull += 1
if bear >= 4: direction = "↓做空"
elif bull >= 4: direction = "↑做多"
else: direction = "○等待"
```

TV DMI grade (TVX/TVA/TVB/TVC) is shown as reference line only.

## TV MCP Timing (Card Generator)

Indicator loading wait times with retry:
- 15m: 5s + 3 retries×3s if VWAP missing
- 1h: 8s + 3 retries×3s
- 4h: 12s + 3 retries×3s

After `chart_set_timeframe(tf)`, sleep then read `data_get_study_values`. Check for "S VWAP" or "VWAP" in the response text. If missing, sleep 3s and retry up to 3 times.

## Alert Format

**Daemon quick pushes:** conversational, no numbering:
```
↓ BTC 62460，跌到大底区(62172-62472)
62,272是周级别大底，守住做多64K+，跌破看61K
15分走跌、量正常
```

**Card gen (deep analysis):** v4.2 structured format with ①②③④⑤ and TV DMI reference.

## Daemon Restart Procedure

```bash
# 1. Kill old
PID=$(cat data/.btc_daemon.pid 2>/dev/null)
taskkill /F /PID $PID 2>/dev/null

# 2. Clean state
rm -f data/.btc_daemon_heartbeat.json data/.btc_daemon_state.json data/.btc_daemon.pid

# 3. Copy updated scripts (D: → C: for runtime)
cp -f scripts/monitor/btc_daemon.py ~/.hermes/scripts/btc_daemon.py
cp -f scripts/monitor/btc_card_gen.py ~/.hermes/scripts/btc_card_gen.py

# 4. Start via terminal(background=true), NO notify_on_complete
# Workdir: D:/Hermes agent
