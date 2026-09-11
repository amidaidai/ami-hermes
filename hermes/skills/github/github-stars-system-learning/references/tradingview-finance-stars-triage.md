# TradingView / Finance Stars Triage

Use this reference when a user's GitHub Stars include TradingView, finance, quant, crypto, or trading-agent repositories and the user wants their Hermes setup strengthened.

## Classification Pattern

Group starred repos into practical lanes:

- **TradingView / chart reading**: TradingView readers, OpenCLI adapters, browser/CDP tools, chart screenshots, watchlists, alerts.
- **Market data / fundamentals**: OpenBB, yfinance, Funda, earnings, valuation, stock correlation, options data.
- **Quant / backtesting**: qlib, freqtrade, vn.py, backtesting engines, factor research.
- **LLM trading research**: TradingAgents, TradingAgents-CN, FinGPT, daily stock analysis agents.
- **Execution / auto-trading**: exchange bots, order placement, broker APIs, copy-trading tools.

## Default Safety Boundary

Do not install or enable trading-adjacent tools automatically if they touch any of:

- account cookies or browser/CDP login state
- exchange/broker credentials
- order placement, trade execution, watchlist/alert modification
- unofficial private APIs for authenticated data

For these, produce a candidate report and ask for explicit user approval before installing or running anything.

## TradingView Reader Pattern

A read-only TradingView reader can be useful, but it is still high-sensitivity when it uses the desktop app, CDP, or cookies. Treat it as:

- **Useful for**: current chart state, screenshots, watchlists, alerts, screener/quote/option reads.
- **Not default safe**: it may read logged-in TradingView session cookies or launch the app with a debug port.
- **Agent action**: report it as a candidate; do not install/run until the user explicitly confirms.

## Recommended Output

When reporting back, include:

1. total star count and saved local artifacts
2. category counts relevant to the user's goals
3. existing installed skills that already cover the area
4. starred repos worth learning from, separated from tools worth installing
5. risky candidates that require explicit approval
6. a practical next-step menu: analyze screenshots/Pine now, install reader after approval, or build a read-only market-data workflow
