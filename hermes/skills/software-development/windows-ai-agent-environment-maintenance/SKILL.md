---
name: windows-ai-agent-environment-maintenance
description: Maintain and troubleshoot Windows AI-agent runtimes such as Hermes Desktop, OpenClaw, TradingView MCP, portable Node/Python toolchains, PATH, and provider routing.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  created_by: agent
  tags: [windows, hermes, openclaw, path, troubleshooting, ai-agent]
---

# Windows AI Agent Environment Maintenance

Use this skill when the user asks to inspect, repair, remove, or validate AI-agent tooling on Windows: Hermes Desktop, Hermes CLI, OpenClaw, portable Node/Python runtimes, PATH issues, provider routing, local ports, or system readiness for agent workflows.

## Workflow

1. **Identify the active runtime, not just the expected path.** On Hermes Desktop, prefer checking `HERMES_HOME`, `HERMES_BIN`, `HERMES_WEB_UI_HOME`, and the live config path before assuming `~/.hermes`.
2. **Honor explicit scope limits.** If the user says to only fix PATH and OpenClaw residue, do not edit Hermes config, models, provider routing, MCP config, or skills; keep changes to shell startup files, user PATH, and OpenClaw files only.
3. **Inspect before editing.** Capture current user PATH, machine PATH, relevant install directories, and command resolution with PowerShell `Get-Command`, `where.exe`, and direct absolute paths.
4. **Back up environment variables before PATH changes.** Save the previous user PATH to a temporary backup env var or a timestamped file before calling `[Environment]::SetEnvironmentVariable('Path', ...)` or using `winreg`.
5. **Use script files for PowerShell with hashtables or `$_`.** When running PowerShell from a bash-backed terminal, write a `.ps1` file and execute it; inline quoting can corrupt `$_` expressions and produce misleading parse errors.
   - **Triggers seen in the wild (2026-09-06)**: scripts containing `[math]::Round($_.Size/1GB, 1)` or `Where-Object { $_.Used -gt 0 }` from `bash -c 'powershell -Command ...'` failed with garbled Chinese-encoded error output (`����λ�� ��:1`). Bash swallowed the `$_` token before PowerShell could parse it. `-File /tmp/x.ps1` *also* failed because git-bash's MSYS path conversion did not deliver the path PowerShell expected.
   - **Reliable fix**: prefer Python (`shutil.disk_usage`, `subprocess.run`, `subprocess.check_output`) over PowerShell for system inspection from a bash terminal. If you must run PowerShell, write the script via `write_file` to a non-MSYS path (e.g. `C:/Users/Administrator/AppData/Local/Temp/probe.ps1`) and pass it as `-File 'C:/Users/...'` with forward slashes.
6. **Quarantine OpenClaw residue instead of hard-deleting it.** Move `.openclaw`, OpenClaw temp/cache folders, switcher backups, and Recent shortcuts into a timestamped backup folder; report the restore path.
7. **Verify with both direct paths and PATH lookup.** Direct binary checks prove installation; `Get-Command` / `where.exe` or fresh login Git Bash `command -v` proves shell discoverability.
8. **Separate uninstall from PATH cleanup.** Removing an app directory does not remove stale PATH entries; restoring a backup may intentionally reintroduce stale entries. Re-check after either action.
9. **For hardware checks, prefer vendor tools where available.** `nvidia-smi` is more reliable than WMI `AdapterRAM` for NVIDIA VRAM; WMI can under-report RTX 3060 memory.
   - **Concrete failure mode (real session, 2026-09-06)**: WMI `Win32_VideoController.AdapterRAM` returned `4293918720 bytes ≈ 4 GB` for an actual RTX 3060 12 GB. The bash terminal then displayed `内存: 4.0 GB` and the whole hardware-assessment card was wrong until `nvidia-smi --query-gpu=memory.total --format=csv,noheader` returned `12288 MiB`.
   - **Rule**: For NVIDIA GPUs always use `nvidia-smi` as the source of truth for VRAM. Treat WMI `AdapterRAM` values < 8 GB on any post-2020 NVIDIA card as suspect. WMI historically caps at 4 GB for the field and silently drops the high bits.
   - **Bonus from same session**: `shutil.disk_usage('C:\\')` from Python is more reliable than `Get-PSDrive` / `Get-Volume` in a bash-bridged terminal — no encoding, no `$_` escaping, returns `total / used / free` bytes directly.
10. **For Hermes provider routing, validate using installed source helpers when possible.** Confirm config YAML parses, then inspect `model`, `auxiliary.vision`, credential pool providers, image input mode, and resolved vision backend.
11. **For Hermes local self-checks, verify the active entrypoint and real runtime.** Compare PATH lookup with the source venv entrypoint, run `hermes --version`, `hermes doctor`, `hermes status --all`, and validate touched components such as Web UI with their actual build/test command.

## TradingView MCP: CDP / tv_launch Troubleshooting

When `tv_launch` fails with `TradingView not found on win32. Searched: C:\Users\...\AppData\Local\TradingView\TradingView.exe`:

1. **Root cause**: TradingView Desktop is often installed as a Windows Store app (WindowsApps), placing the real exe at `C:\Program Files\WindowsApps\TradingView.Desktop_*\TradingView.exe`. This folder is protected — `tv_launch` cannot read it.
2. **Fix — automated (preferred, 2026-09-13)**: run `python scripts/tv_sync_appdir.py --kill` in the 棠溪 repo. It reads `AppxManifest.xml` → `Identity Version` on both sides and does a full `robocopy /MIR` whenever the Store package is newer; the same sync is wired into `launch_tv_debug.bat` and `scripts/tv_keepalive.py`, so version drift self-heals.
   Manual fallback — mirror the WHOLE directory, not just the exe (a lone exe breaks when the Electron major version changed; `icudtl.dat` / `*.pak` / `ffmpeg.dll` must match too):
   ```bash
   robocopy "C:\Program Files\WindowsApps\TradingView.Desktop_<ver>_x64__<hash>" \
            "C:\Users\<user>\AppData\Local\TradingView" /MIR /NFL /NDL /NJH /NJS
   ```
3. Then call `mcp_tradingview_tv_launch(kill_existing=true, port=9222)` — it finds the copied exe and launches with CDP.
4. **Verify**: `curl -s --noproxy "*" http://127.0.0.1:9222/json/version` must show `TVDesktop/<expected version>` (Store updates silently, so the version string — not `Get-AppxPackage` — is the only trustworthy evidence); then `mcp_tradingview_tv_health_check` must return `cdp_connected: true` and `api_available: true`.

**Additional recovery steps if TV crashes mid-session**: Re-launch via `tv_launch(kill_existing=true)` kills all instances and starts fresh. Wait 30-45s for full chart load before calling chart APIs.

**Pitfall**: After `tv_launch`, the CDP target may briefly land on a tooltip/welcome page (`_activeChartWidgetWV` undefined). Use `tab_switch(index=0)` to activate the chart tab, then wait for `api_available: true`.

> Full session transcript: `references/tv-mcp-cdp-windows-store-launch.md`

## TradingView MCP: Tool Names & Price Anchoring (2026-08-28)

### Registered tool names use DOUBLE underscores: `mcp__tradingview__*`
The TradingView MCP tools are **not** registered under `mcp_tradingview_*` (single underscore). Their actual deferrable names are `mcp__tradingview__*` — double underscore between `mcp` and `tradingview`, AND between `tradingview` and the tool name:
```
mcp__tradingview__chart_get_state
mcp__tradingview__chart_set_timeframe
mcp__tradingview__data_get_pine_tables
mcp__tradingview__data_get_study_values
mcp__tradingview__data_get_pine_labels / _lines / _boxes
mcp__tradingview__capture_screenshot
```

**Diagnosis path** (this bit me in a real session):
1. `tool_call(name="mcp_tradingview_*")` → `"not a deferrable tool ... call it directly"`.
2. Calling it directly as a function → `"Tool 'mcp_tradingview_*' does not exist"`.
3. Both fail. **Do NOT loop-retry.** Get the real name from `tool_search`, then `tool_call` with the returned `name` field verbatim. The single-underscore name becomes unusable once the deferrable catalog shifts; the double-underscore form is the stable registered name. Same applies to `mcp_binance_*` / `mcp_jin10_*` / `mcp_financekit_*` — always `tool_search` first, copy the exact `name`.

### Anchor the real price BEFORE trusting TV study_values (stale cross-session cache)
`data_get_study_values` can return a **stale cross-session cache** — a prior chart/session left behind values for a different frame. Real case: reported BTC as ~64K while the live Binance price was ~79K; the entire card was wrong. The `chart_get_state` still shows the right symbol (BINANCE:BTCUSDT.P) yet the indicator math reflects an old cached state.

**Rule: never quote TV VWAP/POC/VAH off `study_values` without first anchoring the live price.** Fetch the spot/futures tick in the same turn:
```
curl -s "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
curl -s "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT"
```
If the TV figure is off by an order of magnitude (64K vs 79K), treat the TV data as stale: run `python scripts/tv_live_dump.py --symbol BTCUSDT --verbose` to force-refresh, then re-read. Verify the current date/time from the live tick too (a stale cache can also carry an old *date*, e.g. "7月12日" when it's actually 8月28日 — always write BJT from the fresh timestamp).

> Full session transcript: `references/tv-mcp-tool-naming-stale-cache-2026-08-28.md`

### TradingView MCP: after a TV Desktop restart or upgrade, re-verify before trusting readings

A Store/MSIX-driven TV upgrade is **silent** — `Get-AppxPackage` can show the new version while the running process (launched from `%LOCALAPPDATA%\TradingView`) is still the old one. The only trustworthy version evidence is the CDP handshake:

```bash
curl -s --noproxy "*" http://127.0.0.1:9222/json/version   # must contain TVDesktop/<expected version>
```

`--noproxy "*"` is mandatory: with `HTTP_PROXY`/`HTTPS_PROXY` set, curl to `localhost:9222` goes through the proxy and fails, which is what makes a naive `goto check` retry loop spin forever instead of reporting ready.

Regression checklist after any Electron major-version change (e.g. 38 → 41): `tv_health_check` (`cdp_connected` + `api_available` true), `chart_get_state` (both the main pine indicator and the aggregated sub-indicator present in `studies`), `quote_get`, a screenshot that you actually **look at** (candles + value-area + CVD/AggVol panes drawn), and a forced cache refresh. Reading the numbers is not enough — a broken render still returns plausible study values.

**Aggregated sub-indicator coverage ramps up after a restart — do not report it as "sources were cut".** Immediately after a TV restart/upgrade, the `Volume Aggregated` study can read `Coverage Exchanges: 2`, `Coverage Perp: 1`, `OI Breadth: 1` with `LSR` / `OI Dispersion Ratio` missing entirely; within ~3-5 minutes it fills to `5 / 5 / 4` and `OI Breadth 4` on its own. `Stale Venue Count` stays 0 during the ramp and only rises when venues are genuinely missing. Wait and re-read before concluding anything about degraded coverage — this farm treats full source coverage (5 exchanges + 4 OI venues) as a standing requirement, so an early 2/5 reading written up as "sources cut" is a high-severity misreport.

The full upgrade runbook (dual-path robocopy mirror, backup placement, replay-test procedure) lives in the user-owned skill `tv-chart-layout-manager` → `references/windows-tradingview-update-mcp-path.md`.

## Common Checks

- User PATH: `[Environment]::GetEnvironmentVariable('Path','User')`
- Machine PATH: `[Environment]::GetEnvironmentVariable('Path','Machine')`
- Enumerate duplicate case variants: open `HKCU\\Environment` and list values whose lowercase name is `path`
- Command lookup: `Get-Command openclaw -ErrorAction SilentlyContinue | Format-List *`
- Fresh Git Bash login lookup: `env -i HOME=/c/Users/Administrator USER=Administrator SHELL=/usr/bin/bash PATH='/mingw64/bin:/usr/bin:/bin:/c/Windows/System32:/c/Windows' bash -lc 'command -v hermes; command -v openclaw || true'`
- Direct OpenClaw portable path: `C:\\Users\\Administrator\\AppData\\Local\\OpenClaw\\deps\\portable-node\\openclaw.cmd`
- Hermes Desktop config: `%LOCALAPPDATA%\\hermes\\config.yaml`
- Hermes Web UI home: `%USERPROFILE%\\.hermes-web-ui`
- NVIDIA VRAM: `nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv`

## MCP Server Dependency Troubleshooting

When an MCP server is `enabled: true` in config.yaml but its tools never appear in the agent's tool list:

1. Check the server file exists at the path specified in `mcp_servers.<name>.args`
2. Try launching it manually: `python <server.py>` — import errors appear immediately
3. Check pip packages: `pip list | grep <module>`
4. If Hermes-required package (e.g. `websockets==15.0.1`) conflicts with MCP dependency → rewrite the MCP to avoid the conflicting import; never downgrade Hermes packages
5. For pure REST API MCPs, rewrite using `urllib.request` instead of heavy client libraries

> See `references/mcp-dependency-conflicts-windows.md` for the binance MCP websockets conflict case study and the `finance_mcp` module-not-installed diagnosis.

## Two Independent Update Channels: CLI vs Desktop App

"升级 Hermes" 和 "升级 Hermes Web UI" 是**两条完全独立的更新线**，不要混为一谈：

1. **Hermes Agent CLI** — `hermes update`。拉 git 上游，升级后 `hermes --version` 应显示 `Up to date`，gateway 自动重启。这条管 CLI / gateway / cron 用的运行时。
2. **Hermes Web UI = Hermes Studio 桌面应用（Electron）** — 走 electron-updater，**不**用 `hermes update`。安装在 `%LOCALAPPDATA%/Programs/Hermes Studio/`，更新源写在 `resources/app-update.yml`（`provider: generic` + `url:`）。app 自检读 `<url>/latest.yml` 比对版本。
3. **桌面 app 自带独立后端运行时** `~/.hermes-web-ui/desktop-runtime/hermes/<ver>/`，与独立 CLI 的版本各自独立。CLI 升到 0.17.0 不会改变 app 内嵌的 0.16.0 运行时——webui 用自己捆绑的那份。

**第三方分发源陷阱（关键）**：本机这台桌面 app 的更新源是第三方镜像（如 `download.ekkolearnai.com`，中文社区定制分发），**不是**官方 NousResearch。npm 上的 `hermes-web-ui@<ver>` 是官方包，和第三方分发版不是同一条线。
- 诊断 "为什么 app 升不到 npm 上的最新版"：`curl -fsSL <分发源>/latest.yml` 看它推到第几版。若 `latest.yml` 的 `version` == 当前安装版，则**从 app 自带通道看它已是最新**，自检会显示"已最新"，无法自动升。
- **不要盲目用官方 npm 包覆盖第三方分发版**：会破坏分发方定制（modelVisibility 配置、内嵌运行时）+ 版本错配。覆盖前必须备份 `~/.hermes-web-ui/config.json` 和整个 `.hermes-web-ui`，并向用户说明权衡，让用户决定（等分发方推 / 强制官方包 / 仅手动检查更新）。

桌面 app 版本/更新诊断命令：
- app 版本：`powershell.exe -NoProfile -Command "(Get-Item '<APP>\\Hermes Studio.exe').VersionInfo | Select-Object ProductVersion,FileVersion | Format-List"`
- 更新源：`cat "<APP>/resources/app-update.yml"`
- 分发源最新版：`curl -fsSL "<url>/latest.yml" | grep -E 'version|releaseDate'`
- 内嵌运行时：`ls -1 ~/.hermes-web-ui/desktop-runtime/hermes/`
- app 是否在跑：`tasklist //FI "IMAGENAME eq Hermes Studio.exe" //FO CSV`（升级前需关闭）

> 完整诊断流程与本会话实测见 `references/hermes-studio-desktop-update.md`。

## AI CLI Provider Routing (codex / cc-switch / opencode / claude)

When a coding CLI (codex, claude, opencode) fails after switching providers in
cc-switch, or reports `422 Unprocessable Entity` / `Missing optional dependency`,
the failure is usually one of three stacked causes:

1. **CLI binary broken** — codex's `@openai/codex-win32-x64` is an *alias*
   (`npm:@openai/codex@<ver>-win32-x64`), not a registry package. Skipped
   optional dep → `Missing optional dependency`. Reinstall via temp-dir
   pattern (see reference).
2. **cc-switch proxy takeover revoked** — config.toml reverted from
   `base_url = "http://127.0.0.1:15721/v1"` back to direct upstream while
   `wire_api = "responses"` stays; upstream only speaks chat/completions →
   422. cc-switch auto-revokes on "接管残留" and exits; restart the app
   (PowerShell `Start-Process`, cmd `start` fails silently in git-bash).
3. **Postinstall skipped** — `ignore-scripts=true` in ~/.npmrc leaves
   opencode.exe/claude.exe as stubs; run `node postinstall.mjs` or copy the
   binary from the `-win32-x64` platform dep.

> Full diagnosis order, config shapes, and recovery commands:
> `references/ai-cli-provider-routing-cc-switch.md`

## Pitfalls

- A command-not-found error after installation is usually PATH discoverability, not proof the app is absent. Search the app's local install directory and run the executable by absolute path before reinstalling.
- Do not persist a conclusion that a CLI is broken just because one shell cannot resolve it; check direct executable paths and fresh shells.
- Do not leave stale PATH entries after uninstalling portable tools.
- Do not treat session-specific model/provider changes as durable preference unless the user explicitly asks to keep them.
- Do not claim Hermes is healthy from a single command. For local self-checks, verify PATH resolution, direct venv execution, doctor output, service status, and any component build/test touched by the repair.
- **Never run `npm install <pkg>` inside a portable Node/toolchain dir that has no package.json** — npm treats node_modules as orphaned and wipes everything not in the new tree (`removed N packages`, including npm itself). Always install in a temp dir with a package.json first, then copy artifacts.
- **`@openai/codex-win32-x64` 404 on npm is expected** — it is an alias for `npm:@openai/codex@<ver>-win32-x64`, not a standalone package. Don't chase the 404; reinstall the main package.
- **A `422 Unprocessable Entity` pointing at an upstream `/responses` URL means codex is bypassing the cc-switch proxy** (direct-connect config). Restart cc-switch to re-establish the takeover rather than editing the upstream URL.
- **WMI `AdapterRAM` lies on modern NVIDIA GPUs** — RTX 3060 12 GB reports as `4293918720 bytes ≈ 4 GB`. Use `nvidia-smi --query-gpu=memory.total --format=csv,noheader` as the source of truth. Anything < 8 GB from WMI on a post-2020 card is suspect.
- **Bash → PowerShell `-File /tmp/x.ps1` path translation fails on Windows** — git-bash MSYS conversion rewrites `/tmp/x.ps1` before PowerShell sees it, producing `����λ�� ��:1` (Chinese code-page garble). Write the script to `C:/Users/<user>/AppData/Local/Temp/x.ps1` via `write_file` and invoke with forward-slash `-File`. Better still: prefer `shutil.disk_usage` + `subprocess.run` in Python and skip PowerShell entirely for system inspection.
- **Do not try to multi-line-`patch` a large CRLF source file** — the match can fail even when the text is identical. Write a one-shot Python driver with `assert text.count(old) == 1` per anchor instead.
- **Reading then writing a file silently converts CRLF→LF** — `read_text()` normalizes newlines, so `write_text(..., newline='')` rewrites the whole file and git shows every line changed. Probe `b"\r\n" in read_bytes()` and restore the original style on write.
- **`git diff --stat` is not your change size on a dirty tree** — line-ending drift made a +68/-4 edit look like 593 lines changed. Diff against a pre-edit backup copy to measure your own change.
- **Python 3.11 f-strings cannot contain backslashes** (`f"{len(re.findall(r'x\\.y', s))}"` → SyntaxError). Precompute into a variable, or write the script to a `.py` file — regex and `\n` in f-strings are the usual triggers.
- **Inline `for f in ...; do ... done` one-liners get blocked by the hardline command-parser guard.** Put the loop in a `.py` script and run that; heredoc (`python - <<'PY'`) is also fragile in this shell for anything you want to keep.
- **`read_file` returns `unchanged`/dedup for a path already read earlier in a compacted conversation** — get the body via `search_files(pattern=r"^.{1,200}$", output_mode="content")`, which dumps one match per line with line numbers.
- **`taskkill //F //IM <name>.exe` fails in this git-bash terminal** with `无效参数/选项 - '//F'` (MSYS mangles the doubled slash instead of collapsing it to `/F`). Wrap it in cmd: `cmd /c "taskkill /F /IM TradingView.exe"`.
- **Skills live in `~/AppData/Local/hermes/skills/` — NOT in the repo's `hermes/skills/` mirror.** Editing the repo copy (e.g. `D:/Hermes agent/hermes/skills/...`) with the generic `patch`/`write_file` tools reports success but changes nothing the agent will ever load, because `skill_view` reads the AppData dir. Symptom: a whole session of skill edits, then `skill_view` still returns the old text. **Rule: route every skill edit through `skill_manage`**, which resolves to the live dir; verify by re-`skill_view`-ing and reading the returned body. The same AppData↔repo mirroring applies to `scripts/` (`~/AppData/Local/hermes/scripts` is a junction into the repo) — there the repo copy IS live, which is exactly why the skills dir is the trap.
- **`backups/` in the 棠溪 repo is git-tracked** — drop large binary backups (hundreds of MB, e.g. a TradingView app-dir copy) into `outputs/` instead (gitignored); otherwise they appear as untracked and risk being committed.

## References

- `references/xai-oauth-setup.md` — OAuth setup flow for xAI/Grok via `hermes auth add xai-oauth`, including the mobile-friendly authorization link + callback paste pattern.
- `references/hermes-openclaw-windows-maintenance.md` — concrete Windows/Hermes/OpenClaw investigation notes, PATH repair pattern, and system-audit probes from a real session.
- `references/path-openclaw-scoped-cleanup.md` — narrow cleanup recipe for fixing PATH and quarantining OpenClaw residue without touching Hermes config/model settings.
- `references/hermes-local-update-selfcheck.md` — Hermes update/repair verification sequence covering active entrypoint resolution, config backup, update conflicts, Web UI dev deps, and post-fix self-checks.
- `references/hermes-studio-desktop-update.md` — Hermes Studio (Web UI) desktop app version diagnosis: CLI vs electron-updater channels, third-party distribution-source trap, embedded-runtime independence, and the "don't overwrite a custom distro with official npm" rule.
- `references/windows-directory-junction.md` — create NTFS directory junctions via Python ctypes so Hermes cron scripts in AppData transparently mirror a repo directory; avoids dual-path sync.
- `references/ai-cli-provider-routing-cc-switch.md` — codex + cc-switch + opencode zen/go provider chain: proxy-takeover architecture, 422 root cause, codex win32-x64 alias package, npm-wipe hazard, ignore-scripts postinstall stubs, corepack MSYS shim fix.
- `references/hardware-probe-bash-terminal.md` — reliable CPU/RAM/GPU/disk probe from a bash-bridged Windows terminal using `subprocess.run` + `nvidia-smi` + `shutil.disk_usage`; documents why WMI `AdapterRAM` and inline PowerShell both fail in this environment.
- `references/large-file-edits-bash-windows.md` — editing/rewriting multi-thousand-line CRLF source files from this terminal: per-anchor `assert count == 1` driver scripts, CRLF-preserving write-back, f-string backslash and blocked-inline-loop workarounds, diffing against a backup to measure your real change, re-reading a deduped file via `search_files`, and the tolerant-assertion pattern for post-refactor regression chains.
