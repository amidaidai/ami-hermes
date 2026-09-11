# TradingView Desktop Windows MSIX CDP Launch

Use this when TradingView Desktop is installed as a Windows Store/MSIX app and MCP cannot connect because port `9222` never opens.

## Symptom

- `tv_launch` reports TradingView not found or starts nothing useful.
- Directly starting `TradingView.exe --remote-debugging-port=9222` does not expose `http://127.0.0.1:9222/json/version`.
- Launching through `explorer.exe shell:AppsFolder\\TradingView.Desktop_n534cwy3pjxzj!TradingView.Desktop` starts TradingView, but CDP remains closed.

## Working Pattern

Use Windows `IApplicationActivationManager.ActivateApplication` and pass the debug args directly to the MSIX app activation call.

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

If using a different package family, discover it with:

```powershell
Get-AppxPackage *TradingView* | Select-Object Name,PackageFamilyName,PackageFullName,InstallLocation
```

Then use `<PackageFamilyName>!TradingView.Desktop` as the app id if the package family differs.

## Verification

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 5
```

A successful response includes `Browser`, `Protocol-Version`, `User-Agent`, and `webSocketDebuggerUrl`. After that, `tv_health_check` should report `cdp_connected: true` and the current chart symbol/timeframe.

## Pitfalls

- Do not save the lesson as "MSIX cannot expose CDP"; the COM activation path can expose CDP.
- Avoid naming a PowerShell variable `$pid`; it conflicts with the built-in read-only `$PID` variable.
- If a quick script defines COM classes directly in PowerShell, put them inside a public wrapper class; otherwise casting can fail with non-public generated types.
