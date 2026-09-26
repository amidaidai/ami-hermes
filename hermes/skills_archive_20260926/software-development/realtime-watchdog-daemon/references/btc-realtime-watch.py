#!/usr/bin/env python3
"""
BTCUSDT 实时巡查守护进程参考实现。
用作 realtime-watchdog-daemon 技能的可复用模板。
"""
import json, time, urllib.request, sys

CHECK_INTERVAL = 10       # 轮询间隔（秒）
TARGET_PRICE = 64600       # 目标价格条件
BUY_RATIO_THRESHOLD = 1.5  # Taker 买卖比阈值

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
    # 1) 当前价格
    p = get_json('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT')
    if p: cp = float(p['price'])
    else: time.sleep(CHECK_INTERVAL); continue

    # 2) 15m K线收盘 — 初始化避免未绑定
    closes = []
    k = get_json('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=3')
    if k and len(k) >= 3:
        closes = [float(x[4]) for x in k]
        kline_ok = all(c >= TARGET_PRICE for c in closes)
    else: kline_ok = False

    # 3) Taker 买卖比
    t = get_json('https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=5m&limit=3&type=USD')
    ratios = []
    if t and len(t) >= 3:
        for x in t:
            b, s = float(x.get('buyVol', 0)), float(x.get('sellVol', 0))
            if s > 0: ratios.append(b / s)
    avg_r = sum(ratios) / len(ratios) if ratios else 0
    taker_ok = avg_r > BUY_RATIO_THRESHOLD

    # 4) 条件判断 — 只在触发时输出
    if cp >= TARGET_PRICE and kline_ok and taker_ok and closes:
        print(f"【条件达成】BTCUSDT 确认站稳 ${TARGET_PRICE:,}！")
        print(f"价格=${cp:,.2f} | "
              f"K线={', '.join(f'${c:,.2f}' for c in closes)} | "
              f"Taker比={avg_r:.2f}")
        sys.exit(0)

    time.sleep(CHECK_INTERVAL)
