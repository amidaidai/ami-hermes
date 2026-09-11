# Concise Analysis Card Format (2026-06-20)

Use this when generating or refining Tangxi trading analysis cards across crypto, metals, forex, stocks, and options.

## Target
- Final card should be around **1500 Chinese characters**.
- The user explicitly rejected report-style cards around 2000–3300+ chars as too long and hard to know what to read.
- Preserve actionability, not exhaustive explanation.

## Keep
- Header decision fields: symbol, timeframe snapshot, price, status, model, score, decision, position/risk, invalidation, data quality.
- Five section headings may remain for continuity: 环境 / 结构 / 博弈 / 操作 / 风控.
- Operation section must keep complete A/B plans with clear items: direction, entry/trigger, risk, position, invalidation, review, trajectory.
- R:R ≥ 1:2, stop/target, position, and invalidation must remain visible.

## Compress
- Environment: 3 lines max — data quality, flow/funding or macro proxy, catalyst/sentiment.
- Structure: 3 lines max — 4h invalidation, 1h/15m support/resistance/execution, 5m trigger/no-chase.
- Game: 3 lines max — structure/engine/order-flow裁决, long-vs-short strength, boundary.
- Risk: 3 lines max — risk/day limit/RR, gates, discipline.
- Avoid long explanations like a research report. One line should answer “what matters for the trade?”

## Symbol Format
- Do **not** render the literal label `交易所：`.
- Use compact venue form:
  - `BTCUSDT.P · BINANCE`
  - `XAUUSD · EXNESS`
  - `EURUSD · OANDA`
  - `AAPL · NASDAQ`
  - `AAPL250117C · OPRA`
- Only crypto perpetuals use `.P`; metals/forex/stocks/options never use `.P`.

## Pitfall
If the user asks to “看模板样式” or “发到电报看看”, send concise mock cards to Telegram for all requested asset classes and report the actual character counts. The acceptance target is around 1500 chars, not merely “shorter than before”.
