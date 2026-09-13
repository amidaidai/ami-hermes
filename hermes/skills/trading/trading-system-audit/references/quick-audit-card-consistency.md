# Quick audit: actual-card consistency

## Proven inspection pattern

1. Read current system overview and repository status; retrieve previous user decisions before suggesting restoration or additional account inputs.
2. Inspect checker entry points before execution. Prefer existing read-only functions such as `inspect_repository()` and `check()` over CLIs that overwrite reports. Run source/alignment guards and focused regressions with `HANGQING_NO_SEND=1`.
3. Read the latest compact card and full report. Treat them as observed output, not independent verification of live sources. If producers are active, ensure cross-section comparisons concern the same generation.
4. Compare source matrix versus completion audit, gate colors versus reason text, and recommendation wording versus FinalVerdict. Trace contradictions to the relevant function.
5. Reproduce suspicious branches using explicit synthetic test inputs in an isolated no-send process. Label these as test fixtures, never market evidence. Inspect both diagnostic gates and execution authorization: misleading diagnostics can coexist with correct fail-closed execution.
6. Re-evaluate artifact health at audit time. Retain evaluation timestamp and source age; distinguish market closure from collection failure. Saved healthy status is not proof of current health.

## Useful regression targets

- `usable=True` with direction text “副指标不足” reveals availability-versus-confirmation conflation if displayed as confirmed resonance. Define what the green light means.
- Omitted portfolio data must not masquerade as verified zero exposure or verified low correlation. Show unknown/not evaluated without forcing account integration.
- `live` in the source matrix versus “no effective fields” in completion audit, or `cache` versus `unavailable`, requires provenance reconciliation. If these represent different subsources, name them separately.
- NO-GO must not produce “只执行禁做”. Observation conditions should name the structure without inventing executable prices.
- WFO count zero at one consumer does not establish that the upstream shadow-evaluation store is empty; trace wiring and eligibility before diagnosing absence.

## Reporting and later repair acceptance

Lead with verified base checks, prioritized defects, then enhancement order. Separate execution vulnerabilities from misleading display, and verified defects from proposals. State absent full-regression/TV/API verification. Pure system audits need not switch charts or generate market-update screenshots.

For repairs, source matrix, completion audit and gate explanation should consume one evidence object. Add actual rendered-output consistency tests alongside verdict tests. Preserve FinalVerdict as sole authority and test NO-GO remains non-executable. Respect manual-only trading and intentionally retired features. Do not ask again for account reconciliation/trade registration the user has declined.

This reference records inspection techniques and acceptance targets, not a claim that defects were repaired. Counts and health readings from a particular run are not durable facts.
