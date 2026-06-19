#!/usr/bin/env python3
"""成交记录 v1.0 — 标记真实开仓，未复盘前自动降级下一笔风险。"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trading_system as ts


def main() -> None:
    ap = argparse.ArgumentParser(description="记录真实开仓，让风控闸门等待成交复盘")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--plan-id", default="")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    ts.ensure_files()
    state = ts.mark_trade_opened(args.symbol.upper(), args.plan_id, args.note)
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
