---
name: trading-system-implementation-closure
description: "Use when verifying trading-system audit repairs."
category: trading
tags: [trading, audit, tdd, runtime, verification]
---

# Trading System Implementation Closure

Use this class-level skill when an audit repair must be implemented and proven. The deliverable is a working, exercised change plus an explicit unresolved register, not a plan or optimistic report.

## Core workflow

1. Re-check git status, current runtime, cron JSON, caches, TV state, and interpreter before using historical evidence.
2. Separate every finding into current, historical, already fixed, not reproduced, or not verified.
3. Repair the load-bearing chain in order: data identity → freshness/semantic validity → normalized data → FinalVerdict → gate → every renderer/delivery consumer.
4. For each root cause: add a minimal regression, run RED, patch production code, run GREEN, then run the relevant suite.
5. After external-state changes, read back the exact file/job/health target and verify its effect.
6. Run focused tests, compilation/import checks, full tests, real quick/full smoke as relevant, and text assertions on generated cards.

## Decision invariants

- `FinalVerdict` is the only execution authority. Legacy A/B/C/X labels cannot override it.
- Only `GO-A` may render executable Entry/Stop/Target. `WAIT` and `NO-GO` clear executable prices; observation values use explicit `candidate_entry`/`watch_entry` names.
- SVP text containing `⚠冲突`, `未收线`, `等收线`, `等解除`, `C等待`, or `观望` forces `WAIT` during migration, even with a legacy A grade.
- Hard main/sub conflict renders `主副强冲突`; soft conflict renders `主副冲突·等待`; never reuse stale `主副同向`.
- AggVol/HALDRO confirms, downgrades, or vetoes and never independently authorizes execution.
- R:R below 1:2 is non-executable.
- The resolver itself must fail closed: an A-grade candidate with a missing Entry/Stop/Target tuple, invalid stop/target geometry, or a claimed R:R that disagrees with the geometric R:R must become `WAIT` with no execution prices. A renderer or compatibility validator is not an acceptable last-line safety net.
- Recompute canonical R:R from the final Entry/Stop/Target whenever the tuple is complete; never authorize based only on an upstream claimed R:R.
- A full pipeline reporting 9/10 is incomplete and must remain labeled 9/10.

## TradingView and cache boundaries

- Unwrap MCP transport envelopes such as `{success,result}` before domain parsing.
- After symbol/timeframe changes, wait for indicator recalculation, verify `chart_get_state`, read tables/lines/boxes/labels/Data Window, and verify identity again before cache or screenshot writes.
- Require an explicit payload timestamp; a fresh file mtime only proves that a file was touched and must not substitute for capture time.
- Validate every required timeframe record, including nested symbol/timeframe identity and semantic evidence. Permit market-specific evidence profiles (for example BTC structure/SVP records versus XAU OHLCV records), but reject non-empty arbitrary shells.
- Wrong chart identity, stale/missing timestamps, invalid layer evidence, or an empty candidate pool must fail closed without overwriting the last good cache.
- Preserve field-level validity: missing POC must not erase valid OI/CVD/HALDRO.
- Candidate levels are not approved levels. Use `TV candidates → human approval → keylevels_config.json → single guard → price event → quick analysis → FinalVerdict`.

## Runtime and scheduled jobs

Check heartbeat liveness and business health (`active_approved_levels > 0` and unexpired), not heartbeat alone. Pin unattended jobs with supported cron commands; verify model/provider/mode/script/workdir with JSON read-back and a real no-trigger or trigger-path run. Audit enabled `no_agent` jobs and their stored prompts for stale direct-push/direct-decision instructions; a local script defaulting to no push is not proof that the scheduled configuration is safe under a future environment change. Keep Telegram delivery behind a per-run explicit authorization and never let a scheduled helper bypass FinalVerdict.

Run a final live-artifact probe after tests: reload the real JSON files with the same validators used by production, check TTL/identity/completeness, and refresh stale caches before reporting runtime health. A green subprocess exit code or a fresh mtime is insufficient evidence.

A price trigger is an event, not a direction signal. If provider quota/setup blocks execution, report the actual failure and only use a tested alternate path.

## Semantic fields

Keep `max_pain` (minimum aggregate settlement payout), `max_oi_strike` (largest OI strike), and `underlying_price` separate. Every consumer must require `max_pain_valid` and suppress invalid/outlier MaxPain values.

## Renderer coverage

Search and test every renderer. Fixing the quick renderer while `render_v96.py` still consumes raw `dual.direction_verdict` or legacy prices is not closure. Pass the same FinalVerdict to quick and full renderers and test WAIT, NO-GO conflict, and valid GO-A separately.

Completion audits must consume structured step results/statuses only. Never mark a source complete because its label (for example `CVD`, `黄金`, or `X情绪`) happens to appear in rendered text; card text is an output, not evidence. Include required non-crypto contracts such as XAU five-TF status in the source matrix as well as in the hard gate.

## Runtime hardening patterns

- Separate semantic freshness from filesystem freshness. A shared health helper should parse explicit payload timestamps, validate identity and usability, and choose among mirrored files by capture timestamp; never use `mtime` as market evidence or let a fresh `usable=false` payload pass.
- Bind paired artifacts with a per-run batch ID and a bounded timestamp skew. For a multi-stage market snapshot, stage all outputs, validate the pair, then publish with an atomic replace. On failure, preserve only a previously validated pair; otherwise publish an explicit stale/unavailable state.
- Keep compatibility gates diagnostic-only. `check_gate()` may expose legacy eight-question statuses, but `go`/`execution_authorized` must be derived solely from a valid FinalVerdict. Surface legacy conflicts under diagnostic fields so a report cannot confuse them with execution authority.
- Use one atomic JSON writer for trigger, heartbeat, watchdog-health, dispatcher-status, and context files: write beside the target, flush/fsync, then `os.replace`. Readers should see either a complete old document or a complete new document.
- Treat unattended delivery as a two-key capability: a per-run/explicit enable flag plus a separately configured target. Ignore historical call-site targets when the job is automated; lint enabled `no_agent` prompts for direct-push/direct-decision instructions and verify `deliver=local` jobs with a no-trigger smoke run.
- Version inherited context and store the previous FinalVerdict summary, primary action, source matrix, and approval/config revision. Reject future-dated or stale context, and never let inherited fields become an execution authorization source.

See `references/runtime-hardening-patterns.md` for the compact RED/GREEN and live-probe recipes behind these rules.

## Interface-drift closure

When a repair touches a producer/consumer contract (indicator plot titles, action-grid row names,
Data Window field names, packed codes), closure is not "tests pass". Three extra steps:

1. **One authority, proven.** Every field name must have exactly one definition site. Grep the
   repo for a handful of the names; if the same batch appears in two or more modules, *that is the
   defect* — a second hand-written whitelist that will silently drift (observed: four parallel
   mappings, and the action grid lost 9 of 13 rows for months without any error). Delete the
   duplicate and make the consumer read the authority.
2. **Keep legacy names readable.** Deleting a whitelist entry drops that key from already-cached
   payloads. Route retired names through the authority's own `LEGACY_*` table rather than keeping a
   parallel list; historical on-disk caches must stay readable, and the legacy table is the only
   place a dead name is allowed to appear.
3. **Automated alignment, not a checklist.** Keep a guard script that diffs the producer's source
   against the contract and exits non-zero on any gap, plus a regression test pinning it, so a
   producer-side edit that skips the contract fails immediately. Guard the *order* of ordered
   fields too, not only membership, and prefer a semantic classification over a hand-maintained
   allow-list (see the reference for a rule that needs no allow-list).
4. **Real-data end-to-end probe.** Hand-written fixtures only prove your own rule is
   self-consistent; they cannot catch "field name correct, value never arrives". Run the production
   chain once against live data (producer → parse → contract decode → resolver → renderer), assert
   on the produced artifact, and keep the probe script next to the audit output so it is re-runnable.
   A silently-empty field is the most common interface failure and only a live run exposes it.

Also re-check the consumers' *derived* whitelists: a skill/reference document that restates the
field list is a fourth drift source. Convert it to a pointer at the single authority.

See `references/interface-drift-closure.md` for the hunt, the guard design, and the probe shape.

## P2 incremental optimization patterns

For a dirty trading-system worktree, take one vertical P2 slice at a time: inventory active producers and consumers first, write a regression, then change the smallest load-bearing layer. Do not combine historical cleanup, renderer decomposition, and concurrency changes in one unverified refactor.

For optional market sources, add a versioned envelope with `source_id`, semantic `status`, explicit capture `timestamp`, raw `payload`, safe `error`, and separate `observed_at`. Preserve legacy flat fields while attaching the envelope, and materialize a source-record map for every routed source, including `not_run`, empty, failed, stale, and quota-cooldown outcomes. Matrix and completion consumers must prefer source records; optional-source degradation remains visible warning context and never becomes FinalVerdict authority.

A source marked `live`, `cache`, or `inherited` must have an explicit capture timestamp. Local call time may be `observed_at`, never a substitute for missing market-data time; filesystem mtime is not evidence. Publish source artifacts atomically and test both the new envelope and the old consumer field shape.

Before parallelizing independent collectors, measure a baseline and add a thread-execution regression. Bound the executor, keep FinalVerdict/TV identity transitions sequential, fetch outside the shared-cache lock, and merge each completed result under a read-modify-write lock or an atomic writer. Preserve deterministic aggregation order. Never parallelize first and retrofit cache safety later.

See `references/p2-source-contract-and-concurrency.md` for the reusable envelope shape, RED/GREEN cases, and concurrency checklist.

## Verification Result Semantics

Treat verification as a matrix, not a boolean. After every subsequent edit, invalidate earlier full-suite evidence and rerun the affected regression; if shared infrastructure changed, rerun the full suite. Record exact command, scope, exit status, and whether the result is `passed`, `degraded`, `failed`, or `not run`. Runtime probes that report stale caches, zero active approvals, or watchdog errors are blockers/degradation even when tests pass.

For parallel source collection, a filesystem atomic replace prevents torn JSON but not lost read-modify-write updates. Fetch outside the lock; use a bounded executor; merge each completed source under a per-path thread/process lock; then atomically publish. Verify both worker execution and preservation of all cache keys.

For source timestamps, `captured_at` must come from the provider/payload and `observed_at` records local observation. Cache write time and filesystem mtime are bookkeeping only; when `captured_at` is absent, keep the source explicitly unavailable/degraded.

## Closure report

Lead with `已完善 / 部分完善 / 未完善`. Enumerate repaired-and-verified items, current runtime state, blockers/degradation with source/timestamp/freshness, every remaining P0/P1/P2 item with acceptance criteria, and the next single active batch. Preserve the manual-decision boundary: no automatic orders unless separately requested.

## Reference

See `references/repair-evidence-patterns.md` for compact RED/GREEN/runtime evidence patterns.
See `references/final-verdict-runtime-contracts.md` for the resolver-invariant, cache-contract, completion-audit, and enabled-cron review patterns learned from live closure work.
