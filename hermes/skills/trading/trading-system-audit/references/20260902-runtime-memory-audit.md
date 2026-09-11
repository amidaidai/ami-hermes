# Runtime freshness and memory audit reference

## Reusable repair pattern

1. Collect fresh TV candidates.
2. Preserve the approval boundary; do not extend expired approvals.
3. Write approved levels with explicit source, approval note, and `valid_until`.
4. Run the watchdog and read back its health result.
5. Refresh every strict-gate artifact, not just a shared compatibility file:
   - `tv_live_<SYMBOL>.json`
   - `source_snapshot_<SYMBOL>.json`
   - five-timeframe state
   - approved key-level configuration
6. Run `audit_preflight.py` and retain its raw output.
7. Run targeted tests, compileall, Pyright, then the full test suite after the final production edit.

## Failure mode to avoid

A synchronizer can refresh `tv_live.json` while strict preflight consumes `tv_live_BTCUSDT.json` and `source_snapshot_BTCUSDT.json`. The producer appears successful but the gate remains stale. Publish per-symbol caches atomically and refresh the per-symbol source snapshot in the same synchronization cycle.

## Evidence hierarchy for memory

- Latest user instructions
- Current `MEMORY.md` and `USER.md`
- Current implementation and verified tests
- Historical `memory_store.db` facts
- Historical skill/session notes

Conflicting historical facts are stale evidence, not rules. Studio/API retrieval failures must be reported as unavailable evidence, never replaced with guessed content.

## Acceptance evidence

- Strict preflight passes.
- Approved-level count is positive and active.
- Watchdog reports a fresh heartbeat and OK status.
- Per-symbol caches have matching identity and explicit timestamps.
- Targeted and full regression tests pass.
