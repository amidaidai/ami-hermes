# Audit Execution + Pre/Post Comparison Pattern (2026-06-30 session)

**Trigger**: User says “执行”、“再跑一次...对比前后”、“按照建议来” after an audit report.

**Core sequence (real outputs only, no description substitute)**:
1. BEFORE capture (single terminal block):
   - `hermes doctor`
   - `hermes status --all`
   - `git status --short --branch`
   - `ls -lt data/source_snapshot*.json data/tv_live.json data/tv_dmi_cache.json data/*_heartbeat.json`
   - `cat` of heartbeats + tv_live/dmi samples

2. Refresh + fixes:
   - Collectors: `data_gatherer.py`, `multi_source_collector.py`, `dune_collector.py`, `deribit_options.py`, `黄金宏观.py`, `macro_poly_refresh.py`, `tv_data_bridge.py`, `x_sentiment_collector.py`, `cot_collector.py`
   - `hermes doctor --fix`
   - Daemon recovery (strict): `rm -f *.lock *.pid`; `terminal(background=true, command="python scripts/btc_daemon.py")`; same for 行情守望.py -s BTCUSDT XAUUSD
   - Poll: sleep + `cat` heartbeats (expect ts <5min, status=running)

3. Verification bundle (不可跳, use timeout 90+):
   - `python scripts/pine_static_scan.py svp_indicator.txt haldro_indicator.txt` (配额 14/12, 非重绘)
   - `python scripts/pipeline_router.py BTCUSDT XAUUSD` (confirm 10/8 steps, main TF)
   - `timeout 90 python scripts/auto_card.py BTCUSDT` (must see full 来源表 + 执行预案表 + 风控闸门表 + 总结; same for XAUUSD)
   - `hermes mcp test tradingview`
   - `python scripts/repo-maintenance/daily_system_audit.py`
   - Post: `ls -lt ...` + `cat` fresh heartbeats/tv_dmi + git status

4. Lock:
   - `git add -A scripts/ *.txt` (or specific dirty files)
   - `git commit -m "audit: ..."`
   - `git push origin main`
   - Confirm clean + pushed

5. Report ONLY deltas + evidence (timestamps, actual table excerpts from auto_card, collector outputs like Dune inflow/COT, tv_dmi refresh to 15:25+, heartbeats 15:26 running, git hash).

**Key enforcements observed**:
- terminal(background=true) mandatory for daemons — foreground & fails with explicit error.
- auto_card requires ≥90s timeout to reach GO/NO-GO gates and tables (60s gives partial).
- tv_dmi_cache + collectors + data_bridge must be run for freshness deltas.
- Git batch + push is part of closure (prevents "修改没生效").
- Daily system audit script run as part of verification.

**Example deltas from 2026-06-30**:
- tv_dmi_cache: 15:10 → 15:25 (POC/VAH/VAL)
- heartbeats: 15:15 → 15:26+ (BTC score 3, monitor running)
- Git: dirty → commit 179436f + push success
- auto_card: full tables with R:R 1:1.1, data A, protections through, real prices
- Config: v31 → v32 via doctor --fix

**Pitfall**: Do not claim "data refreshed" without ls -lt and cat of timestamps + actual collector output. Snapshots may lag even after collectors if full gather cycle not complete.

Update SKILL.md Audit Closure section when new commands or tool quirks appear.