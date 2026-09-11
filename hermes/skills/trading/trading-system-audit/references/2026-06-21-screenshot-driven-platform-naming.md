# Screenshot-Driven 品种平台命名铁律 (2026-06-21, final resolution)

## Core Rule (user-corrected)
When user says "品种已截图，你看到的" + explicit follow-up correction, the final stated name is authoritative for the {平台} token.

**Final locked convention after "TradingView不是交易所，是交易所的名字" correction**:
- **品种行平台标签** (display_symbol + _display_symbol in both 监控警报 and full cards): 
  - XAUUSD → `XAUUSD · OANDA` (actual broker/exchange name user frequently uses)
  - BTCUSDT → `BTCUSDT.P · BINANCE`
- **风控/杠杆文本** (_leverage_text + 操作段): 
  - XAU → `OANDA 1000x` (consistent with user "我经常使用oanda的")
  - BTC → `Binance 100x`

TradingView is **only** the charting platform / data view tool. It must **never** appear as the value for {平台} or "交易所". The platform value must always be the actual broker/exchange the user trades on (OANDA for gold in this case).

## Update Protocol (triggered by screenshot or name correction — treat as P0)
1. Immediately read_file references/master-template-v68.md to load current ①品种示例。
2. Batch-update **all** locations in one pass ("全部一起"):
   - scripts/行情守望.py:display_symbol() — monitoring alerts / Feishu
   - hermes/scripts/auto_card.py:_display_symbol() + _leverage_text()
   - references/master-template-v68.md (example line + 头部规则 + 资产专属规则)
   - scripts/multi_symbol_templates.py (exchange field)
3. Separate concerns:
   - 品种行 = actual exchange name from user's view (OANDA)
   - 风控杠杆 = broker leverage description (OANDA 1000x)
4. Run full verification bundle **before** claiming done:
   - python -c "from scripts.行情守望 import display_symbol; print(display_symbol('XAUUSD'))"
   - python scripts/auto_card.py XAUUSD && python scripts/auto_card.py BTCUSDT
   - grep '^① 品种' + grep '风控：' on the md files
   - grep -iE 'exness|交易所|TradingView.*品种|品种.*TradingView' (must be 0 for platform use)
5. git add -A && git commit -m "fix: 品种平台名..." && git push (棠溪 "锁定" 定义)

## Key Pitfalls (learned this session)
- Do not interpret "tradingview的交易所" literally as platform value "TradingView". Ask or default to user's stated frequent broker (OANDA).
- User corrections on naming are first-class signals — apply the **last explicit name** across renderers + template immediately.
- Dual-renderer drift (行情守望.py vs auto_card.py) is the #1 cause of inconsistent 品种行 after screenshot feedback.
- "全部一起" batch + single commit is the expected workflow when user says "其他的一起全部修复了" or provides naming correction.

## Verification Command Bundle (run after every naming change)
```bash
python -c "
from scripts.行情守望 import display_symbol
print('监控 XAU:', display_symbol('XAUUSD'))
"
python scripts/auto_card.py XAUUSD && python scripts/auto_card.py BTCUSDT
grep -E '^① 品种|^③ 风控' data/auto_card_XAUUSD.md
grep -iE 'exness|交易所|· TradingView' data/auto_card_*.md references/master-template-v68.md || echo '0 bad platform names OK'
```

This session resolved the swing: EXNESS → intermediate TradingView → final OANDA (per explicit correction).
