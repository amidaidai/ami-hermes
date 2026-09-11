# Repair and production-readiness guardrails

This reference captures reusable lessons from the audit-to-repair workflow. It is not a record of one machine's transient state.

## Tight regression seams

Before changing production code, create or run fixtures that prove the exact unsafe behavior is blocked:

- TV cache has parseable `_tv_pine` but `usable=false` → final state is `NO-GO`, with entry/stop/target cleared.
- Advanced confluence/meta gate returns `execute=false` → `FinalVerdict` contains a hard blocker; display-only `gate_verdict` is insufficient.
- Meta-label import/call raises → result is `execute=false`, confidence `0`, and a reason that says the gate is unavailable.
- `C反多` and `C反空` retain `long` and `short` as watch direction while remaining non-executable.
- A source snapshot with a fresh outer timestamp but an expired nested macro timestamp is unusable.
- A cache with no symbol identity is rejected instead of being treated as a generic cache.

Use the smallest deterministic fixture at the seam, then run the full suite and a real no-delivery pipeline. Do not infer success from an exit code alone.

## Dependency repair pattern

1. Build a local import/call graph and distinguish production paths from tests and retired daemons.
2. Restore only pure calculations, replay/labeling adapters, read-only bridges, and explicit compatibility functions.
3. Keep write behavior behind a separate authorization boundary. A restored module must not re-enable order placement, cancellation, resident monitoring, or Telegram delivery by import side effect.
4. Replace missing optional capabilities with structured `unavailable`/`degraded` output when their absence changes a decision. Keep non-decision enrichments visibly optional.
5. Verify both import collection and behavior: focused tests, full tests, syntax checks, then a real no-push invocation.

## TradingView recovery pattern

A live E2E suite may leave a shared chart on a test study or a different symbol. Recovery is:

1. Read chart state and confirm the production symbol/timeframe.
2. Open the saved production Pine script rather than overwriting it from memory.
3. Compile/add it to the chart and wait for indicator recomputation.
4. Read the study list, Pine action tables, Data Window values, and the CVD/AggVol study separately.
5. Capture a fresh full screenshot with price axis and required panes.
6. Only then refresh symbol-specific cache files; reject partial `Volume/Plot` data.

“Script opened” or “compile button clicked” is not equivalent to “study attached”.

## Local-only liveness witness

On native Windows, use `asyncio.start_server(..., host="127.0.0.1", port=0)` for the event-loop witness. Persist the selected port in the heartbeat, and have the supervisor probe `127.0.0.1:<port>` while validating the heartbeat PID. Do not bind the witness to `0.0.0.0`; do not treat an absent witness as proof of a wedge.

## Side-effect verification

- For every external write, read back the exact target or record an explicit dry-run/no-op result.
- Run automated analysis with delivery disabled. A manual `--push` path and an automated cron path must have distinct authorization gates.
- Never drain an old notification queue whose targets, parse mode, or rate-limit history are not revalidated.
- After changing a service launcher or binding setting, verify the running process, listener address, localhost response, and LAN refusal. A launcher edit alone is pending until the service is restarted and rechecked.
