# no_agent TV Cache + Cron Recovery Pattern

Use this when a trading cron fails because an LLM/model provider is out of credits, or when TV cache freshness is the blocker.

## Pattern

1. Replace the LLM cron with a no_agent Python script when the task is deterministic data collection or file refresh.
   - Good candidates: BTC key-level sync, TV cache dump, Orion radar card rendering from cached JSON.
   - Bad candidates: tasks that truly require live reasoning or social/news synthesis.
2. The script should be silent on success and print a concise diagnostic only on failure.
3. For TradingView cache jobs, make the bridge write both canonical cache files:
   - `data/tv_dmi_cache.json` for the indicator bridge path.
   - `data/tv_live.json` for runtime/live-card consumers.
4. For TradingView CDP failures, first run a health check; if CDP is down, launch TV with CDP using `kill_existing=false`, then retry the no_agent cron.
5. Verify with the scheduler itself, not only a direct script run:
   - `cronjob(action="run", job_id="...")` must return `last_status=ok` / `execution_success=true`.
   - Then check refreshed data files for mtime, symbol, and key fields.

## BTC key-level sync fields

A robust BTC key-level sync script should refresh TV cache, then write `data/btc_ref_levels.json` with at least:

| Key | Source |
|---|---|
| `vwap` | TV `s_vwap` / `S VWAP` |
| `val` / `vah` / `poc` | TV `val_price` / `vah_price` / `poc_price` or top-level cache fields |
| `do` | TV `do_price` |
| `w_vwap` | TV `w_vwap_price` |
| `recent_high` / `recent_low` | Binance futures 15m klines, recent 100 bars |
| `updated_at` | Beijing-time ISO timestamp |
| `source` | script name |
| `tv_symbol` | must be `BINANCE:BTCUSDT.P` |

## XAU limitation handling

XAU is not a TV runtime failure when the production SVP indicator contains crypto-specific Funding/OI fields that do not apply to OANDA/XAUUSD. Mark it explicitly as a known degradation:

- Runtime status reason: `XAU使用gold-api+金十代理；TV SVP v10含加密Funding/OI字段，OANDA:XAUUSD程序化读数禁用`
- Card wording: `TV SVP v10 | XAU走gold-api+金十；TV SVP加密字段限制 | 观望 · 已知降级`
- Pipeline audit should show `⚠️` with this reason, not a vague “待刷新/故障”.

## Scheduler gotcha

After converting a job to `no_agent=true`, old `prompt_preview`, `model`, or provider fields may still appear in `cronjob(action="list")`. Do not conclude it is still using the model if `no_agent=true` and `script` is set. The decisive verification is a manual `cronjob(action="run")` returning ok without provider errors.
