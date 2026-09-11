# Multi-Asset Strategy (Crypto / Gold / Forex / Stocks / Options) — 2026-06-21 Community Optimization

## Capability Assessment (from full audit + code review)
- **Renderer (auto_card.py + 行情守望.py display_symbol)**: Strong structural support via `_asset_class` + per-asset branches.
  - Display: BTCUSDT.P · BINANCE, XAUUSD · OANDA, EURUSD · OANDA, AAPL · NASDAQ, options · OPRA.
  - Data/flow/catalyst/confirm lines, leverage, qty, risk text, price formatting: all branched.
  - Kill Zone / session logic extended in this session to asset-aware (XAU priority London/NY, crypto 24/7 high-liquidity, forex/stock London+NY open priority).

- **Core Strategy (models, scoring_engine, data bridge, monitor)**: Currently strongest for crypto + gold.
  - Models (Liquidity Sweep soul + CVD背离 + Displacement + VAL回收 + VWAP反抽) volume/profile/orderflow heavy → excellent for high-liquidity assets.
  - Data: Binance futures (CVD/Taker/Funding/OI) + gold-api/jin10/DXY strong. Forex partial (DXY), stocks (financekit/earnings weak), options (almost none beyond placeholders).

## Identified Gaps (P1 level for full multi-asset)
1. Data pipeline imbalance (P0 for stocks/options).
2. Models & scoring not yet asset-weighted (no earnings for stocks, no Silver Bullet window scoring for forex).
3. Session/time gating incomplete outside XAU (community requires London/NY for forex/gold, US session for stocks).
4. SMT (Smart Money Tool / inter-asset divergence) only in renderer placeholders — engine not systematically pulling correlated assets.
5. Options policy: must be "trade underlying with full ICT, options only for defined-risk overlay".

## Community Consensus (web_search + x_search ICT/SMC 2026 sources)
Core universal: Liquidity Sweep (灵魂) → MSS/CHOCH → Order Block/FVG retest + Displacement.
Asset-specific adaptations (must be encoded):
- Crypto: Funding/OI extremes + spot vs perp CVD + 24/7 liquidity raids.
- Gold: London/NY Kill Zone + DXY/Real Yield + post-sweep Displacement (current system closest).
- Forex: Silver Bullet (NY 10-11am) + DXY leg SMT + central bank windows. Strong session gating.
- Stocks/Indices: Index SMT (ES vs NQ) priority; add earnings + sector + volume. Individual stocks news-heavy — prefer indices.
- Options: ICT only on underlying chart. Use options purely for risk (defined risk spreads, max loss control). Never run full structure models directly on option symbols.

Unified workflow recommended:
1. HTF bias (Daily/4H structure + major liquidity pools).
2. Asset-specific SMT confirmation.
3. Session filter first.
4. Core model + asset confirmation sub-rule.
5. Risk per asset leverage/event rules.

## Concrete Optimizations Performed This Session
- Patched `_compute_perfect_signals` / Kill Zone logic in auto_card.py for multi-asset session awareness.
- Updated master-template-v68.md asset专属操作规则 with community 2026 points (Silver Bullet, SMT, "options only for wind控分层", stocks prefer indices).
- Platform naming iron law reinforced: "品种" line = actual broker/exchange (OANDA for XAU after user "我经常使用oanda的" + "TradingView不是交易所，是交易所的名字"). TradingView = charting source only. Batch update all paths on correction + screenshot feedback. Leverage line may stay broker-specific (OANDA 1000x).
- "全部一起" batch + full verification bundle (read_template → regen → grep 0 leaks/old names → platform display test → git commit+push) now mandatory on multi-asset or naming changes.

## Recommended Next Steps for Skill Users
- When auditing "模板监控策略" or "多资产", always:
  1. read_file references/master-template-v68.md
  2. Test _asset_class + display_symbol + _leverage_text for all 5 classes.
  3. Run community search (x_search + web_search) for latest ICT/SMC asset adaptations.
  4. Verify session logic is asset-aware (not just XAU).
  5. Force "全部一起" batch on any platform name or asset rule change.
- Prioritize data bridge and scoring_engine extensions for forex/stock before enabling live monitoring on them.
- Keep options as template-only until Greeks/IV feeds are real.

## Verification Bundle Extension (multi-asset)
```bash
python -c "
from hermes.scripts.auto_card import _asset_class, _display_symbol, _leverage_text
for s in ['BTCUSDT','XAUUSD','EURUSD','AAPL','AAPL250117C']:
    print(s, _asset_class(s), _display_symbol(s), _leverage_text(s))
"
grep -E 'Silver Bullet|defined risk|底层做ICT|SMT' references/master-template-v68.md
# + full card regen + 0 leaks + platform name grep
```

This reference captures the 2026-06-21 extension of the trading-system-audit workflow for full multi-asset support.