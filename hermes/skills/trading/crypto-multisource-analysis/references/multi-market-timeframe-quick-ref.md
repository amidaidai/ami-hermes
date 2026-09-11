# 多市场时间框架速查 v1.0

> 2026-06-29 · 全市场五层TF统一 · 主周期=截图周期

## 速查表

| 市场 | 品种示例 | TV Symbol | 五层 | 主周期 | SVP行动格 | 副指标 |
|------|---------|-----------|:--:|:--:|:--:|:--:|
| 加密 | BTC/ETH/SOL | BINANCE:BTCUSDT.P | D-4h-1h-**15m**-5m | 15m | 有效 | 有效 |
| 黄金 | XAUUSD | FX:XAUUSD | D-4h-1h-15m-**5m** | 5m | VWAP/EMA | 罢工 |
| 白银 | XAGUSD | FX:XAGUSD | D-4h-1h-15m-**5m** | 5m | VWAP/EMA | 罢工 |
| 外汇 | EURUSD GBPJPY | FX:EURUSD | D-4h-1h-**15m**-5m | 15m | VWAP/EMA | 罢工 |
| 股票 | AAPL TSLA NVDA | NASDAQ:AAPL | D-4h-**1h**-15m-5m | 1h | VWAP/EMA | 罢工 |
| 期货 | ES NQ CL | CME:ES1! | D-4h-1h-**15m**-5m | 15m | VWAP/EMA | 罢工 |

## 读取顺序

每层周期读取相同的四项数据：

D: OHLCV summary (15 bars) -> 等15-30s
4h: OHLCV + pine_tables + pine_labels + pine_lines -> 等8-12s
1h: 同上 -> 等8s
15m: 同上 + screenshot -> 等15-30s
5m: OHLCV + pine_tables -> 等15-30s

回切主周期后全屏截图。

## SVP指标在非加密品种

主指标 VWAP/EMA/POC/VAH/VAL/labels/lines 始终有效。
副指标自动罢工显示"非加密品种"。
行动格可能不展示方向/进场/磁吸行。
处理：非加密品种只读主指标数据，跳过副指标采集。
