---
name: api-dependency-audit
version: 1.0.0
description: "Systematic audit methodology for external API/service dependencies across a codebase: discovering hardcoded endpoints, identifying single-point-of-failure domains, detecting silent failure patterns, finding endpoint mismatches (e.g. spot vs futures), and producing severity-categorized executable fix checklists with file:line references and shared utility recommendations."
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
3. Scan the full source tree for literal key fragments and remove all hardcoded fallbacks.
4. Probe each provider without printing keys or sensitive payloads. Output only provider, HTTP status, semantic result class, and whether required data exists.
5. Distinguish `authenticated`, `public-only`, `plan-restricted`, `network-unverified`, and `invalid`. Never label `HTTP 200 + code 401` as healthy.
6. For multi-part authentication, verify completeness before enabling private operations. A lone API key may be insufficient when secret/passphrase/wallet signing are also required.
7. Run compile checks and the full regression suite after replacing credential-loading imports.

For a reusable probe matrix and safe output contract, see `references/multi-provider-credential-onboarding.md`.

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

## Related Skills
- `diagnose` — for root-causing specific failures found during audit
- `systematic-debugging` — 4-phase loop complements this audit methodology
- `code-quality-verification` — pre-commit gate can include `rg` scans for anti-patterns

## MCP Deferred-Tool Call Mechanics
When fixing dependency/call-site issues that involve MCP-provided tools, see `references/mcp-deferred-tool-call-mechanics.md` — covers the cross-turn re-registration pitfall (`Tool 'x' does not exist` ≠ server down; re-`tool_describe` fixes it), distinguishing registry-stale from CDP/bridge disconnects, and the `tool_call`-cannot-invoke-`tool_call` trap.