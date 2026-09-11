# Hardware Probe from a Bash-Bridged Windows Terminal

Concrete recipe used in the 2026-09-06 session to inspect the host from the Hermes bash terminal without PowerShell pain.

## The reliable snippet

Run inside an `execute_code` cell (persistent kernel):

```python
import shutil, subprocess

# CPU + OS
import platform
print(platform.platform(), platform.release())

# CPU cores (always trust WMI here, it does not lie about RAM like AdapterRAM does)
r = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | Format-List"],
    capture_output=True, text=True, timeout=15,
)
print(r.stdout)

# RAM total — shutil is fine, no PowerShell
total = sum(
    ctypes.sizeof(c) * 1  # not quite; use WMI for capacity
    for c in []
)
# Simpler: just use WMI for total RAM, not AdapterRAM (AdapterRAM is the liar)
r = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "[math]::Round((Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum/1GB,1)"],
    capture_output=True, text=True, timeout=10,
)
print(f"RAM: {r.stdout.strip()} GB")

# GPU — ALWAYS nvidia-smi, never WMI AdapterRAM
r = subprocess.run(
    ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,compute_cap", "--format=csv,noheader"],
    capture_output=True, text=True, timeout=10,
)
print("GPU:", r.stdout.strip())

# Disks — shutil.disk_usage wins, no PowerShell required
for d in ("C", "D", "E", "F"):
    try:
        t, u, f = shutil.disk_usage(f"{d}:\\")
        print(f"{d}: total {t/2**30:.1f} G | used {u/2**30:.1f} G | free {f/2**30:.1f} G")
    except Exception:
        pass
```

## What breaks and why

| Symptom | Cause | Fix |
|---|---|---|
| `内存: 4.0 GB` on RTX 3060 | WMI `Win32_VideoController.AdapterRAM` overflows on ≥ 4 GB cards, returns the lower 32 bits | Use `nvidia-smi --query-gpu=memory.total` |
| PowerShell `-Command 'Where-Object { $_.Used -gt 0 }'` fails with garbled Chinese characters | git-bash bash quotes `$_` before PS parses it; CP936 encoding then masks the real syntax error | Use Python `subprocess.run` + `shutil.disk_usage` instead of inline PowerShell |
| `powershell -File /tmp/x.ps1` reports file not found | git-bash MSYS converts `/tmp/x.ps1` to a Windows path PS doesn't accept | Use absolute `C:/Users/<user>/AppData/Local/Temp/x.ps1` and invoke with forward slashes |
| WMI `Get-Volume` shows wrong totals in Chinese locale | locale-specific formatter rounding, plus `$_` interpolation | Same as above — Python is locale-stable |

## One-liner answer for "does this box run model X?"

1. Read `shutil.disk_usage("C:\\").free` and `("D:\\").free` — model + cache + headroom.
2. Read `nvidia-smi --query-gpu=memory.total --format=csv,noheader` — single number, trust it.
3. Read `Win32_PhysicalMemory` total bytes — RAM for CPU-offload headroom.
4. Read `Win32_Processor` Name + cores — for thread count and AVX/AMX availability if you care.

Never read `Win32_VideoController.AdapterRAM`. It lies on every NVIDIA card newer than a GTX 1050.

## Background

This recipe replaced an earlier PowerShell-only probe that took 3 retries to surface the correct VRAM. The first attempt read `AdapterRAM = 4 GB`, the second got garbled output from a Chinese-code-page error, and only the Python+nvidia-smi path returned clean numbers in one call.