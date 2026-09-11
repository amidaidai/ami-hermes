# Full Injected Perfect Card Review After Optimization (2026-06-20)

## Trigger
User says variations of:
- "完整的卡片看看，修改优化注入之后的"
- "OK，完整的卡片看看"
- After "完美的优化" or community fusion work

## Required Action
1. After any template patch + code injection (e.g. _compute_perfect_signals for liquidity_sweep, cvd_divergence, displacement, kill_zone, confluence).
2. Inject the perfect full content into main files if needed (cp PERFECT_*.md → auto_card_*.md).
3. **Must** use read_file on the full files (D:/Hermes agent/data/auto_card_BTCUSDT.md and XAUUSD.md or PERFECT versions).
4. Present the **complete full text** of both cards in the conversation response.
5. Do not send only summaries, Telegram links, or partial excerpts when user asks for "完整的".

## Why (from session)
User explicitly wanted to see the modified/optimized/injected versions in full after the batch community fusion (Liquidity Sweep is soul, CVD anchoring, Kill Zone, Displacement, Confluence 5/8 and 8/8, etc.).

Previous partial (first 50 lines) was insufficient; full ~100+ line cards were delivered via cat/read.

## Integration into Workflow
In tradingview-indicator-analysis and trading-system-audit:
- Community research → patch template to v6.9.2 → enhance renderer/engine → regen cards → inject to main → read_file full → display complete cards → 0-leak grep + pytest + git lock + push.
- "全部一起给我最完美的优化" = execute the entire chain in one pass, including the full card display step.

## Verification
- Cards contain the community soul text: "Liquidity Sweep 是灵魂，必须锚定关键位 + CVD背离/吸收 + Displacement 确认。"
- Zero machine fields.
- Confluence scores present.
- Full 10-head + 5-body structure per master-template-v68.md.

Update this file after every major fusion + injection session.

Cross-ref: master-template-v68.md (v6.9.2), trading-system-audit/references/v6.9.2-perfect-optimization-pattern.md
