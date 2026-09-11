# Template and Alert Audit Lessons — 2026-06-20

## Durable lessons

① Template length control
- Keep `references/master-template-v68.md` as the card output skeleton only.
- Move model definitions, scoring, data grading, community rationale, and monitoring rules into separate reference files.
- Target main template length: about 120–160 lines.
- Preserve the detailed operation section; compress environment, structure, game-theory/order-flow, and risk sections into dense short lines.

② Symbol and venue display
- Display symbols as separate fields, not TradingView prefix form.
- Correct display examples:
  - `品种：BTCUSDT.P · BINANCE`
  - `品种：XAUUSD · EXNESS`
  - `品种：EURUSD · EXNESS` (or OANDA)
  - `品种：AAPL · NASDAQ`
  - `品种：AAPL250117C · OPRA`
- Only crypto perpetual contracts use `.P`.
- Do not append `.P` to gold, forex, stocks, or options.
- 2026-06-21 更新：监控警报（行情守望短卡 + Feishu sidecar）及模板已统一移除“交易所”字样，改用干净平台名格式。详见 `references/2026-06-21-template-monitor-alert-format-audit.md`。

③ Alert and watchdog runtime audit
- When alert logs show stale behavior after code fixes, inspect live processes before assuming source code is still wrong.
- Duplicate watchdog/monitor instances can keep old code paths alive and produce stale errors.
- Guard long-running monitor processes with atomic single-instance lock files.
- `watchdog.lock` protects the watchdog; `monitor.lock` protects the market monitor.
- On Windows/git-bash, venv shims can show parent/child Python processes; trust the lock-holding PID for the actual main loop.

④ Verification bundle
- Regenerate BTC and XAU cards after template or symbol changes.
- Scan rendered cards for machine field leakage.
- Compile changed Python scripts with `py_compile`.
- Run the repository pytest suite.
- Check post-fix logs by timestamp, not old historical lines.
