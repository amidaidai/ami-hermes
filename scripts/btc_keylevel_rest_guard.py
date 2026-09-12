#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 BTC 关键位实时守卫 — 亚秒 REST 轮询（当前网络下最稳·已验证通畅）。

WS 域名被代理/DNS 卡死（fstream 解析到不可达 IPv6，Python WS 库走代理隧道路径与 curl
不一致，连不上），改用 0.5s REST 轮询——已实测每次 0.35s，健康。价格自上次以来
**穿过 79,633 或 78,400** 任一方向 → 写触发文件，由 agent 做完整分析并推 386。

触发信令：data/btc_keylevel_trigger.json（含已触发位/方向/时间/冷却截止）。
防刷屏：每触发位独立 30 分钟冷却。
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_json import atomic_write_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path("D:/Hermes agent/data")
TRIGGER_FILE = DATA_DIR / "btc_keylevel_trigger.json"
STATE_FILE = DATA_DIR / ".btc_keylevel_rest_state.json"
HEARTBEAT_FILE = DATA_DIR / ".btc_keylevel_rest_heartbeat.json"

BINANCE_APIS = ("https://fapi.binance.com", "https://api.binance.com")
LEVELS = {
    "反抽位79633": 79633.0,
    "买回位78400": 78400.0,
}
COOLDOWN_SECONDS = 1800   # 每触发位独立冷却 30 分钟
POLL_SECONDS = 0.5        # 亚秒轮询

import urllib.request


def ts():
    return time.time()


def now_bjt_iso():
    from datetime import datetime, timezone, timedelta
    return datetime.now(tz=timezone(timedelta(hours=8))).isoformat()


def get_price():
    for base in BINANCE_APIS:
        try:
            req = urllib.request.Request(f"{base}/fapi/v1/ticker/price?symbol=BTCUSDT"
                                         if "fapi" in base else
                                         f"{base}/api/v3/ticker/price?symbol=BTCUSDT",
                                         headers={"User-Agent": "curl/1.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                d = json.loads(r.read())
                return float(d["price"])
        except Exception:
            continue
    return None


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"last_price": None, "triggered": {}}


def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, ensure_ascii=False)


def split_trigger(name, price, direction, cooldown_until):
    try:
        with open(TRIGGER_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["triggered"] = True
    data["zone"] = name
    data["zone_price"] = LEVELS[name]
    data["price"] = price
    data["direction"] = direction
    data["ts"] = now_bjt_iso()
    data["cooldown_until"] = cooldown_until
    TRIGGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(TRIGGER_FILE, data)


def heartbeat(status):
    hb = {"ts": now_bjt_iso(), "pid": os.getpid(), "status": status,
          "last_price": _GLOBAL.get("last_price")}
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(HEARTBEAT_FILE, hb, indent=None)


_GLOBAL = {"last_price": None}


def log(m):
    safe = m.encode("ascii", "replace").decode("ascii")
    print(safe, flush=True)


def main_loop():
    state = load_state()
    last_price = state.get("last_price")
    triggered = state.get("triggered", {})   # {name: {dir, cool_until, price}}
    log(f"BTC keylevel REST guard started PID={os.getpid()}")
    heartbeat("running")

    while True:
        t0 = time.time()
        price = get_price()
        if price is None:
            time.sleep(POLL_SECONDS)
            continue
        _GLOBAL["last_price"] = price
        now = ts()

        for name, lvl in LEVELS.items():
            crossed = None
            if last_price is not None:
                if last_price < lvl <= price:
                    crossed = "up"
                elif last_price >= lvl > price:
                    crossed = "down"
            if crossed:
                info = triggered.get(name, {})
                cool_until = info.get("cool_until", 0.0)
                # 冷却内且方向相同 → 跳过；否则触发
                if now >= cool_until or info.get("dir") != crossed:
                    log(f"TRIGGER {name} {crossed} price={price:,.0f}")
                    new_cool = now + COOLDOWN_SECONDS
                    split_trigger(name, price, crossed, new_cool)
                    triggered[name] = {"dir": crossed, "cool_until": new_cool, "price": price}
                    save_state({"last_price": price, "triggered": triggered, "_ts": ts()})

        last_price = price
        save_state({"last_price": price, "triggered": triggered, "_ts": ts()})
        heartbeat("running")

        # 保持 0.5s 节流
        elapsed = time.time() - t0
        if elapsed < POLL_SECONDS:
            time.sleep(POLL_SECONDS - elapsed)


if __name__ == "__main__":
    print("已退役·生产权威为 keylevel_guard.py", flush=True)
    raise SystemExit(0)
