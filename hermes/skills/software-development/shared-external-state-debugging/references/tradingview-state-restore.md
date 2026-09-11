# TradingView shared-chart state restoration

## Incident pattern

A background XAU collector temporarily switched a shared TradingView chart to `OANDA:XAUUSD`. Its old completion path forced the chart to `OANDA:XAUUSD`/5m, so a user who had just analyzed BTC was left on gold. A BTC collector also restored the chart state it saw on entry, which could preserve XAU when jobs overlapped.

## Reliable fix pattern

- At the start of the collection session, read `chart_get_state`.
- Preserve the literal `symbol` and `resolution` values.
- Switch to the collector’s symbol and collect all required timeframes.
- Put the entire mutation and validation body inside `try/finally`.
- In `finally`, restore the saved symbol first, then the saved resolution.
- If the initial state cannot be parsed, do not choose a default symbol as a “restore” value.
- After the worker exits, independently call `chart_get_state` and assert the final state.

## Verified repository implementation

`D:/Hermes agent/scripts/xau_tv_sync.py` now snapshots the incoming chart state and restores it on all exit paths. A direct XAU sync entered from BTC 15m and emitted:

```text
↩ 已恢复TV图表: BINANCE:BTCUSDT.P 15
```

The independent TradingView health check then reported `BINANCE:BTCUSDT.P` with resolution `15`. Targeted tests reported `22 passed`; the relevant Python files also passed `py_compile`.

## Remaining architecture consideration

The TradingView chart is still a single mutable external target. The strongest long-term design is an isolated tab/session for background collection, or a lock shared by both foreground and background mutations. Snapshot-and-restore is the required minimum when isolation is unavailable; it cannot prevent an uncoordinated foreground mutation from racing during the worker’s critical section.
