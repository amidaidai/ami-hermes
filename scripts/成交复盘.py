#!/usr/bin/env python3
"""成交复盘入口：记录成交结果并更新 risk_state。"""

from __future__ import annotations

import argparse
import json
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trading_system as ts


def main() -> None:
    ap = argparse.ArgumentParser(description="记录一笔交易复盘，并联动 risk_state")
    ap.add_argument("--plan-id", required=True, help="计划ID，例如 ETHUSDT-20260617-1149")
    ap.add_argument("--symbol", required=True, help="品种，例如 ETHUSDT")
    ap.add_argument("--pnl", type=float, required=True, help="实际盈亏U，亏损填负数")
    ap.add_argument("--r", type=float, required=True, help="结果R倍数，亏损填负数")
    ap.add_argument("--mistake", default="无", help="错误标签：追价/未等确认/未按计划出场等")
    ap.add_argument("--discipline", default="遵守", help="纪律标签：遵守/轻微偏离/严重偏离")
    ap.add_argument("--note", default="", help="简短备注")
    ap.add_argument("--model", default="未标注模型", help="模型标签：VWAP反抽/VAH回收/POC拒绝/扫流动性回收/突破接受")
    ap.add_argument("--mae-r", type=float, default=None, help="最大不利波动，R计")
    ap.add_argument("--mfe-r", type=float, default=None, help="最大有利波动，R计")
    ap.add_argument("--exit-quality", default="", help="出场质量：过早/过晚/按计划/止损")
    ap.add_argument("--dry-run", action="store_true", help="只校验输出，不写入复盘和风控状态")
    args = ap.parse_args()

    ts.ensure_files()
    review = {
        "plan_id": args.plan_id,
        "symbol": args.symbol.upper(),
        "pnl_usd": args.pnl,
        "r_multiple": args.r,
        "mistake": args.mistake,
        "discipline": args.discipline,
        "note": args.note,
        "model": args.model,
        "mae_r": args.mae_r,
        "mfe_r": args.mfe_r,
        "exit_quality": args.exit_quality,
    }
    if args.dry_run:
        review["dry_run"] = True
        print(json.dumps(review, ensure_ascii=False, indent=2))
        return
    row = ts.record_trade_review(review)
    print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
