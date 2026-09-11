---
name: realtime-trading-pipeline
description: "Real-time monitoring daemon + watchdog for crypto/XAU - 15s polling background process, 7 fixed price zones, direct TV MCP subprocess for deep analysis, zero-token no_agent. Replaces complex v12 signal system with simple zone-based alerts. Watchdog cron auto-restarts if daemon hangs."

triggers:
  - "build a real-time analysis system"
  - "实时分析系统"
  - "监控系统"
  - "盯盘系统"
  - real-time monitoring
  - no signal received
  - English in Chinese cards
---

# realtime-trading-pipeline

> ⚠ 2026-09-11 校正（**已实测核实**）：本文件部分段落把下列脚本当现行工具，实际状态是——
> ① `btc_alert_watch_v3` / `btc_push_cron` / `btc_collector` / `btc_fast_daemon` **已移入**
>    `scripts/_archive/`（`scripts/` 根下已无此文件）；
> ② `btc_keylevel_ws_guard` / `btc_keylevel_sentinel` / `btc_keylevel_rest_guard` /
>    `btc_price_arrival_sentinel` **文件仍在 `scripts/`，但既不在 cron 也不在任何进程中运行**
>    —— 属历史代际，不要拿它们当现行链路。
> **现行监控链只有一条**：`keylevel_guard.py`（常驻·亚秒 REST·多品种多顶点·每位 30min 冷却）
> + `btc_keylevel_guard_watchdog.py`（cron `*/2` 拉起）+ `keylevel_read_trigger.py`（事件本地分析）
> + `btc_tv_refresh.py`（五周期快照续航）。对照表：
> `trading/realtime-trading-pipeline/references/dead-script-index.md`；
> 系统全貌：`D:/Hermes agent/docs/系统总览.md`；指标字段/行名：`D:/Hermes agent/docs/tv-indicator-field-map.md`。

Build a real-time trading monitoring and analysis pipeline using background daemon processes + 1m watchdog cron, all zero-token no_agent.

## ⚠ Core Principle: Daemon not Cron

**The user has explicitly corrected this multiple times: cron is too slow for price monitoring.**
- 2m cron: price can move through a zone in under 60s, missed entirely
- 5m cron for card gen: a key level breach needs immediate analysis, not 5 minutes later
- **Correct approach**: single background daemon (15s polling, zero token) + 1m watchdog cron (auto-restart if dead)

When the user says "实时" or "太慢了", the answer is ALWAYS a background daemon, not tightening cron intervals. 1m cron is the MINIMUM for watchdog-only tasks.

## 分析调用分层（2026-08-28 用户确认）
监测脚本只负责发现价格穿越并生成 `analysis_request`，不判断多空、不自动下单；触发后默认唤起安禾的 quick 快速分析。

实现契约详见 `references/keylevel-monitor-contract-202608.md`。

- `quick`：看一下/看看/快速过一遍。刷新主执行周期、实时价格、截图；加密保留 OI/资金费率/多空比/Taker；不重拉高周期和宏观情绪。
- `inherit`：现在呢/继续/接着上面/更新。有有效上下文时继承 D/4h/1h，只刷新执行与触发周期和实时衍生品；突破继承关键位、低周期与高周期冲突、上下文过期或用户明确要求全面时升级 full。
- `full`：全面分析/全周期/深度/完整卡/重新从高周期看。刷新 D/4h/1h/15m/5m 和完整多源管线。

不要因为单独出现“分析”就机械启动完整管线；按用户是否表达“全面”判断。触发事件应带 `event_type=keylevel_cross`、`analysis_required=true`、`analysis_status=pending`、`analysis_mode=quick`，供安禾重新核验。当前实现：`keylevel_read_trigger.py` 读取后默认调用 `keylevel_analysis_dispatcher.py --push`，由 dispatcher 运行 `auto_card.py --quick`，成功/失败/重试状态写回 trigger；cron 必须保持 `Deliver=local`，避免重复或 MarkdownV2 退化。

## Architecture (v9.1 · 4-component · daemon-based)

```
┌─ 行情守望 DAEMON (行情守望.py) ────────────────────┐
│  Multi-asset real-time monitor (BTC + XAU)         │
│  Background process via terminal(background)       │
│  Heartbeat: data/monitor_heartbeat.json           │
│  Polls Binance + Yahoo every 10-15s               │
│  Writes: data/source_snapshot_{BTC,XAU}USD.json   │
│  Start: python scripts/行情守望.py -s BTCUSDT XAUUSD│
└────────────────────────────────────────────────────┘

┌─ BTC DAEMON (btc_daemon.py) ───────────────────────┐
│  BTC-specific high-confidence push engine          │
│  Background process via terminal(background)       │
│  Polls Binance API every 60s                      │
│  7 fixed price zones → multi-factor score (0-10)  │
│  Score ≥ 8 → TV MCP subprocess → btc_card_gen.py  │
│            → btc_push_386.py → TG:386             │
│  Heartbeat: data/.btc_daemon_heartbeat.json       │
│  Zero LLM token cost                              │
│  Replaces old BTC高频分析 LLM cron (saves $33/mo) │
└────────────────────────────────────────────────────┘

┌─ WATCHDOG (btc_watchdog.py, */5 cron) ─────────────┐
│  Checks .btc_daemon_heartbeat.json every 5min     │
│  If stale >120s → taskkill old PID + restart      │
│  Zero LLM token cost                              │
└────────────────────────────────────────────────────┘

┌─ XAU MONITOR (gold_monitor.py, */5 cron) ──────────┐
│  Gold-specific trigger monitor                     │
│  no_agent: checks price vs configured zones        │
│  Deliver: origin (user sees on trigger)            │
└────────────────────────────────────────────────────┘
```

## Components

### 1. Data Collector
**no_agent cron, `* * * * *`**. Pure Python, uses `urllib` + Binance REST API.
Each field isolated in try/except — one failure doesn't kill others.
Output dir: `~/AppData/Local/hermes/data/`
Output files: `btc_latest.json` (current snapshot), `btc_history.jsonl` (rolling 2000)

**v1.1 macro addition**: Also fetches:
- DXY from Yahoo Finance `query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB`
- F&G Fear & Greed from `api.alternative.me/fng/?limit=1`
- Writes to `btc_macro.json` (separate file from price data)

### 1.5. TV数据桥
**Preferred: no_agent script bridge, `*/2 8-23 * * *`**. Pure data relay — NO analysis, NO Telegram output.
Purpose: Bridge TradingView Desktop/CDP data to files that the daemon reads without spending LLM tokens.
Steps: wrapper `tv_fetch_bridge.py` runs from the TradingView MCP workdir → invokes `node fetch_tv_data.cjs` → writes `btc_tv_data.json` only after quality gates pass.
Deliver: `local`; `no_agent=true`; stdout silent on success and ASCII-only on failure.
Quality gate: required fields `symbol/resolution/vwap/ema9/cvd/poc/vah/val` must be non-empty; key numeric fields must be normalized to numbers; failed fetch must NOT overwrite the last good cache.
Legacy note: if using an LLM cron to call TV MCP tools directly, it must remain a minimal data relay, but for BTC runtime the zero-token script bridge is preferred.
### 2. Level Watcher Daemon (v12 — Community 7-Feature Edition)

**Background Python process** (terminal background=true, NO notify_on_complete — it never ends).
Maintains state persistence via JSON file for cross‑restart event dedup.
5‑minute block cooling window (each event type fires at most once per 5min slot).

**v10 retained features:**
- Reads collector JSON for taker_ratio
- Tracks price velocity via deque(5)  
- Detects multi‑factor combo signals (taker flip + far deviation = ⭐ reversal)
- Writes to btc_pending.txt + btc_priority.txt

**v11 TV data integration:**
- Reads `btc_tv_data.json` every 30s for dynamic VAL/VAH/VWAP from SVP indicator. Falls back to hardcoded constants if file missing/stale.
- ALL level events carry `CVD+N` or `CVD-N` suffix from the TV data bridge.
- Uses TV's session VWAP (from the user's actual indicator) as the primary VWAP reference. Falls back to locally-calculated 15m 30-bar VWAP from Binance klines.

**v12 Community additions (all 7 implemented 2026-06-22):**

| # | Feature | Detection | Message |
|---|---|---|---|
| 1 | 🔮 **CVD背离** | Track 24 cycles (4min) of price+CVD. Price HH + CVD LH = bear div. Price LL + CVD HL = bull div. | `🔮 CVD空背离 · 纽约 · 价P · CVD+N` |
| 2 | 🎯 **流动性扫荡** | Break VAL/VAH + reclaim within 30s = sweep (not genuine breakout) | `🎯 VAL扫荡 · 触V下$D · 已回收` |
| 3 | 💧 **CVD吸收/派发** | CVD range >150 + price range <$30 over 3min = absorption/distribution | `💧 CVD吸收 · 价不动·CVD大幅波动` |
| 4 | 🕐 **KillZone识别** | Asia 08-16 CST / London 14-17 CST / NY AM 20-23 CST | Attached as tag on events + `btc_signals.json` |
| 5 | 🔫 **Silver Bullet** | 3 windows: 16-17 CST (London) / 23-00 CST (NY AM) / 03-04 CST (NY PM) | Attached as tag with 🔥 on events |
| 6 | 📊 **折价/溢价区** | 50% midpoint between VAH-VAL. Buy in discount, sell in premium. | Written to `btc_signals.json` |
| 7 | ── **FVG** | Simplified kline gap detection (requires OHLC data) | Stub in v12, data-dependent |

**v12 signal summary file:** writes `btc_signals.json` every cycle with `{ts, price, vwap, val, vah, cvd, killzone, silver_bullet, premium_discount, divergence, taker, session}`. The analysis cron reads this file for KillZone/divergence context.

**CVD history persistence:** price_history (deque, 18 = 3min) and cvd_history (deque, 36 = 6min) are saved to/restored from state.json for cross-restart continuity.

**CRITICAL pitfall (TV MCP):** 当 TV MCP 报不可用时，不要立刻调 tv_launch（尤其kill_existing=true）。这杀掉用户正在使用的 TV 窗口。正确流程：tv_health_check → 如CDP不通 → curl localhost:9222/json/version 检查端口 → 如端口活但MCP不通 → 等~60s 让MCP冷却恢复（3次失败后60s自动解锁）→ 确认TV真没运行才 tv_launch。

**CRITICAL pitfall (SVP X grade):** 价格从折价区反弹进入溢价区后，SVP DMI 表（data_get_pine_tables）等级可能从 B多 翻为 X（结构冲突）。SVP X=不进场——风控写"不进场"，执行标"等:看+B1"。此时不要继续推多方向，转观望。

**CRITICAL pitfall:** daemon crashes silently on undefined variables in the signals JSON block. `div` variable is only defined inside the `if cnt > 36:` divergence block but referenced unconditionally in the signals dict. Always initialize `div = None` at the start of the cycle BEFORE any conditionals. Test with `timeout 15 python btc_vwap_daemon.py` after every change — if it exits 124 (timeout) with no output, it's working. If it exits 1 with traceback, fix the variable.

### 3. Push Cron (v6 — Passthrough relay)
**no_agent cron, `* * * * *`**. Reads `btc_pending.txt`, sends directly via Telegram API, then clears pending.
Empty pending = silent. Successful sends = silent. Only failures may print ASCII diagnostics and exit non-zero.

**v6 simplified (2026-06-22):** The v3.5 detector writes self-contained hierarchical cards — `+/−/~` markers,
grouped by direction, with one-line summary, key levels, indicator snapshot, and actionable next-step guidance.
No `---` separators, no direction ambiguity. The pusher reads the file → splits into Telegram-safe chunks → sends via `telegram_direct`.
No regex splitting, no direction inference, no markdown balancing needed.

**v3.6 grade gate (MUST-DO):** The detector (`write_pending()`) checks Confluence grade BEFORE writing to pending.
Only A+ (total_w ≥ 8) and A (total_w ≥ 6) signals pass. B/C/D are silently dropped — pending file stays empty, push
cron has nothing to send. This enforces the user's 80%+ confidence requirement. The grade gate is the FIRST check
after extracting the confluence alert from the active list — it returns 0 before any formatting work.

**v3.5 alert card format:** See `references/alert-format-v34.md`.
Includes: one-line summary (≤40 chars, natural sentence with warning keywords) + next-step operational guidance
(watch which level, what action, contingency for breakout/breakdown).

**Verification:** write a Chinese pending block, run `python btc_push_cron.py`, expect `rc=0`, empty stdout, and pending size `0`.

### 4.5. Multi-Zone Price Watchdog (v4 — Proven Pattern)

**no_agent cron, `* * * * *`**. Zero-token price zone monitoring with individual per-zone cooldowns and intermediate status reporting.

**Design:**
- Multiple named zones with independent (lo, hi, description) tuples
- Per-zone cooldown (180s) via state file — each zone tracks its own last-trigger timestamp
- Intermediate/"status" zones between key levels prevent total silence
- State file MUST be at `~/AppData/Local/hermes/data/` — NOT `__file__`-relative (cron may resolve script directory differently)
- Script resolves relative to `~/.hermes/scripts/` (== `~/AppData/Local/hermes/scripts/`)

**Key zones for BTC watchdog (v4):**
```python
ZONES = {
    "VWAP_ZONE":    (63930, 64000, "反弹做空区(VWAP/DO附近)"),
    "BAND2_BREAK":  (64153, 64200, "Band2上轨突破·看周VWAP"),
    "WVWAP_ZONE":   (64480, 64530, "周VWAP(64,507)附近"),
    "L1":           (63170, 63370, "前低63,270±100"),
    "L2":           (62172, 62372, "大底62,272±100"),
}
```

**Fallback intermediate zones (when price is between key zones):**
- `MID_LOW` — price between VWAP_ZONE top and BAND2_BREAK bottom (e.g. "VWAP上方运行")
- `MID` — price between BAND2_BREAK top and WVWAP_ZONE bottom (e.g. "Band2上-周VWAP之间")
- `VAL_ZONE` — price between L1 top and VWAP_ZONE bottom (e.g. "VAL-折价区运行")
- `ABOVE_WVWAP` — price above WVWAP_ZONE top

**Pitfalls:**
1. **State file path must be absolute and writable by cron** — `__file__`-relative paths (`os.path.join(os.path.dirname(__file__), ".state.json")`) may resolve to a directory the cron process cannot write. Always use `os.path.expanduser("~/AppData/Local/hermes/data/.filename.json")` with `os.makedirs` guard.
2. **Per-zone cooldown, not global** — Each zone must have its OWN cooldown key in the state file. A global cooldown means a VWAP_ZONE trigger blocks L1 from firing for the entire cooldown period.
3. **Intermediates prevent total silence** — If the only zones are 63,270 and 63,930+ and price hangs at 64,100 for 4 hours, the user gets NOTHING and assumes the watchdog is dead. Intermediate zones (`MID_LOW`, `MID`, `VAL_ZONE`) keep cadence.
4. **Delivery to "origin" may fail silently** — no_agent cron with `deliver: origin` can have trigger timestamps in the state file but the user receives no message. No delivery error is reported (last_delivery_error: null). **Fix**: Switch to an agent cron with explicit `deliver: telegram:-1003733144325:386`. This pattern was verified working in the 2026-06-23 session. **Prevention**: Create monitoring crons with explicit chat:topic delivery from the start. If the user complains about missing alerts despite confirmed state-file triggers, switch to explicit delivery immediately rather than debugging the stdout pipeline.
5. **Agent cron alternative when no_agent delivery fails** — If the watchdog triggers (state file has timestamps) but user doesn't receive messages, create an agent cron instead:
   - Schedule: `*/3 * * * *` (every 3 min, longer interval to save tokens)
   - Deliver: `telegram:-1003733144325:386` (explicit chat:topic, NOT "origin")
   - Prompt: Use TV MCP tools to check price → if in trigger zone, generate full analysis card → if not, output empty string (silent)
   - This costs ~2K tokens per run even when silent, so balance interval vs reliability
   - Test with `cronjob(action='run', job_id='...')` and confirm user received the message
6. **Cron "repeat" trap** — Creating a cron with `schedule="once in 10m"` may result in `repeat: once`, causing the job to expire after one run and its job_id to be garbage-collected. Always use a proper cron expression (`* * * * *`, `*/10 * * * *`) and **omit the `repeat` parameter entirely** — it defaults to `forever` for cron expressions. Verified: a job with `*/10 * * * *` showing `repeat: once` was silently removed between sessions.
7. **Script updates take effect immediately** — no_agent cron reads the script file fresh each tick. No need to restart/recreate the cron when updating script content.
8. **Price can jump through a zone between 1-min ticks** — If price spends <60s in a zone, the script may miss it. Widen zone width or accept the gap.

**方向标注 (v3.5 — built into detector format):**
- `+ {model} → {reason} · {conf}%` — 多头信号
- `− {model} → {reason} · {conf}%` — 空头信号
- `~ {model} → {reason}` — 中性/窗口观察
- Headline: `综合: {grade} {偏多/偏空/中性} (多N vs 空M){★高胜率}`
- One-liner: concise warning sentence ≤40 chars with 关注/谨慎/警惕 keywords
- 下一步: operational guidance — which level to watch, what to do, contingency plan

### 4. MTF Analysis → Replaced by btc_daemon (v9.1)

**Old**: LLM-powered cron `*/15 8-23 * * *` consuming ~$33/month in tokens.
**Now**: btc_daemon.py is the zero-token replacement — local multi-factor scoring,
TV MCP subprocess for deep analysis, push only when score ≥ 8/10.

The old LLM cron was deleted 2026-06-29. If you need to recreate it (e.g., daemon
down temporarily), use a minimal prompt without loading heavy skills to keep token
cost low. But prefer restarting the daemon + watchdog.

### 4.5. 2022 ICT Pipeline Modules (on-demand)
Python modules for automated trade setup detection — used by MTF cron and on-demand analysis:
- **`fvg_detector.py`** — 三烛不重叠Fair Value Gap检测 (bullish/bearish, midpoint, gap_size)
- **`order_block.py`** — 机构OB识别 (strength 1-5, displacement_pct, zone_top/bottom)
- **`scoring_engine_v2.py`** — 14因子汇聚评分 (CVD背离·VWAP测试·扫荡·FVG·银弹·KZ·折溢价·多空比·Taker翻转·CVD吸收·量能·OB·EMA交叉·三源一致)
- **`pipeline_2022.py`** — Sweep→Displacement→FVG→Retest→Entry 全流程管线
- **`pipeline_integration.py`** — 全流程串联 + 分析卡生成
- **`auto_review.py`** — 信号→结果→胜率统计复盘 (win_rate, avg_r, expected_value, by_signal, by_day)
- **`event_calendar.py`** — 财经日历集成 (Jin10 + HTTP fallback, 30min事件阻塞)
- `btc_pipeline_daemon.py` — 每3分钟自动化管线守护 + 截图
- `btc_alert_watch.py` — 每分价位提醒（参见 `references/btc-alert-watch-encoding.md`）

All modules testable individually via `python <module>.py`, with `__main__` test harness.
Prices in markup: no `${` + commas (Telegram-conflicting), use `price:,.0f`.

## 🔑 Key Breakthrough: TV MCP Subprocess from no_agent Scripts

**The old assumption was wrong: no_agent scripts CAN use TV MCP directly.**

Pattern (proven in 2026-06-23 session):
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages")))
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

async def main():
    server_params = StdioServerParameters(
        command="node",
        args=["D:/Hermes agent/tools/tradingview-mcp/src/server.js"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Now call any TV MCP tool directly
            await session.call_tool("chart_set_symbol", {"symbol": "BINANCE:BTCUSDT.P"})
            # ... etc
```

This eliminates the need for an LLM cron TV data bridge. The daemon itself connects to TV MCP when it needs deep analysis, producing full analysis cards without any LLM token cost.

**Pitfall: Hermes venv path** — Use `~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages` on Windows, NOT the repo-relative venv. The MCP client library (`mcp.client.stdio`) lives here.

**Pitfall: Subprocess conflict** — Starting a second `node src/server.js` while the Hermes MCP server already manages one may conflict. For the daemon's deep analysis (once per 60s), the conflict is brief (the daemon starts, reads data, and exits the subprocess within ~15s). For real-time continuous monitoring, use the old TV data bridge pattern.

## Daemon Lifecycle & Watchdog Pattern (v9.1)

**Dual daemon architecture** (2026-06-29):

| Daemon | Heartbeat | Check | Restart |
|--------|-----------|-------|---------|
| 行情守望 | `data/monitor_heartbeat.json` | `status=="running"` | `rm -f data/monitor.lock && python scripts/行情守望.py -s BTCUSDT XAUUSD` |
| BTC守护 | `data/.btc_daemon_heartbeat.json` | `ts < 120s` | `rm -f data/.btc_daemon.pid data/.btc_daemon.lock && python scripts/btc_daemon.py` |

**铁律**：用 `terminal(background=true)` 启动守护进程，不要用 shell `&`（Hermes 拒绝执行）。

**Start daemon:**
```bash
# Use terminal(background=true), NO notify_on_complete (it never exits)
terminal(command="python scripts/monitor/btc_daemon.py", workdir="D:/Hermes agent", background=True)
```

**Watchdog (1m cron, no_agent):**
```python
# Algorithm:
# 1. Read heartbeat JSON file
# 2. If ts < 120s old → daemon alive → silent exit
# 3. If stale or missing → taskkill old PID → start /B python daemon.py
# 4. Output restart notification (cron delivers to TG or local)
```

**Kill daemon (for updates):**
```bash
taskkill /F /PID $(cat data/.btc_daemon.pid)
# OR
process(action='kill', session_id='proc_...')  # Only if Hermes-tracked
```

**Key lifecycle rules:**
- watchdog cron `*/1 * * * *`, no_agent, deliver=local (no output on success)
- heartbeat file path MUST be absolute: `D:/Hermes agent/data/.btc_daemon_heartbeat.json`
- PID file at same location for taskkill targeting
- After updating daemon code, ALWAYS kill + restart. No hot-reload.

## Real-time approved-level alerts (daemon direct delivery · 2026-09)

When the user says a one-minute check is too slow or asks for real-time price arrival alerts, do not use a one-minute sentinel as the primary notifier. Use the already-running `keylevel_guard.py` daemon: it polls approved levels at `POLL_SECONDS=0.5`, detects crossings, writes `trigger_{symbol}.json`, and directly sends a short notification to the explicit Telegram topic. The message must only say that price arrived and ask the user to inspect TradingView; it must not infer direction, emit Entry/Stop/Target, or place orders.

Disable/pause any overlapping minute sentinel after direct daemon delivery is enabled, otherwise duplicate alerts occur. After changing daemon code, restart the running daemon and verify its heartbeat PID/status and that the new alert hook is loaded. Keep the watchdog as the restart mechanism; do not claim “real-time” when only a cron job runs every minute.

**Noise-control rule — all structures, not only FVG/OB:** The user's “similar alerts are too many” correction applies to every approved structure type: FVG, OB, VWAP, VAH, VAL, prior highs/lows, weekly highs/lows, and any other configured level. Deduplicate per structure key with an independent 30-minute cooldown. A reverse crossing during that cooldown must remain silent; do not bypass cooldown merely because `cross_direction` changed. Only a new crossing after cooldown expiry may send another arrival notice. Keep the alert as a neutral “到价→请查看 TradingView” reminder, not a directional signal.

**Implementation pitfall:** Do not use `now >= cool_until or info.get("dir") != crossed` as the gate; the second clause defeats spam suppression when price oscillates around a level. Use `if now >= cool_until:` while retaining the latest crossing direction only as metadata.

The approved-level monitor remains separate from dynamic analysis: automatic renewal may extend validity of existing approved levels, but must not promote candidates or replace levels from a one-off analysis. See `references/keylevel-monitor-contract-202608.md` for the event contract.

## Review update: direct real-time arrival alerts (2026-09-05)

When a user rejects one-minute latency and asks for real-time price arrival notifications, route alerts through the already-running `keylevel_guard.py` daemon, not a minute Cron. The guard's `POLL_SECONDS=0.5` loop should detect crossing of explicitly approved, unexpired levels and directly send a short Telegram topic message asking the user to inspect TradingView. The message is a notification only: no direction inference, no Entry/Stop/Target, and no automatic order.

After enabling direct daemon delivery, pause overlapping minute sentinels to prevent duplicate notices. If the daemon code changes, a running process does not hot-reload: obtain user confirmation before terminating it, restart through the watchdog, then verify the new heartbeat PID/status and that the new alert hook is loaded. A successful task registration alone is insufficient evidence of real-time behavior.

The daemon must hot-read `data/keylevels_config.json`; automatic renewal may extend existing approved levels but must not promote candidates or silently replace one-off analysis levels. If direct Telegram delivery cannot be verified, report that it is not successfully configured rather than claiming the user will be notified.

## Key-Level Price Sentinel (no_agent cron · 2026-08-28 verified)

For "到价提醒 / watch this key level" requests, choose by latency requirement: a single **no_agent zero-token sentinel cron** is the minute-level fallback; it is **not real-time**. If the user asks for real-time or rejects one-minute latency, use `keylevel_guard.py` direct daemon delivery as described above. Do not run both primary notifiers simultaneously, or duplicate alerts occur.

**⚠ MUST: register via `hermes cron create` CLI, never by hand-editing `jobs.json`.** Hand-editing the JSON bypasses scheduler registration — no `repeat:∞`, no `workdir`, no deliver routing, and the job silently won't fire the way you expect. Use the CLI:
```bash
hermes cron create '* * * * *' \
  --name 'BTC关键位到价哨兵' \
  --script 'btc_keylevel_sentinel.py' \
  --no-agent --deliver 'local' \
  --workdir 'D:/Hermes agent'
```
- `--no-agent` = script IS the job; empty stdout = silent (zero token).
- `--deliver local` = cron itself is silent; **the script pushes Telegram itself** via `telegram_direct.send_telegram_direct(target, msg) -> (ok, reason)`. Don't double-deliver.
- Cron expression + omit `--repeat` → `repeat: ∞` (verified). `*/1 * * * *` is the practical floor for price windows; ~30s-level wants a daemon instead.
- Verify: `hermes cron list` shows the job with `Repeat ∞`, then let one tick pass and confirm `Last run: ... ok`.

### User-facing arrival reminder contract (2026-09)

When the user asks to be told when price reaches a level, the alert is a **notification to inspect the chart**, not an analysis or trade signal. Use a direct, plain first line such as `○ BTC 到价：79,435，请查看 TradingView 15m`; do not say “到了就买”, do not emit Entry/Stop/Target, and do not infer direction from the crossing itself. The user decides after opening the chart.

The sentinel must hot-read `data/keylevels_config.json` on every tick so approved levels can be changed or renewed without rewriting the script. It may use a narrow tolerance window and per-level cooldown, but must keep state under `~/AppData/Local/hermes/data/`. Use explicit Telegram topic delivery inside the script when `deliver=local`; never rely on `deliver=origin` for user-visible alerts. A successful cron dispatch is not proof of delivery: verify the script exists in the runtime scripts directory, run it once, and read back the cron registration. Dynamic analysis levels are not automatically approved levels; automatic renewal extends validity only and must not promote candidates.

**Sentinel script skeleton** (all in repo `scripts/`, importable siblings `binance_public` + `telegram_direct`):
```python
# price = binance_public.fetch_futures("/fapi/v1/ticker/price", {"symbol": SYM})
# ZONES = {key: {"lo","hi","desc"}} with per-key COOLDOWN (1800s) in state file
# state file at ~/AppData/Local/hermes/data/... (NOT __file__-relative)
# in zone & cooldown passed -> build msg -> telegram_direct.send_telegram_direct("telegram:-1003733144325:386", msg)
# out of zone -> reset per-key last_alerted
```
Delivery target for BTC = `telegram:-1003733144325:386` (topic 386). Per-key cooldown + out-of-zone reset is what stops spam.

## Fixed Price Zones (7-level)

The previous v12 community signal system was too complex and unreliable. The user deleted all 10 old scripts. The replacement is simple fixed price zones detected every 15 seconds:

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

**Rules:**
- Zones are price windows, not indicator-based. Determines which "strategy regime" is active.
- Detection: `lo <= current_price <= hi`
- Zone change → update state + recalculate multi-factor score (v2: NO automatic push)
- Push only when multi-factor score ≥ 8 AND 30min cooldown not active
- Zones update as price regime changes (e.g., when new swing lows form)

## Key Design Decisions

1. **🚨 TV MCP subprocess (MUST-KNOW)** — no_agent scripts CAN connect to TV MCP by starting their own subprocess (`node src/server.js`). This was proven in the 2026-06-23 session. This eliminates the need for an LLM cron data bridge. The daemon's deep-analysis cycle uses this pattern.

2. **🚨 TV MCP agent context priority** — When the LLM agent is active (not in a no_agent script), ALWAYS use TV MCP tools directly. Do NOT read bridge cache files (`btc_tv_data.json`) as a primary data source. The user has corrected this multiple times: "有TV的mcp啊". Cache files are for no_agent daemon use only.

3. **Absolute paths for daemon scripts** — NEVER use `__file__`-relative paths in scripts that run from `~/.hermes/scripts/` via cron. The script's `__file__` resolves to the cron workdir, NOT the project root. Use hardcoded `Path("D:/Hermes agent")` for all data/screenshot/script references.

4. **Per‑field error isolation** — collector has separate try/except per Binance endpoint, with 2 retries + 0.5s delay.
5. **State persistence** — daemon writes JSON state file every cycle. Cross-restart event dedup is critical.
6. **LV‑level monitoring vs LLM analysis** — price levels (VWAP/VAL) are fast mechanical checks (10s daemon). Market structure analysis is LLM‑reasoned (15m cron). Don't mix them.
7. **TV MCP数据桥是fallback** — 当 AI Agent 直接可用 TV MCP 时，永远优先直接调用 MCP 工具而非读桥接文件。桥接文件是给 no_agent 守护进程用的，不是给 Agent 自己用的。
8. **Cron must be recurring** — creating a cron with a schedule string sets `repeat=once` when you pass `repeat` explicitly. Omit `repeat` or set `repeat=forever`.
8. **Macro as separate file** — keep macro data (DXY, F&G) in a separate file (`btc_macro.json`) from price data (`btc_latest.json`). Different update cadences and failure domains.
9. **🚨 DMI table is reference, NOT decision engine** — The TV DMI grade (A/B/C/X) is rendered on cards for context but must NOT determine direction. Direction comes from a 5-factor vote: VWAP position + CVD pressure + EMA alignment + structure bias + level proximity. At least 4/5 factors must agree for a confident direction. This is a user-requested design principle, not an implementation detail.

## Pitfalls

1. **Cron `repeat` trap** — Most cron bugs come from accidentally setting `repeat=once`. For recurring monitoring, use `* * * * *` and omit `repeat` (defaults to forever).
21. **SkillMCP cron 超时修复（2026-06-29）** — 原脚本串行执行 4 个子任务（skills check + curator + 8个MCP逐个测试 + hermes update），最坏 720s 远超 cron 默认 120s 限制。修复：parallelize via ThreadPoolExecutor（skills check + curator + MCP test 并行），MCP test 内 4 线程并行，per-MCP timeout from 30s→15s，official update timeout from 300s→60s。现在总耗时约 90-120s。 Kill with `taskkill //F //PID <n>` in MSYS when updating. Verify PID each restart — they change.
3. **Python SSL in MSYS** — `urllib` to Binance can hang. Always set short timeouts (5-6s) and isolated try/except per endpoint. Never batch futures calls — each must be individually guarded.
4. **Pending file is reliable** — push cron truncates after reading. Daemon uses append mode, both events arriving between ticks are captured. Race conditions are extremely unlikely at 10s vs 60s intervals.
5. **TV MCP data must be primary** — the daemon historically calculated VWAP locally from Binance klines and hardcoded VAL/VAH. This is WRONG — TV's SVP indicator is what the user sees on their chart. Always prioritize `btc_tv_data.json` values. The daemon's local calc is a fallback only. The user WILL point out "有TV的mcp啊" if you ignore this.
6. **TV MCP chart state persistence** — TV MCP calls return data from whatever timeframe the chart is currently on. The data bridge cron must explicitly `chart_set_timeframe("15")` before reading study values. If the previous cron set a different TF, values will be garbage.
7. **TV数据桥 LLM cron cost** — at ~2K tokens per run, */2 8-23 = ~$0.50/day. This is acceptable for bridging MCP to no_agent. Keep the prompt minimal (data relay only, no analysis).
8. **Daemon heatup period** — `cnt > 5` guard prevents false triggers on startup. Allow ~60s after restart before events fire.
9. **Star event prompt** — The event-triggered analysis cron must check-if-content-then-generate. If the priority file is empty, the LLM cron must output NOTHING (zero output = no Telegram delivery). Include a `cat > file` (truncate) step to avoid re-processing the same event.
10. **Macro data cadence** — DXY and F&G change slowly (hours/days). The collector fetches them every 1m which is wasteful but harmless. Consider a separate 5m cron for macro only if token cost is a concern.
11. **TV MCP优先（已升级为顶层 MUST-DO 规则 #1）** — 参见 Key Design Decisions #1。此 pitfall 已不适用，顶层规则覆盖。

12. **Comprehensive audit pattern** — when the user asks to "全面联网社区全方面的进行更新补充完善迭代" or "全面审计", the workflow is: scan skills_list → load relevant skills (realtime-trading-pipeline, trading-system-audit, trading-card-generation) → check MCP inventory (what's available but unused) → read memory for preferences → web search community best practices across 6+ sources → cross-reference gaps against current system → produce priority-ordered gap list (P0→P1→P2) → batch execute ALL improvements when user says "全部做" (don't ask for confirmation on each item).

13. **"全部做" batch execution** — When the user says "全部做" or "一起修复了", execute ALL identified P0+P1+P2 improvements in a single pass. Don't stop to ask which ones. After each major change (daemon restart, cron update), verify with real tool output before moving to the next. At the end, present a consolidated summary of what changed.

14. **Daemon crash from undefined variable** — The signals JSON block at the end of the daemon cycle references variables that may only be defined inside conditional blocks (e.g., `div` is only set inside `if cnt > 36:`). These must be initialized as `None` at the START of each cycle, BEFORE all conditionals. If the daemon crashes silently (exits with exit_code 1, no output), the push cron lasts_status shows "ok" but no events reach Telegram. Test with `timeout 20 python btc_vwap_daemon.py` after every change and check for exit_code 124 (good, normal timeout) vs 1 (crash). If it crashes, run it directly to see the traceback, fix the variable, restart.

15. **No-signal diagnosis checklist** — When user says "没信号" / "怎么没有信号" / "为什么没有警报警告", do NOT assume the daemon crashed. Follow this order:
    1. `process(action='poll')` on daemon session_id → if dead, check exit code + traceback
    2. `cat btc_pending.txt` → if empty, push cron cleared it correctly
    3. `cat btc_signals.json` → check current dv (VWAP-price). If dv is between $60-$200, the daemon is CORRECTLY silent — no conditions are met.
    4. Explain: VWAP测试 needs dv<$60, 极端偏离 needs dv>$200. Current state is a **no-trigger zone**. Silence = correct behavior, not a bug.
    5. Only if dv<$60 or dv>$200 AND pending is empty for >2min → investigate push pipeline.

16. **Two-file path sync on Windows — VERIFY first; may already be one place.** Historically the daemon scripts lived in TWO locations that MUST stay in sync:
    - `C:\\\\Users\\\\...\\\\AppData\\\\Local\\\\hermes\\\\scripts\\\\` (runtime — where the cron/daemon process reads from)
    - `D:\\\\Hermes agent\\\\scripts\\\\` (repo — where git tracks and patches apply)
    When `patch` applies to `D:\\\\Hermes agent\\\\scripts\\\\btc_vwap_daemon.py`, the C: drive copy may fall behind. **BUT (2026-08-28): on this install `cp "$REPO/x.py" "$RUNTIME/x.py"` returned "are the same file"** — the runtime scripts dir is a symlink/junction into the repo, so they are ONE location and no sync is needed. **First test `cp repo/x.py runtime/x.py`; if it says "same file", skip the sync entirely** (wasted copy otherwise). If it copies, then do the full `cp /d/Hermes agent/scripts/*.py /c/Users/Administrator/AppData/Local/hermes/scripts/` + `diff` flow. The daemon runs from C:, patches apply to D: by default; this mismatch caused silent stale-code execution in 2026-06-22 session.

17. **Alert format filter ordering** — The `write_pending()` filter pipeline MUST check `is_confluence` BEFORE the conf<0.35 gate. Confluence alerts often have low conf values (total_weight/10) and will be silently dropped if checked after. Symptom: grade shows `?` in the alert headline. Fix: move the `if a.get("is_confluence")` check to the top, before any conf/priority filters.

18. **OI display unit** — OI from Binance is absolute contract count (e.g., 101,509). Display as `{oi/1000:,.0f}K` not `{oi/1e6:.0f}M`. The latter truncates 0.101M → 0M for BTC OI values under 1M contracts. Only use M for ETH or other high-OI assets.

19. **B2 level mapping** — `B2上` and `B2下` must appear in BOTH `levels_above` and `levels_below` depending on price position relative to each level. When price > B2上, B2上 is a SUPPORT (levels_below). When price < B2下, B2下 is a RESISTANCE (levels_above). Failing to map B2上 to levels_below causes `_gen_next_step` to suggest "上破B2上" when already above it.

20. **Alert noise and grade gating (v3.6+/v2)** — User explicitly requires ONLY very confident alerts. v2 daemon uses multi-factor scoring (0-10, threshold ≥ 8) instead of the old zone-entry push. This is simpler and more reliable than the v3.x confluence grade system. Run Python DMI engine + F&G as subprocess on each deep cycle. Push decisions combine: trend score + CVD confirmation + key level proximity + F&G extremes + not-X state. LOCKING factor: the user said "只有很确定很确定的机会才推送" and also "dmi表只是参考" — do NOT weaken the score gate or fall back to TV grade as primary decision.

18. **TV数据桥缓存质量闸门（Windows/Node路径坑）** — When diagnosing “TV is open but analysis looks abnormal”, verify the bridge cache before blaming TV MCP:
    - Confirm the cron is `no_agent=true`, `deliver=local`, script bridge wrapper, and workdir is the TradingView MCP directory.
    - Run `node --check fetch_tv_data.cjs`, then run the wrapper and assert success stdout is empty.
    - In Node scripts, use `C:/Users/...` forward-slash Windows paths, never string literals like `C:\Users\...` unless every backslash is correctly escaped. Bad literals can become `C:Users...\b...` because `\b` is backspace, causing writes to the wrong/invalid path while logs look plausible.
    - Verify with the same path style the runtime scripts use: Python on Windows should read `C:/Users/Administrator/AppData/Local/hermes/data/btc_tv_data.json`, not a POSIX-looking `/c/...` string inside Windows Python. A bad `/c/...` read can create/read `D:/c/...` and mislead the diagnosis.
    - The cache must contain non-empty `symbol/resolution/vwap/poc/vah/val/cvd/cvd_slope`; numeric fields should be numbers, not comma strings. If quality fails, do not overwrite the last good cache.
    - See `references/tv-data-bridge-windows-debug.md` for the full debug/verification recipe.


## Data Sources

| Source | Endpoint | Tool | Data |
|---|---|---|---|
| Binance Spot | `/api/v3/ticker/price` | urllib | Current price |
| Binance Spot | `/api/v3/klines` | urllib | K-lines for VWAP calc |
| Binance Spot | `/api/v3/ticker/24hr` | urllib | 24h volume |
| Binance Futures | `/fapi/v1/openInterest` | urllib | Open Interest |
| Binance Futures | `/fapi/v1/premiumIndex` | urllib | Funding rate |
| Binance Futures | `/futures/data/topLongShortAccountRatio` | urllib | LS ratio |
| Binance Futures | `/futures/data/takerlongshortRatio` | urllib | Taker volume |
| Yahoo Finance | `/v8/finance/chart/DX-Y.NYB` | urllib | DXY index |
| alternative.me | `/fng/?limit=1` | urllib | Fear & Greed |
| Collector JSON | `btc_latest.json` | file read | Aggregated snapshot |
| Macro JSON | `btc_macro.json` | file read | DXY + F&G |
| TV数据桥 | `btc_tv_data.json` | file read | SVP indicator values |
| TradingView MCP | `data_get_study_values` | MCP tool | SVP indicator values |
| TradingView MCP | `capture_screenshot` | MCP tool | Chart screenshot |

## Event Conditions (v12 — 3 tiers + community signals)

### Level Events (5‑min block dedup, ALL carry CVD context from TV数据桥)

| Symbol | Condition | Message |
|---|---|---|
| 📊 VWAP测试 | `0 < VWAP-价 ≤ $60` | `VWAP测试 · 价P · VWAP V · 上方$D · CVD+N` |
| 🟢 站回VWAP | 价 > VWAP | `站回VWAP · 价P · VWAP上$D · CVD+N` |
| 🔴 破VAL | 价 < VAL | `新破/持续破VAL · 价P · VAL V · 下$D · CVD+N` |
| 🟡 站回VAL | 价 > VAL | `站回VAL · 价P · VAL上$D · CVD+N` |
| 🟠 破VAH | 价 > VAH | `破VAH · 价P · VAH上$D · CVD+N` |

### Community Advanced Signals (v12, 5‑min dedup, cnt>5 heatup)

| Signal | Condition | Window | Message Example |
|---|---|---|---|
| 🔮 CVD空背离 | Price HH + CVD LH over 24 cycles | cnt>36 | `🔮 CVD空背离 · 纽约 · 价64,217 · CVD-92` |
| 🔮 CVD多背离 | Price LL + CVD HL over 24 cycles | cnt>36 | `🔮 CVD多背离 · 伦敦 · 价64,217 · CVD+150` |
| 🎯 VAL扫荡 | Price < VAL then > VAL within 30s | cnt>10 | `🎯 VAL扫荡 · 触63,886下$42 · 已回收` |
| 🎯 VAH扫荡 | Price > VAH then < VAH within 30s | cnt>10 | `🎯 VAH扫荡 · 触64,490上$35 · 已回收` |
| 💧 CVD吸收 | CVD range >150, price range <$30/3min | cnt>36 | `💧 CVD吸收 · 价不动·CVD大幅波动` |
| 💧 CVD派发 | CVD range >150 (negative), price range <$30/3min | cnt>36 | `💧 CVD派发 · 价不动·CVD大幅走负` |
| ⭐ 反转信号(多) | far_down($200) + Taker flip >0.5 (buy) | cnt>5 | `⭐ 反转信号(多) · 价P · Taker 1.89 · 纽约` |
| ⭐ 反转信号(空) | far_up($200) + Taker flip >0.5 (sell) | cnt>5 | `⭐ 反转信号(空) · 价P · Taker 0.37 · 伦敦` |
| ⭐ 空头延续 | far_down($200) + Taker<0.4 | cnt>5 | `⭐ 空头延续 · 价P · VWAP V · Taker卖0.37` |
| ⭐ 多头延续 | far_up($200) + Taker>1.6 | cnt>5 | `⭐ 多头延续 · 价P · VWAP V · Taker买1.89` |
| 📉 快速下跌/上涨 | >0.3% in 30s | cnt>3 | `📉 快速下跌 · 价P · 30s -0.45%` |
| 📊 VWAP偏离 | >$200 from VWAP | cnt>3 | `📊 VWAP偏离 · 价P · VWAP下$203` |

KillZone and Silver Bullet are attached as tags to relevant events (not standalone alerts):
- KillZone: ` · 亚洲` / ` · 伦敦` / ` · 纽约` appended to events
- Silver Bullet: ` · 银弹窗口🔥` appended when active (never English "Silver Bullet")

## Chinese Localization Rules (Event Messages)

**Confirmed conventions** (user corrections from this session — apply to ALL event messages and analysis cards):
- `Silver Bullet` → `银弹窗口` (never English)
- `Taker` → `主动买卖` (never "Taker" standalone)
- `LS` → `多空比` (never "LS")
- `OI` → `持仓` (never "OI")
- `F&G` → `恐惧贪婪` (never bare "F&G")
- `KillZone` → `亚洲`/`伦敦`/`纽约`/`盘外` (English zone names only as code keys)
- `Premium`/`Discount` → `折价`/`溢价`
- `Outside` → `盘外`
- `Funding` and `Spot` stay English per user preference

**方向标注** — 每条告警推送必须在首行前加方向符号：
- `↑做多` — 站回VWAP/VAL、破VAH、CVD多背离
- `↓做空` — 破VAL、CVD空背离
- `○等待` — VWAP测试、流动性扫荡
- `☆入场就绪` — 管线entry_ready

**emoji 保留策略** — 保留 🟡🟢🔴🟠📊🔮🎯💧 等少量 emoji 配合方向文字；不用纯文字也不全用 emoji。

**Allowed English** (universal trading abbreviations the user accepts): VWAP, CVD, EMA, DXY, BTC, USDT, R:R

**Mapping in daemon code:**
```python
kz_label_map = {"asia": "亚洲", "london": "伦敦", "ny_am": "纽约", "outside": "盘外"}
sb_label = "银弹窗口🔥" if sb else ""
# signals JSON: "killzone": kz_cn, "silver_bullet": sb_label (string, not bool)
```

### ⭐/🔮 Priority System (separate files for zero-token alerts vs LLM analysis)

The daemon writes to THREE files:
- `btc_pending.txt` — ALL events. Consumed by push cron (1m, no_agent → Telegram).
- `btc_priority.txt` — Only ⭐ and 🔮 events. Consumed by event analysis cron (2m, LLM → full analysis card + screenshot).
- `btc_signals.json` — Current signal summary. Read by the MTF analysis cron for context (KillZone, divergence, premium/discount, Silver Bullet).

This separation ensures:
- Basic alerts reach the phone in <1m (zero-token pipeline)
- ⭐ signals trigger a full depth analysis card within <2m (LLM-reasoned)

### Priority Detection Logic (Python pseudocode)

```python
# Read collector data for taker_ratio
taker = collector.get("taker_ratio")
last_taker = state.get("last_taker", 1.0)
far_down = vwap - price > 200    # Price far below VWAP
far_up = price - vwap > 200      # Price far above VWAP

# ⭐ Reversal signal: extreme + order flow flip
if (far_down or far_up) and abs(taker - last_taker) > 0.5:
    direction = "多" if far_down and taker > 1.0 else "空" if far_up and taker < 1.0 else None
    write_priority(f"反转信号({direction})", priority="high")

# ⭐ Continuation signal
if far_down and taker < 0.4:
    write_priority("空头延续 (Taker持续卖)", priority="high")
```
## User noise policy: value-area levels are opt-out by default

When the user says that alerts like `价值区·VAL` are unwanted, interpret this as a request to silence the entire value-area layer, not only the named level. Set `enabled: false` for all configured `layer: "价值区"` entries (VAH, VAL, POC, nPOC, DO, M-VWAP and equivalents), preserve the entries for auditability, and leave structural/HTF levels unchanged unless the user explicitly names them too. The daemon hot-reads `data/keylevels_config.json`, so verify the active count after editing; do not send a confirmation alert for a now-disabled value-area level. This is separate from the per-level cooldown rule: cooldown deduplicates enabled structures, while the value-area policy suppresses the category entirely.

## References

- `references/btc-implementation.md` — session-specific implementation details (file structure, cron configs, full event rules)
- `references/community-research-2026-06-22.md` — community research findings: KillZone timing, CVD divergence, Silver Bullet, sweep/absorption detection, verification commands
- `references/push-notification-format.md` — push alert format: direction labels, emoji strategy, alert header regex
- `references/btc-alert-watch-encoding.md` — Windows GBK encoding fixes (legacy stdout UTF-8 approach), btc_alert_watch.py design, verification commands
- `references/windows-noagent-ascii-stdout.md` — final stable pattern for Windows no_agent: ASCII-only stdout + UTF-8 pending/direct Telegram payload
- `references/cockpit-v96-runtime-hardening.md` — v9.6 cockpit/runtime hardening: watchdog guard ordering, canonical wrapper imports, auto_card risk fallback, futures symbol routing, verification checklist
- `references/tv-data-bridge-windows-debug.md` — TV bridge debugging on Windows: no_agent script bridge, Node path escaping, cache quality gates, verification commands
- `references/cron-notification-routing.md` — cron 通知路由/降噪、Telegram vs local 分层、X情绪 LLM 分析卡升级模式
- `agentless-monitoring` skill — covers the no_agent monitoring pattern
- `references/btc-daemon-architecture-v1.md` — BTC background daemon + watchdog + card gen architecture (2026-06-23 session)

## v2 Evolution (2026-06-23) — Multi-Factor High-Confidence Push

**From zone-entry alerts to multi-factor scoring gate.** Key changes from v1:

| Old (v1) | New (v2) | Reason |
|----------|----------|--------|
| Zone entry → immediate alert | Multi-factor score ≥ 8/10 → push | User: "只有很确定很确定的机会才推送" |
| Direction from TV DMI grade | Direction from 5-factor vote (VWAP/CVD/EMA/structure/level) | User: "dmi表只是参考，不能做为决策" |
| Numbered alert format (①②③) | Conversational language (无编号) | User: "警报看不懂，你直白一点" |
| TV MCP wait 2-3s per TF | 5-8-12s + up to 3 retries checking for VWAP | User: "多周期分析太快了，指标还没有加载完成" |
| Push on every event | 30-min cooldown per direction | User: "太频繁了" |
| Single code path | market-regime-classifier patterns integrated | User: "还有很多加密的skill可以用" |

### Multi-Factor Direction (replaces TV DMI grade)

Card direction uses 5-factor voting. DMI grade from TV is RENDERED on cards as reference info (`TVX · 结构冲突`) but does NOT determine direction.

### Multi-Factor Push Gate (daemon)

Every 60s, daemon scores 0-10: zone importance (3) + 15m trend (2) + volume (2) + distance from key level (2) + volatility (1).
**Push only if score ≥ 8**. After push: 30min cooldown per direction.

### Alert Format (daemon quick pushes)

Conversational, no numbering:
```
↓ BTC 62460，跌到大底区(62172-62472)
62,272是周级别大底，守住做多64K+，跌破看61K
```

### Card Format (deep analysis) — v8.0 Narrative Style

The deep analysis card (btc_card_gen.py) uses a 5‑section narrative format, matching master-template-v68.md:

```
{direction} BTC 日内分析 · {zone} · {time}
现价 `{price}` · VWAP偏差 · 日跌~2.3%

① 今日结构
TV DMI: {reference grade only, NOT direction source}
EMA{state}排列 · {ema values} · 4h/1h context
CVD summary

② 关键位
R VAH · R VWAP · S VAL levels with prices

③ 量价分析
CVD directional bias · TV grade reference line

④ 交易方案
主方向: {multi-factor votes}
守支做多: 入场/损/目
破阻做空: 入场/损/目

⑤ 综合评分
CVD✅ · EMA✅ · 关键位✅ · 恐慌✅ · TV{grade}
风控 仓位建议
```

Key rules:
- Direction from 5‑factor vote (VWAP/CVD/EMA/structure/level proximity), NOT TV DMI grade
- TV DMI grade rendered as `① 今日结构 TV DMI: ...` reference line + `③ 量价分析 ⚠X级=仅供参考`
- EMA cloud values shown as `EMA9`xxxx`<21`yyyy` · 34`zzzz`<55`wwww``
- 4h + 1h VWAP deviation shown in structure section
- Both trade plans always rendered (守支做多 + 破阻做空), even on X grade (marked ⚠X级参考)
- ⑤ 综合评分 uses ✅/⚠/❌ for CVD, EMA alignment, key level proximity, panic index
- MEDIA screenshot appended as last line

### TV MCP Timing Fix

After timeframe change, wait: 15m=5s, 1h=8s, 4h=12s + up to 3 retries×3s. Check study_values for VWAP key presence before reading. Only mark data valid when VWAP is confirmed present.

## v3.0 Evolution (2026-06-22)

The alert pipeline upgraded to a unified multi-factor detector. Key changes:
- **btc_alert_watch_v3.py** — replaces old btc_vwap_daemon.py + btc_alert_watch.py split. Single 12-D detector: VWAP Band, CVD, Taker, EMA, KillZone, Silver Bullet, L/S extreme, ★A+ confluence.
- **Engine modules** — session_strategy.py, triple_confirm.py, event_ban_live.py, macro_filter.py, polymarket_bridge.py — all wired into auto_card.py and cron.
- **No more hardcoded TV values** — see tangxi-system-audit skill references/hardcoded-value-detection.md.
