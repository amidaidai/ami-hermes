#!/usr/bin/env python3
"""
多因子评分后台守护进程模板
用途：10s轮询，多因子评分≥75分时推送通知
配置：修改 CONFIG 字典中的关键位和参数
启动：terminal(background=true) — 绝对不加 notify_on_complete=true，否则杀进程会产生回溯通知
杀守护用 terminal("taskkill /PID <pid> /F")，不用 process(action='kill')
"""
import json
import time
import urllib.request
import sys
from datetime import datetime, timezone, timedelta

tz = timezone(timedelta(hours=8))

# ========== 配置区 ==========
CONFIG = {
    "symbol": "BTCUSDT",
    "vwap": 64235.0,
    "stop": 64580.0,    # 止损位
    "tp1": 63946.0,     # 止盈1
    "tp2": 63312.0,     # 止盈2
    "interval": 10,      # 轮询秒数
    "refresh_interval": 60,  # 刷新因子秒数
    "threshold": 75,     # 推送阈值
}

# ========== 数据采集 ==========
def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "HermesDaemon/1.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def calc_vwap(klines):
    vol_sum = 0; vwap_sum = 0
    for k in klines[-50:]:
        hl2 = (float(k[2]) + float(k[3])) / 2
        vol = float(k[5])
        vwap_sum += hl2 * vol
        vol_sum += vol
    return vwap_sum / vol_sum if vol_sum else CONFIG["vwap"]

def calc_ema(klines, period):
    closes = [float(k[4]) for k in klines[-60:]]
    if len(closes) < period: return None
    k = 2 / (period + 1); r = closes[0]
    for v in closes[1:]: r = v * k + r * (1 - k)
    return r

def refresh_cache():
    s = {}
    try:
        price = float(http_get("https://api.binance.com/api/v3/ticker/price?symbol=" + CONFIG["symbol"])["price"])
        s["price"] = price
        ticker = http_get("https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=" + CONFIG["symbol"])
        s["daily_high"] = float(ticker["highPrice"])
        s["daily_low"] = float(ticker["lowPrice"])
        klines = http_get("https://api.binance.com/api/v3/klines?symbol=" + CONFIG["symbol"] + "&interval=15m&limit=60")
        s["klines"] = klines
        s["vwap"] = calc_vwap(klines)
        s["ema9"] = calc_ema(klines, 9)
        s["ema21"] = calc_ema(klines, 21)
        try:
            tk = http_get("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=" + CONFIG["symbol"] + "&period=5m&limit=1")
            if tk: s["taker"] = float(tk[0]["buySellRatio"])
        except: pass
        try:
            gl = http_get("https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=" + CONFIG["symbol"] + "&period=5m&limit=1")
            if gl: s["ls_ratio"] = float(gl[0]["longShortRatio"])
        except: pass
    except: pass
    return s

# ========== 评分 ==========
def score_short(cache):
    total = 0; signals = []
    p = cache.get("price", 0); v = cache.get("vwap", CONFIG["vwap"])
    if p < v: total += 30; signals.append(f"破VWAP下`${v-p:,.0f}` [+30]")
    elif p < v + 80: total += 10; signals.append(f"紧贴VWAP [+10]")
    e9, e21 = cache.get("ema9"), cache.get("ema21")
    if e9 and e21 and e9 < e21: total += 20; signals.append(f"EMA死叉 {e9:,.0f}<{e21:,.0f} [+20]")
    t = cache.get("taker")
    if t and t < 0.8: total += 20; signals.append(f"Taker卖{t:.2f} [+20]")
    elif t and t < 0.95: total += 10; signals.append(f"Taker偏卖{t:.2f} [+10]")
    h = cache.get("daily_high", 0)
    if h and p < h - (h - v) * 0.5: total += 15; signals.append(f"日高回撤深 [+15]")
    ls = cache.get("ls_ratio")
    if ls and ls < 0.95: total += 15; signals.append(f"大户比{ls:.2f}偏空 [+15]")
    elif ls and ls < 1.2: total += 5; signals.append(f"大户比{ls:.2f}中性偏空 [+5]")
    klines = cache.get("klines", [])
    if len(klines) >= 5:
        last5 = klines[-5:]
        dn = sum(1 for i in range(1, 6) if float(last5[i][4]) <= float(last5[i-1][4]))
        if dn >= 3: total += 10; signals.append(f"近5K{dn}/5看跌 [+10]")
    return total, signals

def score_long(cache):
    total = 0; signals = []
    p = cache.get("price", 0); v = cache.get("vwap", CONFIG["vwap"])
    if p > v: total += 30; signals.append(f"VWAP上`${p-v:,.0f}` [+30]")
    elif p > v - 80: total += 10; signals.append(f"紧贴VWAP下方 [+10]")
    e9, e21 = cache.get("ema9"), cache.get("ema21")
    if e9 and e21 and e9 > e21: total += 20; signals.append(f"EMA金叉 {e9:,.0f}>{e21:,.0f} [+20]")
    t = cache.get("taker")
    if t and t > 1.2: total += 20; signals.append(f"Taker买{t:.2f} [+20]")
    elif t and t > 1.05: total += 10; signals.append(f"Taker偏买{t:.2f} [+10]")
    ls = cache.get("ls_ratio")
    if ls and ls > 1.2: total += 15; signals.append(f"大户比{ls:.2f}偏多 [+15]")
    klines = cache.get("klines", [])
    if len(klines) >= 5:
        last5 = klines[-5:]
        up = sum(1 for i in range(1, 6) if float(last5[i][4]) >= float(last5[i-1][4]))
        if up >= 3: total += 10; signals.append(f"近5K{up}/5看涨 [+10]")
    return total, signals

# ========== 主循环 ==========
print(f"[初始化] {CONFIG['symbol']}多因子守护启动", flush=True)

last_side = "init"
cache = {}
last_refresh = 0
last_report_min = -1
TH = CONFIG["threshold"]

while True:
    now = datetime.now(tz)
    ts = now.strftime("%H:%M")
    if time.time() - last_refresh > CONFIG["refresh_interval"]:
        cache = refresh_cache()
        last_refresh = time.time()
    price = cache.get("price", 0)
    if not price:
        time.sleep(CONFIG["interval"]); continue
    short_pts, short_r = score_short(cache)
    long_pts, long_r = score_long(cache)
    # 判断状态
    if short_pts >= TH and short_pts > long_pts:
        side = "short_ready"
    elif long_pts >= TH and long_pts > short_pts:
        side = "long_ready"
    else:
        side = "neutral"
    # 状态变化或新分钟触发
    cur_min = now.minute
    if side != last_side or (side != "neutral" and cur_min != last_report_min):
        last_side = side; last_report_min = cur_min
        if side == "short_ready":
            print(f"\n🔴 {CONFIG['symbol']}做空 {ts} · {short_pts}/{TH}")
            for r in short_r: print(f"  • {r}")
            print(f"  现价`{price:,.0f}` · VWAP`{cache.get('vwap',CONFIG['vwap']):,.0f}`")
            print(f"  止损`{CONFIG['stop']:,.0f}` · 止盈`{CONFIG['tp1']:,.0f}`/`{CONFIG['tp2']:,.0f}`\n", flush=True)
            sys.exit(0)
        elif side == "long_ready":
            print(f"\n🟢 {CONFIG['symbol']}做多 {ts} · {long_pts}/{TH}")
            for r in long_r: print(f"  • {r}")
            print(f"  现价`{price:,.0f}` · VWAP`{cache.get('vwap',CONFIG['vwap']):,.0f}`\n", flush=True)
            sys.exit(0)
        # neutral = 静默
    time.sleep(CONFIG["interval"])
