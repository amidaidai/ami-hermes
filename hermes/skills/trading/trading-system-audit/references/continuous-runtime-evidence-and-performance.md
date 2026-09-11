# Continuous runtime, evidence, and performance audit

Use this after a repair closure when the user asks what still needs optimization. The goal is to determine whether the system stays healthy after cache TTLs and scheduler cycles pass, not to repeat the previous green report.

## Evidence classes

Label every finding as one of:

- **Currently reproduced**: rerun this session produced it.
- **Static verification**: current source/config proves the condition, but no external side effect was triggered.
- **Not yet verified**: plausible risk or optimization hypothesis; never report it as an observed outage.

A prior green preflight is only a baseline. Rerun preflight after one or more TTL windows whenever possible.

## Producer-to-consumer continuity

For every critical artifact, map:

`producer script -> enabled scheduler/trigger -> TTL -> consumer gate`

Check identity, timestamp, freshness, payload completeness, and whether a successful run actually published a newer artifact. Exit code zero is not publication proof. A fresh file with no enabled producer is a continuity P1 because it will inevitably become stale.

Do not enable retired jobs merely to make the audit green. An audit request is not authorization to add Cron jobs, restore delivery, commit, push, or perform broad refactors.

## Approval lifetime is not structural relevance

An `existing_levels_only` renewal policy may extend `valid_until`, but it must not be described as updating market structure. Compare approved levels with the latest same-name/same-class candidates, current price distance, ATR distance, original source time, and renewal count.

Recommend an independent `max_structural_age` or invalidation rule. Intraday BTC levels can start with a proposed 24-hour review horizon, but changing that policy or promoting candidates requires explicit authorization. Candidate pools must never be silently promoted.

## Pipeline completion requires source-correct evidence

Distinguish:

1. route declares a step;
2. executor attempted it;
3. correct source returned a usable result.

Only (3) counts as completed. Examples:

- Binance K-lines do not prove TradingView five-timeframe completion.
- Card text containing “CVD” or “X sentiment” does not prove those sources ran.
- A newly written outer snapshot does not make an embedded stale macro payload live.
- Exit code zero does not prove a collector published a new complete snapshot.

Quick/Standard TV completion requires a verified fresh main execution timeframe and action grid. Full crypto/gold completion requires the strict D/4h/1h/15m/5m contract. Prefer behavioral tests for completion helpers over source-string assertions.

## Profiling external waits correctly

Run a real cProfile plus retain the full pipeline log. Interpret:

- `thread.lock.acquire` or `Thread.join` on the main thread as worker wait until source correlation proves CPU contention.
- Large `ssl.do_handshake` totals as missing connection reuse; introduce a persistent HTTP session/pool before broad concurrency.
- Sequential independent read-only endpoints as bounded-concurrency candidates with one deadline, source statuses, circuit breaking, and deterministic result ownership.
- Low local CPU time as evidence not to micro-optimize calculations.

TradingView is shared mutable state. Symbol/timeframe switch, recalculation, data read, screenshot, and restoration remain serialized under one lock. Never parallelize chart switching.

## Screenshot integrity

If preflight already established the target chart identity and waited 15–30 seconds for indicator recomputation, capture that verified chart directly. Avoid a screenshot helper that unconditionally switches symbol/timeframe again.

If a switch is unavoidable: lock, record original state, switch, wait, verify symbol/timeframe/studies/action-grid freshness, capture, restore, and read back the restored state. Two or three seconds may expose OHLCV but is not proof that SVP and secondary studies recalculated.

## Version recoverability

Untracked production entrypoints, preflight scripts, scheduler scripts, or their regression tests are P1 even if currently runnable: they cannot be restored from Git after workspace loss. Report exact files, but do not stage, commit, or push without permission.

Hardcoded delivery targets in disabled scripts are restoration risks, not current P0s, when the central sender still enforces explicit enable plus configured-target matching. Require migration and dry-run before re-enabling them.

## Prioritization and stop rule

Recommend in this order:

1. continuity gaps that make critical data inevitably stale;
2. structural-expiry governance for automatically renewed approvals;
3. untracked production artifacts;
4. measured I/O bottlenecks such as screenshot waits and repeated TLS handshakes;
5. incremental decomposition of giant orchestrators and classification of broad exceptions.

Explicitly defer unsafe or low-value work: parallel TV switching, reducing required exchange coverage, candidate auto-promotion, restoring historical jobs, whole-repo path replacement, or one-shot rewrites.

If code changed, verify focused behavior tests, full tests, compile/syntax checks, diff checks, and a current preflight. A failed preflight is not automatically a code failure: report the failing contract, TTL, consumer impact, and active degradation behavior.