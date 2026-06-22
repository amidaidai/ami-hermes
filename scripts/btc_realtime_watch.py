#!/usr/bin/env python3
"""
BTCUSDT 实时巡查守护进程 —— 完全静默模式。
每 10 秒检查价格 + Taker 数据，只有条件触发才输出。
零干扰。"""
import json, time, urllib.request, sys

CHECK_INTERVAL = 10
TARGET_PRICE = 64600
BUY_RATIO_THRESHOLD = 1.5

def get_json(url):
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1)
    return None

while True:
    p = get_json('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT')
    if p: cp = float(p['price'])
    else: time.sleep(CHECK_INTERVAL); continue

    closes = []
    k = get_json('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=3')
    if k and len(k) >= 3:
        closes = [float(x[4]) for x in k]
        kline_ok = all(c >= TARGET_PRICE for c in closes)
    else: kline_ok = False

    t = get_json('https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=5m&limit=3&type=USD')
    ratios = []
    if t and len(t) >= 3:
        for x in t:
            b, s = float(x.get('buyVol', 0)), float(x.get('sellVol', 0))
            if s > 0: ratios.append(b / s)
    avg_r = sum(ratios)/len(ratios) if ratios else 0
    taker_ok = avg_r > BUY_RATIO_THRESHOLD

    if cp >= TARGET_PRICE and kline_ok and taker_ok and closes:
        print(f"【条件达成】BTCUSDT 确认站稳 ${TARGET_PRICE:,}！")
        print(f"价格=${cp:,.2f} | K线={', '.join(f'${c:,.2f}' for c in closes)} | Taker比={avg_r:.2f}")
        sys.exit(0)

    time.sleep(CHECK_INTERVAL)
