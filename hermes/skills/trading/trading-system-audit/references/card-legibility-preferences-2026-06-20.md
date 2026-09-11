# Trading Card Legibility Preferences — 2026-06-20

## Trigger

Use this reference when editing 棠溪 trading analysis cards, especially after compressing or changing visual formatting.

## Durable lesson

The most legible default for 棠溪 is the concise ~1500-character execution card, not the ultra-compressed ~800-character variant.

- Prefer ~1300–1500 Chinese characters for analysis cards.
- Keep the operation section detailed: A/B plan, entry, trigger, confirmation, stop, TP1/TP2, size, invalidation, review cadence.
- Keep environment, structure, game, and risk concise but still understandable.
- Do not use Markdown bold markers (`**`) in Telegram-visible card text; they render as visual noise for this user.
- If restoring a previous layout, preserve later safety fixes: multi-asset field isolation and option premium target protection.

## Required checks after formatting changes

Run the normal card bundle and additionally verify:

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
    if '**' in s:
        bad.append((p.name,'bold marker leak'))
    if re.search(r'setup_id|model_id|entry_tag|exit_tag|critical|warning|info|\\|', s):
        bad.append((p.name,'machine leak'))
    if p.name.startswith(('stock','option','forex')) and re.search(r'Funding|Taker|CVD|订单流', s):
        bad.append((p.name,'crypto field leak'))
    if p.name.startswith('option') and re.search(r'止盈[12]：`-', s):
        bad.append((p.name,'negative option target'))
print('BAD', bad)
PY
python -m pytest -q
```

Expected result: five cards sent, approximate length 1300–1500 chars, no `**`, `BAD []`, full pytest passing.

## Pitfall

Restoring `render_card_locked()` from an older commit can reintroduce crypto-only wording into forex/stock/option cards. After any rollback, reconnect these helpers in the restored body:

- `_score13(..., symbol)`
- `_asset_data_line(...)`
- `_asset_flow_line(...)`
- `_asset_catalyst_line(...)`
- `_asset_flow_bias(...)`
- `_asset_flow_label(...)`
- `_asset_confirm_brief(...)`

Do not treat a successful syntax check as sufficient; sample all five asset classes.