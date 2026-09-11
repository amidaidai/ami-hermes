# Windows Directory Junction for Hermes Cron Scripts

## Problem

Hermes cron looks for scripts in `%LOCALAPPDATA%/hermes/scripts/`, but users maintain scripts in their project repo (e.g. `D:/Hermes agent/scripts/`). Keeping two copies creates a sync problem — modifying one doesn't update the other.

## Solution: NTFS Directory Junction

A junction makes one directory path transparently point to another at the filesystem level. Both paths read/write the same files.

### Via Python (ctypes)

```python
import os, ctypes

appdata = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'scripts')
target = r'D:\Hermes agent\scripts'

# 1. Delete existing directory (must be empty first)
#    If the directory is locked by a process, delete files individually first:
#    cd appdata && rm -rf *.py *.json __pycache__/

os.rmdir(appdata)  # fails if dir is locked — retry after a few seconds

# 2. Create junction
kernel32 = ctypes.windll.kernel32
CreateSymbolicLinkW = kernel32.CreateSymbolicLinkW
CreateSymbolicLinkW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
CreateSymbolicLinkW.restype = ctypes.c_bool

result = CreateSymbolicLinkW(appdata, target, 0x1)  # 0x1 = directory
if not result:
    raise OSError(ctypes.get_last_error())
```

### Flags

- `0x1` — directory symlink/junction (SYMBOLIC_LINK_FLAG_DIRECTORY)
- `0x2` — allow unprivileged creation (SYMBOLIC_LINK_FLAG_ALLOW_UNPRIVILEGED_CREATE, Windows 10 14972+)

### Pitfalls

1. **Directory must not exist** when creating the junction. If `hermes/scripts/` is locked by a running process (cron, gateway), wait for it to release or kill the process.
2. **`cmd /c mklink` often fails** with garbled errors on Chinese Windows — use Python `ctypes` instead.
3. **PowerShell `New-Item -ItemType Junction` can fail** with path format errors on localized Windows. Python ctypes is more reliable.
4. After junction creation, **both paths are identical** — deleting files from one path deletes them from the other. The junction itself survives reboots.
5. To verify: `ls %LOCALAPPDATA%/hermes/scripts/` should show the same files as `ls /d/Hermes\ agent/scripts/`.

## When to Use

- Hermes cron scripts maintained in a git repo but executed from AppData
- Any situation where two Windows paths should transparently share the same directory
- Avoids dual-path sync scripts, cron-based copy jobs, or manual `cp` after every edit
