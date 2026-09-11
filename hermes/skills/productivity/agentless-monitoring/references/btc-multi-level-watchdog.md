# BTC 多级关键位看门狗

从一次实时分析会话中产生的实战脚本，在棠溪反复问"现在呢"之后，自动部署了价格监控。

## 场景

分析 BTC 时给出两种走法（破前低 vs 守前低），并承诺"到关键位推你"。用户表示"**因为我每次都要提醒你设置的话好麻烦啊**" — 意味着 agent 应该在承诺时立刻创建监控，而非事后等用户催促。

## 脚本结构

```python
#!/usr/bin/env python3
"""BTC 价格看门狗 — 监控关键位 63,270 / 62,272"""
import json, urllib.request, sys

LEVEL_1 = 63270   # 前低
LEVEL_2 = 62272   # 6/18大底

def get_btc_price():
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            return float(data["price"])
    except Exception:
        return None

price = get_btc_price()
if price is None:
    sys.exit(0)

msg = None

if price <= LEVEL_1 + 50 and price >= LEVEL_1 - 50:
    msg = f"BTC 触及前低 {LEVEL_1}\n现价: {price:.2f}\n— 若破: 看 {LEVEL_2}\n— 若守: 反弹看 64,600-65,000"
elif price < LEVEL_1 - 50 and price > LEVEL_2 + 100:
    msg = f"BTC 已跌破前低 {LEVEL_1}\n现价: {price:.2f}\n下一目标: {LEVEL_2}"
elif price <= LEVEL_2 + 50 and price >= LEVEL_2 - 50:
    msg = f"BTC 触及大底 {LEVEL_2}\n现价: {price:.2f}\n— 若破: 趋势转空\n— 若守: 日线双底"
elif price < LEVEL_2 - 50:
    msg = f"BTC 跌破大底 {LEVEL_2}\n现价: {price:.2f}\n下方空间打开"

if msg:
    print(msg)
```

## 关键设计点

| 点 | 说明 |
|:--|:--|
| 三级预警 | 触及前低(±50) / 跌破前低但未到大底 / 触及大底 / 跌破大底 |
| 静默退出 | 条件不满足时 `sys.exit(0)` — 空 stdout = 不推送 |
| 10分钟间隔 | `*/10 * * * *` cron 表达式，非频繁但足够捕捉破位 |
| 原链推送 | `deliver='origin'` 自动回到当前对话话题 |

## 创建步骤

```python
# 1. 写脚本到 ~/.hermes/scripts/btc_price_watchdog.py
# 2. 创建 cron
cronjob(
    action='create',
    name='BTC 关键位看门狗',
    schedule='*/10 * * * *',
    script='btc_price_watchdog.py',
    no_agent=True,
    deliver='origin',
)
```

## 注意

- 脚本路径必须相对于 `~/.hermes/scripts/`，或用绝对路径会报错
- `repeat` 在创建后显示为 `once` 但实际 cron 表达式 `*/10 * * * *` 会永久循环
- 检查：`cronjob(action='list')` 确认 schedule 和 state 正确
