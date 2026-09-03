#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 反抽位 79,633 警报前置 — 穿越检测（零token）。stdout 注入 agent context。

触发条件：价格自上次巡检以来**穿过 79,633**（向上或向下），且冷却未过。
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

LEVEL = 79633.0            # 反抽位 POC
COOLDOWN = 1800            # 30min
BAND = 60                 # 判"已在位附近"的容差(不再用作窄带触发，仅辅助)
STATE_FILE = Path(os.path.expanduser("~/AppData/Local/hermes/data/btc_alert_79633_xstate.json"))

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
    # 向上穿 或 向下穿
    if (prev < LEVEL <= price) or (prev >= LEVEL > price):
        crossed = True

if crossed:
    if not last_alerted or (now - last_time) > COOLDOWN:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(
            {"last_alerted": True, "time": now, "price": price,
             "last_price": prev, "dir": "up" if price > prev else "down"}))
        d = "向上" if price > prev else "向下"
        print(f"TRIGGER price={price:,.0f} zone=79633 desc=反抽位穿越·{d}穿·不站稳短空", flush=True)
    else:
        print(f"COOLDOWN price={price:,.0f} zone=79633", flush=True)
else:
    # 未穿越：更新 last_price，若在容差外围也可考虑（此处保持简单：仅记录）
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_alerted": False, "time": last_time, "price": price, "last_price": price}))
    print(f"WAIT price={price:,.0f} zone=79633", flush=True)
