# Equity Tracking Audit

## Problem

`data/equity_curve.json` may show a different balance than the actual Binance futures wallet.
The local snapshot is NOT auto-synced from the exchange; it relies on manual updates or trade-event
hooks that may be missing.

## Diagnosis

```python
# Step 1: Read local equity curve
import json
eq = json.load(open('data/equity_curve.json'))
print(f"Local: initial={eq.get('initial_balance')}, current={eq.get('current_balance')}, updated={eq.get('updated')}")

# Step 2: Read Binance wallet (via MCP)
# mcp_binance_get_account_summary() → futures_total_wallet

# Step 3: Compare
delta = float(futures_wallet) - float(eq.get('current_balance', 0))
```

## Interpretation

| Delta | Severity | Action |
|-------|----------|--------|
| 0–$5 | P2 | Minor tracking lag, sync on next trade |
| $5–$30 | P1 | Equity curve stale; investigate if trades happened off-track |
| >$30 | P1 | Significant gap — verify initial_balance matches actual deposit |

## Root Causes

1. **Equity not synced**: `equity_curve.json` was written once at init ($100) but never updated after trades.
2. **Initial balance mismatch**: The wallet may have started below the recorded `initial_balance` (e.g., partial deposit or earlier losses before tracking began).
3. **Trade events not hooked**: `行情守望.py` or the push pipeline writes trade events but doesn't update equity_curve.

## Fix

- After each trade close, update `equity_curve.json` with the actual Binance wallet balance.
- Run a sync check at system startup (or daily via cron) to detect drift.
- If `initial_balance` is wrong, correct it to match the actual first deposit.
