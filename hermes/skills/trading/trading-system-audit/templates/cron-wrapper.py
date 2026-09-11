#!/usr/bin/env python3
"""Cron wrapper template — call a script that lives outside the cron Junction directory."""
import subprocess, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "hermes" / "scripts" / "REPLACE_WITH_SCRIPT_NAME.py"

if not SCRIPT.exists():
    print(f"ERROR: {SCRIPT} not found")
    sys.exit(1)

cp = subprocess.run(
    [sys.executable, str(SCRIPT)] + sys.argv[1:],
    cwd=str(ROOT),
    capture_output=True, text=True, timeout=30
)
print(cp.stdout)
if cp.stderr:
    print(cp.stderr, file=sys.stderr)
sys.exit(cp.returncode)
