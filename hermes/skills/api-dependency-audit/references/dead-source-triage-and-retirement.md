# Dead-source triage and dependency retirement

Use when a source/step must be judged: "this one never has data, remove it", or an audit keeps showing
`⚠️ no valid fields this round` / `stale_cache` for the same step.

## 1. Probe matrix — prove the death cause before deleting anything

Write a throwaway probe (keep it as evidence) that prints **only** status + provider `error_code` + a short body
prefix. Read the credential through the shared credential reader; never echo the key.

| Probe | What it distinguishes |
|---|---|
| public host + the header the code currently sends | reproduces the failing code |
| public host + the header the credential's tier requires | `200` ⇒ cause #1 confirmed: header/tier mismatch |
| public host + no key | public tier still usable (tighter rate limit) |
| paid host + paid header | "no subscription" vs "wrong syntax" |

CoinGecko worked example (measured):

| Combination | Result |
|---|---|
| `api.coingecko.com` + `x-cg-pro-api-key` (demo key) | **400 · error_code 10010** |
| `api.coingecko.com` + `x-cg-demo-api-key` (demo key) | **200 · data returned** |
| `api.coingecko.com` + no key | 200 (tighter limits) |
| `pro-api.coingecko.com` + `x-cg-pro-api-key` (demo key) | 400 · error_code 10011 |

Rule: a key prefixed `CG-` is a **demo** key ⇒ public host + `x-cg-demo-api-key`. Sending it under the pro header
is what made a working credential look permanently dead.

## 2. Get the real exception — the recorded error is a taxonomy code

The source contract stores `request_failed` / `quota_or_rate_limited` / `credential_or_plan_blocked` / `timeout`
(see the classifier), not the exception text. A `TypeError` inside the parser is therefore bucketed as a network
failure. Two monkeypatches (the collector resolves both names as module globals, so patching the module works):

```python
# A. Did HTTP actually fail?
orig = m._fetch
m._fetch = lambda url, headers=None, timeout=10, **kw: (
    print("hdr", list((headers or {}).keys())), orig(url, headers=headers, timeout=timeout, **kw))[1]

# B. Where did it really raise? (bypasses the cache helper's try/except that swallows it)
def spy_cached(key, fetcher, ttl=300, cache_when=None):
    try:
        return fetcher()
    except Exception:
        traceback.print_exc()
        raise
m._cached = spy_cached
```

Interpretation:
- HTTP fine + source still errors ⇒ **parser** broke (e.g. a provider field that is present but `null`: `get(k, 0)`
  covers "missing", not "null", and the downstream aggregation raises).
- HTTP errors ⇒ re-read the probe matrix; do not touch the parser yet.
- Also inspect the circuit-breaker state file — entries are keyed by *source name*, and an old entry whose
  `blocked_until` already passed is a red herring; convert the timestamp before believing it blocks anything.

## 3. Retirement checklist

1. Remove the step from the canonical pipeline tuple and from any `ordered`/routing list.
2. Keep the step id in the step table with an **empty asset set** + reason in its description (historical
   cards/artifacts still need the label); add a guard test: for every `(symbol, mode)`, the id never appears.
3. Executor: delete the collection code, the completion marking (`completed.add("<step>")`), and the audit label
   mapping — a leftover row shows up as permanently `⚠️` or as a missing line in the completion table.
4. Source/verification matrix: delete its context row, otherwise it emits a permanent degradation warning that
   pollutes the final gate's warning list and desensitizes readers.
5. Sync the hardcoded fallback step list (the one used when the router import fails) and every "N-stage" comment
   or doc string.
6. Tests: update length/sequence assertions; `grep -rn "<step>" tests/` for hand-written assertions that pin the
   old code text (they fail the build until updated); add the guard test from item 2.
7. Docs: pipeline step-count tables and flow chains in `docs/` and `references/`, plus the skill body's own "N
   steps" mentions.
8. Acceptance: run the real entry point once, confirm the printed route length equals the audit table row count,
   and only then run the full test suite.

## 4. Credential hygiene while touching this area

- One module owns tier→header→host mapping (probe it, then forbid hand-written headers with a repo-scanning test).
- Keys come from the credential store only; **never** write a key into a skill, reference file, README or comment.
  A key pasted into a guide freezes the (usually wrong) usage of that moment as the documented standard.
- Verify a fix with a real end-to-end call showing the source's own `live` status — a green unit suite does not
  prove the contract can parse a real payload.
- Read `stale_cache` carefully **right after** a fix: it is what you get when the *new* attempt failed while an old
  payload still exists, so a `stale_cache` that carries an error means the fix is incomplete; a pure within-TTL
  cache hit returns `cache` without touching the network. Only a fresh call reporting `live` (real fields, no
  error) counts as fixed — do not conclude "fix failed" from a stale payload that the cache is still serving.

## 5. What NOT to do

- Do not conclude "inherently useless" from repeated failures — run section 1 first.
- Do not delete the collector: keep the functions plus the retirement note so restore cost is one line.
- Do not silently re-collect a retired source from inside another step to "fill the gap".
