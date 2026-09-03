#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 买回位 78,400 警报前置 — 穿越检测（零token）。stdout 注入 agent context。

触发条件：价格自上次巡检以来**穿过 78,400**（向上或向下），且冷却未过。
比窄带"落在区间内"更稳健——价格跳升越过关键位也能捕捉。
出区/无穿越 → WAIT（静默）；触发 → TRIGGER 供 agent 分析推送。
"""
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEVEL = 78400.0            # 多空分水岭
COOLDOWN = 1800            # 30min
STATE_FILE = Path(os.path.expanduser("~/AppData/Local/hermes/data/btc_alert_78400_xstate.json"))

try:
    import urllib.request
    req = urllib.request.Request(
        "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT",
        headers={"User-Agent": "curl/1.0"},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        price = float(json.loads(r.read())["price"])
except Exception as e:
    print(f"PRICE_UNAVAILABLE {e}", flush=True)
    sys.exit(0)

try:
    state = json.loads(STATE_FILE.read_text())
except Exception:
    state = {}

prev = state.get("last_price")
last_alerted = state.get("last_alerted", False)
last_time = state.get("time", 0.0)
now = time.time()

crossed = False
if prev is not None:
    if (prev < LEVEL <= price) or (prev >= LEVEL > price):
        crossed = True

if crossed:
    if not last_alerted or (now - last_time) > COOLDOWN:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(
            {"last_alerted": True, "time": now, "price": price,
             "last_price": prev, "dir": "up" if price > prev else "down"}))
        d = "向上" if price > prev else "向下"
        print(f"TRIGGER price={price:,.0f} zone=78400 desc=多空分水岭穿越·{d}穿·守住试多/破位下探", flush=True)
    else:
        print(f"COOLDOWN price={price:,.0f} zone=78400", flush=True)
else:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_alerted": False, "time": last_time, "price": price, "last_price": price}))
    print(f"WAIT price={price:,.0f} zone=78400", flush=True)
