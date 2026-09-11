#!/usr/bin/env python3
"""
棠溪 · 复盘聚合器 v1.0
读取 data/trade_reviews.jsonl，输出五类模型胜率看板。
"""

import json, sys, os
from collections import defaultdict
from pathlib import Path

REVIEWS_PATH = Path(os.environ.get("HERMES_WORKSPACE", ".")) / "data" / "trade_reviews.jsonl"

def load_reviews(path, limit=50):
    reviews = []
    if not path.exists():
        return reviews
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    reviews.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return reviews[-limit:]

def aggregate(reviews):
    models = defaultdict(lambda: {"count": 0, "wins": 0, "total_r": 0.0, "r_list": []})
    for r in reviews:
        model = r.get("model", "unknown")
        result_r = r.get("result_r", 0)
        models[model]["count"] += 1
        models[model]["total_r"] += result_r
        models[model]["r_list"].append(result_r)
        if result_r > 0:
            models[model]["wins"] += 1
    return models

def format_table(models):
    lines = []
    lines.append("模型胜率看板（最近{0}笔有效复盘）：".format(sum(m["count"] for m in models.values())))
    lines.append("┌──────────┬────┬───────┬────────┬────────┐")
    lines.append("│ 模型     │ 次数│ 胜率  │ 平均RR │ 总盈亏 │")
    lines.append("├──────────┼────┼───────┼────────┼────────┤")
    for model, stats in sorted(models.items(), key=lambda x: -x[1]["count"]):
        count = stats["count"]
        win_rate = stats["wins"] / count * 100 if count > 0 else 0
        avg_rr = sum(stats["r_list"]) / count if count > 0 else 0
        lines.append(f"│ {model:<8} │ {count:>2} │ {win_rate:>4.0f}% │ {avg_rr:+.1f}R  │ {stats['total_r']:+.1f}R │")
    lines.append("└──────────┴────┴───────┴────────┴────────┘")
    total = sum(m["count"] for m in models.values())
    total_wins = sum(m["wins"] for m in models.values())
    total_r = sum(m["total_r"] for m in models.values())
    if total > 0:
        lines.append(f"总体：{total}笔 · 胜率 {total_wins/total*100:.0f}% · 总盈亏 {total_r:+.1f}R")
    if models:
        best = max(models.items(), key=lambda x: x[1]["total_r"])
        worst = min(models.items(), key=lambda x: x[1]["total_r"])
        lines.append(f"最佳模型：{best[0]}（{best[1]['total_r']:+.1f}R · {best[1]['count']}笔）")
        lines.append(f"最差模型：{worst[0]}（{worst[1]['total_r']:+.1f}R · {worst[1]['count']}笔）")
    return "\n".join(lines)

def main():
    reviews = load_reviews(REVIEWS_PATH)
    if not reviews:
        print("暂无复盘数据。")
        return
    models = aggregate(reviews)
    print(format_table(models))

if __name__ == "__main__":
    main()
