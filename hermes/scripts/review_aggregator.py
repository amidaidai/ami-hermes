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
    """按模型聚合统计"""
    models = defaultdict(lambda: {"count": 0, "wins": 0, "total_r": 0.0, "r_list": []})
    
    for r in reviews:
        model = r.get("model", "unknown")
        result_r = r.get("result_r", 0)
        is_win = result_r > 0
        
        models[model]["count"] += 1
        models[model]["total_r"] += result_r
        models[model]["r_list"].append(result_r)
        if is_win:
            models[model]["wins"] += 1
    
    return models

def format_table(models):
    """格式化胜率看板"""
    lines = []
    lines.append("模型胜率看板（最近{0}笔有效复盘）：".format(
        sum(m["count"] for m in models.values())
    ))
    lines.append("┌──────────┬────┬───────┬────────┬────────┐")
    lines.append("│ 模型     │ 次数│ 胜率  │ 平均RR │ 总盈亏 │")
    lines.append("├──────────┼────┼───────┼────────┼────────┤")
    
    for model, stats in sorted(models.items(), key=lambda x: -x[1]["count"]):
        count = stats["count"]
        win_rate = stats["wins"] / count * 100 if count > 0 else 0
        avg_rr = sum(stats["r_list"]) / count if count > 0 else 0
        avg_win = sum(r for r in stats["r_list"] if r > 0) / max(stats["wins"], 1)
        avg_loss = sum(r for r in stats["r_list"] if r <= 0) / max(count - stats["wins"], 1)
        
        lines.append(
            f"│ {model:<8} │ {count:>2} │ {win_rate:>4.0f}% │ "
            f"{avg_rr:+.1f}R  │ {stats['total_r']:+.1f}R │"
        )
    
    lines.append("└──────────┴────┴───────┴────────┴────────┘")
    lines.append("")
    
    # 总体统计
    total = sum(m["count"] for m in models.values())
    total_wins = sum(m["wins"] for m in models.values())
    total_r = sum(m["total_r"] for m in models.values())
    all_r = [r for m in models.values() for r in m["r_list"]]
    
    lines.append(f"总体：{total}笔 · 胜率 {total_wins/total*100:.0f}% · 总盈亏 {total_r:+.1f}R")
    lines.append(f"平均赢 {sum(r for r in all_r if r>0)/max(sum(1 for r in all_r if r>0),1):+.1f}R · "
                 f"平均亏 {sum(r for r in all_r if r<=0)/max(sum(1 for r in all_r if r<=0),1):+.1f}R")
    lines.append(f"最大连胜：待实现 · 最大连亏：待实现")
    lines.append("")
    
    # 最佳/最差模型
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
        print(f"请将复盘记录写入 {REVIEWS_PATH}")
        print("格式：{model, result_r, tags, timestamp}")
        return
    
    models = aggregate(reviews)
    print(format_table(models))
    
    # 输出JSON供脚本消费
    output = {
        "review_count": len(reviews),
        "models": {
            model: {
                "count": s["count"],
                "win_rate": s["wins"] / s["count"] if s["count"] else 0,
                "total_r": s["total_r"],
                "avg_r": sum(s["r_list"]) / s["count"] if s["count"] else 0,
            }
            for model, s in models.items()
        }
    }
    print("\n--- JSON ---")
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
