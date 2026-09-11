# 中文专业术语映射

分析卡和监控推送统一使用中文术语，不裸放英文缩写。

| 英文 | 中文 | 说明 |
|------|------|------|
| POC | 筹码峰 | Point of Control，最大成交量位 |
| VAH | 价值区上沿 | Value Area High |
| VAL | 价值区下沿 | Value Area Low |
| DO | 多空分界 | Day Open，日内开盘价 |
| VWAP | 均價線 | Volume Weighted Average Price |
| W_VWAP | 周均價 | Weekly VWAP |
| S_VWAP | 日均價 | Session VWAP |
| EMA | 均线 | Exponential Moving Average |
| CVD | 累积量差 | Cumulative Volume Delta |
| SL | 止损 | Stop Loss |
| TP | 止盈 | Take Profit |
| R:R | 盈亏比 | Risk:Reward |
| HTF | 高周期 | Higher Timeframe |
| LTF | 低周期 | Lower Timeframe |

## 推送消息模板

监控推送必须包含：
1. 中文术语 + 方向箭头 ↑↓ + 百分比距离
2. 上次分析周期（如 `4h 空 · 15m 弱`）
3. 明确行动指令（`→ 说「分析 BTC」`）

```
🟡 BTC 接近关键位
价格：`66416`
多空分界 `66293` (↑0.19%) · 周均價 `66284` (↑0.20%)

上次周期：4h 空 · 15m 弱

📊 可分析确认
→ 说「分析 BTC」
```
