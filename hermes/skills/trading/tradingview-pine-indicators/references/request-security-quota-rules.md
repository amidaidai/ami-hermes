# `request.security` quota: how Pine actually counts (and why "free quota" tricks fail)

## The rule (officially rechecked, Pine v6 — 2026-08)
TradingView allows **40 unique executed `request.*()` requests per script**, or **64 for Ultimate**. With v6 dynamic requests, exceeding the budget can be a **runtime** error (the official loop example fails when the 41st distinct timeframe executes), not universally a compile-time/static count.

Pine v6 enables dynamic requests by default when the compiler determines they are needed. One source-level `request.security()` instance can execute zero, one, or many contexts in loops/conditionals, and each distinct executed function+argument/context combination consumes the unique-call budget. Therefore:

- ✅ A branch/local-scope request that never executes can consume no runtime request context. An `input.bool` gate can therefore avoid executing that request in genuinely dynamic v6 code.
- ⚠️ Once a branch executes for any historical bar, its distinct context counts. Realtime bars cannot introduce a brand-new context/expression that was never requested on historical bars.
- ⚠️ With `dynamic_requests = false`, requests cannot appear directly in local scopes; compiler-translated/wrapped v5-style behavior differs. Do not generalize v5 static-hoisting rules to v6 dynamic requests.
- ✅ **Identical executed requests** (same `request.*()` function and same arguments) normally reuse the first dataset and count once. A loop can invoke the same request 50 times without using 50 slots.
- ⚠️ Calls inside imported libraries count separately even when the main script has an apparently identical call.
- ✅ **Genuinely unused** request code that no script output depends on can be optimized away.
- ✅ **Tuple batching** — `[a,b,c] = request.security(sym, tf, [expr1, expr2, expr3])` — fetches many values from one symbol/timeframe request. It cannot merge different contexts. All `request.*()` calls together still have a 127 tuple-element limit; use a UDT when needed.
- ✅ Pushing same-context math into the expression can reduce calls: `request.security(s, "D", high-low)` is one request.

Official sources:
- https://www.tradingview.com/pine-script-docs/writing/limitations/#request-calls
- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#dynamic-requests
- https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/#dynamic-requests

## Mandatory step before touching security calls
**Count the distinct request contexts that actually execute under the target configuration, and also the worst enabled configuration.** Watch for calls hidden inside a custom function that is invoked with different symbol/timeframe arguments — each distinct executed argument combination is a separate request. Example:

```pine
data(sym) => request.security(sym, timeframe.period, close)
plot(data("EURUSD")); plot(data("GBPUSD"))  // two distinct contexts
```

A toggle only helps when it prevents the `request.*()` call itself from executing in a v6 dynamic local scope. Fetching first and applying `enabled ? value : na` afterward does not save a context.

## Worked case — HALDRO "Aggregated Volume Spot & Futures"副指标
In the audited implementation, the request calls executed regardless of display/default-off toggles, so the enabled execution set was:
- `GetExchange` calls `GetRequest`→`request.security` for 9 exchanges, invoked 4×
  (SPOT1/SPOT2/PERP1/PERP2) = **36** (each exchange×pair is a distinct symbol; tuple batching cannot merge them).
- `VAREUR` (FX_IDC:EURUSD) + `VARRUB` (MOEX) = **2**.
- OI single source = **1**.
- **Total = 39/40 — already at the non-Ultimate ceiling.**

Therefore for that code:
- Adding a 4-source OI aggregation (+4) → **43**, so non-Ultimate execution fails unless real contexts are gated or removed.
- Merely hiding exchanges or applying a ternary after data retrieval frees nothing.
- Options are: (a) physically remove sources; or (b) on Pine v6, place the request itself inside a genuine dynamic branch that never executes for disabled sources. Option (b) changes data availability and must still preload every context needed on realtime bars during historical execution.
- Cutting 9→5 always-active exchanges frees 16 worst-case contexts (4 pairs × 4 exchanges), enough for four OI sources, but reduces venue coverage and needs user approval.

## Zero-quota wins to prefer instead
When you can't add data sources, add **pure-logic derivations** of data you already fetch:
- OI×price divergence (price up + OI down, or price down + OI up = leverage moving against
  price → squeeze/flush precursor; community "Leverage Hunter" framing). Flag with a glyph
  (e.g. ⚡) in the action panel. Costs no quota.
- Session-anchored CVD reset period made user-selectable (D/W/M via `ta.change(time(tf))`)
  to align a secondary indicator's CVD with the main indicator's anchor — pure logic.

## Process lesson
If you catch yourself asserting "this frees quota / this is safe to add" about request calls, STOP and verify three things before shipping: Pine version and `dynamic_requests` mode; whether the toggle gates the call itself or only its output; and the distinct contexts executed under both default and worst-case inputs. Validate in TradingView because dynamic overages can surface only at runtime.
