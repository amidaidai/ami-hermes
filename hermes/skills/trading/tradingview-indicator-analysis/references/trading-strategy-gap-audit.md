# Trading Strategy Gap Audit: SVP/VWAP/EMA/ICT/CVD + Sentiment

Session-derived guidance for reviewing a discretionary TradingView workflow that combines SVP/Volume Profile, VWAP, EMA trend filters, ICT session levels, CVD, and X/web sentiment.

## Community-Derived Gaps To Check

| Gap | Why it matters | Suggested implementation |
|---|---|---|
| Risk/R module | A chart read is not a trade until max loss, stop distance, and target R are defined. | Add risk state: normal / half / light / no trade; require invalidation and expected R before entry. |
| Fixed playbooks | Too many confluences can create analysis paralysis. | Limit to 3-5 setup classes: VWAP pullback, VAH/VAL reclaim, POC rejection, liquidity sweep/reclaim, breakout acceptance. |
| Trade journal tags | Without tags, the user cannot tell whether losses came from structure, timing, CVD, news, or discipline. | Log setup, timeframe, chart state, CVD state, sentiment state, result in R, and error type. |
| Crypto derivatives layer | Perpetual futures are heavily affected by leverage positioning. | For BTC/ETH, add funding rate, open interest, long/short ratio, and liquidation heatmap as context tools. |
| Gold macro layer | XAUUSD is sensitive to dollar and rates. | For gold, include DXY, US yields, macro calendar, London/NY session context, and major news proximity. |
| Data reliability note | TradingView VP/CVD can be exchange/data-source dependent and may not equal true footprint order flow. | Treat SVP/CVD as structure/reference confirmation, not proof; state when volume reliability is weak. |
| News-time filter | Volatile releases can invalidate clean technical setups. | Avoid or reduce size before CPI/PCE/FOMC/NFP/major exchange or ETF news. |

## Recommended Setup Playbooks

1. **VWAP pullback continuation**: HTF direction agrees; price pulls back to VWAP/EMA; CVD does not diverge; enter only after retest/reclaim.
2. **VAH/VAL reclaim**: price breaks value edge, fails to hold outside, then reclaims; CVD supports reversal or shows absorption.
3. **POC rejection**: price returns to POC/balance and rejects; use as range fade or continuation depending on HTF context.
4. **Liquidity sweep then reclaim**: session high/low or obvious level is swept; price quickly reclaims; CVD divergence/non-confirmation supports trapped flow.
5. **Breakout acceptance**: price breaks VAH/VAL/VWAP, holds on retest, and CVD/volume confirms; avoid chasing if already extended.

## No-Trade Rules Worth Surfacing

- `X / 禁追 / 不进场` is a valid decision and should not be weakened by extra narrative.
- Do not chase when price is far from VWAP or already extended outside value.
- Do not trade if expected reward is less than roughly 1.5R unless there is a special reason.
- Do not let X/Twitter sentiment override chart structure; use it only as a catalyst/crowding filter.
- Reduce size or skip around major macro/news events, especially gold during U.S. data and crypto during ETF/exchange/regulatory headlines.

## Suggested Dashboard Rows

Keep the table concise for live trading. If adding one row, prioritize risk/position sizing over more signals:

| Row | Meaning |
|---|---|
| 状态 | A多 / A空 / X / 震荡 |
| 处理 | 等回踩 / 等反抽 / 禁追 / 不进 |
| 背景 | 4h/1h directional filter |
| 位置 | VAL/VAH/POC/VWAP/nPOC/session level context |
| 量流 | Volume + CVD confirmation/conflict |
| 仓位 | 正常 / 半仓 / 轻仓 / 禁止 |
| 计划 | Long/short trigger or wait condition |
| 失效 | Exact price/condition that invalidates the idea |
