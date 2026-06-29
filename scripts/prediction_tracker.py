#!/usr/bin/env python3
"""
棠溪 · 模型胜率追踪器 v1.0
记录多模型引擎预测→定时校验结果→自动聚合胜率。
写入 data/prediction_log.jsonl + 更新 strategy_model_stats.json
"""

import json, time, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
PRED_FILE = DATA / "prediction_log.jsonl"
STATS_FILE = DATA / "strategy_model_stats.json"
TZ = timezone(timedelta(hours=8))


def log_prediction(symbol: str, merged: dict, model_results: list, price: float = 0) -> dict:
    """记录一次引擎预测"""
    pred = {
        "time": datetime.now(TZ).isoformat(timespec="seconds"),
        "symbol": symbol,
        "price_at_prediction": price,
        "direction": merged["bias"],
        "long_confidence": merged["long_confidence"],
        "short_confidence": merged["short_confidence"],
        "global_confidence": merged["global_confidence"],
        "action": merged["action"],
        "models": {r["name"]: {"dir": r["direction"], "conf": r["confidence"]} 
                   for r in model_results if r["confidence"] > 0.15},
        "verified": False,
        "verification_time": None,
        "price_at_verification": None,
        "was_correct": None,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    with open(PRED_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(pred, ensure_ascii=False, separators=(",", ":")) + "\n")
    return pred


def verify_predictions(symbol: str, current_price: float, lookback_hours: float = 4.0) -> list:
    """回验N小时前的预测"""
    if not PRED_FILE.exists():
        return []
    
    cutoff = datetime.now(TZ) - timedelta(hours=lookback_hours)
    verified = []
    
    with open(PRED_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Read all, update verified ones
    updated_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            pred = json.loads(line)
        except json.JSONDecodeError:
            updated_lines.append(line)
            continue
        
        if pred.get("verified"):
            updated_lines.append(json.dumps(pred, ensure_ascii=False, separators=(",", ":")))
            continue
        
        pred_time = datetime.fromisoformat(pred["time"]).astimezone(TZ)
        if pred_time > cutoff:
            updated_lines.append(json.dumps(pred, ensure_ascii=False, separators=(",", ":")))
            continue
        
        if pred["symbol"] != symbol:
            updated_lines.append(json.dumps(pred, ensure_ascii=False, separators=(",", ":")))
            continue
        
        # Verify
        old_price = pred.get("price_at_prediction", 0)
        if old_price <= 0:
            pred["verification_time"] = datetime.now(TZ).isoformat(timespec="seconds")
            pred["verified"] = True
            pred["was_correct"] = None  # can't verify without price
            updated_lines.append(json.dumps(pred, ensure_ascii=False, separators=(",", ":")))
            continue
        
        price_change = (current_price - old_price) / old_price

        # Direction check: only count meaningful moves (>=0.5% or high confidence)
        direction = pred["direction"]
        conf = max(pred.get("global_confidence", 0), pred.get("long_confidence", 0), pred.get("short_confidence", 0))
        min_move = 0.005  # 0.5% for meaningful
        if direction == "偏多":
            was_correct = price_change > min_move
        elif direction == "偏空":
            was_correct = price_change < -min_move
        else:
            # "方向不明" 不算预测，不计入胜率
            pred["verified"] = True
            pred["verification_time"] = datetime.now(TZ).isoformat(timespec="seconds")
            pred["was_correct"] = None  # excluded from stats
            pred["excluded"] = True
            updated_lines.append(json.dumps(pred, ensure_ascii=False, separators=(",", ":")))
            continue

        # Additional: low confidence predictions are not counted as "correct" for stats
        if conf < 0.5 and not was_correct:
            pred["was_correct"] = None
            pred["excluded"] = True

        pred["verified"] = True
        pred["verification_time"] = datetime.now(TZ).isoformat(timespec="seconds")
        pred["price_at_verification"] = current_price
        pred["was_correct"] = was_correct
        pred["price_change_pct"] = round(price_change * 100, 3)
        
        verified.append(pred)
        updated_lines.append(json.dumps(pred, ensure_ascii=False, separators=(",", ":")))
    
    if updated_lines != [l.strip() for l in lines]:
        with open(PRED_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(updated_lines) + "\n")
    
    return verified


def aggregate_stats() -> dict:
    """聚合所有已验证预测的胜率统计"""
    if not PRED_FILE.exists():
        return _empty_stats()
    
    predictions = []
    with open(PRED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
                if p.get("verified") and p.get("was_correct") is not None and not p.get("excluded"):
                    predictions.append(p)
            except json.JSONDecodeError:
                continue
    
    if not predictions:
        return _empty_stats()
    
    # Per-model stats
    model_stats = {}
    for p in predictions:
        models = p.get("models", {})
        overall_correct = p.get("was_correct", False)
        for name, m in models.items():
            if name not in model_stats:
                model_stats[name] = {"total": 0, "correct": 0, "sum_conf": 0.0}
            model_stats[name]["total"] += 1
            model_stats[name]["sum_conf"] += m.get("conf", 0)
            if overall_correct:
                model_stats[name]["correct"] += 1
    
    # Format
    result = {
        "total_predictions": len(predictions),
        "verified_predictions": len([p for p in predictions if p.get("was_correct") is not None]),
        "overall_accuracy": sum(1 for p in predictions if p["was_correct"]) / len(predictions) if predictions else 0,
        "models": {},
    }
    
    for name, s in sorted(model_stats.items(), key=lambda x: -x[1]["total"]):
        accuracy = s["correct"] / s["total"] if s["total"] > 0 else 0
        result["models"][name] = {
            "predictions": s["total"],
            "correct": s["correct"],
            "accuracy": round(accuracy, 3),
            "avg_confidence": round(s["sum_conf"] / s["total"], 3) if s["total"] > 0 else 0,
        }
    
    return result


def _empty_stats() -> dict:
    return {"total_predictions": 0, "overall_accuracy": 0, "models": {}}


# ═══════════════════ CLI ═══════════════════
if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "stats"
    
    if action == "stats":
        stats = aggregate_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif action == "verify":
        symbol = sys.argv[2] if len(sys.argv) > 2 else "BTCUSDT"
        price = float(sys.argv[3]) if len(sys.argv) > 3 else 0
        hours = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
        verified = verify_predictions(symbol, price, hours)
        print(f"Verified {len(verified)} predictions")
        for v in verified[:5]:
            print(f"  {v['time']} {v['direction']} → {'✓' if v['was_correct'] else '✗'} ({v.get('price_change_pct', 0):+.2f}%)")
    
    elif action == "log":
        # Simulate: log a prediction for testing
        pred = {
            "time": datetime.now(TZ).isoformat(),
            "symbol": "BTCUSDT",
            "price_at_prediction": float(sys.argv[2]) if len(sys.argv) > 2 else 65000,
            "direction": "偏多",
            "long_confidence": 0.65,
            "short_confidence": 0.45,
            "global_confidence": 0.65,
            "action": "可交易 · 轻仓",
            "models": {"Taker背离": {"dir": "long", "conf": 0.8}, "EMA趋势": {"dir": "short", "conf": 0.3}},
            "verified": False,
        }
        DATA.mkdir(parents=True, exist_ok=True)
        with open(PRED_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(pred, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"Logged test prediction at {pred['price_at_prediction']}")
    
    else:
        print("Usage: python prediction_tracker.py [stats|verify|log]")
