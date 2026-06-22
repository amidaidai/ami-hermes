#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · 10秒快速守护 v2.0
轻量 sub-minute 检测层：CVD背离 · 扫荡 · 吸收
配合 1m v3多因子告警器，不替代

运行: python btc_fast_daemon.py (后台常驻 · 10秒轮询)
"""

import json, os, sys, time, urllib.request
from collections import deque
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DIR = Path.home() / "AppData/Local/hermes/data"
PENDING = DIR / "btc_pending.txt"
STATE = DIR / "fast_daemon_state.json"
TV_DATA = DIR / "btc_tv_data.json"
COOLDOWN = {}  # event_type → last_fired_ts
COOLDOWN_S = 300  # 5min 事件冷却
HEATUP = 8  # 启动后前8轮抑制

def emit(s: str):
    sys.stdout.write(s.encode("ascii","replace").decode("ascii").rstrip()+"\n")
    sys.stdout.flush()

def _f(v, d=0.0):
    try: return float(v)
    except: return d

def get_price():
    try:
        r=urllib.request.Request("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            headers={"User-Agent":"D/1.0"})
        with urllib.request.urlopen(r,timeout=4) as resp:
            return float(json.loads(resp.read())["price"])
    except: return 0.0

def get_tv():
    try:
        if TV_DATA.exists():
            return json.loads(TV_DATA.read_text(encoding="utf-8"))
    except: pass
    return {}

def write_event(direction: str, signal: str, msg: str):
    line = f"{direction} | {signal}: {msg}"
    with open(PENDING,"a",encoding="utf-8") as f:
        f.write(f"{line}\n---\n")

def main():
    cnt = 0
    price_hist = deque(maxlen=36)   # 6min of 10s = 36 samples
    cvd_hist = deque(maxlen=36)
    last_sweep = {"val": None, "vah": None}  # track sweep states

    while True:
        try:
            cnt += 1
            price = get_price()
            if price <= 0:
                time.sleep(10); continue
            price_hist.append(price)

            tv = get_tv()
            vah = _f(tv.get("vah"), 64460)
            val = _f(tv.get("val"), 63894)
            vwap = _f(tv.get("vwap"), 64200)
            cvd = _f(tv.get("cvd"), 0)
            cvd_slope = _f(tv.get("cvd_slope"), 0)
            cvd_hist.append(cvd)

            now = time.time()

            # ═══ CVD背离 ═══ (price HH + CVD LH or vice versa)
            if cnt > HEATUP and len(price_hist) >= 24 and len(cvd_hist) >= 24:
                p_fst = list(price_hist)[-24:-12]; p_snd = list(price_hist)[-12:]
                c_fst = list(cvd_hist)[-24:-12]; c_snd = list(cvd_hist)[-12:]
                if p_fst and p_snd and c_fst and c_snd:
                    p_avg1 = sum(p_fst)/len(p_fst); p_avg2 = sum(p_snd)/len(p_snd)
                    c_avg1 = sum(c_fst)/len(c_fst); c_avg2 = sum(c_snd)/len(c_snd)
                    last_fired = COOLDOWN.get("cvd_div",0)

                    if p_avg2 > p_avg1 and c_avg2 < c_avg1 and now-last_fired > COOLDOWN_S:
                        COOLDOWN["cvd_div"] = now
                        write_event("↓做空", "🔮CVD空背离",
                            f"价{p_avg2:.0f}>前{p_avg1:.0f}·CVD{c_avg2:.0f}<前{c_avg1:.0f}")

                    if p_avg2 < p_avg1 and c_avg2 > c_avg1 and now-last_fired > COOLDOWN_S:
                        COOLDOWN["cvd_div"] = now
                        write_event("↑做多", "🔮CVD多背离",
                            f"价{p_avg2:.0f}<前{p_avg1:.0f}·CVD{c_avg2:.0f}>前{c_avg1:.0f}")

            # ═══ 扫荡 ═══ (cross VAH/VAL and recover)
            if cnt > 5 and vah > 0 and val > 0:
                last_fired = COOLDOWN.get("sweep",0)
                if price < val and last_sweep["val"] is None:
                    last_sweep["val"] = price
                elif last_sweep["val"] is not None and price > val:
                    dist = abs(last_sweep["val"] - val)
                    if dist > 10 and now-last_fired > COOLDOWN_S:
                        COOLDOWN["sweep"] = now
                        write_event("↑做多", "🎯VAL扫荡",
                            f"触{val:.0f}下{dist:.0f}·已回收")
                    last_sweep["val"] = None

                if price > vah and last_sweep["vah"] is None:
                    last_sweep["vah"] = price
                elif last_sweep["vah"] is not None and price < vah:
                    dist = abs(last_sweep["vah"] - vah)
                    if dist > 10 and now-last_fired > COOLDOWN_S:
                        COOLDOWN["sweep"] = now
                        write_event("↓做空", "🎯VAH扫荡",
                            f"触{vah:.0f}上{dist:.0f}·已回收")
                    last_sweep["vah"] = None

            # ═══ 吸收/派发 ═══ (CVD moves, price stays flat)
            if len(cvd_hist) >= 18 and len(price_hist) >= 18:
                cvd_range = max(list(cvd_hist)[-18:]) - min(list(cvd_hist)[-18:])
                price_range = max(list(price_hist)[-18:]) - min(list(price_hist)[-18:])
                last_fired = COOLDOWN.get("absorb",0)
                if cvd_range > 150 and price_range < 30 and now-last_fired > COOLDOWN_S:
                    direction = "↑做多" if cvd > 0 else "↓做空"
                    label = "💧CVD吸收" if cvd > 0 else "💧CVD派发"
                    COOLDOWN["absorb"] = now
                    write_event(direction, label,
                        f"价不动(P-range{price_range:.0f})·CVD波动{cvd_range:.0f}")

            # Save state periodically
            if cnt % 60 == 0:
                try:
                    STATE.parent.mkdir(parents=True,exist_ok=True)
                    STATE.write_text(json.dumps({
                        "last_price":price,"cnt":cnt,"cvd":cvd,"vwap":vwap,
                        "ts":datetime.now(TZ).strftime("%H:%M:%S")},ensure_ascii=False,indent=2),encoding="utf-8")
                except: pass

            time.sleep(10)

        except KeyboardInterrupt:
            emit("daemon stopped")
            break
        except Exception as e:
            emit(f"ERROR: {str(e)[:80]}")
            time.sleep(10)

if __name__ == "__main__":
    main()
