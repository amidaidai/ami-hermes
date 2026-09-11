# Final System Audit Governance v10

## When to use
Use this reference when 棠溪 asks for a full audit of the trading analysis strategy, templates, monitoring system, Hermes setup, skills, memory, security, or self-improvement loop.

## Audit stance
- Be critical first. Do not praise before findings.
- Treat the system as a semi-automated trading decision system, not a prompt-only template.
- Grade each layer separately: strategy, template, monitoring, risk, review loop, Hermes infrastructure, security isolation, self-improvement governance.
- Distinguish what is working from what is safe enough for automation. The current target is assisted decision-making, not autonomous execution.

## Current baseline conclusions
- Overall maturity is high for analysis and monitoring, but not ready for auto-trading.
- Analysis template is strong: A/B/X status, five execution models, scoring, position sizing, risk checklist, price confidence, key-level confidence, Chinese card format.
- Monitoring is strong: 10s `行情守望.py`, 1m `信号巡检.py`, single-instance lock, heartbeat, strict push, cooldowns, hourly budget, noise history, structure refresh queue.
- Main weakness is not alerting; it is empirical validation. `trade_reviews.jsonl` must grow before strategy weights or smart evolution can be trusted.

## P0 audit findings to check every time
1. Real trade review loop
   - Compare counts of `trade_plans.jsonl`, `trade_events.jsonl`, `monitor_events.json`, and `trade_reviews.jsonl`.
   - If reviews are sparse, say the system can remind but cannot yet know which model makes money.
   - Do not let smart evolution change strategy weights without real review samples.

2. Account-linked risk
   - `risk_state.json` is only as accurate as recorded trades unless connected to real fills.
   - If real trades are not logged via `成交复盘.py` or exchange sync, treat risk gate as planned-risk, not true account-risk.
   - Recommend downgrading the next trade to B等待 when recent live trades are unreviewed.

3. Smart structure update governance
   - `智能更新结构.py` can replenish candidate key levels.
   - It must not independently change directional bias or promote A做多/A做空 without a full analysis card.
   - Smart update output should be candidate levels plus reasons, not final trade permission.

4. Security isolation
   - If Hermes profile has web/browser/terminal/file/memory/skills/cron/messaging plus financial MCPs, call it high-capability and high-permission.
   - Recommend a dedicated trading profile with least-privilege tools and MCPs.
   - Warn that prompt injection cannot be fully solved by model behavior; permissions and profile isolation are the mitigation.

5. Source snapshots
   - Latest `source_snapshot.json` is useful for realtime cards but insufficient for review.
   - Recommend append-only historical snapshots under `data/source_snapshots/YYYY-MM-DD/<symbol>-<time>.json` while keeping `source_snapshot.json` as latest cache.

## P1 improvements
- Add per-model statistics: sample size, win rate, average R, max losing streak, best session, top failure reasons, current status active/degraded/retired.
- Split event taxonomy: observe_event, setup_event, trade_event, risk_event, system_event.
- Add data anomaly fuse: stale quote timestamp, jump anomaly, repeated API failure, all-source outage, inconsistent source clock.
- Upgrade CVD from C级 kline approximation to finer aggTrade/WebSocket/order-flow source before using it as strong confirmation.
- For XAUUSD, add a separate macro layer: DXY, US10Y, US02Y, real-rate proxy, CME GC, Jin10 event calendar.

## User-specific standing decisions
- Active monitoring scope is only `BTCUSDT` and `XAUUSD` unless 棠溪 explicitly opens more symbols.
- ETH/SOL/BNB/USOIL/SPX can remain in templates but should not actively monitor by default.
- Different-market spread/point difference for non-crypto, especially XAU spot vs futures, is visible context only; do not use it as a push suppressor or fixed forbidden-trade reason.

## External standards to cite
- Hermes official docs for cron/memory/skills/security posture: https://hermes-agent.nousresearch.com/docs
- OWASP LLM Top 10 and Agentic AI threats for prompt injection, tool abuse, sensitive data and permission risks: https://owasp.org/www-project-top-10-for-large-language-model-applications/ and https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
- NIST Generative AI Risk Management for governance, auditability, change control, and evaluation: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- Binance official derivatives docs for OI, long/short, taker, funding, basis data semantics: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest
- Bookmap order-flow/CVD references for treating CVD as confirmation, not standalone signal.
- TradeZella/trading journal materials for review discipline, mistakes, and position sizing.

## Final judgement language
Use this concise conclusion when supported by the checks:

`系统已适合高质量交易辅助驾驶，但不适合自动驾驶。下一步不是继续堆功能，而是封版、复盘、统计、隔离、治理。`
