# P1 TV Cache and Push Protection Lessons

Session: 2026年7月1日 棠溪交易系统全方位审计与修复。

Reusable lessons for future full-stack trading-system audits:

- After fixing a stale TradingView cache, do not only check `mtime`. Verify the consumer path: `auto_card.py` must skip stale/wrong-symbol `tv_live.json` and continue to fresh `tv_dmi_cache.json`.
- `tv_data_bridge.py` may need to parse TradingView MCP CLI JSON (`values` with `poc_price/vah_price/val_price`) rather than legacy text output.
- `tv_live_dump.py` should be a wrapper around `tv_data_bridge.collect_and_cache()`; static hard-coded POC/VAH/VAL dumps can reintroduce cross-symbol contamination.
- XAU/BTC contamination regression: XAU must reject `BINANCE:BTCUSDT.P` caches and BTC must accept BTC caches.
- When archiving duplicate scripts, do not add untracked legacy files blindly. Run a secret scan first, especially for `reset_remote.py`, token helpers, or backup scripts.
- If GitHub Push Protection blocks an unpushed commit, do not bypass it. Soft-reset to the remote base, remove the sensitive file from the commit set/history, rebuild commits, and push again.
- Windows Python may reject GNU `strftime("%-m")`; use explicit f-string Chinese time formatting.
