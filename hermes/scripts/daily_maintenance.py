#!/usr/bin/env python
"""凌晨维护 — 每天3:20。日度数据刷新、持仓快照、周度更迭检查。"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA = Path(__file__).resolve().parent.parent.parent / "data"

def daily_snapshot():
    """拍当日持仓快照"""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    
    # 快照最近交易计划
    plans_file = DATA / "trade_plans.jsonl"
    snapshot = {"date": date_str, "time": now.isoformat(), "plans": 0, "reviews": 0}
    
    if plans_file.exists():
        lines = plans_file.read_text().strip().split('\n')
        snapshot["plans"] = len(lines)
    
    reviews_file = DATA / "trade_reviews.jsonl"
    if reviews_file.exists():
        lines = reviews_file.read_text().strip().split('\n')
        snapshot["reviews"] = len(lines)
    
    # 计算本周统计数据
    week_ago = now - timedelta(days=7)
    weekly_plans = 0
    if plans_file.exists():
        for line in plans_file.read_text().strip().split('\n'):
            try:
                plan = json.loads(line)
                ts = plan.get("timestamp", "")
                if ts and datetime.fromisoformat(ts).replace(tzinfo=timezone.utc) > week_ago:
                    weekly_plans += 1
            except:
                pass
    snapshot["weekly_plans"] = weekly_plans
    
    # 写日常维护日志
    log_file = DATA / "maintenance_log.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    
    return snapshot

def check_weekly_limits():
    """检查周度宪法限制"""
    reviews_file = DATA / "trade_reviews.jsonl"
    if not reviews_file.exists():
        return "无交易数据"
    
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    weekly_pnl = 0
    weekly_reviews = 0
    
    for line in reviews_file.read_text().strip().split('\n'):
        try:
            review = json.loads(line)
            ts = review.get("timestamp", "")
            if ts and datetime.fromisoformat(ts).replace(tzinfo=timezone.utc) > week_ago:
                weekly_pnl += review.get("pnl_usd", 0)
                weekly_reviews += 1
        except:
            pass
    
    if weekly_pnl < -10:
        return f"⚠周亏损${abs(weekly_pnl):.0f} — 超过10U软限"
    return f"周P&L: ${weekly_pnl:.2f} ({weekly_reviews}笔)"

if __name__ == "__main__":
    silent = "--quiet" in sys.argv
    snap = daily_snapshot()
    wl = check_weekly_limits()
    
    if not silent:
        print(f"[凌晨维护 {snap['date']}]")
        print(f"  快照: {snap['plans']}计划 / {snap['reviews']}复盘")
        print(f"  本周: {snap['weekly_plans']}计划")
        print(f"  周度: {wl}")

print("✅ 3 scripts created")
