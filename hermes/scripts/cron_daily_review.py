#!/usr/bin/env python3
"""
棠溪 · 每日复盘生成器 v1.0
每天 23:00 运行，汇总当日 trades → 推 Telegram
"""
import json, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DATA_DIR = "D:/Hermes agent/data"

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def main():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    
    # Load daily review
    review = load_json(f"{DATA_DIR}/daily_review.json")
    events = load_json(f"{DATA_DIR}/monitor_events.json")
    trades = load_json(f"{DATA_DIR}/trades.json")
    
    plans_today = review.get("plans", [])
    events_today = [e for e in events.get("events", []) if e.get("time", "").startswith(today)]
    trades_today = [t for t in trades.get("trades", []) if t.get("time", "").startswith(today)]
    
    total_r = sum(t.get("r_multiple", 0) for t in trades_today)
    wins = [t for t in trades_today if t.get("r_multiple", 0) > 0]
    
    summary = {
        "date": today,
        "plans": len(plans_today),
        "monitor_events": len(events_today),
        "trades": len(trades_today),
        "wins": len(wins),
        "total_r": round(total_r, 2),
        "win_rate": f"{len(wins)}/{len(trades_today)}" if trades_today else "0/0",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    
    # Save
    with open(f"{DATA_DIR}/daily_review.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Output for hermes cron deliver
    lines = [
        f"📊 每日复盘 · {today}",
        f"计划数：{summary['plans']} · 交易笔数：{summary['trades']}",
        f"胜率：{summary['win_rate']} · 合计R：{summary['total_r']}",
    ]
    print("\n".join(lines))

if __name__ == "__main__":
    main()
