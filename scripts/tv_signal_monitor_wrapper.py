#!/usr/bin/env python3
"""TV信号监控 cron wrapper — 调用 hermes/scripts/tv_signal_monitor.py"""
import subprocess, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "hermes" / "scripts" / "tv_signal_monitor.py"

if not SCRIPT.exists():
    print(f"ERROR: {SCRIPT} not found")
    sys.exit(1)

# Pass all arguments through
cp = subprocess.run(
    [sys.executable, str(SCRIPT)] + sys.argv[1:],
    cwd=str(ROOT),
    capture_output=True, text=True, timeout=30
)
print(cp.stdout)
if cp.stderr:
    print(cp.stderr, file=sys.stderr)
sys.exit(cp.returncode)
