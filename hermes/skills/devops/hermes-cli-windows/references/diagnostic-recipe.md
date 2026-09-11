# Diagnostic recipe — Hermes CLI silent-failure on Windows

Reproduced 2026-07-07. User: Administrator. Shells involved: PowerShell (complaint), git-bash/MSYS (Hermes terminal tool), Windows Terminal.

## Symptom
In PowerShell:
```
PS C:\Users\Administrator> hermes
PS C:\Users\Administrator> hermes --version
PS C:\Users\Administrator>
```
Both return immediately with NO output. `winpty hermes` → "无法将'winpty'项识别为 cmdlet" (winpty not installed).

## Confirm launcher type
```
$ file ~/.local/bin/hermes
# Bourne-Again shell script, ASCII text executable
$ head -3 ~/.local/bin/hermes
# #!/usr/bin/env bash
# # Hermes Git-Bash wrapper: avoid Windows uv trampoline failures from the PE launcher.
# exec python -m hermes_cli.main "$@"
```

## Locate real exe
```
$ ls "$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/" | grep -i hermes
# hermes.exe  hermes-acp.exe  hermes-agent.exe  hermes-feishu-card.exe
```

## READ THE REAL WINDOWS PATH (critical)
`cmd /c "echo %PATH%"` called from git-bash returns BASH's PATH (3 lines, wrong). Use instead:
```
powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('PATH','User') -split ';' | Where-Object { $_ -match 'hermes|local|venv|Scripts' }"
```
Observed User PATH matches:
```
C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts
C:\Users\Administrator\.local\bin
C:\Users\Administrator\AppData\Local\hermes\bin
C:\Users\Administrator\AppData\Local\hermes\node
...
```
Both `~/.local/bin` (bash script) and `venv\Scripts` (exe) are present → Windows matches unextended `hermes` first, can't run it, silent fail.

## Wrong test (do NOT do)
```
python "$HOME/.local/bin/hermes" --version
# File "...hermes", line 3  exec python -m hermes_cli.main "$@"
# SyntaxError: Missing parentheses in call to 'exec'
```
Feeding a bash script to the python interpreter fails. Correct direct form: `python -m hermes_cli.main --version`.

## The fix
Create `C:\Users\Administrator\.local\bin\hermes.cmd`:
```
@echo off
"C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" %*
```
First attempt used `%~dp0..\AppData\Local\...` relative path → PowerShell reported "系统找不到指定的路径". Switched to absolute path → works.

## Verify
```
powershell.exe -NoProfile -Command "hermes --version"
# Hermes Agent v0.18.0 (2026.7.1) · upstream ce038a0e
# Project: C:\Users\Administrator\AppData\Local\hermes\hermes-agent
# Python: 3.11.15  OpenAI SDK: 2.24.0
# Update available: 322 commits behind — run 'hermes update'
```

## Side notes
- `hermes tools | Select-Object -First 3` in PowerShell hung 180s (pipe didn't let process exit). Use `--version` or unfiltered short subcommands for automated checks.
- At fix time the install trailed upstream by 322 commits (v0.18.0, 2026.7.1).
