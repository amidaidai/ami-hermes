# Multi-Asset Optimization Workflow + Data Bridge Extension (2026-06-21)

## "你的建议推送一次，优化一次" Execution Pattern
When user requests comprehensive multi-asset optimization with "按照你的建议来全方面的帮我优化，全部优化吧。你的建议推送一次，优化一次。":

1. Produce a clear prioritized list (high/mid) of suggestions based on gaps (data, scoring, session, SMT).
2. For **each** suggestion immediately:
   - Read relevant files (system_data_bridge.py, auto_card.py, master-template-v68.md, 行情守望.py).
   - Apply targeted patches.
   - Run verification (python -c for new functions, card regeneration, grep for leaks/old terms, asset_class tests).
   - git add + commit + push (棠溪 "锁定").
3. Summarize completed + remaining at end of batch.

This replaces step-by-step confirmation with full-batch + verification.

## Concrete Data Bridge Additions (system_data_bridge.py)
```python
def get_dxy() -> Optional[float]:
    # Yahoo DX-Y.NYB real-time for SMT on gold/forex
    ...

def get_basic_earnings_flag(symbol: str) -> str:
    # Stocks earnings window placeholder
    ...

def asset_macro_enrich(symbol: str) -> dict:
    ac = _get_asset_class_simple(symbol)
    # branches: dxy for gold/forex, event_flag for stock, macro_note
    ...

def _get_asset_class_simple(symbol: str) -> str:
    # returns crypto/gold/forex/stock/option/other
    ...
```

## Confluence Scoring Integration (hermes/scripts/auto_card.py)
In _compute_perfect_signals:
- Add asset-aware time boost.
- Try: import + call asset_macro_enrich(symbol).
- +1 for DXY present on XAU/forex (SMT).
- -1 for earnings flag on stocks.
- Path fix: sys.path insert to scripts/ for cross-dir import.

## Platform Naming Final Rule (reinforced this session)
- 品种行 = real broker/exchange name (OANDA for XAU after user "我经常使用oanda的" + "TradingView不是交易所，是交易所的名字" + screenshot).
- TradingView = charting source **only**, never as the platform value.
- Leverage line can stay broker-specific (OANDA 1000x).
- Batch update on any correction: display_symbol (行情守望), _display_symbol + _leverage_text (auto_card), master-template examples, multi_symbol_templates.
- Always run full verification bundle after naming changes.

## Verification Bundle (mandatory after each optimization round)
- read_file references/master-template-v68.md
- python scripts/auto_card.py XAUUSD && ... BTCUSDT
- python -c tests for asset_macro_enrich + _asset_class on 5 classes
- grep 0 leaks / 0 old broker names
- git status clean + commit + push

## Pitfalls Captured
- Do not treat TradingView as exchange name even if user says "tradingview的交易所" — clarify immediately.
- Stocks/options data remains weak — keep as template support until bridge matures.
- Always do "全部一起" batch for naming or asset-rule changes.

This file records the exact 2026-06-21 implementation pattern for future audits and extensions.
