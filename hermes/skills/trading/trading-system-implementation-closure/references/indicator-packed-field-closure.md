# Indicator packed-field closure

## Scope

Use this reference when a Pine indicator exposes machine-readable Data Window buses and Python must turn them into a single FinalVerdict. It records the validated pattern from the September 2026 SVP/AggVol closure work.

## Authority chain

1. Verify the checked-in Pine source hash and plot/action-grid alignment.
2. Keep packed formulas and code meanings in one contract module (`tv_indicator_contract.py`).
3. Add decoder round-trip tests using known encoded values.
4. Consume decoded values at the resolver boundary (`decision_loop.resolve_final_verdict`).
5. Audit `auto_card.py`, the backtest replay path, gates, and renderers for raw-field bypasses.

Never maintain a second decoder or handwritten field whitelist in a consumer.

## SVP buses

| Bus | Formula/meaning | Conservative handling |
|---|---|---|
| Trigger Pack | `(triggerCode+10)*100000 + age*100 + fresh*10 + (signalState+3)` | stale/pending → WAIT; X state → NO-GO |
| Regime Pack | `regime*10000 + preferredModel*100 + confidence` | unknown regime or confidence < 50 → WAIT |
| Contract Pack | `171000 + marketCode*10 + 1` | malformed contract → NO-GO |
| Evidence Pack | `date*10000 + direction/position/trigger/closed flags` | missing location, trigger, or closed flag → WAIT |
| StructPack | `FvgQ*10000 + (OB+1)*100 + (BOS+2)*10 + (LV+1)` | malformed value → WAIT; strategy selection cannot invent structure |
| Quality Code | bit mask: HTF, CVD, liquidity, ADR, FVG, MSS, EMA-order quality | non-zero → visible warning and WAIT |
| CVD Method Code | `0` no decision, `1` bar estimate, `2` lower-TF estimate | 0/unknown → WAIT when supplied |

`Entry Valid`, `NoTrade Reason`, and the SVP risk-row authorization remain higher-priority execution gates. R:R 1.5–1.99 is only a B/C observation candidate; execution requires R:R >= 2.0 and the complete geometric tuple.

## AggVol quality inputs

When supplied for crypto, decode `Coverage Feed Mode` before evaluating alignment:

- aggregate = usable;
- fallback single-chart = usable only as a degraded WAIT;
- single-source = no collaboration authorization;
- abnormal = hard block.

A positive stale-venue count, unavailable CVD quality, or OI present with low agreement downgrades to WAIT. OI absence is not the same as a true 0.00% change. Non-crypto paths must not inherit these crypto gates.

## Lease-aware verification

A collector may print an explicit defer message while the interactive TradingView analysis lease is active. The safe recovery sequence is:

```text
read tv_analysis_lease.py status
end the current/stale lease via tv_analysis_lease.py end
read status again and require active=false
rerun the failed focused tests
rerun the full suite if shared runtime code was touched
```

The lease must not be removed from production code merely to make tests pass. Record the initial failed run as runtime-state interference, and report only the clean rerun as final evidence.
