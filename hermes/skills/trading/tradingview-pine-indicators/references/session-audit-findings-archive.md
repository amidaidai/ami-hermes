# Session Audit Findings Archive

## 2026-06-25: SVP+ICT+VWAP+EMA+CVD Audit

P0:
1. Session-end labels hidden by `barstate.islast` merge (fixed)
2. Instant sweep after session end (fixed with 3-bar protection)
3. `f_cutoff_ms` using `time` instead of `timenow` (fixed)

P1 Multi-Market:
1. 3-channel CVD running on forex/metals (Asia noise) → auto-disable
2. VWAP anchor not market-adaptive → forex/metals force daily anchor
3. VP bucket width auto-adjustment needed

## 2026-06-26: Action Panel Execution Gate

R:R must gate execution; targets direction-filtered; grade controls price specificity; HTF checklist side-specific.
Weekly liquidity pools on intraday: display distance 8ATR, line width 1, label size small, bg transp 80.
Draw from curWeekStartBar on `ta.change(time("W"))`, not from ATR-visibility-first bar. No dedupe against daily pools.

## 2026-06-27: 主/副指标联用审计

- 主指标（3134行）：无P0/P1。ADR正确(非重绘)、扫线拒绝确认已修、R:R到位、POC #0F0F0F白主题可见。
- 副指标（415行）：P2×3（shareTxtA死代码、OI聚合tooltip误导、PERP命名错位）。
- 关键发现：Pine request.security编译期静态计数 → 砍交易所到5家腾16配额 → 加4源OI聚合 → 27/40安全。
- 用户偏好：磁吸保持独立两行不合并、默认"标准"模式、副指标非加密自动门控。
- 两套CVD共存规则：背离以主指标真逐笔为准，副指标影线估算仅背景佐证。
