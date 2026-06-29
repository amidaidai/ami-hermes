#!/usr/bin/env python3
"""BTC 关键区到价提醒 — no_agent 零token监控"""
import json, urllib.request, sys, os, time

SYM = "BTCUSDT"
ZONE_LOW = 60267   # S VWAP
ZONE_HIGH = 60342  # 支撑墙上沿

STATE_FILE = os.path.join(os.path.dirname(__file__), "btc_zone_state.json")

def get_price():
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={SYM}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
        return float(data["price"])

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except: return {"last_alerted": False}

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f)

price = get_price()

if ZONE_LOW <= price <= ZONE_HIGH:
    state = load_state()
    if not state.get("last_alerted"):
        print(f"🔔 BTC {price} 进入关键区 {ZONE_LOW}~{ZONE_HIGH}")
        print(f"S VWAP~支撑墙区间，站稳做多目标60558→60734")
        save_state({"last_alerted": True, "price": price, "time": time.time()})
else:
    save_state({"last_alerted": False})
    # 静默 — 不在区间不推送
