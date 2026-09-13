---
name: trading-system-implementation-closure
description: "Use when verifying trading-system audit repairs."
category: trading
tags: [trading, audit, tdd, runtime, verification]
---

> **同族导航** — 审计组 6 个技能各司其职，别加载错 （同族入口：`tangxi-analysis-audit-checklist`）
> · **本技能 `trading-system-implementation-closure`** = 修复后的验收收口（改完才用）
> · 同族其余：`tangxi-analysis-audit-checklist`（入口 · 七维全景扫描 + 资产面三查（记忆/技能/MCP），先取证后定级）、`trading-system-audit`（全栈审计，P0/P1/P2 深挖与修复）、`tangxi-runtime-audit-and-cleanup`（运行态（心跳/PID/cron/数据新鲜度）+ 脚本生存性评估与归档）、`tangxi-system-audit`（大版本更新后的全面审计 + git 收口）、`trading-analysis-system-audit-methodology`（审计方法论与定级口径（过程文档））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# Trading System Implementation Closure

Use this class-level skill when an audit repair must be implemented and proven. The deliverable is a working, exercised change plus an explicit unresolved register, not a plan or optimistic report.

## Core workflow

1. Re-check git status, current runtime, cron JSON, caches, TV state, and interpreter before using historical evidence. A pasted “audit complete / P0 fixed” narrative (user or prior agent) is a list of claims, not evidence — do not echo its tables; re-read the live files.
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
- `valid_until` auto-renewal of existing approved levels is not a structure refresh. Read each level's `source` and price; if `source` is an old candidate timestamp while `keylevels_candidates.json` is fresh, the pool was collected but not promoted. Do not report “关键位数据已更新” from TTL alone.

## Runtime and scheduled jobs

Check heartbeat liveness and business health, not heartbeat alone. `active_approved_levels > 0` is **ok**; all configured levels `enabled=false` (user silenced) is **idle**, not DEGRADED — do not auto-enable or auto-renew silenced levels. Zero configured/expired levels remain degraded. Pin unattended jobs with supported cron commands; verify model/provider/mode/script/workdir with JSON read-back and a real no-trigger or trigger-path run. Audit enabled `no_agent` jobs and their stored prompts for stale direct-push/direct-decision instructions; a local script defaulting to no push is not proof that the scheduled configuration is safe under a future environment change. Keep Telegram delivery behind a per-run explicit authorization and never let a scheduled helper bypass FinalVerdict.

An analysis lease with `active=true` is not a lease if the holder PID is dead; background deferral may return 0 only when the published cache is still usable. After an analysis or screenshot run: `python scripts/tv_analysis_lease.py status`. If the holder PID is dead or `expires_at` has passed, `python scripts/tv_analysis_lease.py end` then `status` until the reason is `无分析租约`. Status may still echo the stale blob under `lease` when `active=false` / `租约已过期` — only `end` clears the file.

Do not treat stale `monitor_heartbeat.json` / `.btc_daemon_heartbeat.json` as the current monitoring chain. The live chain is `keylevel_guard` + `btc_keylevel_guard_watchdog` + `keylevel_read_trigger` + `btc_tv_refresh`. Weeks-old daemon heartbeats are historical dead, not a P0 of the current guard.

Historical sentinel scripts still on disk (`btc_keylevel_sentinel` / `rest_guard` / `ws_guard` / `btc_price_arrival_sentinel`) must fail closed at `__main__` (retired banner, exit 0) — they are state ② (present, not running), not deleted.

Run a final live-artifact probe after tests: reload the real JSON files with the same validators used by production, check TTL/identity/completeness, and refresh stale caches before reporting runtime health. A green subprocess exit code or a fresh mtime is insufficient evidence.

A price trigger is an event, not a direction signal. If provider quota/setup blocks execution, report the actual failure and only use a tested alternate path.

## Semantic fields

Keep `max_pain` (minimum aggregate settlement payout), `max_oi_strike` (largest OI strike), and `underlying_price` separate. Every consumer must require `max_pain_valid` and suppress invalid/outlier MaxPain values.

## Renderer coverage

Search and test every renderer. Fixing the quick renderer while `render_v96.py` still consumes raw `dual.direction_verdict` or legacy prices is not closure. Pass the same FinalVerdict to quick and full renderers and test WAIT, NO-GO conflict, and valid GO-A separately.

SVP panel `风控` text (`入/止/标`) is display-only. Executable Entry/Stop/Target come only from MCP Data Window prices when `risk_label==风控`. Observation (`风控·观察`) goes to `candidate_*` / watch tuples. Renderers must never fall back `entry or position` — `位置` is structure, not an order.

Completion audits must consume structured step results/statuses only. Never mark a source complete because its label (for example `CVD`, `黄金`, or `X情绪`) happens to appear in rendered text; card text is an output, not evidence. Include required non-crypto contracts such as XAU five-TF status in the source matrix as well as in the hard gate.

## Runtime hardening patterns

- Separate semantic freshness from filesystem freshness. A shared health helper should parse explicit payload timestamps, validate identity and usability, and choose among mirrored files by capture timestamp; never use `mtime` as market evidence or let a fresh `usable=false` payload pass.
- Bind paired artifacts with a per-run batch ID and a bounded timestamp skew. For a multi-stage market snapshot, stage all outputs, validate the pair, then publish with an atomic replace. On failure, preserve only a previously validated pair; otherwise publish an explicit stale/unavailable state.
- Keep compatibility gates diagnostic-only. `check_gate()` may expose legacy eight-question statuses, but `go`/`execution_authorized` must be derived solely from a valid FinalVerdict. Surface legacy conflicts under diagnostic fields so a report cannot confuse them with execution authority. A GO/NO-GO row `R:R GREEN` can coexist with FinalVerdict `NO-GO` from `haldro_state_conflict` / `advanced_confluence`. Grep the card artifact for any claimed `rr2=` number; if absent, do not copy it from the narrative. Body text `·R:R不足` is not proof of geometric R:R < 2 when the gate row is green — name the actual hard-gate ids.
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

## Indicator packed-field closure and lease hygiene

For a Pine producer with packed Data Window fields, decode through the single contract module before adding gates. The validated sequence is: source hash/plot alignment → packed-code unit tests → resolver gates → renderer/backtest consumer audit. The SVP buses `Trigger Pack`, `Evidence Pack`, `Regime Pack`, `Contract Pack`, `StructPack`, `Quality Code`, and `CVD Method Code` must be fail-closed when present; legacy payloads may omit them, but malformed supplied buses cannot become decorative text. For the AggVol side, `Coverage Feed Mode`, stale-venue count, CVD quality, OI presence, and OI agreement belong in FinalVerdict semantics, not only card annotations. Keep B/C as observation-only and never let the副指标 upgrade SVP authorization.

When tests exercise TradingView background collectors, an interactive analysis lease can intentionally defer them. A full-suite failure that prints an explicit lease/defer message is usually shared runtime state, not a production regression: read the lease status, end only the stale/current test lease through the supported CLI, verify `active=false`, then rerun the failed tests and the full suite. Never weaken the lease guard or patch tests to bypass it.

See `references/indicator-packed-field-closure.md` for pack formulas, gate mapping, and the lease-aware verification recipe.

## Chart evidence closure: price bar + ICT + visual chart

A complete TradingView review is not equivalent to reading the SVP/AggVol action tables. Build a `chart_evidence` record that binds the same live chart identity to the price bar, visible studies, Pine lines/boxes/labels, and ICT structure. At minimum capture: symbol, resolution, studies, last price, OHLC/day range when available, VAH/VAL/POC/nPOC/VWAP, FVG/OB/Breaker zones, BOS/MSS/CHoCH labels, and liquidity levels.

Use explicit evidence states: `verified`, `partial`, `identity_mismatch`, and `unavailable`. `verified` requires the expected symbol/timeframe, required studies, a live price, and machine-readable ICT objects or equivalent structured evidence. `partial`/visual-only evidence may support an observation path but must never produce `GO-A`; `identity_mismatch` is a hard blocker. For BTC, 15m is the execution timeframe and 5m is only the trigger timeframe—never let a 5m chart silently stand in for the 15m decision layer.

After any chart switch, read state again after recalculation, then read tables, Data Window, lines, boxes, and labels, and only then write the cache or screenshot. Treat an empty object read as missing evidence, not as proof that no FVG/OB/BOS/MSS exists. Preserve the chart evidence status and identity in `FinalVerdict` and add a dedicated gate so renderers cannot silently bypass it.

See `references/chart-evidence-closure.md` for the reusable schema, fail-closed matrix, and live probe checklist.

## Live TradingView acceptance evidence

A Pine compile result is only one layer of proof. For a dual-indicator release, run the following independent acceptance sequence: compile/open the saved SVP script and saved AggVol script with the TradingView smart-compile path and require `has_errors=false`; read `chart_get_state` and require the exact symbol, resolution, and both study names; read `data_get_study_values` from that same active chart and require non-empty raw values plus source-bar time; read both action tables and compare the SVP `协同` S-code with the AggVol `信号` S-code; finally capture a full-chart screenshot after the identity/state read. A live S3 or WAIT result is valid evidence of the fail-closed contract, not a compile failure. Do not claim cloud/runtime acceptance from source hashes or local tests alone.

The verified packed-field rule is: use raw Data Window values, not rounded display text; decode `Trigger/Evidence/Regime/Contract/Struct/Quality` through the single contract module; and treat supplied malformed or stale packs as gates. Preserve the exact observed `symbol`, `resolution`, study IDs, source-bar timestamps, and screenshot path in the closure report.

## Verification Result Semantics

Treat verification as a matrix, not a boolean. After every subsequent edit, invalidate earlier full-suite evidence and rerun the affected regression; if shared infrastructure changed, rerun the full suite. Record exact command, scope, exit status, and whether the result is `passed`, `degraded`, `failed`, or `not run`. Runtime probes that report stale caches, zero active approvals, or watchdog errors are blockers/degradation even when tests pass.

For parallel source collection, a filesystem atomic replace prevents torn JSON but not lost read-modify-write updates. Fetch outside the lock; use a bounded executor; merge each completed source under a per-path thread/process lock; then atomically publish. Verify both worker execution and preservation of all cache keys.

For source timestamps, `captured_at` must come from the provider/payload and `observed_at` records local observation. Cache write time and filesystem mtime are bookkeeping only; when `captured_at` is absent, keep the source explicitly unavailable/degraded.

## Closure report

Lead with `已完善 / 部分完善 / 未完善`. A self-summary that lists P0/P1 as done is not a closure report — independent live probes first, then those three labels against the probes. Enumerate repaired-and-verified items, current runtime state, blockers/degradation with source/timestamp/freshness, every remaining P0/P1/P2 item with acceptance criteria, and the next single active batch. Preserve the manual-decision boundary: no automatic orders unless separately requested.

## Reference

See `references/repair-evidence-patterns.md` for compact RED/GREEN/runtime evidence patterns.
See `references/final-verdict-runtime-contracts.md` for the resolver-invariant, cache-contract, completion-audit, and enabled-cron review patterns learned from live closure work.
See `references/self-report-closure-verification.md` for verifying a pasted audit-complete narrative against live keylevels, card, lease, and guard state.
