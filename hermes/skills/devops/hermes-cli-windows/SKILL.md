---
name: hermes-cli-windows
description: Troubleshoot and fix Hermes CLI launcher invocation failures on Windows across PowerShell, CMD, and git-bash/MSYS. Covers the bash-script-launcher + PATHEXT silent-failure problem, the hermes.cmd shim fix, reading the REAL Windows PATH from git-bash, and verifying the fix.
---

# hermes-cli-windows

Fix Hermes CLI launcher (`hermes`) not responding / silently failing in PowerShell or CMD on Windows. Also covers reliable invocation of `hermes` subcommands and the terminal TUI from any Windows shell.

## When to use
- User reports `hermes` "does nothing", "no response", "hangs", or "silently fails" in PowerShell/CMD (but it may work in git-bash).
- User asks why `hermes` works in one shell but not another.
- You must invoke `hermes` subcommands (`config`, `tools`, `update`, `cron`) from PowerShell/CMD reliably.
- After `hermes update`, CLI entry points behave differently than before.

## Core mental model
On Windows the `hermes` launcher installed to `~/.local/bin/hermes` (i.e. `C:\Users\<user>\.local\bin\hermes`) is a **bash script**, shebang `#!/usr/bin/env bash`, body exactly:
```bash
exec python -m hermes_cli.main "$@"
```
- **git-bash / MSYS / WSL**: reads the shebang, executes it → `hermes` works.
- **PowerShell / CMD**: does NOT read bash shebangs. Windows uses `PATHEXT` (default `.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC`) to decide executability. An unextended file named `hermes` is **NOT** covered → Windows silently skips it with NO output and returns straight to the prompt. That is the "no response" the user sees.

The REAL Windows executable is `hermes.exe` at:
`C:\Users\<user>\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe`
(also mirrored under `...\Roaming\cn.org.hermesagent.desktop\runtime\hermes-home\hermes-agent\venv\Scripts\`).

Note: PATH usually contains BOTH `~/.local/bin` (the bash script) and `...\venv\Scripts` (the exe). Windows PATH lookup tries PATHEXT extensions in order and matches the unextended `hermes` script first but cannot run it → silent fail. The `.cmd` shim below takes priority over the unextended script.

## Diagnostic recipe (run from the git-bash terminal tool)
1. Confirm the launcher is a bash script:
   `file ~/.local/bin/hermes` → "Bourne-Again shell script, ASCII text executable"
   `head -3 ~/.local/bin/hermes`
2. Locate the real executable:
   `ls "$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/" | grep -i hermes`
3. **Read the REAL Windows PATH** — do NOT use `cmd /c "echo %PATH%"`. When called from git-bash that returns bash's PATH, NOT PowerShell's. Use:
   `powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('PATH','User') -split ';'"`
   `powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('PATH','Machine') -split ';'"`
   Filter with `| Where-Object { $_ -match 'hermes|local|venv|Scripts' }` if needed.
4. Reproduce the failure from PowerShell's perspective:
   `powershell.exe -NoProfile -Command "hermes --version"` → expect empty/error BEFORE the fix.

## The fix: add a `.cmd` shim
Create `C:\Users\<user>\.local\bin\hermes.cmd` pointing at the real exe. Windows always treats `.cmd` as executable and **prioritizes `.cmd` over the unextended `hermes` script** during PATH lookup, so both PowerShell/CMD and git-bash work (git-bash still uses the bash script; no conflict).

```
@echo off
"C:\Users\<user>\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" %*
```

### Pitfalls when writing the shim
- **Use ABSOLUTE paths.** Relative `%~dp0..\<relpath>` style FAILS inside the PowerShell→cmd call chain ("系统找不到指定的路径" / "The system cannot find the path specified"). Hard-code the full absolute exe path in the shim.
- `.cmd` is standard and fine; avoid creating both `hermes.cmd` AND `hermes.bat` to prevent ambiguity.
- Put it in a directory already on the Windows PATH (`~/.local/bin` is, per step 3 above). No PATH edit needed.
- Do not try `python "$HOME/.local/bin/hermes"` to test — that feeds a bash script to the python interpreter and throws `SyntaxError: Missing parentheses in call to 'exec'`. The correct direct invocation is `python -m hermes_cli.main`.

## Verification
```
powershell.exe -NoProfile -Command "hermes --version"
```
Expect: `Hermes Agent vX.Y.Z (date) · upstream <hash>` plus Project/Python/SDK lines. Then `hermes tools`, `hermes config list`, `hermes update` run normally.

## Notes
- The Hermes desktop GUI already runs independently; the `hermes` CLI is for subcommands (config, tools, update, cron) or the terminal TUI. Daily chat does NOT require launching `hermes`.
- For the interactive TUI under the old Windows PowerShell console, prefer Windows Terminal or git-bash (PTY support); legacy console may render the TUI poorly.
- `python -m hermes_cli.main` is the PowerShell-equivalent direct invocation if the shim is unavailable for any reason.
- `hermes tools` piped through `Select-Object -First N` in PowerShell can hang the pipe (process doesn't exit cleanly); prefer `--version` or unfiltered short subcommands for automated checks.

## References
- `references/diagnostic-recipe.md` — exact commands and observed outputs from the session that produced this skill.
