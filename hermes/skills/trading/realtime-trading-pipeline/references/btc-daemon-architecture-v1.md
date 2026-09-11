# BTC Daemon Architecture v1 (2026-06-23)

## Files

### `scripts/monitor/btc_daemon.py` — Main daemon
- Background process (15s polling, 0 token)
- 7 fixed BTC price zones (大底→周VWAP上方)
- Binance API `api/v3/ticker/price` every 15s
- Zone change → immediate TG:386 push + write `data/btc_signal.json`
- Every 60s: if signal pending → TV MCP subprocess → full card
- Heartbeat: `data/.btc_daemon_heartbeat.json` (ts, zone, pid)

### `scripts/monitor/btc_watchdog.py` — Watchdog cron
- cron `*/1 * * * *`, no_agent, deliver=local
- Checks heartbeat → if stale >120s → taskkill + restart daemon
- Silent on success, only outputs on restart

### `scripts/monitor/btc_card_gen.py` — Card generator (standalone)
- Also callable directly for manual debug
- Connects to TV MCP via subprocess independently
- Useful as reference for the subprocess connection pattern

## Cron Jobs
Only 1 cron: `BTC看门狗` (no_agent, `*/1 * * * *`, deliver=local)
Daemon runs on boot via `terminal(background=true)` or manual start.

## Key Data Files
| File | Purpose |
|------|---------|
| `data/.btc_daemon_heartbeat.json` | Heartbeat (read by watchdog) |
| `data/.btc_daemon_state.json` | Zone state + alert count (persistence) |
| `data/.btc_daemon.pid` | PID (for taskkill) |
| `data/btc_signal.json` | Signal (pending→completed, triggers card gen) |
| `data/btc_latest_card.md` | Latest full analysis card |

## Daemon Push Format (Zone Alert)
```
↓ BTC · 大底 · `62,460` · 18:11
① 区间 大底 (62172-62472)
   大底62,272周级别 · 守→双底多64K+ · 破→空61K
② 15m跌 · 量1,234 · 振幅236
```

## Daemon Push Format (Deep Analysis Card)
```
○等待 BTC · 大底 · `62,460` · 06/23 18:15
① VWAP`63,950`下1.5% · CVD`-1,200`空 · EMA空头
   TV B·观望 · 空
② VAH`64,500`·POC`63,800`·VAL`63,200`·VWAP`63,950`
③ 多→守`63,200`做多 · 止损`62,800` · 目标`63,800`
   空→破`63,900`做空 · 止损`64,500` · 目标`63,200`
④ 4h EMA空 · CVD-12,000
⑤ 风控 轻仓0.5U · 100x
MEDIA:D:/Hermes agent/tools/tradingview-mcp/screenshots/btc_15m_analysis.png
```
