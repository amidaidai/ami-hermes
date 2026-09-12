# Session Outputs and Fixes — 2026-09-12

## Key Code Fixes

### 1. `scripts/pipeline_router.py` — MODE_SPECS Configuration Isolation
- **Problem**: `analysis_mode_spec()` returned a shared reference to `MODE_SPECS` entries, so callers modifying the returned `required_output` list would pollute subsequent calls.
- **Fix**: Return `deepcopy(MODE_SPECS.get(key))` instead of the raw dict; changed `dict(MODE_SPECS["quick"])` to `deepcopy(MODE_SPECS["quick"])`.
- **Test**: `tests/test_router_spec_isolation.py` — 12 TDD tests verify read-only access and no cross-call pollution.

### 2. `scripts/tv_data_bridge.py` — Main/Sub Study Isolation
- **Problem**: `read_dmi_table()` and `read_indicators()` traversed all SVP-named studies, allowing sub-study rows/values to override main SVP conclusions.
- **Fix**: 
  - Added `_is_main_study(study)` guard: matches `name` starting with `SVP` (case-insensitive).
  - Added `read_dmi_table(symbol, study_role="main")` with `"main"`/`"sub"` roles to independently filter tables.
  - Added `risk_row_label(rows)` using `tv_indicator_contract.RISK_ROW_VARIANTS` for authoritative风控标签识别 (supports `风控`/`风控·观察`/`风控·未授权`/`禁做·不出价`).
  - Updated `_collect_and_cache_locked()` to use `risk_row_label()` instead of hardcoded `required_action_rows` check.
- **Test**: `tests/test_tv_collector_isolation.py` — 12 TDD tests verify main/study separation and contract label handling.

## Test Files Added

| File | Purpose | Tests |
|---|---|---|
| `tests/test_router_spec_isolation.py` | Verify `analysis_mode_spec()` returns deep copies; no cross-call pollution across all defined modes + invalid modes. | 12 passed |
| `tests/test_tv_collector_isolation.py` | Verify `_is_main_study()`, `read_dmi_table(study_role=...)`, and `risk_row_label()` work correctly under `HANGQING_NO_SEND=1`. | 12 passed |

## Output Artifacts

| Path | Description |
|---|---|
| `outputs/analysis-system-memory-review-20260912.md` | Memory convergence & user-preference consolidation report. |
| `outputs/tv-collector-validation-20260912.md` | TV data-collector drift fixes + live verification evidence. |
| `outputs/live-validation-20260912/btc-raw.json` | Full BTC/15m live capture: identity, tables, indicators, quotes, Binance cross-validation, OHLCV. |

## Important Patterns Identified

- **Never trust `success: true` from MCP without reading back `chart_get_state`** — identity can change mid-read.
- **Sub-study data must not silently overwrite main SVP conclusions** — always filter by study name prefix.
- **`required_action_rows` hard checks are brittle** — use contract-authoritative label matching (`risk_row_label`) instead.
- **`MODE_SPECS` shared dict must never be mutated by callers** — return deep copies; treat any nested list as immutable unless explicitly documented.
- **Cron `enabled`+`state` is the source of truth; `last_status` may be historical** — never rely on scheduler exit codes alone for "is alive" decisions.

## Anti-Patterns Avoided

- Do not merge main+sub study tables and treat as a single set — they serve different purposes (structure vs. order-flow confirmation).
- Do not use `dict(MODE_SPECS["quick"])` to create a "copy" — it's a shallow reference; use `deepcopy`.
- Do not rely on `last_status` from `hermes cron list` to detect active failures — read the scheduler config's `enabled`+`state` fields.
- Do not skip the `_is_main_study()` guard when traversing SVP studies — sub-study rows will corrupt main conclusions.

## References Within This Skill

- `references/current-audit-evidence-pattern.md` — detailed evidence-pattern template (unchanged).
- New: `references/collector-isolation-fixes-20260912.md` — this file.