# Backtest Honest Interpretation Rules

## Core Principle

**Backtest numbers are NEVER actionable out of the box.** They require honest interpretation before any trading decision.

## Known Inflation Sources

### 1. Trend Bias
- VWAP反抽在单边趋势中胜率可膨胀到90%+，因为"卖VWAP反弹"在跌势里几乎全赢
- 同一模型在震荡市中胜率可能降到50%以下
- **Rule**: Always run at least 2 market regimes (trend + range) before quoting any win rate

### 2. VWAP Band Distance Inflation
- 入场设VWAP（理论最优），止盈设Band2（2 ATR），RR自然≥2
- 实际成交极少在精确VWAP价，滑点吃掉0.1-0.3%
- **Rule**: Always apply `slippage_pct=0.10` minimum

### 3. Model Crowding
- 当12引擎的EMA趋势在每根K线都开仓时，会挤掉五模型信号
- 需要model diversity规则：同模型冷却5根K线，五模型+10分优先级
- **Rule**: Verify no single model >50% of total trades

### 4. Simplified Estimation
- 回测VAH/VAL/POC是简化估算（滚动窗口midpoint）
- 回测CVD是近似值（taker_buy_vol - (volume - taker_buy_vol)）
- **Rule**: Mark backtest results with "estimated indicators" flag

### 5. Insufficient Data Window
- 5天数据得出的胜率毫无意义
- 30天数据可看出模型相对排名，但绝对数字不可信
- **Rule**: Minimum 3 months / 8000+ candles before quoting any absolute metrics

## What Backtests CAN Tell You

✅ Relative model ranking (VWAP反抽 > POC拒绝 > 扫流动性回收)
✅ Which models never fire (conf < 0.5 → need parameter tuning)
✅ Directional bias of each model (EMA趋势 20% win rate = negative expectancy)
✅ Parameter sensitivity (risk_per_trade=3 vs 10 → similar outcome = parameter robust)

## What Backtests CANNOT Tell You

❌ Absolute win rate (>70% is almost certainly inflated)
❌ Expected R per trade (>2R avg is suspect without 3+ months of data)
❌ Maximum drawdown (5-day data max_dd is a random sample)
❌ "This strategy makes money" (need walk-forward validation on out-of-sample period)

## Delivery Rules

When presenting backtest results to 棠溪:
1. **Lead with caveats**, not numbers
2. **Show model-by-model breakdown**, not just aggregate
3. **Mark inflated models explicitly** with ⚠
4. **Recommend next data pull** (e.g., "需要拉3个月数据验证")
5. Never say "胜率90%所以可以用" — always say "90%是这个趋势窗口的特征，需要震荡市验证"
