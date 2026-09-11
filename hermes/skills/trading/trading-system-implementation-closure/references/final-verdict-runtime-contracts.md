# FinalVerdict and Runtime Contract Patterns

Reusable notes for closing trading-system audit findings.

## Resolver-level safety

Test the resolver directly, not only renderers:

1. A-grade + claimed R:R but missing Entry/Stop/Target → `WAIT`, `executable=false`, all execution prices `None`.
2. A-grade + wrong long/short stop-target geometry → `WAIT`, no executable prices.
3. A-grade + claimed R:R that differs from `abs(Target-Entry)/abs(Entry-Stop)` → use geometric R:R; if below 2.0, `WAIT`.
4. WAIT/NO-GO must not regain prices through a renderer or legacy adapter.

The renderer and compatibility validator are defense-in-depth. They cannot be the only place that blocks malformed execution data.

## Five-timeframe payloads

- Require an explicit capture timestamp. Do not fall back to filesystem mtime.
- Normalize aliases to `D`, `4h`, `1h`, `15m`, `5m`.
- Validate top-level and nested chart identity/timeframe.
- Require each non-empty record to carry valid price evidence plus a semantic evidence profile. BTC may use price + SVP/action-grid structure; XAU may use OHLCV. A non-empty arbitrary dictionary is not a valid layer.
- Preserve `invalid_timeframes` separately from missing layers so coverage cannot hide malformed content.

## Completion audits

Completion is evidence-based:

- Accept structured source status (`live`, `cache`, `inherited`) and successful phase output.
- Do not infer completion from rendered labels or prose such as `CVD`, `黄金`, or `X情绪`.
- Do not default an unstamped source to `live`; at most treat a non-empty legacy payload as `cache`, and expose the downgrade.
- Required XAU five-timeframe status belongs in the source matrix with `hard_gate` role when Full requires it.

## Live closure probe

After focused/full tests, reload actual production files using production validators. Check:

- BTC five-timeframe `usable`, coverage, missing and invalid layers;
- XAU five-timeframe + 5m action-grid pair usability;
- temporary staging files absent;
- payload timestamps within TTL;
- enabled cron jobs, scripts, `no_agent`, delivery target, and stale stored prompts;
- external delivery authorization remains off unless explicitly requested.

A successful child process, fresh mtime, or passing unit suite alone is not runtime proof. If the probe finds stale data, refresh it and probe again; never relabel stale cache as live.

## TDD evidence sequence

For each closure finding: add the smallest behavioral regression, run it red against the current code, patch the production boundary, run the focused green suite, then run compile/type/full tests and a live artifact probe. Keep the unresolved register separate from passing evidence.
