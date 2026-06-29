#!/usr/bin/env python3
"""BTC daemon watchdog — 1m cron, restarts if heartbeat stale >120s"""
import json, os, subprocess, time
from pathlib import Path
from datetime import datetime

DAEMON = "D:/Hermes agent/scripts/btc_daemon.py"
HEARTBEAT = "D:/Hermes agent/data/.btc_daemon_heartbeat.json"
PID_FILE = "D:/Hermes agent/data/.btc_daemon.pid"
WORKDIR = "D:/Hermes agent"


def log(m):
    safe = m.encode("ascii", "replace").decode("ascii")
    print(f"[watchdog] {safe}", flush=True)


# Check heartbeat
hb = None
try:
    with open(HEARTBEAT) as f:
        hb = json.load(f)
except Exception:
    pass

now = time.time()
alive = False

if hb and "ts" in hb:
    try:
        dt = datetime.fromisoformat(hb["ts"])
        age = now - dt.timestamp()
        if age < 120:
            alive = True
            log(f"Daemon alive @ {hb.get('zone','?')}, age={age:.0f}s")
    except Exception as e:
        log(f"hb parse: {e}")

if alive:
    # All good, silent exit
    exit(0)

# Daemon dead — restart
log("Heartbeat stale, restarting daemon...")

# Kill old PID if file exists
try:
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            old = f.read().strip()
        if old.isdigit():
            subprocess.run(["taskkill", "/F", "/PID", old],
                           capture_output=True, timeout=5)
            log(f"Killed old PID {old}")
except Exception as e:
    log(f"kill old: {e}")

# Start new daemon — use start /B (background, same console)
cmd = f'start /B python "{DAEMON}"'
log(f"Running: {cmd}")
subprocess.Popen(
    cmd, shell=True, cwd=WORKDIR,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

print(f"BTC daemon restarted at {time.strftime('%H:%M:%S')}")
