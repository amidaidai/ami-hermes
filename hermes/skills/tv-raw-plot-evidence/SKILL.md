---
name: tv-raw-plot-evidence
description: Use when TradingView packed values lose precision.
---

> **同族导航** — TV证据组 5 个技能各司其职，别加载错 （同族入口：`tradingview-consumer-evidence`）
> · **本技能 `tv-raw-plot-evidence`** = packed 值丢精度时读原始 plot
> · 同族其余：`tradingview-consumer-evidence`（入口 · 消费 TV 证据的总口径（什么算已验证））、`tradingview-state-integrity`（共享图表状态一致性（身份/周期/指标/同轮一致））、`tv-raw-study-evidence`（读原始 study 数值证据）、`pine-indicator-audit`（Pine 源码审计（正确性/配额/面板/合同/消费方核验））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# Exact TradingView plot evidence

Verified implementation: `D:/Hermes agent/tools/tradingview-mcp/src/core/data.js::getStudyValues` and `scripts/tv_data_bridge.py`.

In one synchronous CDP evaluation read active chart `symbol()` and `resolution()`, its `_chartWidget.model().model().dataSources()`, and study `id()`. Confirm method shapes after TV updates. For each study, `metaInfo().plots` includes colorers; match Data Window item's `_id` to its plot index. Observed `s.data().last().value[0]` is source bar Unix seconds and `value[plotIndex+1]` the exact numeric plot. Return source bar time and same-call identity. Do not derive identity from requested symbol or a separate state call.

K/M/B/T formatted text loses low packed digits; never reconstruct flags from it. Null, NaN, Infinity or absent raw evidence stays absent. Still validate freshness, bar closure, source identity and selected direction downstream. Do not cache session-specific study IDs.

Generic alias parsing must skip `mcp_evidence_*`, `mcp_location_valid`, `mcp_trigger_confirmed`, `mcp_bar_closed`; only the validated main-SVP evidence decoder may produce these. Otherwise invalid/foreign fields bypass decoding. Reject duplicate main studies/titles, unsupported versions, bad integer flags, malformed timestamps and missing identity. Literal True only authorizes.

Tests: execute the actual JS evaluation body in a mocked page, cover exact integer, colorer indexing, null/NaN/Infinity, and same-call identity. Exercise Python actual transport-parser-resolver, not invented True flags. Verify actual CLI `node src/cli/index.js values` read-only. CLI reloads disk code; an already-running MCP server may retain old modules, so read its response before claiming it updated.

Cloud Pine compile is syntax acceptance, not deployed source identity, runtime request quota, bus wiring or profitability. A raw plot read of an old chart does not verify a new Pine build.
