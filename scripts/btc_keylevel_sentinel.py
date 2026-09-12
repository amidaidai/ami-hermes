#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 关键位到价哨兵 — zero-token, no_agent cron.

监控两个关键位，价格进入区间且冷却未过 → 组装一条到价提醒（现价+关键位+衍生品方向票）
推到 TG 386。出区间重置。纯 REST，不经 Hermes TV MCP（避免抢会话）。
"""
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保能导入同目录的 binance_public / telegram_direct
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from binance_public import fetch_futures  # noqa: E402

SYM = "BTCUSDT"
# 关键位：价格进入 lo~hi 且冷却未过 → 触发。
# 78390 = nPOC 回踩位(主指标"现位")；78522 = 周四低 强磁吸(分81)
ZONES = {
    "N_POC_78390": {"lo": 78365, "hi": 78415, "desc": "nPOC 回踩位 78390 · 站稳看多攻 78998"},
    "LOW_MAGNET_78522": {"lo": 78497, "hi": 78547, "desc": "周四低 强磁吸 78522 · 守住看反弹/破位看 78390"},
}
COOLDOWN_SECONDS = 1800  # 每 key 独立冷却 30 分钟
STATE_FILE = Path(os.path.expanduser("~/AppData/Local/hermes/data/btc_keylevel_sentinel_state.json"))
TG_TARGET = "telegram:-1003733144325:386"


def get_price_and_deriv():
    """取现价 + 衍生品方向票。任何一项失败不阻塞整体。"""
    out = {}
    p = fetch_futures("/fapi/v1/ticker/price", {"symbol": SYM}, timeout=8)
    if isinstance(p, dict) and p.get("price"):
        out["price"] = float(p["price"])

    # 资金费率 + OI
    pi = fetch_futures("/fapi/v1/premiumIndex", {"symbol": SYM}, timeout=8)
    if isinstance(pi, dict) and pi.get("markPrice"):
        out["mark_price"] = float(pi["markPrice"])
        out["funding"] = float(pi.get("lastFundingRate", 0.0))

    oi = fetch_futures("/fapi/v1/openInterest", {"symbol": SYM}, timeout=8)
    if isinstance(oi, dict) and oi.get("openInterest"):
        out["oi"] = float(oi["openInterest"])

    # 大户多空比
    ls = fetch_futures("/futures/data/topLongShortAccountRatio", {"symbol": SYM, "period": "15m", "limit": "1"}, timeout=8)
    if isinstance(ls, list) and ls and isinstance(ls[0], dict):
        out["ls"] = float(ls[0].get("longShortRatio", 0.0))

    # Taker 买卖比
    tk = fetch_futures("/futures/data/takerlongshortRatio", {"symbol": SYM, "period": "15m", "limit": "1"}, timeout=8)
    if isinstance(tk, list) and tk and isinstance(tk[0], dict):
        out["taker"] = float(tk[0].get("buySellRatio", 0.0))

    return out


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, ensure_ascii=False)


def build_message(price, zone_key, zone, data):
    """组装到价提醒。方向票由衍生品决定。"""
    lines = []
    lines.append(f"🔔 BTC 到价 · {zone['desc']}")
    lines.append(f"现价 {price:,.0f} · mark {data.get('mark_price', 0):,.0f}")
    # 方向票
    taker = data.get("taker", 0.0)
    oi_txt = f"OI {data.get('oi', 0)/1000:,.0f}K" if data.get("oi") else "OI --"
    fund_txt = f"费率 {data.get('funding', 0)*100:+.3f}%" if "funding" in data else "费率 --"
    ls_txt = f"大户多空 {data.get('ls', 0):.2f}" if data.get("ls") else "多空 --"
    lines.append(f"{oi_txt} · {fund_txt} · {ls_txt} · 主动买卖 {taker:.2f}")
    lines.append("需完整分析请说「分析BTC」")
    return "\n".join(lines)


def main():
    data = get_price_and_deriv()
    price = data.get("price")
    if price is None:
        print("BTC price unavailable — silent", flush=True)
        sys.exit(0)

    state = load_state()
    now = time.time()
    changed = False
    messages = []

    for key, zone in ZONES.items():
        in_zone = zone["lo"] <= price <= zone["hi"]
        last = state.get(key, {})
        last_alerted = last.get("last_alerted", False)
        last_time = last.get("time", 0.0)

        if in_zone:
            if not last_alerted or (now - last_time) > COOLDOWN_SECONDS:
                messages.append(build_message(price, key, zone, data))
                state[key] = {"last_alerted": True, "time": now, "price": price}
                changed = True
        else:
            # 出区间重置（不清 time，保留触发轨迹）
            if last_alerted:
                state[key] = {"last_alerted": False, "time": last_time}
                changed = True

    if changed:
        save_state(state)
    if not messages:
        sys.exit(0)

    if os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") != "1":
        print("TB_PUSH DISABLED | automated Telegram delivery is off", flush=True)
        return

    try:
        from telegram_direct import send_telegram_direct
        for m in messages:
            ok, reason = send_telegram_direct(TG_TARGET, m)
            print(f"TB_PUSH {'OK' if ok else 'FAIL'} | {reason}", flush=True)
    except Exception as e:
        print(f"TB_ERROR {e}", flush=True)


if __name__ == "__main__":
    print("已退役·生产权威为 keylevel_guard.py", flush=True)
    raise SystemExit(0)
