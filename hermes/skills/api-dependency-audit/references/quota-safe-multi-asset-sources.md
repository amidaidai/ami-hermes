# Quota-safe multi-asset source contract

## Scope
Use when a trading analysis pipeline combines TradingView/SVP with free or quota-limited APIs across crypto, metals, forex, stocks, futures, and options.

## Required adapter behavior

1. Run the critical path first: asset identity, TV/primary quote, core indicator, risk gates, and FinalVerdict.
2. Mark enrichment sources independently; an optional-source failure must not abort the analysis.
3. Return one explicit state: `live`, `cache`, `stale_cache`, `unavailable`, or `quota_cooldown`.
4. Include source, asset/symbol, timeframe where relevant, timestamp, freshness, quality, semantic validity, and typed failure class.
5. On 429/rate-limit/quota failure, persist a per-source cooldown and suppress repeated calls.
6. Expose stale use and lower completeness; never label stale data as live or completed.
7. A missing load-bearing source may force WAIT/NO-GO, but must not fabricate values or bypass FinalVerdict.

## Tested acceptance cases

- Simulated HTTP 429 returns `unavailable`, classifies `quota_or_rate_limited`, and writes circuit state.
- A second call during cooldown returns `quota_cooldown` without invoking the fetcher.
- Failed refresh with an old cache returns `stale_cache` and preserves the error class.
- CoinGecko failure does not stop TV/SVP and the core decision path; the card exposes degraded status.
- Non-crypto assets do not request or render crypto-only Funding/Taker/OI/CVD/AggVol fields.
- Completion counters inspect structured source status rather than text presence.
- Monitor/event routing does not create a directional analysis card or execution prices.

## Audit traps

- A successful process exit is not proof of valid market data.
- A non-empty cache is not proof of freshness or correct symbol identity.
- `stale_cache`, `unavailable`, and `quota_cooldown` must not be counted as completed live enrichment.
- Never replace an unavailable crypto source with stale BTC data in a non-crypto card.
- Do not solve cross-asset contamination by hiding forbidden fields as `N/A`; keep them absent and render the market-specific alternative.
