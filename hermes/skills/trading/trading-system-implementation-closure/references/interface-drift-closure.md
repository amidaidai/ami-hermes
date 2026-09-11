# Interface-drift closure recipe

> 示例命令中的旧字段名仅用于检测漂移，不代表当前生产字段。

Companion to the `Interface-drift closure` section of SKILL.md. Reusable whenever a change
touches a producer/consumer contract: indicator source ↔ Python contract, schema ↔ consumers,
packed-code decoder ↔ encoder, renderer ↔ card schema.

## 1. Hunt the duplicate definition sites

```bash
grep -rn "MCP \|OI Total\|HALDRO " --include="*.py" scripts/ | grep -v <contract_module>  # 示意名/检测用
grep -rln "<field-name>" --include="*.md" .        # skill/reference docs count as sites too
```

Anything that appears in two or more places is a drift source. The failure mode is *silent*:
no exception, no warning — the consumer just stores an empty key forever. A field that is
"always empty" in the rendered artifact is the signature; search for its name and count the
definition sites before debugging anything else.

Record what each site was, then delete all but one. Report the count in the closure summary —
"removed N duplicate whitelists" is the evidence that the root cause is gone, not just the symptom.

## 2. Guard design: classify, don't enumerate

A guard that holds its own list of "which producer fields count" decays exactly like the
whitelists it is meant to police. Prefer reading the semantics out of the producer:

| Producer attribute | Category | Must be in the contract? |
|---|---|---|
| `display.data_window` | exported field | yes |
| `display.price_scale` | axis / structural line | yes |
| anything else (default display) | visual only | no — list it, don't fail |

Then check both directions: exported-but-missing (consumer silently loses data) **and**
contract-but-absent (dead field). Add the ordered-name case: compare the producer's emission
order against the contract's declared order.

Pin the guard with a regression test that imports the guard module and asserts zero gaps, so
the guard cannot itself rot unnoticed. Also include an "authorization literals exist in producer
source" check when semantics are driven by producer-side string literals — that is how a contract
that documented four labels when the producer emitted three got caught.

## 3. Legacy name handling

The authority owns one `LEGACY_*` map: `internal_key -> retired producer name`. Consumers read the
canonical map first and fall back to the legacy map (`dict.setdefault` so canonical wins).
Two rules learned the hard way:

- **Do not list a legacy name whose key already exists in the canonical map.** One key can map to
  only one producer name, so the duplicate entry can never be used — dead weight that misleads the
  next reader into thinking the old name is still supported.
- **Keep the mapping in the authority, not in each consumer.** The whole point is one site.

## 4. Real-data probe shape

Keep it as a runnable script beside the audit output (not an inline snippet), so the next session
can re-run it unchanged:

```
producer read (live source)
  -> parse into producer rows + exported fields
  -> build the internal payload
  -> print: which authorization label was seen, whether the export tuple was complete,
            which contract error was raised
  -> resolve the single verdict (print state / executable / blockers / gate statuses)
  -> render the artifact
  -> assert no unauthorized price token appears in the artifact text
```

Printing the intermediate facts (label seen, contract error, verdict blockers) is what makes the
probe diagnostic rather than just pass/fail. Assert on the rendered text for leak checks: an
unauthorized state must not contain any order-price token.

Do not switch the chart/symbol to "make" a probe work; a probe that mutates shared chart state
costs more than it proves. Prefer running on whatever symbol the chart is already on.

## 5. Closure-report line items for an interface change

- duplicate definition sites found / removed (with the count)
- guard command + exit status, and the field/row/order counts on both sides
- regression tests added (count + what they pin)
- live probe result: the observed label, the contract error path, the verdict, the leak check
- legacy map contents (what is still readable from old caches)
