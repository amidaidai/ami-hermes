# Repair evidence patterns

## FinalVerdict renderer regression

Use a legacy A grade with raw prices and a final WAIT/NO-GO verdict. Assert no executable prices. Add hard conflict with stale `direction_verdict="主副同向"`; assert `主副强冲突` and not `主副同向`.

## SVP migration gate

A legacy A grade may coexist with `⚠未收线 · 等收线` or `A空 ⚠冲突`. Treat the hard-wait tokens as a fail-closed compatibility gate until typed indicator contracts replace text parsing.

## MCP envelope and cache safety

Handle both direct domain JSON and `{success:true,result:"<json>"}`. If not unwrapped, parsers silently produce empty tables and may overwrite candidates with a false success. Unwrap first; empty candidates fail closed.

## TV identity

After symbol/timeframe changes, wait for indicator recalculation, verify symbol and resolution, read, and verify again before writing. OHLCV freshness alone does not prove indicator identity.

## Runtime level health

Check process/heartbeat plus enabled, unexpired approved levels. For temporary degraded-cache approval, preserve a timestamped backup and use a short explicit expiry.

## Options guard

Every formatter must suppress invalid MaxPain:

```python
mp = d.get("max_pain") if d.get("max_pain_valid") else "—"
```

`max_oi_strike` is not MaxPain.

## Evidence checklist

Focused RED/GREEN; full test count and duration; compile/import result; quick/full smoke; exact cache identity/freshness; heartbeat and active-level read-back; cron model/provider/mode/status read-back; explicit unresolved items.
