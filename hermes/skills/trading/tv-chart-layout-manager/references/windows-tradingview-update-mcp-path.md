# Windows TradingView 更新与 MCP 启动路径闭环

## 触发场景

用户要求“更新 TradingView 应用程序 / 更新 TV CDP”、TV Desktop 版本落后、或 TradingView MCP `tv_launch` 启动后仍显示旧版 `TVDesktop/x.y.z`。

## 关键发现：Windows 双路径

| 路径 | 作用 |
|:--|:--|
| `C:\Program Files\WindowsApps\TradingView.Desktop_<version>_x64__<hash>` | 官方 MSIX / Microsoft Store 安装位（**Store 会自动更新它**） |
| `C:\Users\Administrator\AppData\Local\TradingView\TradingView.exe` | TV MCP `tv_launch` / `launch_tv_debug.bat` 的**实际启动位** |

**两个位置互不同步。** MSIX/Store 更新只动第一条路径，而启动链路只认第二条 → 典型症状：

```
Get-AppxPackage *TradingView*  → 3.4.1.8194   （软件"已更新"）
curl /json/version             → TVDesktop/3.3.0（实际在跑旧版）
```

2026-07-03 首次踩到（3.2.0 → 3.3.0），2026-09-13 复现（3.3.0 → 3.4.1：Store 已于 9-10 静默升到 3.4.1，本地副本停在 7 月的 3.3.0）。

## 已固化的自动闭环（2026-09-13）

新增 `scripts/tv_sync_appdir.py`，比对两条路径的 `AppxManifest.xml` → `Identity Version`：

- Store 版本更高（或本地无副本）→ `taskkill` + `robocopy /MIR` 全量同步（Electron 跨大版本**必须全量**，只换 exe 会因 dll/pak 版本不匹配而崩）
- 版本已一致 → 直接返回，**零副作用**（不杀进程、不落盘）
- 找不到 WindowsApps 包（只有便携副本的机器）→ 静默跳过

已接入两个入口，正常情况下**不需要手工操作**：

| 入口 | 位置 | 触发时机 |
|:--|:--|:--|
| `launch_tv_debug.bat` | `tools/tradingview-mcp/scripts/` | 每次启动 TV 前 |
| `scripts/tv_keepalive.py` | cron 每 10 分钟 | 仅当 9222 未开时执行 |

手工调用：

```bash
python scripts/tv_sync_appdir.py                 # 一致则静默、落后则同步
python scripts/tv_sync_appdir.py --kill          # 同步前先清场（文件被占用时必须）
python scripts/tv_sync_appdir.py --dry-run       # 只报告
python scripts/tv_sync_appdir.py --json          # 机读
```

## 标准流程（手工兜底）

1. 确认 Store 包版本与本地副本版本：
   ```bash
   powershell -NoProfile -Command "Get-AppxPackage *TradingView* | Select-Object Name,Version,InstallLocation"
   grep -oE '<Identity[^>]*>' "/c/Users/Administrator/AppData/Local/TradingView/AppxManifest.xml"
   ```
2. 备份本地启动目录（数百 MB，建议放 `backups/`）：
   ```bash
   robocopy "C:\Users\Administrator\AppData\Local\TradingView" \
            "D:\Hermes agent\backups\tradingview-local-<oldver>-<date>" /E /NFL /NDL /NJH /NJS
   ```
3. 同步（脚本会自己 taskkill + robocopy）：
   ```bash
   python scripts/tv_sync_appdir.py --kill
   ```
4. 启动：`cmd /c launch_tv_debug.bat 9222`（或 MCP `tv_launch(kill_existing=true, port=9222)`）。
5. 验证：
   ```bash
   curl -s --noproxy "*" http://127.0.0.1:9222/json/version
   ```
   必须含 `TVDesktop/<new version>`。
6. **跨 Electron 大版本必须做一次回归**（3.3.0/Electron 38 → 3.4.1/Electron 41 实测通过）：
   - `tv_health_check` → `cdp_connected=true` + `api_available=true`
   - `chart_get_state` → 主指标 SVP + 副指标 AggVol 都在 studies 列表
   - `quote_get` → 现价可取
   - `python scripts/tv_screenshot.py BTCUSDT` → 出图，且**肉眼看图**确认 K 线、SVP 价值区、CVD/AggVol 窗格都渲染正常
   - `python scripts/tv_live_dump.py --symbol BTCUSDT` → 缓存刷新且跨源校验 `status=live`

## Pitfalls

- 不要只看 WindowsApps 已更新就结束；启动链路可能仍指向 AppData Local 旧版。**唯一可信证据是 `/json/version` 里的 `TVDesktop/<ver>`。**
- **不要**直接运行 WindowsApps 下 exe 并传 `--remote-debugging-port`；实测报 `bad option` 或缺少 package identity。必须同步到 AppData Local 再启动。
- **`launch_tv_debug.bat` 的 CDP 就绪探测必须 `curl --noproxy "*"`**：本机存在 `HTTP_PROXY/HTTPS_PROXY` 时，curl 访问 `localhost:9222` 会走代理而失败，旧版 bat 的 `goto check` 会**无限循环**（2026-09-13 实测挂死 7 分钟被工具超时掐断，而 TV 其实早已就绪）。现已加 `--noproxy "*" --max-time 5` + 30 次重试上限。
- `tv_keepalive.py` 等待 CDP 的上限已从 20s 提到 90s：全量同步（数百 MB）+ TV 冷启动可能超过 1 分钟，等待太短会误记"拉起失败"冷却 30 分钟。
- `python` 在 cmd/Hermes 终端环境可用（Hermes venv 3.11，已在 PATH），bat 里可直接调用。
- 更新后若 BTC 关键位同步仍失败，先区分 TV CDP 与外部行情接口；CDP 正常后再查 Binance/网络 fallback。

## 实测证据（2026-09-13）

| 项 | 值 |
|:--|:--|
| Store 包 | `TradingView.Desktop_3.4.1.8194_x64__n534cwy3pjxzj` |
| 升级前 CDP | `Chrome/140.0.7339.133 … TVDesktop/3.3.0`（Electron 38.2.2） |
| 升级后 CDP | `Chrome/146.0.7680.216 … TVDesktop/3.4.1`（Electron 41.7.1） |
| 回归 | 主指标 SVP+ICT+VWAP+CVD ✅、副指标 AggVol ✅、quote ✅、截图 ✅、缓存跨源 `live` ✅ |
| 闭环演练 | 伪造本地版本为 3.3.0 + 关闭 TV → `tv_keepalive.py` 4.5s 内自动同步并拉起 3.4.1（`outputs/tv_upgrade_20260913/replay_result.txt`） |
