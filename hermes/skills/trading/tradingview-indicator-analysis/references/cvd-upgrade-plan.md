# CVD 升级方案：C级→A级 (Binance aggTrades) · 2026-06-18

## 现状
- CVD 等级：**C级**（K线估算）
- 影响：订单流评分×0.6 · 仓位上限半仓 · 需多重确认
- BTC/XAU 分析卡均受降权

## 方案1：REST轮询（推荐·2小时）

```python
# 每30秒轮询 Binance aggTrades
url = "https://fapi.binance.com/fapi/v1/aggTrades?symbol=BTCUSDT&limit=500"
# 计算 CVD = sum(buy_qty - sell_qty)
# 写入 data/cvd_btcusdt.json → 行情守望读取
```

## 方案2：WebSocket（4小时）

```python
import websockets
async with websockets.connect("wss://fstream.binance.com/ws/btcusdt@aggTrade") as ws:
    # 实时流 → CVD A级
```

## 评级映射

| 来源 | 等级 | 订单流分 |
|------|------|----------|
| Binance aggTrades WS | A | ×1.0 (+1.4分) |
| Binance aggTrades REST | B | ×0.9 (+1.2分) |
| Binance Taker统计(B级) | B | ×0.9 |
| K线估算 | C | ×0.6 |

## 接入后提分
BTC分析卡：8-9/13 → 10-12/13 (+2-3分)
仓位从轻仓→常规/高置信
