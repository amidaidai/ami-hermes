#!/usr/bin/env python3
"""检查 BTCUSDT 是否满足偏多确认条件。零 token 消耗，静默运行。"""
import json
import urllib.request
import sys

def get_json(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return None

# 1. 当前价格
price_data = get_json('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT')
if not price_data:
    sys.exit(0)  # 静默退出
current_price = float(price_data['price'])

# 2. 最近3根15m K线收盘价
klines = get_json('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=3')
if not klines or len(klines) < 3:
    sys.exit(0)

closes = [float(k[4]) for k in klines]  # index 4 = close
all_above_64600 = all(c >= 64600 for c in closes)

# 3. Taker buy/sell volume ratio（最近3个5m周期）
taker = get_json('https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=5m&limit=3&type=USD')
if not taker or len(taker) < 3:
    sys.exit(0)

buy_ratios = []
for t in taker:
    buy_vol = float(t.get('buyVol', 0))
    sell_vol = float(t.get('sellVol', 0))
    if sell_vol > 0:
        buy_ratios.append(buy_vol / sell_vol)

avg_buy_ratio = sum(buy_ratios) / len(buy_ratios) if buy_ratios else 0

# 4. 条件判断
if current_price >= 64600 and all_above_64600 and avg_buy_ratio > 1.5:
    print(f"【条件达成】BTCUSDT 确认站稳 $64,600!")
    print(f"当前价格：${current_price:,.2f}")
    print(f"最近3根15m收盘：{', '.join(f'${c:,.2f}' for c in closes)}")
    print(f"Taker 平均买卖比：{avg_buy_ratio:.2f}")
    print(f"偏多信号确认，可以入场。")
else:
    # 静默退出——no_agent模式下空输出=不通知
    sys.exit(0)
