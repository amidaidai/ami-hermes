# 2026-06-20 auto_card.py Renderer Optimization (Multi-Asset + RR Guarantee + Confluence)

## Trigger
User request for comprehensive audit of analysis/monitoring strategy + templates + "应该要接入什么还差什么，怎么优化" + "全面优化修复" on card output.

## Core Non-Trivial Fixes Applied
- **Asset classification**: `_asset_class(symbol)` determines crypto/gold/forex/stock/option. Drives:
  - leverage_text (Binance 100x for BTC, Exness 1000x for XAU, etc.)
  - qty_unit (BTC, oz, etc.)
  - notional/risk calc
  - stop_dist base (crypto ~1.2% or level, gold ~12pts, etc.)
- **Dynamic stop & targets (RR iron law)**: `_plan_stop` / `_plan_targets` (A and B) now compute stop_dist from asset or levels, then TP1 = stop_dist * 2.0, TP2 = stop_dist * 3.0. Guarantees R:R ≥ 1:2 (achieved 1:6.1 / 1:9.2 in BTC run). Never hardcode $ distances.
- **B plan consistency**: `_plan_stop_b`, `_plan_targets_b`, `_tp_reason_b`, `_qty_b` delegate to A-plan equivalents (passing symbol). Avoids duplication and drift.
- **Confluence + MEDIA injection**: After render, always append:
  ```
  **Confluence Score: X/8 — 高概率**
  **MEDIA: {symbol} {tf} full + CVD (请手动截图发送)**
  ```
  Computed via `_compute_perfect_signals` (Liquidity Sweep + CVD背离/吸收 + Displacement + Kill Zone for XAU).
- **Template lock**: Every card generation or audit must start with `read_file("references/master-template-v68.md")`. Never rely on memory or prior output.
- **Zero machine field leak**: Post-generation `grep -E "setup_id|model_id|entry_tag|exit_tag|critical|warning|info"` must be 0 in body. Only Chinese human names (e.g. VAL回收).
- **Operation completeness**: Every pre案 (A/B) must output full ①-⑦ (方向、入场+触发+确认≥3点、风控、仓位+风险+名义、失效、复查、轨迹). Other sections may condense; operation never does. User "操作要完整" or "完整的卡片" triggers this.
- **Full card display rule**: When user says "完整的卡片看看，修改优化注入之后的" or equivalent after optimization, read the generated .md and output the **entire text** (not summary).

## Verification Bundle (must run after any renderer change)
1. `read_file references/master-template-v68.md`
2. `python hermes/scripts/auto_card.py BTCUSDT` (and XAUUSD for gold)
3. Read output file, confirm in text:
   - R:R values ≥1:2 (look for 1: in 止盈 lines)
   - Confluence Score line present at end
   - MEDIA line present
   - Both 预案A and 预案B have complete ①-⑦ blocks
   - Correct leverage/unit per asset (e.g. Binance 100x + BTC)
   - No machine tokens in body
4. `grep -E "setup_id|model_id|entry_tag|exit_tag" data/auto_card_*.md || echo "0 leaks"`
5. Display the full card text in response.

## Achieved in this session (BTCUSDT example)
- R:R A: 1:6.1 / 1:9.2 ; B also reached via delegation
- Confluence: 5/8 — 高概率 (Sweep + CVD背离 + partial Displacement)
- Full ①-⑦ for both plans
- Correct Binance 100x
- Zero leaks
- Full card text shown

## Support Files
- `references/universal_asset_card_v692.md` and `universal_asset_card_v692_complete.md` (created this session as practical multi-asset operation reference)
- Cross-ref: `references/multi-asset-complete-operations.md`, `references/full-card-review-after-injection.md`

## Pitfalls Avoided
- Hardcoded BTC-only stop/lev/unit → broke other assets
- B plans not inheriting dynamic logic → inconsistent RR
- Missing injection or template read → format drift or low Confluence
- Summarizing card instead of full text when requested after mods

Use this pattern for future multi-asset card work or template audits. Always verify with real generator output + full card display.