#!/usr/bin/env python3
"""Push BTC analysis card to 386 topic."""
import json, sys, asyncio, os, subprocess
from pathlib import Path

# Run the card generator and capture output
result = subprocess.run(
    [sys.executable, "D:/Hermes agent/scripts/btc_push_cron.py"],
    capture_output=True, text=True, timeout=120
)

if result.returncode != 0:
    print(f"ERROR: card generator failed: {result.stderr[:500]}", flush=True)
    sys.exit(1)

try:
    data = json.loads(result.stdout.strip())
except Exception as e:
    print(f"ERROR: parse output: {e}", flush=True)
    print(f"Output: {result.stdout[:500]}", flush=True)
    sys.exit(1)

card = data.get("card", "")
screenshot = data.get("screenshot", "")

# Build message with media reference
message = card
if screenshot and Path(screenshot).exists():
    message += f"\n\nMEDIA:{screenshot}"

# Push to 386
target = "telegram:-1003733144325:386"
sys.path.insert(0, "D:/Hermes agent/scripts")
from telegram_direct import send_telegram_direct

ok, reason = send_telegram_direct(target, message)
print(f"Push to 386: {'OK' if ok else 'FAIL'} | {reason}", flush=True)
print(f"--- CARD ---\n{card}\n---", flush=True)
