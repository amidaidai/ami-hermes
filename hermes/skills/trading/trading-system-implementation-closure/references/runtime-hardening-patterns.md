# Runtime hardening patterns

Reusable patterns for closing trading-system audit findings without trusting process exit codes or file mtimes.

## Semantic freshness

1. Parse an explicit payload timestamp (`updated_epoch`, `updated_at`, `timestamp`, `ts`, or `time`).
2. Validate symbol identity, freshness window, explicit status, and `usable`/`error` fields.
3. If mirrored files exist, select by payload capture time, not filesystem mtime.
4. A missing timestamp is a visible degraded state; never infer live data from a newly touched file.

Recommended status vocabulary: `live`, `cache`, `inherited`, `stale_cache`, `unavailable`, `quota_cooldown`, `not_run`.

## Paired publication

For artifacts that must describe one market state (for example, five-timeframe OHLCV plus a primary action grid):

- Generate a fresh batch ID at the start of the run.
- Propagate it through every producer.
- Require matching IDs and a bounded capture-time skew before promotion.
- Write to a staging path, validate the complete pair, then `os.replace` the published file.
- On failure, keep only a pair that passes the same validator; otherwise write explicit stale/unavailable metadata.

## Authority separation

Legacy gate calculations can remain for observability during migration, but their result must be labelled diagnostic. The only execution boolean is:

```text
FinalVerdict.state == GO-A and FinalVerdict.executable == true
```

Invalid state, missing execution tuple, invalid stop/target geometry, non-finite prices, zero risk budget, or R:R below 1:2 must fail closed before rendering.

## Atomic state and delivery

Use a common writer that creates a same-directory temporary file, flushes and fsyncs it, and replaces the target atomically. Apply it to triggers, heartbeats, health records, dispatch status, and inherited context.

For unattended Telegram delivery, require both an explicit enable flag and a separately configured `telegram:<chat>:<thread>` target. A legacy target passed by an old call site is not an authorization source. Inspect enabled `no_agent` prompts for direct push or direct decision instructions, then run a no-trigger smoke test.

## Closure evidence

The minimum proof set is:

- focused RED/GREEN regressions for each boundary;
- full test suite, compile/import check, and core static/type check;
- reload of real production artifacts through production validators;
- identity, timestamp, pair/skew, temporary-file, approved-level, heartbeat, Cron-policy, and delivery-authorization read-back;
- an explicit unresolved register for historical documentation, performance work, or legacy code not in the active path.
