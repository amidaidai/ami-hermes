# 日内止损止盈方法论 v6.9.11

## 问题

旧算法用固定百分比（`nearest_level * 0.97` / `nearest_level * 1.03`）—— BTC 3% 止盈 ≈ 1,920 点，是周线/波段目标，不适用于 5m/15m 日内交易。

## 算法

### 核心常数
- `ATR_MULTIPLIER = 2.0`（2× 15m ATR 为最小止损距离）
- `MIN_STOP_PCT = 0.003`（0.3% 日内止损底线）
- `NOISE_FILTER_PCT = 0.003`（0.3% 以内的关键位视为噪音跳过）

### 止损计算
```
atr_stop = max(ATR_15m × 2.0, price × 0.003)
空头 stop = max(price + atr_stop, _meaningful_level_above(price))
多头 stop = min(price - atr_stop, _meaningful_level_below(price))
```

### 止盈计算
```
_meaningful_level_above(price):
  跳过 price × (1 + 0.003) 以内的位
  在 ("vah","vwap","high","poc","ema21") 中找最近
  三周期 (15m/1h/4h) 遍历
  兜底: price × 1.008

_meaningful_level_below(price):
  跳过 price × (1 - 0.003) 以内的位
  在 ("val","low","npoc","poc") 中找最近
  兜底: price × 0.992
```

### R:R 底线
```
rr = abs(tp - price) / abs(stop - price)
if rr < 2.0:
    标注 ⚠R:R不足
    不为了达标而伪造 target
```

## 参考代码

`hermes/scripts/auto_card.py` → `_compact_card()` 函数

## 陷阱

- BTC 紧致结构（价夹在 POC-VAL 之间 ~500 点）时 R:R 不达标是正常的。市场不给机会时不要编造目标。
- 0.3% 噪音阈值对于 BTC（~192 点）和 XAU（~12 点）都适用。
- klines 数据源来自 Binance/Yahoo K 线计算，可能与 TV SVP 指标值有差异（如 TV VAL 64,136 vs 系统 VAL 63,871）。棠溪以 TV 为主源，但 auto_card 以系统数据出卡。差异 ≤0.5% 可接受。
