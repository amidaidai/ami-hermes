# Binance验证与位置型跟踪模式

## 最小现场核验

轻量更新至少调用：

- TradingView health/state/quote
- TradingView 主指标与副指标 pine table
- TradingView full screenshot
- Binance `get_price(symbol=BTCUSDT)`

标准或完整更新增加：

- `get_open_interest_history`
- `get_funding_rate_history`
- `get_long_short_ratio` 与 `get_global_long_short`
- `get_taker_volume`
- 签名只读 `get_account_summary` 或 `get_balance`（仅在需要核验账户链路时）

## 结果写法

先写“Binance验证：✅/⚠️”，再写价格、时间戳和数据状态。TV/Binance小幅价格差需给出百分比，但不能仅凭微差否决结构。

## 位置型跟踪

用户问“现在呢/目前看哪一个位置”时，从行动格选一个最近且有意义的主位，例如日VWAP。只给：

1. 收线站上主位的含义；
2. 反抽受阻并完成结构确认的含义；
3. 未收线或横盘时的等待结论。

若 S3/S4、未收线、缩量或 OI缺失，保持观望，不输出正式执行三件套。
