#!/usr/bin/env python3
"""
棠溪 · 权益曲线追踪器 v1.0
从 trade_reviews.jsonl 计算运行权益曲线+关键统计
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path("D:/Hermes agent")
REVIEW_FILE = ROOT / "data" / "trade_reviews.jsonl"
EQUITY_FILE = ROOT / "data" / "equity_curve.json"
RISK_FILE = ROOT / "data" / "risk_state.json"
TZ = timezone(timedelta(hours=8))


def load_account_baseline(default: float = 100.0) -> float:
    try:
        state = json.loads(RISK_FILE.read_text(encoding="utf-8"))
        for key in ("daily_starting_balance", "weekly_starting_balance", "capital_usd"):
            value = state.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return default


def load_reviews() -> list[dict]:
    if not REVIEW_FILE.exists():
        return []
    reviews = []
    with open(REVIEW_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                reviews.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return reviews


def build_equity_curve(
    initial_balance: float | None = None,
    reviews: list[dict] | None = None,
) -> dict:
    """
    从复盘记录构建权益曲线
    
    Returns:
        {
            "initial_balance": float,
            "current_balance": float,
            "total_return_pct": float,
            "points": [{"time": str, "balance": float, "trade_id": str, "pnl_r": float}],
            "stats": {...}
        }
    """
    if reviews is None:
        reviews = load_reviews()
    if initial_balance is None:
        initial_balance = load_account_baseline()
    
    balance = initial_balance
    points = [{
        "time": datetime.now(TZ).isoformat(),
        "balance": initial_balance,
        "trade_id": "START",
        "pnl_r": 0,
    }]
    
    real_trades = []
    for r in reviews:
        if r.get("test"):
            continue
        if not r.get("taken"):
            continue
        
        result_r = float(r.get("result_r", 0))
        risk = float(r.get("risk_usd", 0) or 10)
        pnl_amount = result_r * risk
        balance += pnl_amount
        
        points.append({
            "time": r.get("time", ""),
            "balance": round(balance, 2),
            "pnl_r": round(result_r, 2),
            "trade_id": r.get("plan_id", ""),
            "model": r.get("model", "未标注"),
            "symbol": r.get("symbol", ""),
        })
        real_trades.append(r)
    
    # 统计
    trades = real_trades
    wins = [t for t in trades if float(t.get("result_r", 0)) > 0]
    losses = [t for t in trades if float(t.get("result_r", 0)) < 0]
    total_r = sum(float(t.get("result_r", 0)) for t in trades)
    
    # 最大回撤
    peak = initial_balance
    max_dd_pct = 0.0
    max_dd_r = 0.0
    running = initial_balance
    for p in points[1:]:
        running = p["balance"]
        if running > peak:
            peak = running
        dd = (peak - running) / peak * 100
        if dd > max_dd_pct:
            max_dd_pct = dd
            max_dd_r = (peak - running) / 10  # 近似R
    
    # 亏损串
    current_streak = 0
    max_streak = 0
    for p in reversed(points[1:]):
        if p["pnl_r"] < 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            break
    
    result = {
        "schema": "equity_curve_v1",
        "updated": datetime.now(TZ).isoformat(),
        "initial_balance": initial_balance,
        "current_balance": round(balance, 2),
        "total_return_pct": round((balance - initial_balance) / initial_balance * 100, 2),
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "total_r": round(total_r, 2),
        "avg_r": round(total_r / len(trades), 2) if trades else 0,
        "max_drawdown_r": round(max_dd_r, 2),
        "profit_factor": round(
            sum(float(t.get("result_r", 0)) for t in wins) / 
            abs(sum(float(t.get("result_r", 0)) for t in losses)) if losses else 999, 2
        ),
        "current_loss_streak": current_streak,
        "max_loss_streak": max_streak,
        "points": points,
    }
    
    EQUITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    EQUITY_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = build_equity_curve()
    print(json.dumps(result, indent=2, ensure_ascii=False))
