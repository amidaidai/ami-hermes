# TradingView Order-Flow Community Evidence — 2026-07-21

Use this note when evaluating CVD, Volume Profile, VWAP, liquidity sweeps, OI aggregation, non-repainting claims, or order-flow dashboard density. Recheck URLs/dates before reuse.

## Evidence levels

- **A** — TradingView official documentation/product semantics.
- **B** — open-source script with explicit methodology/limitations.
- **C** — protected/community script description or a concrete screenshot comparison.
- **D** — forum/X trader experience; hypothesis only, requiring backtest/forward test.

## Highest-confidence findings

1. **TradingView CVD and Volume Delta are estimates, not exchange-native aggressor tape.**
   - Official CVD: https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/
   - Official Volume Delta: https://www.tradingview.com/support/solutions/43000725057-volume-delta/
   - Both classify lower-timeframe volume from intrabar price movement, then accumulate it. Label outputs `Estimated CVD` / `估算CVD`; never claim true bid/ask.

2. **Ordinary Volume Profile up/down volume is not buy/sell volume.**
   - Official: https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/
   - TradingView uses lower-timeframe bars and classifies `close >= open` as up volume, otherwise down volume. POC/VAH/VAL remain useful structural outputs, but colored VP delta must not be presented as true aggressor flow.

3. **`request.footprint()` does not justify “true exchange order flow” wording.**
   - January 2026 release notes: https://www.tradingview.com/pine-script-docs/release-notes/#footprint-requests
   - Current docs: https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#requestfootprint
   - Official wording says footprint data categorizes lower-timeframe volume from intrabar price action. It exposes buy/sell categories, delta, POC, VA and imbalances, but is not documented as exchange bid/ask aggressor tape. Premium/Ultimate only; one unique footprint request; `na` when unavailable.

4. **Confirmed-bar stability and non-repainting are separate from data accuracy.**
   - Official repainting guide: https://www.tradingview.com/pine-script-docs/concepts/repainting/
   - Stable HTF request pattern: offset expression such as `close[1]` with `lookahead_on`; naked `lookahead_on` leaks future history.
   - Realtime intrabar/tick estimates can change after refresh. Permanent signals should use confirmed bars; realtime previews must be labeled provisional.

## Community implementation evidence

- **Orderflow Suite** — open source, 2026-07-11: https://www.tradingview.com/script/eZnsyK2g-Orderflow-Suite-martineye15/
  - Explicitly says delta is an approximation; realtime tick accumulation can differ after refresh because TradingView does not store ticks. Confirmed footprints/pivots are stable; pivot confirmation lag is not repainting.

- **Quantum Liquidity Map** — open source, published 2026-04-14, updated 2026-04-18: https://www.tradingview.com/script/5xom3FAB-Quantum-Liquidity-Map-VP-VWAP-CVD-Confluence-NikaQuant/
  - Says VP, VWAP and CVD each generate false signals alone; uses confluence. CVD is close-location estimated. Divergence requires price extreme, CVD non-confirmation and swing magnitude >1.5×ATR. Suppresses VWAP deviation bands for first five bars after reset because early variance is unstable.

- **Mirage Liquidity Sweep Pro** — protected description, 2026-06-17: https://www.tradingview.com/script/qBUHu6aW-Mirage-Liquidity-Sweep-Pro-WillyAlgoTrader/
  - Sweep = wick through + confirmed close back inside. A close beyond means the level was consumed, not swept. Optional CHoCH confirmation; confirmed-bar alerts.

- **Delta Flow** — protected description, 2026-07-09: https://www.tradingview.com/script/KyAPOOvy-Delta-Flow/
  - Compact dashboard intended alongside VWAP/VP; explicitly says pressure is estimated from volume/candle direction and is not true bid/ask flow.

- **Open Interest Bubbles** — open source, 2025-12-19: https://www.tradingview.com/script/7EI5Bhe0-Open-Interest-Bubbles-BackQuant/
  - Aggregates OI, normalizes regime differences, errors on missing coverage rather than plotting garbage, and warns OI events are not support/resistance by themselves.

## Concrete community complaints (do not promote above C/D)

- TV CVD differs from Sierra/Quantower/NinjaTrader/ATAS, 2024-04-01: https://www.reddit.com/r/TradingView/comments/1btioh5/viable_alternative_to_tvs_cumulative_volume_delta/
- Footprint comparison vs Exocharts/Coinglass, 2024-04-23: https://www.reddit.com/r/TradingView/comments/1cbdb1y/beware_the_new_volume_footprint_feature_does_not/
- Contradictory VP delta over same region, 2025-07-19 (62 score/88 comments): https://www.reddit.com/r/TradingView/comments/1m3wwns/do_not_rely_on_tradingviews_volume_profiles/
- CVD gives mixed true/false/lagging signals, 2025-08-06: https://www.reddit.com/r/FuturesTrading/comments/1miv4t7/does_volume_delta_work_for_you/
- Chart overload/noise, 2025-12-04: https://www.reddit.com/r/OrderFlow_Trading/comments/1pdzgmq/stop_overloading_your_charts_this_is_what_you/

## Design implications

### Main overlay

Use VP/VWAP/liquidity levels for location and structure. Sweep state machine:

1. `potential`: wick crosses level;
2. `reclaimed`: confirmed close returns inside;
3. `confirmed`: displacement/MSS/CHoCH within N bars;
4. `breakout/accepted`: close remains outside — do not count as sweep.

Display explicit entry, stop, target, R:R and invalidation. A pivot signal must show its confirmation delay rather than backpainting as if known at the pivot bar.

### Order-flow subpane

Show aggregate spot/perp volume, **Estimated CVD**, OI change, source coverage and quality. Normalize exchange units before aggregation; distinguish spot/perp; missing venue data must be visible, not silently zero-filled. CVD/OI confirm or veto plans only near key levels; neither should generate standalone direction.

### Dashboard density

Default live view: 5–7 decision lines, one concept per line. Suggested order: conclusion → direction → entry → stop → target/R:R → confirmation → data-quality/risk. Keep exchange-level diagnostics in detailed mode/Data Window. Do not build a “Christmas tree” panel of raw metrics.

## Not applicable / reject

- “True order flow” claims for ordinary Pine CVD, VP delta or `request.footprint()` without an exchange-native tape source.
- CVD divergence in a vacuum away from structural levels.
- Mechanical VWAP mean reversion immediately after anchor reset or during strong acceptance/trend.
- VP/CVD on illiquid symbols or non-standard charts without explicit distortion warnings.
- Using forum/X posts as proof of profitability or universal consensus.
