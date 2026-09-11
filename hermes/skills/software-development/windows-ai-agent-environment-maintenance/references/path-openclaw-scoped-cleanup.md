# Scoped PATH + OpenClaw Residue Cleanup

Use this reference when the user asks for a narrow Windows cleanup such as "only fix PATH and OpenClaw residue; do not touch Hermes config/model".

## Scope Contract

Allowed:
- User-level `Path` / shell startup files such as `%USERPROFILE%\.bashrc`.
- OpenClaw runtime leftovers, backups, temp/cache directories, and Recent shortcuts.
- Timestamped backups/quarantine folders under `%LOCALAPPDATA%\Temp`.

Not allowed unless the user explicitly broadens scope:
- Hermes `config.yaml`, `.env`, model/provider/auxiliary settings.
- MCP server config, tool enablement, profile config, or skill library content.
- Destructive deletion of OpenClaw state without a restore path.

## Cleanup Pattern

1. Read current HKCU `Path` and any duplicate case variant such as `PATH`; save both to a timestamped backup.
2. Build a cleaned user PATH by deduping entries, removing OpenClaw/.openclaw entries, and placing the stable Hermes venv before stale desktop `hermes-home` shims when the goal is to fix Hermes CLI resolution.
3. If Git Bash startup prepends an obsolete Hermes path in `.bashrc`, replace only that line and leave unrelated shell setup intact.
4. Move OpenClaw leftovers into a timestamped quarantine directory rather than deleting them:
   - `%USERPROFILE%\.openclaw`
   - `%USERPROFILE%\.cc-switch\backups\openclaw`
   - `%LOCALAPPDATA%\Temp\openclaw`
   - `%LOCALAPPDATA%\Temp\jiti\openclaw`
   - `%LOCALAPPDATA%\Temp\node-compile-cache\openclaw`
   - `%APPDATA%\Microsoft\Windows\Recent\Openclaw.lnk`
5. Verify with a fresh login Git Bash environment, not only the current process PATH:

```bash
env -i HOME=/c/Users/Administrator USER=Administrator SHELL=/usr/bin/bash \
  PATH='/mingw64/bin:/usr/bin:/bin:/c/Windows/System32:/c/Windows' \
  bash -lc 'command -v hermes; command -v openclaw || echo openclaw-not-found; command -v claw || echo claw-not-found'
```

## Verification Checklist

- `command -v hermes` resolves to the intended Hermes venv path.
- `command -v openclaw` and `command -v claw` return not found after cleanup.
- User PATH no longer contains `OpenClaw` or `.openclaw`.
- Registry contains only one user-level PATH value when possible (`Path`, not both `Path` and `PATH`).
- Quarantine manifest lists every moved path and the backup root is included in the final reply.
