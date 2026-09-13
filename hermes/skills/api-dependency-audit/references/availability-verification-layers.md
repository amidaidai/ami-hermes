# Availability verification: layers, silent failures, and probe self-validation

Companion detail for the "three-layer availability check" and "auditing the auditor" sections of
SKILL.md. Written from a real multi-asset trading-system audit where every item below was hit.

## 1. The three layers, with the failure each one produces

```
Config layer     →  the manifest carries the setting            (static read)
Runtime layer    →  the RUNNING process carries the setting     (process env / effective config)
Functional layer →  the upstream answers through that path      (A/B probe)
```

| Symptom seen by the caller | Config | Runtime | Functional | Real diagnosis |
|---|---|---|---|---|
| `429 / Too Many Requests` from a geo-blocked API | ✔ present | ✘ absent | setting is load-bearing | stale process, not API rate limiting |
| Works interactively, fails from a scheduled job | ✔ | ✔ | ✘ | different network path / credential context per entrypoint |
| `unavailable`, no data, no error | ✔ | ✔ | ✘ | upstream entitlement or plan, not connectivity |

**The A/B probe is the cheapest way to prove whether a setting is load-bearing.** Same URL, two openers
(one with the proxy/env, one without), report only the status codes. If direct succeeds, the runtime-layer
finding is cosmetic; if direct fails and proxied succeeds, the runtime finding is real and actionable.

```python
def ab(url, proxy):
    out = {}
    for label, use_proxy in (("direct", False), ("via_env", True)):
        handler = (urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                   if use_proxy else urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(
            handler, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        try:
            with opener.open(urllib.request.Request(url, headers=UA), timeout=20) as r:
                out[label] = f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            out[label] = f"HTTP {e.code}"
        except Exception as e:
            out[label] = f"ERR {type(e).__name__}"
    return out
```

### Runtime staleness mechanics

Many harnesses filter the child environment through an allow-list and then merge the server's declared
`env:` block on top. That merge is usually unconditional, **so the config block does work** — the trap is
that the edit lands after the process started. Before blaming the merge logic, check whether the process is
simply older than the config change. Two remedies, in order:

1. A programmatic reload of the MCP/dependency bridge (prefer an HTTP endpoint over an interactive command —
   it is scriptable and idempotent).
2. Reap the instances that still lack the env, so each client reconnects and gets a fresh one.

Expect this to **recur** while any client older than the config change is still running. Report it as a
recurring maintenance item, not as a one-shot fix.

## 2. Silent-failure catalogue

These all produce a *successful-looking* result. They are more dangerous than loud failures because no
gate, watchdog, or renderer will flag them.

### 2.1 Hardcoded request window

```python
# BROKEN: returns 2026-06-18 forever, no error, all fields present
client.get_aggs(ticker=t, multiplier=1, timespan="day",
                from_="2026-06-17", to="2026-06-18", limit=2)

# FIXED: rolling window resolved per call + freshness self-check in the payload
today = datetime.now(timezone.utc).date()
result = client.get_aggs(ticker=t, multiplier=1, timespan="day",
                         from_=(today - timedelta(days=WINDOW_DAYS)).isoformat(),
                         to=today.isoformat(), limit=10)
bar_date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
payload["as_of"] = bar_date.isoformat()
payload["stale_days"] = (today - bar_date).days
if payload["stale_days"] > MAX_AGE_DAYS:
    payload["_stale"] = True   # visible degradation, not silent staleness
```

Detection: for every outbound request, grep for date/numeric literals in the params. Any literal that looks
like a timestamp is a candidate. Then assert in a test that the resolved window tracks `today`.

### 2.2 Error truncation that removes the diagnosis

`str(exc)[:80]` on a provider JSON error cut a message at `…"error":"You a` — the words `not entitled` and
`upgrade your plan` were exactly what the operator needed, and they landed past the cut. Normalize first,
truncate second:

```python
except Exception as e:
    low = str(e).lower()
    if "not entitled" in low or "upgrade your plan" in low:
        return {"_error": "plan_not_entitled: <interface>需要付费套餐"}
    if "429" in low or "rate limit" in low:
        return {"_error": "quota_or_rate_limited"}
    return {"_error": str(e)[:200]}   # generous, only for genuinely unknown errors
```

### 2.3 Placeholder credentials used as live ones

A credential file shaped like this is **documentation, not a secret**:

```
# <Provider> API token
# Format: <32-hex-char-token>
# How to obtain: log in to …
PLACEHOLDER_REPLACE_WITH_REAL_TOKEN
```

Consumed raw, it is non-empty ⇒ truthy ⇒ sent as a bearer token ⇒ URL/header error ⇒ swallowed by a broad
`except` ⇒ reported as "provider unavailable". The operator then debugs the *provider* instead of noticing the
credential was never configured. Guard rules, in order of strength:

| Rule | Catches |
|---|---|
| No meaningful line after dropping comment/blank lines | comment-only file |
| First meaningful line matches `PLACEHOLDER\|TODO\|CHANGEME\|YOUR_\|<...>\|XXX` | explicit placeholder |
| A meaningful line has CJK and **no** ASCII run ≥8 chars | prose written where a token belongs |

Two mandatory counter-checks, because over-rejection silently breaks *working* sources:

1. **A comment header followed by a real value must stay usable.** Only apply the prose heuristic to the
   *meaningful* lines, never the whole file.
2. **Structured formats (`.json`) must be exempt** — they legitimately contain descriptive text.

Then lock it with a test that asserts every real credential in the tree is still readable, and that exactly
the placeholder file is rejected. Report `secret_status()`-style output that names the *marker type* only —
never echo the value, even for a rejected file.

### 2.4 Status tables without measurement dates

A docs page that said "provider X: 403 / expired key" was six weeks stale; on re-measurement X, Y and Z had
all recovered. A reader trusting that table skips three working sources. Every status table needs
`measured_at` plus the one-line command that regenerates it.

### 2.5 Inverted mislabeling — the mirror image (healthy data reported as degraded)

Everything in 2.1–2.4 is *failure disguised as success*. The inverse is just as costly and much less
suspected: **a source that is working correctly while the report says it is not.** Two real shapes:

**(a) Status derived from a field the payload doesn't use.**

A source-health contract resolves freshness by looking up a recognised timestamp key:

```python
TIMESTAMP_KEYS = ("updated_epoch", "updated_at", "timestamp", "ts", "time", "updated")
# contract: status in {live, cache} AND no resolvable timestamp  ->  downgrade to `unavailable`
```

A collector returned complete, real-time data but published its timestamp under the provider's own name
(`last_updated`), which is not in that tuple ⇒ `payload_timestamp()` returned `None` ⇒ the contract labelled a
perfectly healthy source `unavailable(missing_timestamp)`. It had been red in the cross-source verification
table for months while its data was actually being consumed.

```python
# FIX: carry the same instant under a key the contract recognises, keep the provider's own key too
return {..., "last_updated": raw["last_updated"], "updated_at": raw["last_updated"]}
```

**Checklist item when wiring any new collector into a status contract:** *is its timestamp key in the
contract's recognised set?* If not it will be permanently downgraded, and because the data itself looks fine
nobody investigates.

**Re-verification trap:** after fixing the payload, clear the disk cache for that key first. The cache still
holds the pre-fix shape, so you read the old payload back and conclude the fix did nothing.

```bash
# evict just the affected keys from the payload cache, then re-call
python -c "import json,pathlib; p=pathlib.Path('data/api_cache.json'); c=json.loads(p.read_text()); \
  [c.pop(k,None) for k in ('<key1>','<key2>')]; p.write_text(json.dumps(c))"
```

**(b) A by-design skip rendered with failure styling.**

Same family, at the presentation layer. A tiered pipeline deliberately does not run certain steps at low
tiers, and the renderer printed the *same* warning for "this tier skips it" and "the upstream actually
failed":

```
⚠️ fear/greed: no valid fields this round (source not routed or failed)   # ambiguous: skip or breakage?
```

Harm is identical to alert fatigue: readers learn to ignore the marker, so a *real* outage of that source
becomes invisible. **"Failures must be visible" does not mean "make normal degradation look like a failure"
— noise is itself a form of invisibility.** Fix by reusing the pipeline's existing deliberate-skip
convention and reserving the warning icon for genuine failures:

```
⏭️ fear/greed: skipped at this tier (requires the `macro` step)
⚠️ fear/greed: collection failed (status=unavailable) — investigate source
```

Audit action: for every "not collected / not_run / empty" line the renderer can print, ask **which condition
is this, by-design or broken?** — and if the answer differs, the line needs to split.

**(c) Why this class survives normal verification.** Both forms pass unit tests and connectivity scans: the
data is present and the endpoint answers. They only surface when you **run the real pipeline end-to-end and
read its output lines**. Treat "all tests green" as insufficient evidence for any change touching a data
plane (collector / contract wiring / renderer / status text) — the acceptance step is one actual run whose
output is read line by line.

## 3. Probe/output contract

Buckets that keep a report actionable (avoid a binary ok/broken that hides *why*):

| State | Meaning |
|---|---|
| `live` | answered with real data |
| `quota_or_limit` | 429 / quota exhausted |
| `plan_or_auth` | 401/402/403, or `200` + in-body `code=401` / "upgrade plan" |
| `unconfigured` | credential missing **or** present but placeholder-shaped |
| `unavailable` | DNS/TLS/network failure |

Rules: never print the secret; record the credential's *source* (`from_env` / `from_file`) not its value;
keep `unconfigured` distinct from `unavailable` (different operator action); persist the snapshot and diff it
against the previous run so regressions surface on their own.

## 4. Auditing the auditor — probe bug classes

| Probe bug | It reported | Truth |
|---|---|---|
| Wrong credential field name | credential absent | credential fine |
| Invented/guessed endpoint path | `404`, source dead | endpoint path was wrong; source fine |
| State classification via string prefix | error bucketed as `live` | body carried `code=401` |
| Over-broad heuristic (any CJK ⇒ placeholder) | valid `.json` credential unusable | file was fine |
| Timeout too short for a slow-but-working route | `network unavailable` | route worked with a longer timeout / other transport |

Discipline: for every risk the scanner raises, **verify through a second independent channel before putting
it in the report**, and state in the report itself which findings are probe-verified versus inferred. When the
probe was wrong, fix the probe and say so — do not quietly drop the finding.

## 5. Non-fabrication rule for referenced-but-missing artifacts

When a doc/skill references a file (script, template, reference) that was never written, do **not** author a
plausible substitute — that manufactures a false as-built record. Instead annotate the reference in place as
not-yet-implemented (and make the annotation idempotent), or repoint it at the real artifact if a rename
happened. Keep a scanner that buckets findings into *genuinely missing* / *already annotated* /
*doc-example placeholder* so the recurring signal isn't drowned by the acknowledged ones.
