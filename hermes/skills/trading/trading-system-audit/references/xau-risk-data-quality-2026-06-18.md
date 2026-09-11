# Audit Finding Patterns · XAU Risk/Data Quality · 2026-06-18

## Durable lesson

During a full trading-system audit, XAUUSD showed a subtle but high-impact bug class: data-quality spread was being reused as market volatility.

## Pattern 1 — source spread passed as volatility

### Symptom

Trade event risk gate contains text like:

```text
24h波动 47.4% ≥ 1% XAU波动禁做
```

but the value originates from `snapshot.price_spread_pct`, not real 24h move.

### Root cause

`行情守望.py` called:

```python
check_constitution(..., volatility_24h_pct=abs(snapshot.get("price_spread_pct", 0) or 0))
```

`price_spread_pct` is cross-source price spread in percent units. `risk_constitution` expects `volatility_24h_pct` as a decimal ratio.

### Correct model

```text
price_spread_pct / source_spread_pct → data-quality gate only
volatility_24h_pct                  → market-risk gate only
```

If true 24h volatility is unavailable, pass `0` or an explicitly named fallback. Never substitute cross-source spread.

## Pattern 2 — XAU spot vs futures basis

`gold-api.com` and 金十 are spot-like XAU sources. Yahoo `GC=F` and `MGC=F` are futures proxies and can show persistent basis vs spot. They should not be equal voters in spot consensus.

Recommended scoring:

1. `OANDA + 金十 + gold-api` aligned → `A92`.
2. `金十 + gold-api` aligned, no OANDA → cap at `A-88` or `B+`.
3. Yahoo GC/MGC disagreement should be reported as `futures basis偏离`, not necessarily spot-data failure.
4. If all sources are mixed and spread > `0.5%`, downgrade confidence and expose basis reason.

## Pattern 3 — restart-limit observability

If watchdog rate-limits restart after repeated failures, log-only is insufficient for a trading monitor. A future fix should add:

```json
{
  "restart_count_1h": 3,
  "restart_blocked_until": "...",
  "last_restart_reason": "..."
}
```

and push a visible `监控不可恢复` alert.
