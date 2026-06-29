#!/usr/bin/env python3
"""Wrapper for TV data bridge — runs fetch_tv_data.cjs and verifies output.

v4.3: The production SVP indicator's action panel (行动格 v2) uses row labels
结论/方向/进场/止损/目标/磁吸↑/磁吸↓ — there is NO 等级/处理 row, and the panel
is drawn via table.new() whose cells live in the CDP `dwgtablecells` collection.
fetch_tv_data.cjs now reads that collection directly and writes tv_grade /
tv_treatment / tv_conclusion / tv_entry / tv_stop / tv_target into the JSON, so
the old separate `tv data tables --study SVP` re-read (which looked for the
non-existent 等级/处理 rows in the wrong collection) has been removed.
"""
import subprocess, sys, os, json
from pathlib import Path

DIR = Path(__file__).resolve().parent
TV_DIR = DIR.parent / "tools" / "tradingview-mcp"
BRIDGE_SCRIPT = TV_DIR / "fetch_tv_data.cjs"

DATA_DIR = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
OUTPUT_FILE = DATA_DIR / "BTCUSDT.P_tv_data.json"

# Run main bridge — it now writes the full action-panel decode into OUTPUT_FILE.
if BRIDGE_SCRIPT.exists():
    result = subprocess.run(
        ["node", str(BRIDGE_SCRIPT), "BINANCE:BTCUSDT.P"],
        cwd=str(TV_DIR), capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        sys.stdout.write("ERROR: bridge failed\n")
        sys.stdout.write((result.stderr or result.stdout or "")[-800:])
        sys.exit(1)

# Verify output exists and carries the action-panel conclusion.
if OUTPUT_FILE.exists():
    try:
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        grade = data.get("tv_grade")
        conc = data.get("tv_conclusion")
        if not conc:
            # Non-fatal: structure/price still present; panel just not captured this tick.
            sys.stdout.write("WARN: tv_conclusion missing (action panel not captured)\n")
        else:
            sys.stdout.write(f"OK grade={grade} conclusion={conc}\n")
    except Exception as e:
        sys.stdout.write(f"WARN: could not re-read output json: {e}\n")
    sys.exit(0)

sys.stdout.write("ERROR: no output file\n")
sys.exit(1)
