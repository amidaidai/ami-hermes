#!/usr/bin/env python3
"""Wrapper for TV data bridge — runs fetch_tv_data.cjs + TV CLI tables capture."""
import subprocess, sys, os, json
from pathlib import Path

DIR = Path(__file__).resolve().parent
TV_DIR = DIR.parent / "tools" / "tradingview-mcp"
BRIDGE_SCRIPT = TV_DIR / "fetch_tv_data.cjs"
TV_CLI = TV_DIR / "src" / "cli" / "index.js"

DATA_DIR = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
OUTPUT_FILE = DATA_DIR / "BTCUSDT.P_tv_data.json"

# Step 1: Run main bridge
if BRIDGE_SCRIPT.exists():
    result = subprocess.run(
        ["node", str(BRIDGE_SCRIPT), "BINANCE:BTCUSDT.P"],
        cwd=str(TV_DIR), capture_output=True, text=True, timeout=50
    )

# Step 2: Get decision table from TV CLI
try:
    result2 = subprocess.run(
        ["node", str(TV_CLI), "data", "tables", "--study", "SVP"],
        cwd=str(TV_DIR), capture_output=True, text=True, timeout=15
    )
    if result2.returncode == 0 and result2.stdout:
        table_data = json.loads(result2.stdout)
        for study in table_data.get("studies", []):
            if "SVP" in study.get("name", ""):
                for table in study.get("tables", []):
                    for row in table.get("rows", []):
                        parts = row.split("|")
                        if parts[0].strip() == "等级" and len(parts) > 1:
                            # Merge into existing data file
                            if OUTPUT_FILE.exists():
                                try:
                                    existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
                                    existing["tv_grade"] = parts[1].strip()
                                    # Also get treatment
                                    for r2 in table.get("rows", []):
                                        p2 = r2.split("|")
                                        if p2[0].strip() == "处理" and len(p2) > 1:
                                            existing["tv_treatment"] = p2[1].strip()
                                    OUTPUT_FILE.write_text(
                                        json.dumps(existing, indent=2, ensure_ascii=False),
                                        encoding="utf-8"
                                    )
                                    break
                                except: pass
except Exception as e:
    # Non-critical — data file already has VWAP/EMA/CVD from bridge
    pass

# Verify output exists
if OUTPUT_FILE.exists():
    sys.exit(0)

sys.stdout.write("ERROR: no output file")
sys.exit(1)
