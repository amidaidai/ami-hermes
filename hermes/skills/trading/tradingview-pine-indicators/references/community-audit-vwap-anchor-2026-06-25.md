# Multi-Community Audit: VWAP/SVP Anchor Consensus (2026-06-25)

## Sources Cross-Referenced

| Source | Platform | Key Finding |
|--------|----------|-------------|
| VWAP Institutional Pro (breakoutrhythmfx) | TradingView | Gold→1H/4H chart, Forex→15m/1H, Crypto→1H/4H (chart TF, not anchor) |
| TraderInsight | Web | Intraday→Session VWAP, Swing→Weekly/Monthly, Position→Quarterly |
| Reddit r/TradingView | Reddit | Anchored VWAP at volume-spike bars, daily VWAP as background direction |
| Reddit r/FuturesTrading | Reddit | 4-8 Anchored VWAPs from swing points, daily VWAP secondary |
| Reddit r/Forex (XAUUSD) | Reddit | Gold VWAP anchored at specific intraday times (11:14/12:22 UTC), not calendar periods |
| TradersPost (gold blog) | Blog | Session VWAP for mean reversion, Anchored VWAP for structure S/R |
| Betashorts multi-asset guide | Medium | Use syminfo.mintick + ATR normalization, avoid hardcoded values |
| NikaQuant Quantum Liquidity Map | TradingView | CVD divergence needs 3-condition gate: new extreme + CVD non-confirm + swing > 1.5×ATR |
| ICT Community | Reddit/Discord | KillZone windows differ by market: crypto 24/7, forex 5×24, metals overlap periods |

## VWAP Anchor: Community is Split

**Session派** (TraderInsight, VWAP Institutional Pro, TradersPost):
- Daily anchor = gold standard for intraday execution
- Weekly/Monthly = only for swing/position directional bias

**Swing锚定派** (Reddit r/FuturesTrading, r/Forex XAUUSD):
- Anchored VWAP from structure points > calendar-period anchors
- Gold traders anchor at specific UTC timestamps, not daily reset

**棠溪's position**: Uses calendar-period anchors (D/W/M) with SMART_HIDE_VWAP as a safety net. When weekly VWAP drifts after weekend gap → auto-hidden by ATR threshold → effectively falls back to daily. This is a **smarter implementation** than the simple "force daily" community advice because it preserves multi-TF context while filtering noise.

## Pitfall: Blindly Applying Community Advice

Community "best practices" (like "forex/metals must use daily VWAP") are often written for **simple single-anchor indicators** without:
- SMART_HIDE auto-filtering
- Manual anchor override
- Multi-TF weight/confidence systems

When these safeguards exist, the simple rule becomes **over-optimization**. The maturity of the indicator's guard rails should gate whether community simplifications apply.

## CVD: Asia Session Filtering — Community Consensus Confirmed

Multiple cross-platform sources agree:
- **Crypto**: 3-session CVD analysis is meaningful (24/7 market, Asia has volume)
- **Forex**: London + NY sessions dominate; Asia CVD is noise (only JPY crosses matter)
- **Metals (Gold)**: London/NY overlap is key; Asian session is consolidation zone
- **Stocks/Indices**: Only RTH (regular trading hours) CVD matters

This confirms the auto-disable of Asia CVD for non-crypto markets as a high-signal change.
