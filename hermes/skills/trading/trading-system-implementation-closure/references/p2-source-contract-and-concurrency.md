# P2 source contracts and safe concurrency

## Scope

Use this reference when extending a multi-asset trading pipeline without changing execution authority. The pattern applies to API responses, local caches, Cron artifacts, and optional sentiment/on-chain/context sources.

## Canonical source envelope

Attach this metadata without removing legacy flat fields:

```json
{
  "version": 1,
  "source_id": "provider_or_logical_source",
  "status": "live|cache|inherited|stale_cache|unavailable|quota_cooldown|not_run",
  "timestamp": "explicit data capture time or null",
  "payload": "raw source payload",
  "error": "safe classification or null",
  "observed_at": "local observation time",
  "cached": false,
  "symbol": "identity or null",
  "payload_present": true
}
```

Rules:

- `timestamp` is the source-data capture time. `observed_at` is when the local process saw it.
- `live/cache/inherited` without `timestamp` must downgrade to `unavailable` with `missing_timestamp`.
- Never substitute file mtime for `timestamp`.
- Keep secrets and credential-bearing error text out of `error`; use classifications such as `timeout`, `quota_or_rate_limited`, `credential_or_plan_blocked`, `cache_missing`, or `upstream_error`.
- A compatibility decorator may expose `_source_contract`, `_source_status`, and `_source_timestamp` while preserving the old payload keys.

## Aggregator contract

For every routed provider, emit a source-record map even when the provider returns no payload:

- successful direct fetch → `live` plus capture timestamp;
- TTL cache hit → `cache` plus cached capture timestamp;
- failed refresh with an older valid artifact → `stale_cache` plus older timestamp;
- quota circuit open → `quota_cooldown`;
- skipped by route or asset boundary → `not_run`;
- no usable result or identity failure → `unavailable`.

Consumers should prefer the record map over truthy checks on legacy fields. Matrix rows should expose timestamp, safe error, and payload presence. Optional rows can warn or degrade, but only core gates may block or influence FinalVerdict.

## RED/GREEN regression set

1. Decorate a normal payload and assert old keys remain readable and the envelope contains source id, status, timestamp, payload, and error.
2. Decorate a `live` payload without capture time and assert fail-closed `unavailable/missing_timestamp`.
3. Feed the decorated payload to the shared health checker and assert timestamp/status are honored.
4. Run an aggregator with one empty provider and assert the provider is present in the record map as `not_run` or `unavailable` without breaking other providers.
5. Put a stale record beside a non-empty legacy value and assert the matrix/completion consumer reports `stale_cache`.
6. Write an artifact to a temporary directory and assert the old fields, envelope, and absence of a leftover temp file.

## Safe parallelization checklist

1. Measure a serial baseline with representative source latency and record result completeness.
2. Add a regression proving independent fetchers run on bounded worker threads and all source records remain present.
3. Protect shared cache reads and writes with a lock; perform network I/O outside the lock.
4. On write, re-read or merge the latest cache document before updating one key, then publish atomically.
5. Collect futures in stable route order so card output and tests remain deterministic.
6. Keep TV symbol/timeframe transitions, FinalVerdict resolution, gate evaluation, and external delivery sequential.
7. Re-run focused tests, full tests, compile/import checks, type checks, strict preflight, and the live-artifact probe.

## Dirty-worktree guard

Before P2 work, classify files as active, archived, generated, or already modified. Do not delete `.bak`, disabled scripts, or historical documents merely to make a scan clean. Treat historical cleanup as a separate explicitly scoped batch with its own inventory and verification.
