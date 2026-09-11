# 2026-06-19 Audit → Fix → Verify → Lock Bundle

This reference captures the concrete verification steps executed after price guard hardening and card compliance enforcement in the 2026-06-19 full system check + fix pass.

## Core Iron Laws Demonstrated
- XAUUSD / non-USDT symbols **must never** reach Binance ticker (returns 400).
- Analysis cards **must** be regenerated after any relevant change and scanned for machine-field leakage.
- "锁定" = git commit + push (not just local edit).
- Always start card work by reading the live `references/master-template-v68.md`.
- Fix-in-source ≠ fix-in-process: must clear pycache, restart via watchdog/taskkill, and re-verify with live execution.

## Mandatory Post-Fix Verification Bundle (copy-paste runnable)

```bash
# 1. Price guard validation (critical for XAU)
python -c "
from scripts.行情守望 import get_price
print('XAUUSD guard:', repr(get_price('XAUUSD')))
print('BTCUSDT sample:', get_price('BTCUSDT'))
"

# 2. Cache clear (Windows git-bash)
find . -type d -name __pycache__ -exec rm -rf {} +

# 3. Regenerate cards + leak scan
python scripts/auto_card.py BTCUSDT
python scripts/auto_card.py XAUUSD

# Check zero machine leaks + structure
grep -E "setup_id|model_id|entry_tag|exit_tag" data/auto_card_BTCUSDT.md data/auto_card_XAUUSD.md || echo "✅ 0 leaks"
# Also visually: head10 present, 5 full sections

# 4. Snapshot quality
python -c '
import json
for s in ["BTCUSDT", "XAUUSD"]:
    try:
        d = json.load(open(f"data/source_snapshot_{s}.json"))
        print(s, d.get("quality"), d.get("confidence_label"), "primary:", d.get("prices",{}).get("primary"))
    except Exception as e: print(s, e)
'

# 5. Heartbeat & process health
cat data/monitor_heartbeat.json
tasklist //FI "IMAGENAME eq python.exe" //V //FO CSV | findstr /I "python"

# 6. Git hygiene (required for "锁定")
git status --short
git add -A
git commit -m "fix: 硬化 XAUUSD 价格守卫 + 卡片合规验证 + 进程清理"
git push origin main
```

## Expected Outcomes (from the session)
- XAUUSD get_price → None (guard active, no 400 attempt)
- Cards: 0 machine fields, 10-head segments present, 5/5 body sections, match master-template-v68.md
- Snapshots: BTC "A", XAU "A-" (金十+gold-api present)
- New heartbeat PID after restart
- Remote has the commit
## Observed in "一起修复了" batch run (2026-06-20)

When user explicitly requests batch P0 fix ("一起修复了"):
- Execute all identified P0s + full hygiene + verification bundle in one continuous pass.
- Real outputs from this run:
  - XAU guard test: `XAU: None` (no Binance call)
  - BTC: normal price returned
  - prediction_log: reduced to 2 fresh lines after clear + stricter rules (0.5% move + low-conf exclude)
  - Cron: recreated with correct workdir; scripts copied to AppData; all 3 jobs active
  - pyclean + py_compile: passed
  - Cards: regenerated, `grep ...` returned 0 leaks
  - pytest: 98 passed
  - Git: 2 commits pushed, working tree clean
  - Process: stale monitor killed via `taskkill //F //PID <pid>` to force watchdog reload

Always report the concrete tool outputs in the closure. Do not claim fixed until bundle produces these results.

## Related
- trading-system-audit SKILL.md (XAU guard + template sections)
- tradingview-indicator-analysis (v6.9 card format iron laws)
- references/audit-pitfalls.md (process restart verification)
- references/master-template-v68.md (authoritative card bottom plate)
