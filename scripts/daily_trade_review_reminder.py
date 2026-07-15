#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily trade review reminder: silent unless today's plans need review."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BJT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def fmt_time(dt: datetime) -> str:
    bjt = dt.astimezone(BJT)
    return f"{bjt.year}年{bjt.month}月{bjt.day}日{bjt.hour:02d}：{bjt.minute:02d}"


def main() -> int:
    now = datetime.now(BJT)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    plans = read_jsonl(DATA / "trade_plans.jsonl")
    reviews = read_jsonl(DATA / "trade_reviews.jsonl")
    reviewed = {r.get("setup_id") or r.get("plan_id") for r in reviews if (r.get("setup_id") or r.get("plan_id"))}

    today_plans = []
    pending = []
    for plan in plans:
        created = parse_dt(plan.get("created_at"))
        if not created or created.astimezone(BJT) < start:
            continue
        setup_id = plan.get("setup_id") or plan.get("plan_id")
        if not setup_id:
            continue
        today_plans.append(plan)
        expires = parse_dt(plan.get("expires_at"))
        actionable = (expires is None or expires <= now) or plan.get("status") not in {"B等待", "C等待"}
        if setup_id not in reviewed and actionable:
            pending.append(plan)

    if not pending:
        return 0

    symbols = Counter(p.get("symbol", "?") for p in pending)
    models = Counter(p.get("model_id") or p.get("model") or "未知" for p in pending)
    first = pending[0]
    direction = "○复盘"
    report = f"""{direction} 待复盘{len(pending)}笔 · {fmt_time(now)}

| 项目 | 数据 | 状态 |
|:----|:----|:----|
| 计划 | `{len(today_plans)}`笔 | 今日生成 |
| 待复盘 | `{len(pending)}`笔 | 需要处理 |
| 首笔 | `{first.get('symbol','?')}`·`{first.get('status','?')}` | {first.get('model_id') or first.get('model') or '未知'} |

| 来源 | 方向 | 证据 |
|:----|:---:|:----|
| 品种分布 | ⚡异动 | {" · ".join(f"{k}`{v}`" for k, v in symbols.most_common(4))} |
| 模型分布 | ⚖中性 | {" · ".join(f"{k}`{v}`" for k, v in models.most_common(4))} |
| 复盘缺口 | 🐻偏空 | `trade_reviews.jsonl` 未匹配 `{len(pending)}` 个setup |

| 方向 | 触发 | 动作 |
|:---:|:----|:----|
| ○复盘 | 今日待复盘`{len(pending)}`笔 | 打开最近计划逐笔确认 |
| ×禁拖 | 超过当日22：30未处理 | 先标记过期/取消 |
| ↑改进 | 同模型连续等待 | 检查入场条件是否过窄 |

**总体结论**: **○先完成{len(pending)}笔复盘，再开启新计划**；重点检查等待条件与失效位。"""
    print(report)
    # v9.7: 统一走 RichMarkdown 真表格通道推 TG
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from telegram_reliable import push_tg_rich
        push_tg_rich("telegram:-1003733144325:846", report)
    except Exception as _te:
        print(f"⚠ 复盘提醒RichMarkdown推送失败: {_te}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
