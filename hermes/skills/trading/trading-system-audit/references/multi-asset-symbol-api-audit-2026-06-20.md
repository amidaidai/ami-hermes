# Multi-Asset Symbol + API Capability Audit — 2026-06-20

Use this when auditing 棠溪 trading templates, monitor cards, API capability, and multi-asset readiness.

## Durable Findings

### 1. Rendered symbol venue must match asset class

The authority is not the raw symbol alone; rendered cards must show `{SYMBOL}.P:{venue}`.

Expected mapping:
- Crypto: `BTCUSDT.P:BINANCE`, `ETHUSDT.P:BINANCE`, other USDT crypto → `BINANCE`
- Gold / precious metals: `XAUUSD.P:EXNESS`
- Forex: `EURUSD.P:OANDA`, etc.
- Stocks: `AAPL.P:NASDAQ` unless a more specific exchange is known
- Options: option symbol `.P:OPRA`

Audit check:
```bash
python scripts/auto_card.py BTCUSDT
python scripts/auto_card.py XAUUSD
python - <<'PY'
from pathlib import Path
for f in ['data/auto_card_BTCUSDT.md','data/auto_card_XAUUSD.md']:
    t = Path(f).read_text(encoding='utf-8')
    print(f, t.splitlines()[0], t.splitlines()[1])
PY
```

Pitfall: a card can be otherwise valid but still drift from the master template if the first two header lines are reversed or if XAU is rendered as `OANDA` instead of the user's execution broker `EXNESS`.

### 2. Header order is part of correctness

Current master template header order begins with:
1. `**◷ YYYY-MM-DD HH:MM CST**`
2. `**① 品种：...**`
3. `**② 周期：**`

Do not treat this as cosmetic. The user explicitly reviews the whole template and expects rendered cards to follow it.

### 3. API capability audit must distinguish template coverage from live readiness

Multi-asset templates may cover crypto, metals, forex, stocks, and options, but live readiness depends on data sources:
- Crypto: Binance MCP + futures derivatives + TradingView OK → live-ready if account timestamp checks pass.
- Gold: 金十 + gold-api + macro proxies OK → live-ready; ensure snapshots refresh frequently.
- Stocks: finance/financekit may return unavailable market overview/VIX → template-only until a stable quote/index data source is confirmed.
- Options: template must require Greeks/IV/expiry/max-loss, but live monitoring is template-only until an options chain/Greeks source is reliable.

### 4. Binance account health is not implied by prices

Price/position endpoints can work while account summary returns Binance `-1021 Timestamp ... outside recvWindow` on spot assets.
Flag as P1 if recurring because account/trading actions may intermittently fail. Recommended fix: Windows NTP/time sync plus MCP recvWindow/server-time offset handling.

### 5. Snapshot freshness matters separately from source availability

If live quote tools return fresh XAU but `data/source_snapshot_XAUUSD.json` is hours old, mark as P1 freshness drift: monitor may still read live quotes, but analysis cards can inherit stale context. Suggested fix: include XAU snapshot refresh in `持仓与信号` or `智能更新结构` path.

### 6. Discord residuals are not runtime failures, but are audit debt

If Hermes status says Discord is not configured and Telegram is the active route, old comments/scripts mentioning Telegram + Discord are P2/P1 cleanup depending on whether any live push path still attempts Discord. Do not call it P0 unless alerts are actually lost.

## Verification Bundle

After fixing symbol/header rendering:
```bash
python -m py_compile hermes/scripts/auto_card.py
python scripts/auto_card.py BTCUSDT
python scripts/auto_card.py XAUUSD
grep -RInE 'setup_id|model_id|entry_tag|exit_tag|critical|warning|info|\|' data/auto_card_BTCUSDT.md data/auto_card_XAUUSD.md || echo '0 leaks OK'
python -m pytest -q
git add hermes/scripts/auto_card.py && git commit -m "fix card symbol venue formatting" && git push origin main
```
