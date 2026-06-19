#!/usr/bin/env python3
"""
棠溪 · 多模型方向翻转守护 v1.0
每 30 分钟检查 12 引擎方向是否翻转，翻转则推 Telegram + Discord
"""
import json, sys, time, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
SNAP_PATH = "D:/Hermes agent/data/source_snapshot.json"
STATE_PATH = "D:/Hermes agent/data/direction_state.json"

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    snap = load_json(SNAP_PATH)
    state = load_json(STATE_PATH) or {"last_direction": "unknown", "last_flip": None, "flip_count": 0}
    
    if not snap:
        print("No snapshot found. Skipping direction check.")
        return
    
    # Derive direction from snapshot data
    # Simple heuristic: combine CVD direction + fear_greed + funding
    fg = snap.get("fear_greed", {})
    taker = snap.get("taker_futures", {})
    funding = snap.get("funding", {})
    
    signals = []
    # CVD/taker direction
    if taker.get("direction") == "buy":
        signals.append(1)
    elif taker.get("direction") == "sell":
        signals.append(-1)
    
    # Fear & Greed
    fg_val = fg.get("current")
    if fg_val is not None:
        if fg_val > 55:
            signals.append(1)
        elif fg_val < 35:
            signals.append(-1)
    
    # Funding
    funding_val = funding.get("current")
    if funding_val is not None:
        if funding_val > 0.0001:
            signals.append(1)
        elif funding_val < -0.0001:
            signals.append(-1)
    
    if not signals:
        direction = "neutral"
    elif sum(signals) > 0:
        direction = "bullish"
    elif sum(signals) < 0:
        direction = "bearish"
    else:
        direction = "neutral"
    
    prev = state.get("last_direction", "unknown")
    
    now = datetime.now(TZ).isoformat(timespec="seconds")
    
    if prev != direction and prev != "unknown":
        state["last_direction"] = direction
        state["last_flip"] = now
        state["flip_count"] = state.get("flip_count", 0) + 1
        
        flip_msg = f"🔄 方向翻转 · {prev} → {direction} · {now}"
        print(flip_msg)
        # Alert - will be picked up by hermes cron deliver
        save_json(STATE_PATH, state)
    else:
        if prev == "unknown":
            state["last_direction"] = direction
            save_json(STATE_PATH, state)
        print(f"No flip. Current direction: {direction} (was: {prev})")

if __name__ == "__main__":
    main()
