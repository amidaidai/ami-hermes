# Windows TradingView 更新与 MCP 启动路径闭环

## 触发场景

用户要求“更新 TradingView 应用程序”、TV Desktop 版本落后、或 TradingView MCP `tv_launch` 启动后仍显示旧版 `TVDesktop/x.y.z`。

## 关键发现

Windows 上存在双路径：

| 路径 | 作用 |
|:--|:--|
| `C:\Program Files\WindowsApps\TradingView.Desktop_<version>...` | 官方 MSIX/Appx 安装位置 |
| `C:\Users\Administrator\AppData\Local\TradingView\TradingView.exe` | TradingView MCP `tv_launch` 默认启动位置 |

只执行 `Add-AppxPackage` 可能只更新 WindowsApps 包，而 MCP 仍从 AppData Local 启动旧版。更新完成必须同步本地 MCP 启动目录。

## 标准流程

1. 下载官方 MSIX：
   - 官方页面：`https://www.tradingview.com/desktop/`
   - Windows 包通常为：`https://tvd-packages.tradingview.com/stable/latest/win32/TradingView.msix`
2. 读取 MSIX manifest 验证版本：解压/Zip 读取 `AppxManifest.xml` 的 `Identity Version`。
3. 停止旧进程：`taskkill.exe //F //IM TradingView.exe`。
4. 安装/更新官方包：
   ```powershell
   Add-AppxPackage -Path 'D:\Hermes agent\outputs\TradingView-latest.msix' -ForceUpdateFromAnyVersion
   ```
5. 查询最新 WindowsApps 包：
   ```powershell
   Get-AppxPackage *TradingView* | Select-Object Name,Version,InstallLocation
   ```
6. 备份并同步 MCP 启动目录：
   - 备份 `C:\Users\Administrator\AppData\Local\TradingView` 到带时间戳目录。
   - 将 `InstallLocation` 下所有文件复制到 `C:\Users\Administrator\AppData\Local\TradingView`。
7. 通过 MCP 启动：`mcp_tradingview_tv_launch(kill_existing=true, port=9222)`。
8. 验证：
   - `curl http://127.0.0.1:9222/json/version` 中 `User-Agent` 必须含 `TVDesktop/<new version>`。
   - `mcp_tradingview_tv_health_check()` 必须返回 `cdp_connected=true`、`api_available=true`。
   - 必要时确认 `chart_symbol` 与 `chart_resolution`。

## 验证证据格式

| 项 | 合格证据 |
|:--|:--|
| Appx版本 | `Get-AppxPackage *TradingView*` 显示目标版本 |
| MCP启动版本 | CDP `/json/version` 显示 `TVDesktop/<目标版本>` |
| TV MCP | health check：`cdp_connected=true` + `api_available=true` |
| 交易系统 | `btc_ref_levels_sync.py` 或 `tv_data_bridge.py` 能刷新 TV 缓存 |

## Pitfalls

- 不要只看 WindowsApps 已更新就结束；MCP 可能仍启动 AppData Local 旧版本。
- 不要直接运行 WindowsApps 下 exe 并传 `--remote-debugging-port`；实测可能报 `bad option`。让 MCP 的 `tv_launch` 启动 AppData Local 路径更稳。
- 更新后若 BTC 关键位同步仍失败，先区分 TV CDP 问题和外部行情接口问题；CDP 正常后再查 Binance/网络 fallback。
