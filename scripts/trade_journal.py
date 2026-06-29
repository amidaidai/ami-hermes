#!/usr/bin/env python3
"""复盘助手 — 记录每次分析判断，留待后续验证"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
from datetime import datetime, timezone, timedelta

tz = timezone(timedelta(hours=8))
LOG = r"D:\Hermes agent\data\trade_journal.jsonl"

def record(symbol, direction, entry_zone, stop, targets, reasoning, confidence):
    """记录一次分析判断"""
    entry = {
        "time": datetime.now(tz).isoformat(),
        "symbol": symbol,
        "direction": direction,
        "entry_zone": entry_zone,
        "stop": stop,
        "targets": targets,
        "reasoning": reasoning,
        "confidence": confidence,
        "result": None,  # 待后续填写
        "closed_at": None,
        "pnl_r": None,
    }
    with open(LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✅ 已记录: {symbol} {direction} @ {entry_zone}")

def review(limit=10):
    """查看最近记录"""
    try:
        with open(LOG) as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("暂无记录")
        return

    recent = [json.loads(l) for l in lines[-limit:]]
    for r in recent:
        res = r.get("result", "待定")
        pnl = r.get("pnl_r", "?")
        sym = r["symbol"]
        dr = r["direction"]
        entry = r["entry_zone"]
        print(f"  [{r['time'][:16]}] {sym} {dr} @ {entry} → {res} (R:{pnl})")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "review":
        review()
    else:
        print("用法: python trade_journal.py [review]")
        print("  review — 看最近10条记录")
