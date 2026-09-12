#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 到价提醒哨兵：热读已批准关键位，只提醒用户查看图表，不做方向裁决。"""
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
CONFIG = DATA / "keylevels_config.json"
STATE = Path(os.path.expanduser("~/AppData/Local/hermes/data/btc_price_arrival_sentinel.json"))
TARGET = "telegram:-1003733144325:386"
SYMBOL = "BTCUSDT"
WINDOW = 35.0
COOLDOWN = 1800.0


def get_json(url, timeout=8):
    try:
        req = Request(url, headers={"User-Agent": "Tangxi-BTC-Price-Sentinel/1.0"})
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE)


def load_levels():
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        levels = cfg.get("symbols", {}).get(SYMBOL, {}).get("levels", [])
        return [
            (str(level["name"]), float(level["price"]))
            for level in levels
            if isinstance(level, dict)
            and level.get("enabled", True) is not False
            and level.get("price") is not None
        ]
    except Exception:
        return []


def send_message(text):
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from telegram_direct import send_telegram_direct
        return send_telegram_direct(TARGET, text, timeout=10)
    except Exception as exc:
        return False, type(exc).__name__


def main():
    quote = get_json("https://fapi.binance.com/fapi/v1/ticker/price?symbol=" + SYMBOL)
    if not isinstance(quote, dict) or not quote.get("price"):
        return 0
    price = float(quote["price"])
    levels = load_levels()
    if not levels:
        return 0

    state = load_state()
    previous = state.get("previous_price")
    now = time.time()
    alerts = []
    for name, level in levels:
        distance = abs(price - level)
        crossed = previous is not None and ((previous < level <= price) or (previous > level >= price))
        in_window = distance <= WINDOW
        record = state.get(name, {}) if isinstance(state.get(name), dict) else {}
        last_time = float(record.get("time", 0) or 0)
        if (crossed or in_window) and now - last_time >= COOLDOWN:
            alerts.append(
                f"○ BTC 到价：{price:,.0f}，触及{name} {level:,.0f}\n"
                "请查看 TradingView 15m 图表，自己确认结构。\n"
                "仅提醒，不代表方向，不自动下单。"
            )
            state[name] = {"time": now, "price": price}

    state["previous_price"] = price
    state["updated_at"] = now
    save_state(state)
    for message in alerts:
        ok, reason = send_message(message)
        if not ok:
            # 只输出 ASCII，避免 Windows no_agent 编码问题
            print("BTC_ALERT_SEND_FAILED " + str(reason), flush=True)
    return 0


if __name__ == "__main__":
    print("已退役·生产权威为 keylevel_guard.py", flush=True)
    raise SystemExit(0)
