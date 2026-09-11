# TradingView MCP Bridge Notes

Use when the user wants the agent to analyze their live TradingView Desktop chart through an MCP server instead of by uploading screenshots or Pine files.

## Candidate Repo

- Repo: `tradesdontlie/tradingview-mcp`
- Purpose: MCP stdio server that connects to TradingView Desktop through Chrome DevTools Protocol (default `localhost:9222`).
- Runtime: Node.js, JavaScript, `@modelcontextprotocol/sdk`, `chrome-remote-interface`.
- Typical Hermes add pattern:

```bash
git clone https://github.com/tradesdontlie/tradingview-mcp.git "D:/Hermes agent/tools/tradingview-mcp"
cd "D:/Hermes agent/tools/tradingview-mcp"
npm install
hermes mcp add tradingview --command node --args "D:/Hermes agent/tools/tradingview-mcp/src/server.js"
```

TradingView Desktop must run with CDP enabled, e.g. the repo's Windows launcher `scripts/launch_tv_debug.bat` or manually with `--remote-debugging-port=9222`.

### Windows MSIX / Microsoft Store Launch Workaround

On Windows Store/MSIX TradingView installs, direct exe args, `shell:AppsFolder`, and `ELECTRON_EXTRA_LAUNCH_ARGS` may start TradingView but leave port `9222` closed. When that happens, use the Windows `IApplicationActivationManager` COM API and pass the debug arguments through `ActivateApplication`.

Known-good PowerShell pattern:

```powershell
$code = @"
using System;
using System.Runtime.InteropServices;

public class Launcher {
  [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IApplicationActivationManager {
    int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId, [MarshalAs(UnmanagedType.LPWStr)] string arguments, uint options, out uint processId);
    int ActivateForFile([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId, IntPtr itemArray, [MarshalAs(UnmanagedType.LPWStr)] string verb, out uint processId);
    int ActivateForProtocol([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId, IntPtr itemArray, out uint processId);
  }

  [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
  class ApplicationActivationManager { }

  public static string Launch(string appId, string args) {
    var manager = (IApplicationActivationManager)new ApplicationActivationManager();
    uint pid;
    int hr = manager.ActivateApplication(appId, args, 0, out pid);
    return "hr=" + hr + " pid=" + pid;
  }
}
"@
Add-Type -TypeDefinition $code
[Launcher]::Launch("TradingView.Desktop_n534cwy3pjxzj!TradingView.Desktop", "--remote-debugging-port=9222 --remote-allow-origins=*")
```

Verify with:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 5
```

If it returns Browser/Protocol/User-Agent JSON, continue with `tv_health_check` and read-only chart analysis.

## Safety Posture

Treat this MCP as useful but not purely read-only by default. It exposes tools that can modify TradingView state.

Recommended default for this user: **read-only analysis mode** unless the user explicitly authorizes chart modification.

Prefer these tools for analysis:

- `tv_health_check`
- `chart_get_state`
- `quote_get`
- `data_get_ohlcv` with `summary: true`
- `data_get_study_values`
- `data_get_pine_lines`
- `data_get_pine_labels`
- `data_get_pine_tables`
- `data_get_pine_boxes`
- `capture_screenshot`
- `pine_analyze`
- `pine_check`

Require explicit confirmation before using tools that write, save, delete, or automate arbitrary UI/JS:

- `ui_evaluate`, `ui_click`, `ui_keyboard`, `ui_type_text`, `ui_mouse_click`
- `alert_create`, `alert_delete`
- `pine_set_source`, `pine_save`, `pine_new`, `pine_open`
- `replay_trade`
- `draw_shape`, `draw_clear`, `draw_remove_one`
- `chart_set_symbol`, `chart_set_timeframe`, `chart_set_type`, `chart_manage_indicator`
- `layout_switch`, `pane_set_layout`, `tab_close`

## Analysis Workflow

1. Verify installation and connection with `hermes mcp list` and `tv_health_check`.
2. Start with `chart_get_state` once; reuse IDs and state instead of repeatedly querying.
3. Pull compact context: `quote_get`, `data_get_ohlcv(summary=true)`, and `data_get_study_values`.
4. For custom Pine dashboards, read visible drawings/tables using `data_get_pine_lines`, `data_get_pine_labels`, `data_get_pine_tables`, and `data_get_pine_boxes`, with `study_filter` whenever possible.
5. Use `capture_screenshot` for visual confirmation and then analyze in the user's preferred execution format: environment, location, event, confirmation, plan, invalidation.
6. Do not chase every available tool. Keep outputs compact and action-focused.

## User-Specific Output Defaults

For TradingView decision support, keep the response practical:

- Short bias: `偏多` / `偏空` / `震荡观望` / `禁追`.
- Explain the current handling: wait, pullback, rejection, reclaim, no-trade.
- Give concrete plan and invalidation levels from chart data when available.
- Mention CVD/volume/structure conflicts explicitly.
- Avoid implying indicator states or scores are win rates.

## Pitfalls

- Do not say "there is no TradingView MCP" after only checking installed MCP servers. Distinguish **installed MCPs** from **available MCP projects** in the user's stars or provided URLs.
- This repo is unofficial and uses undocumented TradingView internals; TradingView updates can break it.
- CDP exposes the logged-in TradingView desktop session. Treat arbitrary page JS execution as high-risk.
- Alert and Pine save tools change cloud/user state; require explicit approval before use.
- Replay trades are simulated, not broker orders, but still modify the replay session and should be user-approved.
