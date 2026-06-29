#!/usr/bin/env python3
"""策略治理 v1.0 — 统计模型期望值，禁止样本不足自动升权。"""
from __future__ import annotations
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
    ts.ensure_files()
    gov = ts.read_json(ts.GOVERNANCE_FILE, ts.default_governance())

    # Aggregate real stats from trade_reviews
    reviews = []
    rev_path = ts.REVIEW_LOG
    if rev_path.exists():
        for line in rev_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    reviews.append(json.loads(line))
                except: pass

    model_stats = {}
    for r in reviews:
        m = r.get("model", "未标注")
        if m not in model_stats: model_stats[m] = {"count":0, "sum_r":0.0, "wins":0}
        model_stats[m]["count"] += 1
        model_stats[m]["sum_r"] += r.get("r_multiple", 0)
        if r.get("r_multiple", 0) > 0: model_stats[m]["wins"] += 1

    updated = False
    for model, st in model_stats.items():
        if model in gov.get("rules", {}):
            rule = gov["rules"][model]
            sample = st["count"]
            avg_r = st["sum_r"] / sample if sample > 0 else 0
            winrate = st["wins"] / sample if sample > 0 else 0
            rule["current_sample"] = sample
            rule["avg_r"] = round(avg_r, 3)
            rule["win_rate"] = round(winrate, 3)
            if sample >= rule.get("min_sample", 10) and avg_r >= gov.get("policy", {}).get("min_expectancy_r", 0.15):
                # modest weight boost if good
                rule["current_weight"] = min(1.5, rule.get("current_weight", 1.0) + 0.1)
            updated = True

    if updated:
        gov["updated"] = __import__("datetime").datetime.now(__import__("datetime").timezone(__import__("datetime").timedelta(hours=8))).isoformat()
        ts.write_json(ts.GOVERNANCE_FILE, gov)
        print("策略治理 updated from reviews")
    else:
        print("策略治理 (no new reviews or no change)")

    print(json.dumps(gov, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
