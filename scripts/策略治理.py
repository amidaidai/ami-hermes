#!/usr/bin/env python3
"""策略治理 v1.0 — 统计模型期望值，禁止样本不足自动升权。"""
from __future__ import annotations
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trading_system as ts


def main() -> None:
    ts.ensure_files()
    gov = ts.read_json(ts.GOVERNANCE_FILE, ts.default_governance())
    print(json.dumps(gov, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
