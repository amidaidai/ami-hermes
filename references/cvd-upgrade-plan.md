# CVD 升级方案：C级→A级 (Binance aggTrades)

## 现状
- CVD 等级：**C级**（K线估算）
- 影响：订单流评分×0.6 · 仓位上限半仓 · 需多重确认
- 所有分析卡（BTC+XAU）均受降权影响

## 目标
接入 Binance Futures `aggTrades` WebSocket → CVD A级 → 订单流评分恢复 100%

## 方案

### Step 1: 接入 Binance aggTrades WebSocket

```python
# 新增 hermes/scripts/cvd_collector.py
import asyncio, json, websockets

BINANCE_WS = "wss://fstream.binance.com/ws"

async def stream_agg_trades(symbol: str = "btcusdt"):
    url = f"{BINANCE_WS}/{symbol}@aggTrade"
    async with websockets.connect(url) as ws:
        while True:
            msg = await ws.recv()
            trade = json.loads(msg)
            # aggTrade 包含: price, quantity, is_buyer_maker
            # is_buyer_maker=True → 主动卖出 (taker sell)
            # is_buyer_maker=False → 主动买入 (taker buy)
            yield trade

def calculate_cvd(trades: list) -> dict:
    """从 aggTrades 计算累积成交量 Delta"""
    delta = 0
    for t in trades:
        qty = float(t['q'])
        if t['m']:  # is_buyer_maker = True = sell
            delta -= qty
        else:       # is_buyer_maker = False = buy  
            delta += qty
    return {
        "cvd": delta,
        "quality": "A",           # 真实 aggTrades
        "source": "Binance aggTrades WS",
        "last_trade_id": trades[-1]['a'] if trades else None,
    }
```

### Step 2: 缓存写入 + 行情守望接入

```python
# 每 10 秒写入 data/cvd_btcusdt.json
# 行情守望.py 读取 → 替换当前 C 级估算
# 博弈段 CVD 等级从 C→A
```

### Step 3: 评分体系自动恢复

接入后：
- 订单流评分：×1.0（不再×0.6）
- 仓位上限：正常（不再半仓）
- CVD C级多重确认 → CVD A级单源确认即有效

## 预期提分
- BTC 分析卡：8-9/13 → 10-12/13（+2-3分）
- 订单流段从0.6分→2分（+1.4分）
- 仓位从轻仓→常规/高置信

## 替代方案（如果 WS 复杂度太高）
使用 Binance REST API 拉取 aggTrades：
```
GET https://fapi.binance.com/fapi/v1/aggTrades?symbol=BTCUSDT&limit=500
```
每 30 秒轮询 → CVD B 级（非实时但比 K 线估算好）

## 实施时间
- REST 轮询方案：2 小时
- WebSocket 方案：4 小时
- 集成到行情守望：1 小时
