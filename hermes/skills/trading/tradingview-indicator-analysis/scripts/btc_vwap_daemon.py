#!/usr/bin/env python3
"""BTC多因子守护模板 — 10s轮询+60s全数据刷新，零token
用法: terminal(background=true) python btc_vwap_daemon.py
     (不加 notify_on_complete=true, 避免回溯噪音)
杀: terminal("taskkill /PID <pid> /F")

多因子评分 (6项):
1. 价vsVWAP (±30pt) — 最重要权重
2. EMA死叉/金叉 (±20pt)
3. Taker卖/买压 (±20pt)
4. 日高回撤 (+15pt)
5. 大户多空偏度 (±15pt)
6. 近5K趋势 (±10pt)
触发阈值: ≥75pt

当指标判X时的处理:
- 拆解矛盾原因 (价在VWAP下但EMA多头 = 结构冲突)
- 多空优先级判断
- 双路触发: VAL守+回VWAP→做多 / 放量砸穿VAL→做空
"""

import json, time, urllib.request, sys
from datetime import datetime, timezone, timedelta

tz = timezone(timedelta(hours=8))

# ====== 品种参数 ======
SYMBOL = "BTCUSDT"
VWAP = 64218.0      # 来自TV指标 S VWAP
VAL = 63946.0
DO = 63312.0
POC = 64566.0
STOP_LONG = 63800.0
STOP_SHORT = 64218.0

# ====== HTTP 工具 ======
def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "HermesDaemon/1.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def get_klines(interval="15m", limit=30):
    return http_get(f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval={interval}&limit={limit}")

# ====== 评分引擎 ======
def calc_score(price, klines):
    """返回 (short_score, long_score, reasons)"""
    s, l = 0, 0
    r = []
    closes = [float(k[4]) for k in klines[-60:]]
    highs = [float(k[2]) for k in klines[-60:]]
    lows = [float(k[3]) for k in klines[-60:]]
    vols = [float(k[5]) for k in klines[-60:]]
    opens = [float(k[1]) for k in klines[-60:]]

    # 1. 价vsVWAP
    pAbove, pBelow = price > VWAP, price < VWAP
    l += 30 if pAbove else 10 if price > VWAP - 80 else 0
    s += 30 if pBelow else 10 if price < VWAP + 80 else 0
    if pAbove: r.append(f"VWAP上 [+{30 if pAbove else 10}]")
    elif pBelow: r.append(f"VWAP下 [+{30 if pBelow else 10}]")

    # 2. EMA
    def ema(data, n):
        k = 2/(n+1); result = [data[0]]
        for v in data[1:]: result.append(v*k + result[-1]*(1-k))
        return result[-1]
    e9, e21 = ema(closes,9), ema(closes,21)
    if e9 < e21: s += 20; r.append(f"EMA死叉 [+20]")
    elif e9 > e21: l += 20; r.append(f"EMA金叉 [+20]")

    # 3. Taker
    try:
        tk = http_get(f"https://fapi.binance.com/futures/data/takerlongshortRatio?symbol={SYMBOL}&period=5m&limit=1")
        if tk:
            tr = float(tk[0]["buySellRatio"])
            if tr < 0.8: s += 20; r.append(f"Taker卖{tr:.2f} [+20]")
            elif tr > 1.2: l += 20; r.append(f"Taker买{tr:.2f} [+20]")
    except: pass

    # 4. 量能
    avg_v = sum(vols[-5:])/5 if len(vols)>=5 else 1
    last_v = vols[-1] if vols else 0
    vh = last_v > avg_v * 1.5
    last_cp = (closes[-1]-lows[-1])/(highs[-1]-lows[-1]) if (highs[-1]-lows[-1])>0 else 0.5
    if vh and last_cp >= 0.7: l += 10; r.append("放量上收 [+10]")
    elif vh and last_cp <= 0.3: s += 10; r.append("放量下收 [+10]")

    # 5. LS
    try:
        ls = http_get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={SYMBOL}&period=5m&limit=1")
        if ls:
            lsr = float(ls[0]["longShortRatio"])
            if lsr < 0.9: s += 10; r.append(f"LS偏空{lsr:.2f} [+10]")
            elif lsr > 1.2: l += 10; r.append(f"LS偏多{lsr:.2f} [+10]")
    except: pass

    # 6. K线趋势
    down5 = sum(1 for i in range(1, min(6,len(closes))) if closes[i] < closes[i-1])
    up5 = min(5, len(closes)) - down5
    if down5 >= 3: s += 10; r.append(f"近5K{down5}/5跌 [+10]")
    if up5 >= 3: l += 10; r.append(f"近5K{up5}/5涨 [+10]")

    return min(s,100), min(l,100), r

# ====== 主循环 ======
print("[init] 静默初始化", flush=True)
while True:
    try:
        p = float(http_get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}")["price"])
        k = get_klines()
        init_s, init_l, _ = calc_score(p, k)
        last_state = "short" if init_s >= init_l else "long"
        last_refresh = time.time()
        alerted = set()
        break
    except:
        time.sleep(10)

while True:
    time.sleep(10)
    ts = datetime.now(tz).strftime("%H:%M")
    try:
        price = float(http_get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}")["price"])
    except:
        continue

    if time.time() - last_refresh > 60:
        try:
            klines = get_klines()
            vol_surge = False
            if klines:
                vols = [float(k[5]) for k in klines[-5:]]
                all_v = [float(k[5]) for k in klines]
                avg_v = sum(all_v)/len(all_v) if all_v else 1
                vol_surge = vols[-1] > avg_v * 1.8
                closes5 = [float(k[4]) for k in klines[-5:]]
                down5 = sum(1 for i in range(1,5) if closes5[i] < closes5[i-1])
        except:
            pass

        s_score, l_score, reasons = calc_score(price, klines)
        last_refresh = time.time()

        # 双路触发
        now_state = "short" if s_score >= 75 and s_score > l_score else "long" if l_score >= 75 and l_score > s_score else "wait"

        if now_state != last_state and now_state != "wait":
            last_state = now_state
            ts_key = int(time.time()) // 300 * 300
            if ts_key not in alerted:
                tag = "🔴 BTC做空" if now_state == "short" else "🟢 BTC做多"
                print(f"\n{tag}信号 · {ts} · 评分空{s_score}/多{l_score}", flush=True)
                for rr in reasons[-4:]:
                    print(f"  • {rr}", flush=True)
                print(f"  止损`{STOP_SHORT if now_state=='short' else STOP_LONG}` · 止盈`{VAL if now_state=='short' else POC}`/`{DO if now_state=='short' else POC+200}`", flush=True)
                alerted.add(ts_key)

    # 快速急跌检测 (10s级)
    try:
        cur = float(http_get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}")["price"])
        if cur < VWAP - 100 and cur < price - 100:
            print(f"⚠ 快速下跌 · {ts} · 现价`{cur:,.0f}` · VWAP下`${VWAP-cur:,.0f}`", flush=True)
            print(f"  目标`{VAL:,.0f}`/`{DO:,.0f}`", flush=True)
    except:
        pass
