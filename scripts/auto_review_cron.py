#!/usr/bin/env python3
"""自动复盘 Cron 脚本 — 每15分钟执行，复盘最新30分钟内完成/过期的计划

适配 no_agent cron：输出简短的 Markdown 结果到 stdout
    python scripts/auto_review_cron.py

行为：
- 只处理 created_at/time 在最后30分钟内（或 status 非 B等待 且未复盘）的计划
- 生成复盘记录追加到 trade_reviews.jsonl
- 输出 Markdown 摘要（可 cron 投递到 Telegram/邮件等）
"""
import sys
import os
import json
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
WINDOW_MINUTES = 30  # 只看最后 N 分钟

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TRADE_PLANS = os.path.join(DATA_DIR, "trade_plans.jsonl")
TRADE_REVIEWS = os.path.join(DATA_DIR, "trade_reviews.jsonl")


def get_timestamp(plan):
    """从计划中提取时间戳。"""
    for key in ("created_at", "time", "created", "labeled_at"):
        val = plan.get(key, "")
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
    return None


def load_reviewed_keys(filepath):
    """加载已复盘的键集合（plan_id + setup_id）。"""
    keys = set()
    if not os.path.exists(filepath):
        return keys
    with open(filepath, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            pid = obj.get("plan_id", "")
            sid = obj.get("setup_id", "")
            if pid:
                keys.add(f"pid:{pid}")
            if sid:
                keys.add(f"sid:{sid}")
    return keys


def generate_review(plan, now_iso):
    """生成简版复盘记录（与 batch_review.py 保持同一格式）。"""
    pid = plan.get("plan_id", "")
    sid = plan.get("setup_id", "")
    symbol = plan.get("symbol", "")
    model = plan.get("model", plan.get("model_id", ""))
    direction = plan.get("direction", "")
    status = plan.get("state", plan.get("status", ""))

    if status == "A做多":
        review_result = "active_long"
        note = "A做多·活跃"
    elif status in ("C等待", "cancelled", "expired"):
        review_result = "expired"
        note = "C等待·已过期"
    elif status in ("X禁做", "blocked"):
        review_result = "blocked"
        note = "X禁做·风控拦截"
    elif status in ("B等待", "waiting"):
        review_result = "pending"
        note = "B等待·监控中"
    else:
        review_result = "completed"
        note = f"{status}·已完成"

    return {
        "plan_id": pid if pid else None,
        "setup_id": sid if sid else None,
        "symbol": symbol,
        "model": model,
        "direction": direction,
        "status": status,
        "auto_generated": True,
        "reviewed_at": now_iso,
        "review_result": review_result,
        "result_r": None,
        "pnl_estimate": None,
        "note": note,
        "schema": "trade_review_v1",
    }


def main():
    now = datetime.now(TZ)
    now_iso = now.isoformat()
    window_start = now - timedelta(minutes=WINDOW_MINUTES)

    # 加载已复盘键
    reviewed = load_reviewed_keys(TRADE_REVIEWS)

    # 扫描计划：找 WINDOW 内新增的、且未复盘的
    candidates = []
    new_completed = []  # 非 B等待 的（模拟"刚完成"）
    total_lines = 0

    if os.path.exists(TRADE_PLANS):
        with open(TRADE_PLANS, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                total_lines += 1
                try:
                    plan = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                pid = plan.get("plan_id", "")
                sid = plan.get("setup_id", "")
                key = f"pid:{pid}" if pid else f"sid:{sid}"
                status = plan.get("state", plan.get("status", ""))

                # 已复盘则跳过
                if key in reviewed:
                    continue

                ts = get_timestamp(plan)
                in_window = ts is not None and ts >= window_start

                # 符合条件1：在窗口内 且 未复盘
                if in_window:
                    candidates.append(plan)
                # 符合条件2：非等待状态 且 未复盘 且 在窗口内
                elif (
                    status in ("A做多", "C等待", "X禁做", "filled", "closed", "completed")
                    and in_window
                ):
                    new_completed.append(plan)

    # 合并候选（去重）
    seen = set()
    to_review = []
    for p in candidates + new_completed:
        key = p.get("plan_id", "") or p.get("setup_id", "")
        if key not in seen:
            seen.add(key)
            to_review.append(p)

    # 写入
    written = 0
    if to_review:
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(TRADE_REVIEWS, "a", encoding="utf-8") as f:
                for plan in to_review:
                    review = generate_review(plan, now_iso)
                    f.write(json.dumps(review, ensure_ascii=False) + "\n")
                    written += 1
        except IOError as e:
            print(f"⚠️ 写入错误: {e}")
            sys.exit(1)

    # 计算最新复盘率
    total_plans = total_lines
    reviewed_after = len(reviewed) + written
    rate = reviewed_after / total_plans * 100 if total_plans > 0 else 0

    # 输出 Markdown（适配 no_agent cron）
    timestamp_str = now.strftime("%Y-%m-%d %H:%M CST")
    print(f"## 🔄 自动复盘 [{timestamp_str}]")
    print()
    if written == 0:
        print(f"> 无新增复盘对象（窗口 {WINDOW_MINUTES}min 内无新触发计划）")
    else:
        print(f"| 项目 | 值 |")
        print(f"|------|-----|")
        print(f"| 本次新增 | **{written}** |")
        print(f"| 当前复盘率 | **{rate:.1f}%** |")
        print(f"| 总计划行数 | {total_plans} |")
        print()
        if rate >= 50:
            print(f"🎯 **复盘率达标（≥50%）**")
        else:
            print(f"⚡ 距50%还差 {max(0, 50 - rate):.1f}%")
    print()


if __name__ == "__main__":
    main()
