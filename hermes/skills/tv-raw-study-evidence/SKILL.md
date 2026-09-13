---
name: tv-raw-study-evidence
description: Use when reading TradingView packed numeric evidence.
---

> **同族导航** — TV证据组 5 个技能各司其职，别加载错 （同族入口：`tradingview-consumer-evidence`）
> · **本技能 `tv-raw-study-evidence`** = 读原始 study 数值证据
> · 同族其余：`tradingview-consumer-evidence`（入口 · 消费 TV 证据的总口径（什么算已验证））、`tradingview-state-integrity`（共享图表状态一致性（身份/周期/指标/同轮一致））、`tv-raw-plot-evidence`（packed 值丢精度时读原始 plot）、`pine-indicator-audit`（Pine 源码审计（正确性/配额/面板/合同/消费方核验））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。

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
