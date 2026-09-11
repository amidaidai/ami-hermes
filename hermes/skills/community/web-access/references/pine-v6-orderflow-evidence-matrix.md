# Pine v6 / Order-Flow Evidence Bank (2025–2026)

Session research notes for evidence-matrix work. Treat URLs as primary sources and re-check dates before reuse.

## Official TradingView constraints

- [Pine release notes](https://www.tradingview.com/pine-script-docs/release-notes/): Pine v6 added `request.footprint()` and footprint/volume-row data access.
- [Other timeframes and data — `request.footprint()`](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#requestfootprint), rechecked 2026-07-21: TradingView categorizes lower-timeframe volume as “buy” or “sell” from intrabar price action, then exposes delta, POC, VA and row imbalance. Do **not** relabel this as exchange tick-level bid/ask or order-book data. One unique footprint request per script; only Premium/Ultimate; unavailable data can be `na`.
- [Alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/), rechecked 2026-07-21: alerts only trigger on realtime bars; creation stores a server-side snapshot of script, inputs, symbol and timeframe, so script/input changes require deleting and recreating existing alerts. `alertcondition()` consumes plot count; `alert()` supports dynamic messages and explicit close frequency.
- [Dynamic requests](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#dynamic-requests), rechecked 2026-07-21: Pine v6 enables dynamic requests by default. Budget runtime unique contexts, not only textual call sites; an unexecuted short-circuited branch need not create a request, while one dynamic call can accumulate many contexts. Realtime cannot first access a context not requested during historical execution.
- [Repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/): confirmed HTF pattern is an offset expression with `lookahead_on`; never use naked `lookahead_on` for historical signals.
- [Limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/): request uniqueness, plot/object and tuple limits must be budgeted for the worst enabled configuration.
- [Profiling and optimization](https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/): combine same-context requests using tuple expressions; use `calc_bars_count` where appropriate.
- [Volume Profile basics](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/): POC/VAH/VAL are profile outputs; ordinary VP up/down volume is not equivalent to native bid/ask footprint.
- [Open Interest](https://www.tradingview.com/support/solutions/43000685269-open-interest/): OI is outstanding derivative contracts; crypto can have intraday data while many traditional futures are daily.
- [Long/Short Ratio Accounts](https://www.tradingview.com/support/solutions/43000762399-long-short-ratio-accounts/): account ratio is a trader-account sentiment metric, not a notional position ratio.

## Community implementation evidence

- [CVD Aggregated Lite](https://www.tradingview.com/script/CRKW4dvv-Cumulative-Volume-Delta-Candles-Aggregated-Lite/), updated 2025-10-18: aggregates Binance/Bybit/OKX/Bitget/Coinbase, supports denomination and anchor reset, and explicitly discloses that Lite uses lower-timeframe estimation rather than exchange tick-level delta.
- [OI Aggregated Lite](https://www.tradingview.com/script/qiqehv0U-Open-Interest-Aggregated-Lite/), updated 2026-03-11: aggregates several exchanges, normalizes coin/USD, exposes OHLC/change views; useful model for provenance and unit normalization.
- [Footprint Lookback](https://www.tradingview.com/script/mFzdS8hv-Footprint-Lookback-Order-Flow/), updated 2026-06-22: one native footprint request, rolling profile, confirmed-bar stability, explicit “No footprint data”, 300-bar performance cap, and warnings about forex/CFD tick volume.
- [Naked POC Clean](https://www.tradingview.com/script/3r5whRmf-Naked-POC-nPOC-Clean-and-No-Clutter/), updated 2026-06-08: removes a level when touched and expires old levels; close-weighted triangular distribution is a community choice, not an official VP definition.
- [Trade Execution Desk](https://www.tradingview.com/script/RyafCWPs-Trade-Execution-Desk-JOAT/), published 2026-06-05: converts an identified setup into entry/stop/TP/RR/position-size/session-lock workflow instead of pretending to generate predictive signals.
- [quant-order-book](https://github.com/nssanta/quant-order-book): 2025-12 initial release and 2026-04 update; external WebSocket architecture for multi-exchange order-book heatmap, CVD, delta and imbalance. Supports the boundary that deep real-time order flow belongs outside Pine.
- [TradeBobby audit commit](https://github.com/SoCloseSociety/TradeBobbyTerminal/commit/bed5b8b67391da728bfaec73a476d95844f11cd3): useful governance example—reject biased simulated win rates; require HTF alignment, pre-marked level, confirmation, ATR stop, risk cap, RR and session/news rules.

## Official exchange semantics

- [Bybit long-short ratio](https://bybit-exchange.github.io/docs/v5/market/long-short-ratio): defines long account ratio and short account ratio, with 5m/15m/30m/1h/4h/1d periods; volatility can delay delivery. Do not mix this with top-trader position ratios.
- [OKX API guide](https://www.okx.com/docs-v5/en/): exposes separate contract OI, taker volume, margin long/short ratio and top-trader endpoints; endpoint names reinforce that these are different measures.

## Interpretation safeguards

1. Label every field with source, exchange coverage, contract type, unit, timeframe, estimate/native status and confirmed/live status.
2. Aggregate CVD/OI only after unit normalization; aggregate LSR only within identical semantic definitions.
3. Treat nPOC, imbalance, absorption, FVG and OB as community constructs or contextual observations, not guaranteed magnets or proof of institutional intent.
4. Put native Footprint in a separate premium-capability layer; do not claim a Pine script can silently downgrade to real footprint on unsupported plans.
5. Use evidence tiers A/B/C/D in the final matrix and keep forum posts as hypotheses requiring backtest or forward validation.
