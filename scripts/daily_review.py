#!/usr/bin/env python3
"""交易系统每日复盘 v9.5。"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
OUT = DATA / "daily_review.md"


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def same_day(row, day):
    t = str(row.get("time", ""))[:10]
    return t == day


def main():
    day = datetime.now().astimezone().date().isoformat()
    plans = [x for x in read_jsonl(DATA / "trade_plans.jsonl") if same_day(x, day)]
    events = [x for x in read_jsonl(DATA / "trade_events.jsonl") if same_day(x, day)]
    reviews = [x for x in read_jsonl(DATA / "trade_reviews.jsonl") if same_day(x, day)]
    monitor = json.loads((DATA / "monitor_events.json").read_text(encoding="utf-8")) if (DATA / "monitor_events.json").exists() else []
    monitor_today = [x for x in monitor if same_day(x, day)]

    model_counts = Counter(x.get("model", "未标注") for x in plans)
    mistake_counts = Counter(x.get("mistake", "未标注") for x in reviews)
    total_r = sum(float(x.get("result_r", 0) or 0) for x in reviews)
    wins = sum(1 for x in reviews if float(x.get("result_r", 0) or 0) > 0)

    lines = [f"# 交易系统每日复盘 · {day}", ""]
    lines.append("## 概览")
    lines.append(f"- 计划数：`{len(plans)}`")
    lines.append(f"- 监控事件：`{len(monitor_today)}`")
    lines.append(f"- 交易事件：`{len(events)}`")
    lines.append(f"- 复盘笔数：`{len(reviews)}`")
    lines.append(f"- 合计R：`{total_r:.2f}`")
    lines.append(f"- 胜率：`{wins}/{len(reviews)}`" if reviews else "- 胜率：`暂无成交复盘`")
    lines.append("")
    lines.append("## 模型分布")
    if model_counts:
        for k, v in model_counts.most_common():
            lines.append(f"- {k}：`{v}`")
    else:
        lines.append("- 暂无计划记录")
    lines.append("")
    lines.append("## 错因排行")
    if mistake_counts:
        for k, v in mistake_counts.most_common():
            lines.append(f"- {k}：`{v}`")
    else:
        lines.append("- 暂无复盘错因")
    lines.append("")
    lines.append("## 明日改进")
    if not plans:
        lines.append("- 每次分析后必须写入 trade_plans.jsonl，避免只分析不沉淀。")
    if monitor_today and not reviews:
        lines.append("- 监控有触发但没有复盘，成交或放弃都要记录原因。")
    if reviews and total_r < 0:
        lines.append("- 今日R为负，明日默认降一档风险。")
    if not lines[-1].startswith("-"):
        lines.append("- 保持按计划执行，继续积累样本。")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
