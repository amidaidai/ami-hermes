---
name: tv-raw-study-evidence
description: Use when reading TradingView packed numeric evidence.
---
# Exact TradingView study evidence

Data Window `_value` may round 100003 to `100 K`, 1099901 to `1.1 M`, and buses to trillions. Multiplying display text back cannot recover flag digits.

## Verified read path
Within ONE synchronous evaluation:
- `active = window.TradingViewApi._activeChartWidgetWV.value()`.
- Sources: `active._chartWidget.model().model().dataSources()`.
- Match Data Window item `_id` against `study.metaInfo().plots` array; include colorer slots.
- Raw number: `study.data().last().value[plotIndex + 1]`; element zero is source-bar UNIX time.
- Return `active.symbol()`, `active.resolution()`, `study.id()` and source-bar time alongside values. Never use requested identity or a separate state read.
- Accept finite raw numbers only. Missing raw execution evidence stays missing; no rounded-text fallback.

## Python boundary
Generic title aliases must not insert mcp_evidence_* or execution flags before the strict main-study decoder. Otherwise malformed or foreign evidence bypasses rejection. Validate unique main study, integer/version/digits, source times, identity and literal booleans. Explicit exchange/product requests must match exactly; explicit spot must not match perpetual.

## Verification
Use Node VM fixtures with fake page objects for same-evaluation identity, raw versus rounded values and null/NaN/infinity. Exercise CLI values read-only and inspect exact values. New CLI processes load disk changes; already-running MCP servers may require separately authorized restart. Cloud compile, active-chart deployment and real runtime acceptance are distinct. Do not save or replace user scripts without authorization.
