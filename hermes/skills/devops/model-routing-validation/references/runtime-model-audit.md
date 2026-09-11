# Runtime model audit evidence template

Use this compact record after probing a Hermes profile. Never include API keys or tokens.

| Role | Provider/model | Configured | Credential listed | Text probe | Tool probe | Vision probe | Actual route | Decision |
|---|---|---:|---:|---|---|---|---|---|
| Primary | ... | yes/no | yes/no | pass/fail + error class | pass/fail/not tested | pass/fail/not tested | direct/MoA | use/hold |
| Fallback 1 | ... | yes/no | yes/no | pass/fail + error class | pass/fail/not tested | pass/fail/not tested | fallback | repair/hold |

## Error classes

Use `auth_401`, `auth_403`, `timeout`, `protocol`, `model_not_found`, `tool_failure`, or `unknown`; do not report every failure as simply unavailable.

## Trading-specific anomaly checks

- BTC options MaxPain must be compared with the live BTC price and isolated if the order of magnitude is implausible.
- A single asset-class contract must drive crypto/metal branches across all modules.
- Cache freshness is recomputed from the timestamp at read time; producer flags such as `fresh: true` are advisory only.
- Quick analysis must expose actual TV period coverage such as `1/5`.
- Missing or contradictory evidence may safely yield WAIT; it must not be silently converted to neutral directional evidence.

## Session-derived evidence (2026-08-29)

The active profile showed `deepseek-v4-flash-vision-exp` as the direct primary. Its text probe and a real terminal tool probe passed. Configured `api.aijws.com/gpt-5.6-sol`, `ollama-cloud/deepseek-v4-flash:cloud`, `ollama-cloud/glm-5.2:cloud`, and `ollama-cloud/kimi-k2.6:cloud` returned authentication failures during independent probes; this is evidence to repair and re-probe, not a permanent claim that those providers are unusable.

A BTC quick card exited successfully with WAIT and a 2/3 pipeline completion indication, while TV coverage was 1/5. It also exposed two data-quality signals worth guarding: BTC was inconsistently labeled non-crypto in one branch, and options MaxPain was displayed as 2200 against a BTC price near 77869. These should be treated as validation findings, not trading signals.
