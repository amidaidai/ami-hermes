# TradingView MCP in Hermes

Use this reference when the user wants Hermes to analyze or control their live TradingView Desktop chart through an MCP server.

## Prerequisites: TradingView Desktop Installation

TradingView Desktop (not web-only) must be installed AND running with Chrome DevTools Protocol (CDP) enabled. The MCP tools connect through port 9222 — without a running TV Desktop exposing that port, ALL MCP tools fail with "CDP connection failed".

### Windows standard install

1. Download from [tradingview.com/desktop](https://www.tradingview.com/desktop/)
2. Standard install location: `C:\Users\<user>\AppData\Local\TradingView\TradingView.exe`
3. Launch with CDP enabled:
   ```bash
   "C:\Users\<user>\AppData\Local\TradingView\TradingView.exe" --remote-debugging-port=9222
   ```
4. Verify: `curl http://127.0.0.1:9222/json/version` — should return JSON with `webSocketDebuggerUrl`

### If TV Desktop is not installed

- The `tv_launch` tool searches standard paths and fails cleanly if not found.
- Do not attempt `tv_launch` repeatedly — it won't find what isn't installed.
- Search alternative paths:
  ```bash
  find /c/Users/<user> -name "TradingView.exe" 2>/dev/null
  find /c/Program\ Files -name "TradingView.exe" 2>/dev/null
  ls /c/Users/<user>/AppData/Local/TradingView/ 2>/dev/null
  ```
- If truly absent, report to the user: "TradingView Desktop not installed — cannot use TV MCP tools."

### Windows Store / MSIX install

If installed from Microsoft Store, the standard launch method may not expose CDP. See `references/tradingview-windows-msix-cdp.md` for the COM activation workaround.

### When TV is permanently unavailable

Some machines may not have TV Desktop (headless servers, minimal installs). In that case:
- All TV MCP tools (`pine_tables`, `study_values`, `chart_set_symbol`, `capture_screenshot`, etc.) are unavailable.
- Fallback to alternative data: Binance MCP (K线+衍生品), Jin10 MCP (快讯+XAU), financekit MCP (股票/ETF).
- For crypto technical indicators (RSI/EMA/VWAP/ATR), pull raw OHLCV from Binance MCP and compute in Python.
- For TV DMI decision tables specifically: write failure status to `data/tv_dmi_cache.json` preserving the last good snapshot, so downstream consumers (monitoring, auto_card) gracefully degrade.

## Recommended server

Primary choice: `tradesdontlie/tradingview-mcp`.

Why:
- Native MCP server over stdio.
- Connects to TradingView Desktop through Chrome DevTools Protocol on localhost, usually port `9222`.
- Exposes chart state, screenshots, quotes, OHLCV, visible indicator values, Pine drawings/tables/labels/boxes, Pine compile/check workflows, panes/tabs/layouts, alerts, replay, and UI automation.
- Fits this user's workflow better than generic TradingView screener MCPs when the request is "analyze my current TradingView chart".

Complementary projects to consider:
- `atilaahmettaner/tradingview-mcp` — better as a market scanning / technical-analysis / multi-exchange data MCP, not a current-desktop-chart reader.
- `fiale-plus/tradingview-mcp-server` — lightweight screener/search/TA MCP.
- OpenCLI `tradingview-reader` from `himself65/finance-skills` — alternative read-only workflow, but overlaps with the MCP and adds another tool stack.

## Hermes install pattern

Install into the user's tools area, then register with Hermes MCP rather than copying Claude Code `.mcp.json` instructions verbatim:

```bash
mkdir -p tools
git clone https://github.com/tradesdontlie/tradingview-mcp.git tools/tradingview-mcp
cd tools/tradingview-mcp
npm install
hermes mcp add tradingview --command node --args 'D:/Hermes agent/tools/tradingview-mcp/src/server.js'
hermes mcp list
```

If `hermes mcp add` prompts to enable tools in a non-interactive terminal, pipe approval only after the user has granted broad permissions:

```bash
yes Y | hermes mcp add tradingview --command node --args 'D:/Hermes agent/tools/tradingview-mcp/src/server.js'
```

Hermes MCP changes require a fresh Hermes session (`/reset` or restart) before the newly registered MCP tools are available to the agent.

## TradingView CDP startup

The MCP needs TradingView Desktop running with CDP enabled:

```bash
D:/Hermes agent/tools/tradingview-mcp/scripts/launch_tv_debug.bat
```

or use the MCP/CLI launch helper once the tools are loaded:

```bash
node src/cli/index.js launch
node src/cli/index.js status
```

On Windows Store/MSIX installs, direct launching the discovered `TradingView.exe` from Git Bash with `--remote-debugging-port=9222` may reject the flag. Prefer the repository's Windows `.bat` launcher or a Windows-native shell/shortcut launch route.

## First analysis workflow

After a fresh session with MCP tools loaded:

1. `tv_health_check` — verify CDP and active TradingView chart.
2. `chart_get_state` — symbol, timeframe, chart type, indicator list/entity IDs.
3. `quote_get` — current price snapshot.
4. `data_get_study_values` — visible indicator values.
5. `data_get_pine_lines`, `data_get_pine_labels`, `data_get_pine_tables`, `data_get_pine_boxes` — custom indicator outputs. Use `study_filter` whenever possible.
6. `data_get_ohlcv` with `summary: true` — compact price action summary.
7. `capture_screenshot` — visual confirmation.

Then present the result in the user's preferred compact live-trading style: direction, key location, event, confirmation, plan, invalidation, and no-chase reason.

## Permission boundaries

If the user grants broad permission, the MCP can modify TradingView state. Still separate actions by risk:

- Low-risk/read: health, chart state, quote, OHLCV summary, study values, Pine drawings/tables, screenshot, Pine static analysis/check.
- Medium-risk/chart changes: switch symbol/timeframe/type, layout/pane/tab changes, add/remove indicators, draw shapes.
- High-risk/account/workflow changes: save Pine scripts, create/delete alerts, execute arbitrary `ui_evaluate`, type/click arbitrary UI, replay trade actions.

For this user, default to direct read/analysis. Use write/control tools when requested, and clearly state the action being taken before high-risk modifications.

## Troubleshooting: CDP connection failure

### Diagnostic flow

When `tv_health_check` or any TV MCP tool returns "CDP connection failed":

1. **Try `tv_launch(kill_existing=true)`** — may auto-launch TV if binary exists at standard paths.
2. **If tv_launch fails** ("TradingView not found on win32"), search for the binary:
   ```bash
   find /c/Users/<user> -name "TradingView.exe" 2>/dev/null
   ```
   Check both `AppData/Local/TradingView/` and `Program Files/`.
3. **If binary found but still no CDP** → try manual launch with `--remote-debugging-port=9222`.
4. **If binary not found** → TV Desktop is not installed. Report to user with install instructions.

### Important: tv_launch error is misleading

`tv_launch()` may report "TradingView not found on win32" even when TV IS running with CDP already on port 9222 (e.g., from a prior monitoring session). Before concluding TV is not installed, check if port 9222 is already answering:

```bash
curl -s http://127.0.0.1:9222/json/version
```

If this returns JSON, TV is already running. Call `tv_health_check` again after a brief pause — the MCP tools may reconnect.

### Fallback when TV MCP is down

Do NOT retry the same MCP tool repeatedly. Instead:
1. Check if TV can be launched (above).
2. If TV is genuinely unavailable, fall back to alternative data sources for the task:
   - Crypto OHLCV + indicators → Binance MCP
   - XAU quotes + news → Jin10 MCP
   - Stock/ETF/fundamentals → financekit MCP
   - BTC price → Binance `get_price`
3. For cron jobs that need TV DMI tables: write error state to cache with last good data preserved, so monitoring pipelines gracefully degrade rather than produce stale signals.