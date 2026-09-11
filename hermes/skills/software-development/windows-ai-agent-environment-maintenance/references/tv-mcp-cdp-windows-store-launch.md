# TradingView MCP: CDP Launch on Windows Store Installation

## Problem

`mcp_tradingview_tv_launch` returned:
```
TradingView not found on win32. Searched:
  C:\Users\Administrator\AppData\Local\TradingView\TradingView.exe,
  undefined\TradingView\TradingView.exe
```

Meanwhile, TradingView Desktop was installed and running (launched via start menu / desktop shortcut), but port 9222 was not open → no CDP connection → MCP tools returned `_activeChartWidgetWV` errors.

## Root Cause

TradingView Desktop was installed from the **Microsoft Store** (Windows Store). The actual binary lives in the protected `C:\Program Files\WindowsApps\` folder:

```
C:\Program Files\WindowsApps\TradingView.Desktop_3.2.0.7916_x64__n534cwy3pjxzj\TradingView.exe
```

The Hermes MCP server's `tv_launch` module searches for the exe at:

```
%LOCALAPPDATA%\TradingView\TradingView.exe
# → C:\Users\<user>\AppData\Local\TradingView\TradingView.exe
```

WindowsApps is ACL-protected and not discovered by the MCP server's search paths.

## Fix

Copy the executable from WindowsApps to the path the MCP server expects:

```bash
# 1. Kill existing TV instances
taskkill //F //IM TradingView.exe

# 2. Create target directory
mkdir -p "/c/Users/Administrator/AppData/Local/TradingView"

# 3. Copy the exe (the cp command works because Administrator can read WindowsApps)
cp "/c/Program Files/WindowsApps/TradingView.Desktop_3.2.0.7916_x64__n534cwy3pjxzj/TradingView.exe" \
   "/c/Users/Administrator/AppData/Local/TradingView/TradingView.exe"

# 4. Launch via MCP
mcp_tradingview_tv_launch(kill_existing=true, port=9222)
# → success, pid=21200, cdp_port=9222
```

## Recovery After Crashes

If TV crashes during use (e.g., after `tab_new` when chart isn't fully loaded):

1. Wait for port 9222 connections to reach TIME_WAIT state
2. Re-launch with `tv_launch(kill_existing=true)`
3. Wait 30-45 seconds for full chart load
4. Call `tab_switch(index=0)` to activate the chart tab
5. Verify with `tv_health_check` → `api_available: true`

## CDP Target Selection

After a fresh launch, the MCP server may connect to a tooltip page or welcome dialog instead of the chart webview. The symptom is:

```
JS evaluation error: TypeError: Cannot read properties of undefined (reading '_activeChartWidgetWV')
```

Fix: Call `tab_switch(index=0)` — this activates the chart tab as the active CDP target. Then wait for `api_available: true` before calling chart APIs.

## Dialog Dismissal

On first launch the app may show a "知道了" (Got it) dialog. Click it:
```
mcp_tradingview_ui_mouse_click(x=461, y=229)
```

## Verification

```json
// tv_health_check response after successful launch
{
  "cdp_connected": true,
  "target_url": "https://cn.tradingview.com/chart/<CHART_ID>/",
  "chart_symbol": "BINANCE:BTCUSDT.P",
  "chart_resolution": "15",
  "api_available": true
}
```

## AUMID (Windows Store Package)

For reference — the App User Model ID for this TV installation:
- Package Family Name: `TradingView.Desktop_n534cwy3pjxzj`
- App ID: `TradingView.Desktop`
- AUMID: `TradingView.Desktop_n534cwy3pjxzj!TradingView.Desktop`
- Launch via: `start shell:AppsFolder\TradingView.Desktop_n534cwy3pjxzj!TradingView.Desktop` (no CDP args)
