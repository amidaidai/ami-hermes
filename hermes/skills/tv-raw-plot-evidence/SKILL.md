---
name: tv-raw-plot-evidence
description: Use when TradingView packed values lose precision.
---

# Exact TradingView plot evidence

Verified implementation: `D:/Hermes agent/tools/tradingview-mcp/src/core/data.js::getStudyValues` and `scripts/tv_data_bridge.py`.

In one synchronous CDP evaluation read active chart `symbol()` and `resolution()`, its `_chartWidget.model().model().dataSources()`, and study `id()`. Confirm method shapes after TV updates. For each study, `metaInfo().plots` includes colorers; match Data Window item's `_id` to its plot index. Observed `s.data().last().value[0]` is source bar Unix seconds and `value[plotIndex+1]` the exact numeric plot. Return source bar time and same-call identity. Do not derive identity from requested symbol or a separate state call.

K/M/B/T formatted text loses low packed digits; never reconstruct flags from it. Null, NaN, Infinity or absent raw evidence stays absent. Still validate freshness, bar closure, source identity and selected direction downstream. Do not cache session-specific study IDs.

Generic alias parsing must skip `mcp_evidence_*`, `mcp_location_valid`, `mcp_trigger_confirmed`, `mcp_bar_closed`; only the validated main-SVP evidence decoder may produce these. Otherwise invalid/foreign fields bypass decoding. Reject duplicate main studies/titles, unsupported versions, bad integer flags, malformed timestamps and missing identity. Literal True only authorizes.

Tests: execute the actual JS evaluation body in a mocked page, cover exact integer, colorer indexing, null/NaN/Infinity, and same-call identity. Exercise Python actual transport-parser-resolver, not invented True flags. Verify actual CLI `node src/cli/index.js values` read-only. CLI reloads disk code; an already-running MCP server may retain old modules, so read its response before claiming it updated.

Cloud Pine compile is syntax acceptance, not deployed source identity, runtime request quota, bus wiring or profitability. A raw plot read of an old chart does not verify a new Pine build.
