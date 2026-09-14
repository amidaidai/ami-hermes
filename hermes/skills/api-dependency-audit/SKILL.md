---
name: api-dependency-audit
version: 1.0.0
description: "Systematic audit methodology for external API/service dependencies across a codebase: discovering hardcoded endpoints, identifying single-point-of-failure domains, detecting silent failure patterns, finding endpoint mismatches (e.g. spot vs futures), and producing severity-categorized executable fix checklists with file:line references and shared utility recommendations, and mapping vendored third-party tool forks against their upstream (drift, missing capabilities, non-destructive sync probing)."
tags:
  - audit
  - api
  - reliability
  - binance
  - network
  - debugging
---

# API Dependency Audit Skill

## Purpose
Provide a repeatable, tool-driven methodology for auditing external API/service dependencies across a codebase. Designed to catch:
- Hardcoded single-domain endpoints with no fallback
- Silent exception swallowing that masks failures
- Endpoint category mismatches (spot vs futures, v1 vs v3, etc.)
- Data-source-failure-masquerading-as-success patterns
- Duplicate HTTP client logic that should be centralized

## When to Use
- Taking ownership of a codebase that calls external APIs
- Preparing for production hardening / reliability review
- Investigating "works locally but fails in cron/production" issues
- Before adding a new external dependency (baseline existing patterns)

## Methodology (4 Phases)

### Phase 1: Discovery — Map the Surface
```bash
# 1. Find all unique external domains
rg -o 'https?://[^/"]+' scripts/ | sort -u

# 2. Group by service (Binance spot, Binance futures, CoinGecko, etc.)
# 3. For each service, find all call sites with file:line
rg -n 'fapi\.binance\.com' scripts/
rg -n 'api\.binance\.com' scripts/
rg -n 'data-api\.binance\.vision' scripts/
```

**Output**: Service → [Endpoints] → [(file, line, endpoint, call_pattern)]

### Phase 2: Classification — Tag Each Call Site
For each call site, classify:
| Tag | Meaning |
|-----|---------|
| `SINGLE_POINT` | Only one domain used, no fallback list |
| `SILENT_SWALLOW` | `try/except: pass` or returns `None`/`{}` without upstream check |
| `ENDPOINT_MISMATCH` | Spot endpoint called with futures symbol (or vice versa) |
| `MASKED_FAILURE` | Function returns success-like structure even when all sources failed |
| `DUPLICATE_LOGIC` | Same HTTP + retry + fallback logic copied across ≥3 files |

### Phase 3: Severity Scoring
| Severity | Criteria | Example |
|----------|----------|---------|
| **S1** | Single-point futures endpoint (`fapi.binance.com`) with no `data-api.binance.vision` fallback; failure = silent data loss | `liquidation_collector.py:30` |
| **S2** | Single-point spot endpoint (`api.binance.com`) with no vision fallback | `btc_monitor.py:121` |
| **S3** | Silent swallow / masked failure / endpoint mismatch | `auto_card.py:2486` (spot/vision klines with futures symbol) |
| **S4** | All sources failed but code returns "OK" / empty success | `liquidation_collector.py:80` returns `data_ok=False` but exit 0 |

### Phase 4: Fix Checklist Generation
Produce a markdown table with **executable** rows:
| # | File:Line | Severity | One-Line Fix | Est. Lines |
|---|-----------|----------|--------------|------------|
| 1 | `liquidation_collector.py:11,30,31` | S1 | Extract `_fetch_with_fallback([fapi, vision])` | ~15 |

Always include:
- A **shared utility recommendation** (e.g. `scripts/binance_http.py`) to eliminate `DUPLICATE_LOGIC`
- **Acceptance criteria** for CI/smoke test (network fault injection, key-less fallback, freshness watchdog)

## Tools & Patterns

### Search Patterns (ripgrep)
```bash
# Binance endpoints
rg -n 'fapi\.binance\.com' --type py
rg -n 'api\.binance\.com' --type py
rg -n 'data-api\.binance\.vision' --type py

# Silent swallow patterns
rg -n 'except Exception:\s*pass' --type py
rg -n 'except:\s*return None' --type py
rg -n 'except Exception as e:\s*return' --type py

# HTTP clients
rg -n 'urllib\.request|requests\.get|httpx\.' --type py
```

### Shared Utility Template
Create `scripts/binance_http.py` (or `http_clients/<service>.py`):
```python
"""<Service> HTTP client: multi-domain fallback + signing + structured errors."""
SPOT_BASES = ("https://api.binance.com", "https://data-api.binance.vision")
FAPI_BASES = ("https://fapi.binance.com", "https://data-api.binance.vision")

def get_with_fallback(bases, path, params="", headers=None, timeout=8):
    """Returns (data, source_base) or (None, "")."""
    for base in bases:
        url = f"{base}{path}?{params}" if params else f"{base}{path}"
        data = _safe_get(url, headers, timeout)
        if data is not None:
            return data, base
        time.sleep(0.15)  # micro-jitter
    return None, ""

def signed_fapi(path, params, api_key, secret, timeout=10):
    """HMAC-signed request with FAPI_BASES fallback."""
    # ... signing logic ...
    return get_with_fallback(FAPI_BASES, path, signed_params, {"X-MBX-APIKEY": api_key}, timeout)
```

**All callers**: `from binance_http import get_with_fallback, signed_fapi, SPOT_BASES, FAPI_BASES`

## Anti-Patterns to Flag
| Pattern | Why It's Wrong | Fix |
|---------|----------------|-----|
| `requests.get(url, timeout=5)` inline in business logic | No retry, no fallback, no observability | Delegate to shared client |
| `except Exception: pass` / `return {}` | Masks 403/429/5xx/timeout/dns | Return structured error; let caller decide |
| `api.binance.com/api/v3/klines?symbol=BTCUSDT` | Spot klines endpoint with futures symbol | Use `fapi.binance.com/fapi/v1/klines` for futures |
| `data-api.binance.vision/api/v3/klines?symbol=BTCUSDT` | Vision spot endpoint with futures symbol | Vision spot only serves spot symbols |
| Writing cache file with `source="binance"` when all calls failed | Downstream freshness watchdog sees "fresh" file | Write `source="failed"` or skip write; watchdog must check content |
| Treating HTTP 200 as API success | Providers may return `200` with semantic errors such as `code=401`, plan restrictions, rate limits, or empty data | Validate provider-specific `code/msg/error/data`, not status alone |
| API keys embedded as source fallbacks (`env or "literal-key"`) | Secrets leak into Git/history and source scans | Use environment first, then an ignored local credential store; never a literal fallback |
| Testing new trading credentials by placing/cancelling an order | Verification creates unnecessary side effects | Use a signed read-only account endpoint; report auth as unverified if the network blocks it |
| Hardcoded request window/params (`from_="<date>", to="<date>"`, `date.today() - 90` literals) | Returns valid-looking, well-formed, but **stale** data forever; the freshness watchdog and the card renderer both pass it | Compute the window from `now()` at call time; echo the resolved window back in the payload (`as_of`) |
| `str(exc)[:N]` with a small `N` on provider errors | Truncation cuts off the diagnostic word (`You are not **entitled** to this data…upgrade your plan` → `{"status":"ERROR","error":"You a`) | Normalize known provider errors to a short reason code *before* any truncation |
| A credential file that contains only comments / `PLACEHOLDER…` / prose | Non-empty string ⇒ truthy ⇒ passed downstream as a real token; request fails and gets swallowed as "source unavailable" instead of "never configured" | Validate placeholder shape in the shared credential reader; return empty so callers see the configured/unconfigured distinction |
| A status table (docs/README/skill) listing provider health without a measurement date or re-run command | Freezes a past outage into a permanent false fact — the next reader trusts it and skips a working source | Stamp every status table with `measured_at` + the one-line command that re-measures it |
| A healthy payload whose freshness timestamp is keyed under a name the status contract doesn't recognise | The source is permanently labelled `unavailable` while its data is actually consumed — inverted mislabeling, and it hides real degradations behind constant noise | Publish the instant under a contract-recognised key as well; when re-verifying, evict the cached payload first |
| Renderer prints one warning for both "this tier deliberately skips the step" and "the upstream failed" | Readers learn to ignore the marker, so a genuine outage of that source becomes invisible | Reuse the pipeline's deliberate-skip convention (e.g. `⏭️ … skipped at this tier`); keep the warning icon for real failures only |
| Accepting a green unit-test run as verification for a data-plane change | Tests assert construction logic, not that the contract can parse the payload or that the output text is honest — both real defects of this class were invisible to a fully passing suite | Run the real pipeline end-to-end and read its output lines; if you have not looked at the actual output, it is not verified |
| `dict.get(key, default)` guarding a provider field that can be **present and `null`** | The default only covers a *missing* key; one null in a list makes a downstream `sum()`/comparison raise, and the collector reports a generic `request_failed` — indistinguishable from a network outage | Normalize nulls explicitly (drop before aggregating, or coerce to a sentinel) and add a unit test that feeds a null-bearing payload through the real parser |
| Guessing the auth header / host pair instead of deriving it from the credential's tier | Every call returns the provider's own "you are using the wrong API" code (4xx + provider `error_code`), which is consistently read as "source unavailable" — a perfectly good credential looks permanently dead | Probe the matrix (public host × pro header / × tier-correct header / × no key, paid host × paid header) printing only status + `error_code`; map tier→header→host in ONE module and forbid hand-written auth headers with a repo-scanning test |

## Quota-aware degradation and circuit breaking

Free-tier exhaustion is an expected runtime state, not a reason to abort the analysis pipeline. Treat every external source as optional unless it is explicitly the primary source for that asset and decision. A source failure must be visible and typed, while the core structure/price path continues.

Use a source-state contract such as:

| State | Meaning | Pipeline behavior |
|---|---|---|
| `live` | Fresh request succeeded | Use and timestamp it |
| `cache` | Cache is inside TTL | Use, but retain cache provenance |
| `stale_cache` | Request failed; old cache exists | Use only as degraded context and show the age/error |
| `unavailable` | No usable result | Mark the step incomplete; continue with required sources |
| `quota_cooldown` | 429/quota/plan limit recently observed | Do not retry repeatedly; continue and retry after cooldown |

On HTTP 429, rate-limit, or quota errors, persist a per-source/per-query cooldown (for example 10–15 minutes). Do not make every card re-hit an exhausted provider. Classify errors into `quota_or_rate_limited`, `credential_or_plan_blocked`, `timeout`, and `request_failed`; never print a green success marker for an empty or error-shaped payload.

Fallbacks must preserve semantic boundaries. For crypto, CoinGecko/CMC/FinanceKit are cross-checks and may degrade without blocking TV SVP, Binance Futures, or FinalVerdict. Do not replace an unavailable crypto source with a stale BTC value in a gold, forex, stock, or futures card. Propagate source status into the card's completeness/data-grade fields and into the final gate when the missing source is decision-critical.

**Acceptance tests:** inject 429 and 403 responses; assert the first failure is typed, a stale cache is explicitly marked, a second call during cooldown performs no network request, and the main analysis still returns a safe WAIT/NO-GO rather than crashing.

### Cross-asset execution audit rule
Before calling a collector, resolve the asset class and select its source profile. Crypto-only fields (Funding, Taker, OI, CVD, AggVol) must be absent from gold, forex, stock, futures, and unrelated option paths—not merely rendered as `N/A`. Pipeline completion counters must inspect the source status object; text presence or a non-empty stale payload is not evidence that a source completed successfully. Monitor/event mode is not an analysis mode and must not render a directional card or execution prices. A compact tested acceptance matrix is in `references/quota-safe-multi-asset-sources.md`.

## Credential onboarding and semantic verification

When a user supplies multiple provider credentials, onboarding is not complete after writing files:

1. Store them under a repository-ignored credentials directory; verify `.gitignore` covers the directory and naming patterns.
2. Use one class-level credential reader: environment variables first, local credential files second. Give the **code module** a neutral filename such as `credential_store.py`; broad rules like `*secret*` can accidentally ignore a module named `secret_loader.py`.
3. Scan the full source tree — **including docs, skills, READMEs and code comments** — for literal key fragments and
   remove all hardcoded fallbacks. A key pasted into a guide does not merely leak: it freezes whatever usage was
   current at the time as the documented standard, so the next reader re-introduces the exact bug.
4. Probe each provider without printing keys or sensitive payloads. Output only provider, HTTP status, semantic result class, and whether required data exists.
5. Distinguish `authenticated`, `public-only`, `plan-restricted`, `network-unverified`, and `invalid`. Never label `HTTP 200 + code 401` as healthy.
6. For multi-part authentication, verify completeness before enabling private operations. A lone API key may be insufficient when secret/passphrase/wallet signing are also required.
7. Run compile checks and the full regression suite after replacing credential-loading imports.

For a reusable probe matrix and safe output contract, see `references/multi-provider-credential-onboarding.md`.

## "Configured" ≠ "running with it": the three-layer availability check

A dependency can be correctly configured and still be broken in production. Check all three layers
separately, because each fails differently and the *diagnosis* differs even when the symptom is identical:

| Layer | Question | Signature of failure |
|---|---|---|
| **Config** | Does the config/manifest carry the required env (proxy, base URL, credentials)? | Static read of the config file |
| **Runtime** | Does the **process actually running** have that env? | Config edited after the process started ⇒ process is stale; config edits are not picked up without an explicit reload |
| **Functional** | Does the upstream actually answer *through that path*? | A/B the same request with and without the env (e.g. direct vs proxy) to prove whether the setting is even necessary |

Worked example (the exact bug class): a Yahoo-backed collector returned rate-limit errors. Config had the
proxy; six *running* subprocesses did not, because they predated the config edit. An A/B proved the setting
was load-bearing (direct `403`, via proxy `200`). The fix was reload + reaping the stale processes — not
touching the collector code at all.

**Corollary — instance multiplicity:** when several surfaces (CLI / gateway / desktop app) each spawn their
own subprocess, some instances carry the env and some don't, and any caller may bind to either. The invariant
to assert is **"no instance lacking the required env exists"**, not "at least one good instance exists".
Aggregate the report per server (`with-env N / without-env M`) instead of emitting one warning per PID.

**Corollary — multi-line file credentials:** reading a "comment header + value" file raw and using the whole
content as a token corrupts the auth header. Strip comment lines and take the first meaningful line; keep the
whole content only for structured formats (`.json`). See the silent-failure reference for the guard rules.

## Auditing the auditor: validate the probe before trusting the finding

A probe that reports a risk is itself untested code. Every false positive costs credibility and every false
negative hides a real outage. **Confirm each `MISSING` / `BROKEN` / `unavailable` finding through a second
independent channel before it enters the report.** Real probe bugs seen in one session:

- Wrong credential field name (`api_secret` vs `secret_key`) reported the credential as *absent*.
- An invented endpoint path reported `404` — the provider was fine; the probe was wrong.
- Classifier ordering: `code=401` inside a `200` body was bucketed as `live` because the state check
  compared a prefix the error string didn't have. Assert on parsed fields, not on string prefixes.
- A CJK heuristic meant to reject prose credentials also rejected a valid JSON credential file.
  Tighten guards until the real credentials in the tree all still pass — then keep that as a regression test.

Two rules that follow: **separate the probe's own bugs from the system's bugs in the report**, and **make the
probe re-runnable with a persisted baseline**, so "this used to work and now doesn't" is detected automatically
instead of waiting for someone to ask again.

For the detailed recipes, guard rules, and scanner shape, see
`references/availability-verification-layers.md`.

## Retiring a dependency is a lifecycle operation, not a deletion

When the user says a source/step "is useless, remove it", triage before retiring. A source that has failed for
weeks is usually **two stacked, fixable defects** (auth-scheme mismatch + a parser crash); deleting the step
just buries the bug until the next source repeats it. Prove the death cause first, then retire with a checklist.

**Step 1 — prove why it dies (probe matrix).** Print only HTTP status + provider `error_code`, never the key:
public host × the header the code currently sends / public host × the header the credential's *tier* requires /
public host × no key / paid host × paid header. A demo-tier key sent under the paid header on the public host
returns 4xx with a provider error code **on every call** — the most common disguise for "this source is dead".

**Step 2 — get the real exception.** The recorded error is a *classified code* (`request_failed`,
`quota_or_rate_limited`, `credential_or_plan_blocked`, `timeout`), not the message, so a parser crash reads as
"request failed" and sends you chasing the network. To see the traceback, monkeypatch the collector's own
module-level cache helper to call the fetcher directly and `traceback.print_exc()` (collectors look that name up
as a module global, so the patch applies); patch the HTTP helper too — **HTTP succeeding while the source still
errors means the parser broke, not the request**.

**Step 3 — retirement checklist** (every missed item leaves a ghost):
1. Remove the step from the canonical pipeline tuple **and** from any `ordered`/routing list.
2. Keep the step id in the step table with an **empty asset set** (+ reason in its description) so historical
   cards/artifacts still resolve labels; add a guard test asserting it cannot re-enter a route for any
   `(symbol, mode)`.
3. Delete the executor's collection code, its completion marking, and its audit-label mapping — otherwise the
   completion table keeps a row that is permanently `⚠️` or silently absent.
4. Delete its row from the source/verification matrix: a retired-but-still-listed source emits a permanent
   degradation warning, which trains both readers and downstream gates to ignore that field.
5. Sync the hardcoded fallback step list and every "N-stage" comment and doc string.
6. `grep` the test tree for the step id **and for hand-written assertions that pin the old code text** — those
   break the build until updated, and they are invisible if you only run the tests you thought were relevant.
7. Re-run the real pipeline once and confirm the printed route length and the audit row count agree; then run the
   full suite.

**Step 4 — leave a restore path.** Keep the collector functions (still library-callable) and write the retirement
reason plus the fixed root causes next to the step definition, so "bring it back" costs one line instead of a
re-investigation. Never re-add a retired step — or quietly call its collector from another step — without
reading that note.

Worked recipe (probe script shape, monkeypatch snippets, acceptance checks):
`references/dead-source-triage-and-retirement.md`.

## Trading and derivatives data contracts

When auditing a multi-source trading pipeline, endpoint availability is not enough: verify that price, K-lines, OI, funding, taker flow, and TradingView all describe the same execution market. For Binance USD-M perpetual analysis, Futures price and `/fapi/v1/klines` are the primary contract; spot/CMC/CoinGecko are cross-checks or explicitly graded fallbacks, never silent replacements. Require structured `available/stale/timeout/invalid/missing/not_applicable` states and propagate them into the final gate instead of swallowing errors.

For scheduled analysis, pin the provider and model on the job itself. Interactive model switching must not change an unattended production job or cause it to fail closed on provider/model drift. Verify the pin by running the job once and inspecting both the job record and execution result.

For options, distinguish `max_pain` (strike minimizing aggregate settlement payout) from `max_oi_strike` (largest open-interest strike). Apply a configurable distance sanity check against the underlying and mark implausible values `invalid`; invalid options fields must not enter directional or execution gates.

See `references/trading-data-source-contract.md` for source priority, semantic validation, fallback grading, and acceptance tests.

## Acceptance Criteria (Definition of Done)
1. **Zero S1/S2** findings in `rg` scan after fixes
2. **Shared client** used by ≥80% of call sites for each service
3. **Fault injection test**: `tc qdisc add dev eth0 root netem loss 30%` → all collectors return `source: "data-api.binance.vision"` with non-empty key fields
4. **Keyless mode**: `unset API_KEY` → collectors degrade gracefully (public endpoints only) with `quality: "public_fallback"` tags
5. **Freshness watchdog** validates both mtime AND content (non-empty key fields) for each critical cache file

## Vendored third-party tools: fingerprint before evaluating, probe before upgrading

When the user shares an article/post/repo claiming a capability ("this MCP lets an AI drive charting — is it useful for us?"), do not evaluate it as something new. Fingerprint the install first: we may already run that exact tool as a local fork. The MCP servers under `D:/Hermes agent/tools/` are forks, not pristine upstream checkouts — the registered `tradingview` server is one such fork carrying owner patches.

```bash
# Which MCP servers exist and where do their entry points live
grep -n -A5 '^  [a-z0-9-]*:$' ~/AppData/Local/hermes/config.yaml
# Is the shared repo a fork we already carry
cd "<tools-dir>/<tool>" && git remote -v && git status -sb | head -1
```

Report the delta only. A post describing a tool we already run has zero new capability; its value is the upstream repo it links, not the workflow it teaches.

### Drift check: local fork vs upstream

Measure three dimensions before recommending anything — commit drift alone does not say what is missing.

| Dimension | Command | What it answers |
|---|---|---|
| Commits | `git fetch origin` then `git rev-list --count HEAD..origin/main` + `git log origin/main..HEAD --oneline` | How far behind, how many owner commits to preserve |
| Entry surface | grep registrations on both sides, then `comm -13 ours.txt upstream.txt` | Which capabilities are actually missing locally (new tools often land inside existing files, so diff the registration names, not the file list) |
| Collision risk | `git status --porcelain` + `git diff --stat` | Which files an upgrade would collide with — uncommitted owner work is the thing you must not clobber |

Pull the upstream copy of a file with `git show origin/main:<path>` to compare without checking anything out. Never trust a README's tool count — count registrations.

### Non-destructive sync probe

Never trial-merge inside the live checkout. Probe each candidate commit in a throwaway detached worktree and report CLEAN vs CONFLICT per commit before touching anything:

```bash
bash <skill>/scripts/upstream_sync_probe.sh "D:/Hermes agent/tools/<tool>" <sha> [sha ...]
```

Decision rules:
- A whole-repo `merge`/`pull` into a fork with uncommitted work in the same files is the wrong move: it collides with owner patches and can overwrite unfinished work. Never do it.
- Cherry-pick only the commits whose fixes reach a live path we depend on, in dependency order, once the probe says CLEAN; resolve the conflicting ones by hand.
- A conflict almost always means the owner already patched that same file. Treat it as "two authors touched one file", not as a failed upgrade.
- Owner work always wins: back up / commit local edits to a branch before any sync, and never discard them to make the merge clean.

### Closing the loop after a sync
1. Run the project's own test suite (`npm test` / `pytest`) — a fork's tests may have been edited locally, so a green suite is only evidence if it ran the fork's suite.
2. Clear bytecode/caches for anything a scheduler or plugin host holds open (`find . -name '*.pyc' -delete`). Source edits are not picked up by an already-running scheduler or MCP host process.
3. Reload the MCP server (`POST /api/hermes/mcp/reload` with the profile header) and re-run its health tool. The reported tool count is the proof that a pinned/self-updating binary did not silently swap under you.
4. Re-run the real pipeline entry point end-to-end, not just unit tests.

See `references/vendored-fork-upstream-sync.md` for the worked fingerprint/drift/probe sequence and the release-check table used to report the result.

## Related Skills
- `diagnose` — for root-causing specific failures found during audit
- `systematic-debugging` — 4-phase loop complements this audit methodology
- `code-quality-verification` — pre-commit gate can include `rg` scans for anti-patterns

## MCP Deferred-Tool Call Mechanics
When fixing dependency/call-site issues that involve MCP-provided tools, see `references/mcp-deferred-tool-call-mechanics.md` — covers the cross-turn re-registration pitfall (`Tool 'x' does not exist` ≠ server down; re-`tool_describe` fixes it), distinguishing registry-stale from CDP/bridge disconnects, and the `tool_call`-cannot-invoke-`tool_call` trap.