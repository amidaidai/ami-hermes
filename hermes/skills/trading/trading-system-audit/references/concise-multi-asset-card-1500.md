# Concise Multi-Asset Trading Cards (~1500 chars)

## Trigger

Use this reference when the user asks to compress, audit, or optimize trading analysis cards while keeping them actionable across crypto, gold/metals, forex, stocks, and options.

## Durable lesson

A concise card should not be a shortened report. It should be a compact execution plan:

1. Keep only executable fields: entry, trigger, confirmation, stop, take-profit, position size, invalidation, review cadence.
2. Preserve A/B plans and risk controls; compress environment, structure, and game sections.
3. Keep the card around 1300–1500 Chinese characters when possible.
4. Do not remove the operation section detail just to save length.
5. Use selective Markdown bold only for high-signal trading fields. Do not wrap whole cards or long narrative lines in `**`; Telegram becomes visually noisy and hard to scan.

## Community-aligned minimum fields

- TradingView-style alerts: exact price context, SL, TP, risk, invalidation, and trigger condition.
- Freqtrade-style risk controls: stoploss/ROI logic, position sizing, leverage awareness, and avoid heavy runtime calculations.
- Forex plans: entry, stop, target, risk-reward, position size, leverage/drawdown guard, major event window.
- Options plans: premium risk, Delta/Theta/Vega/IV context, max loss, no negative premium targets.

## Selective bolding rule

The preferred 1500-char card is not plain text and not fully bolded. Bold only the fields the user must act on:

- Header: current price, status, decision, position size/risk, invalidation.
- Operation plans: direction, entry, stop, take-profit, position size, risk, invalidation.
- Risk section: total risk and discipline line.
- Do not bold long environment, structure, or game narrative lines; they should stay readable context.
- Target density from the verified session: roughly 1300–1450 chars and about 48 `**` markers per card across crypto/gold/forex/stock/option mocks.

## Multi-asset field isolation

Never show crypto-only fields in non-crypto cards.

- Crypto: Funding, Taker, CVD, OI, spot-vs-perp split.
- Gold/metals: DXY, US10Y, London/NY kill zone, spot/futures basis, CVD only if real source exists.
- Forex: DXY/USD leg, rate differential, central-bank or CPI/FOMC window, spread/rollover.
- Stocks: index bias, sector bias, volume state, earnings/halts/pre/post-market risk.
- Options: Delta, Theta, Vega/Gamma if available, IV rank/event, liquidity/spread, premium max loss.

## Critical pitfalls

### Crypto field contamination

If stock/forex/option samples contain `Funding`, `Taker`, `CVD`, or `订单流`, flag as P1 unless there is a real data source for that asset. Replace with asset-specific labels such as `美元腿`, `板块量`, or `希腊值`.

### Negative option target

Options are premium instruments. Targets and stops must never render negative premium values. Use a premium-percentage stop distance (e.g. max(price * 0.18, 0.15)) and clamp targets to `>= 0.01`.

### Template drift after compression

Compression can make rendered cards diverge from `references/master-template-v68.md`. If the concise format is intended to be canonical, update the template version and wording rather than leaving a long-form template with a short-form renderer.

## Verification bundle

After changing concise card rendering:

```bash
python -m py_compile hermes/scripts/auto_card.py
python sandbox/send_multi_asset_mock_cards.py
python - <<'PY'
from pathlib import Path
import re
bad=[]
for p in sorted(Path('outputs/mock_cards').glob('*.md')):
    s=p.read_text(encoding='utf-8')
    print(p.name, len(s))
    if re.search(r'setup_id|model_id|entry_tag|exit_tag|critical|warning|info|\|', s):
        bad.append((p.name,'machine leak'))
    if p.name.startswith(('stock','option','forex')) and re.search(r'Funding|Taker|CVD|订单流', s):
        bad.append((p.name,'crypto field leak'))
    if p.name.startswith('option') and re.search(r'止盈[12]：`-', s):
        bad.append((p.name,'negative option target'))
print('BAD', bad)
PY
python -m pytest -q
```

Expected result: all five mock cards sent, lengths roughly 1300–1500 chars, `BAD []`, full pytest passing.

## Implementation pattern

- Add `_asset_data_line()`, `_asset_flow_line()`, `_asset_catalyst_line()` for section-specific asset text.
- Add `_asset_flow_label()`, `_asset_flow_bias()`, `_asset_confirm_brief()` to avoid generic `订单流` language outside crypto.
- Add `_fmt_asset_price()` and use it in stop/target helpers so forex/options keep decimals while crypto/gold remain compact.
- Keep helper defaults backward-compatible so older tests calling functions without `symbol` still work.
