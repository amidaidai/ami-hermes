---
name: trading-system-audit
description: >
  Full-stack 棠溪 system audit with P0/P1/P2 findings on data, runtime, strategy, and delivery.
  Trigger on: "全面审计", "审计看看", "trading system health check".
triggers:
  - 全面审计
  - 全方位多维度检查
  - 全面检查我的能力
  - 全面多维度
  - 审计看看
  - trading system audit
  - system health check
  - trading health
  - 监控状态
  - 模板监控策略
  - 监控警报格式
tools_required:
  - terminal
  - read_file
  - search_files
  - mcp_binance
  - mcp_jin10
  - web_search
  - web_extract
  - x_search
---

## Quick system audits

For “快速过一下系统”, use a bounded read-only audit, not a full market refresh. Check actual cards as well as tests: available ≠ supportive, missing exposure ≠ zero, safe FinalVerdict ≠ accurate diagnostics. Re-evaluate saved health at audit time. Respect declined/retired features. Give concise Chinese conclusions, priorities and verification limits. See `references/quick-audit-card-consistency.md`.

## Capability Utilization Audit

> ⚠ 2026-09-11 校正（**已实测核实**）：本文件部分段落把下列脚本当现行工具，实际状态是——
> ① `btc_alert_watch_v3` / `btc_push_cron` / `btc_collector` / `btc_fast_daemon` **已移入**
>    `scripts/_archive/`（`scripts/` 根下已无此文件）；
> ② `btc_keylevel_ws_guard` / `btc_keylevel_sentinel` / `btc_keylevel_rest_guard` /
>    `btc_price_arrival_sentinel` **文件仍在 `scripts/`，但既不在 cron 也不在任何进程中运行**
>    —— 属历史代际，不要拿它们当现行链路。
> **现行监控链只有一条**：`keylevel_guard.py`（常驻·亚秒 REST·多品种多顶点·每位 30min 冷却）
> + `btc_keylevel_guard_watchdog.py`（cron `*/2` 拉起）+ `keylevel_read_trigger.py`（事件本地分析）
> + `btc_tv_refresh.py`（五周期快照续航）。对照表：
> `trading/realtime-trading-pipeline/references/dead-script-index.md`；
> 系统全貌：`D:/Hermes agent/docs/系统总览.md`；指标字段/行名：`D:/Hermes agent/docs/tv-indicator-field-map.md`。

Freshness, approval-boundary, and memory-provenance repair details: `references/20260902-runtime-memory-audit.md`.

Continuous runtime, evidence-truth, structural-expiry, and cProfile audit method: `references/continuous-runtime-evidence-and-performance.md`.

## TradingView evidence integrity and indicator participation

For every TV-backed audit or analysis-card refresh, treat a successful mutation response as only an intent acknowledgement. After symbol/timeframe changes, wait for the appropriate recalculation window, then read back `chart_get_state` and require exact symbol, exchange, and timeframe identity before reading tables, study values, labels, lines, or taking the final screenshot. If identity is stale or mismatched, fail closed: do not reuse the old chart, old screenshot, or old indicator values as current evidence; retry the transition or rebuild the CDP session.

The audit must trace indicator participation, not merely indicator presence. For the SVP primary indicator, follow ICT sweep/reclaim → structure/BOS/CHoCH/MSS gates → action path/invalidations → Python `FinalVerdict`; record whether each field is actually consumed by the action panel and decision layer. For crypto AggVol, trace CVD/volume/OI and LSR separately. LSR is a crowding-risk input only: document its source, freshness, availability, ratio thresholds, and missing-data semantics; it must not become a direction vote or independent execution authorization. A missing LSR is missing evidence, not neutral evidence.

The evidence package for a TV audit should include: final `chart_get_state` read-back, parsed action/Data Window output, source/freshness status, and a full screenshot captured only after identity verification. Verify the screenshot file exists and is copied to the renderable upload directory before citing it. See `references/tv-evidence-and-indicator-participation-2026-09.md` for the compact checklist and failure examples.

## Repair and production-readiness loop

When a full audit is followed by “修复”, continue from evidence rather than producing a second report. Establish a red-capable regression at each load-bearing seam before changing code, then repair one root cause at a time and re-run the focused test before broad verification. See `references/repair-and-verification-patterns-2026-09.md` for cache identity/content contracts, FinalVerdict closure, Windows loop witnesses, MCP pin alignment, and side-effect safety.

- Treat `FinalVerdict` as the only execution authority. Renderers, legacy GO/NO-GO summaries, advanced order-flow text, and model scores may explain or veto, but must not independently authorize an order.
- Make freshness, identity, completeness, and explicit validity part of the data contract. A parseable cache, a JSON `fresh` flag, or process heartbeat is not proof of live data; stale/mismatched/partial TV or nested source snapshots must fail closed to WAIT/NO-GO.
- Preserve directional observation separately from execution permission: B/C and C-reversal paths may retain `watch_side`/human candidates, but must clear executable entry/stop/target and never create automatic trade authority. Keep R:R and risk-constitution checks in the final verdict.
- When an archived module is still on the dependency graph, restore a small, testable compatibility boundary or read-only adapter. Do not revive retired daemons, automatic delivery, or legacy write behavior just to make imports pass; replace broad silent `except: pass` with an explicit degraded result where the missing capability affects a decision gate.
- Audit every external side effect separately: Binance write tools default read-only and require explicit per-call human authorization; automated Telegram delivery stays opt-in; pending delivery queues are never flushed during verification.
- For TradingView, distinguish editor/cloud compilation from “indicator attached to the live chart”. E2E tests can mutate the shared chart; after them, restore the production Pine study, wait for recomputation, then verify symbol, timeframe, action table, Data Window, CVD/AggVol pane, price axis, and a new screenshot. Never let a successful subprocess exit code replace content validation.
- On Windows, an asyncio UNIX-socket witness is not portable. Use a loopback-only TCP witness with a dynamic heartbeat port, and make the external probe consume that port; keep the witness local-only.

The compact repair checklist and regression fixtures are in `references/repair-and-runtime-guardrails.md`.

When user says "全方位优化" / "完美运用我的能力" / "全部修复", follow `references/capability-utilization-audit-checklist.md` — 11-item checklist covering: Pine indicator bridge health, triple confirm integration, CVD absorption/distribution, Polymarket/macro bridge, TV decision table direct read, MTF VWAP scoring, KillZone matching, jin10 calendar, cron health, A-grade push gating, and TV screenshot standards.

For **comprehensive multi-dimensional audit** (用户说"全方位多维度检查" / "全面检查我的能力" / "全面审计"), use `references/2026-06-30-comprehensive-audit-10-section-format.md` — 10-section report template covering: runtime health, data freshness, review closure, hidden engines, orphan scripts, auto_card architecture, multi-asset pipeline utilization, MCP utilization, community benchmarking, and overall capability utilization rate estimation with P0/P1/P2 priority output.

**DMI Engine Verification**: After any changes, run `references/dmi-engine-integration-verification.md` to validate the Pine→Python decision bridge, grade gating, and format compliance.

After DMI engine alignment, also reference `references/dmi-engine-integration-pattern.md` for the three-layer pattern: Python replicate Pine logic → TV decision table direct read → dynamic data bridge fallback.

## Community-Driven Strategic Audit (v2.2 · 2026-06-21)

When the user asks to "联网社区，多个社区，全面的看一遍，提取精华，审计我们的系统", follow the methodology in `references/community-strategic-audit-methodology.md`.

**Six mandatory community sources**:
1. Freqtrade/X — backtesting/WFO/protections/position sizing
2. NautilusTrader — architecture/risk/pre-trade validation
3. Bookmap — CVD/iceberg/absorption/stop-run detection
4. TradingView Pine v6 — new APIs (footprint, multi-TF)
5. Reddit r/algotrading — retail lessons/drawdown/sizing
6. X/Twitter ICT/SMC — strategy evolution/2026 consensus

**Output**: 20-30 item consensus checklist with 🟢已对齐/🟡差距/🔴缺失 markers → P1 strategic gaps → P2 enhancements → unique advantages.

**Latest v7.3 consensus**: `references/v7.3-community-audit-fixes-2026-06-21.md` — v7.2的20条共识中3项P1+2项P2已全量实施（00cc113）：止损升级→对手方流动性池后方、连亏自动缩仓、余额膨胀守卫、CVD冰山检测、多资产相关性检查。101/101测试通过。

- `references/fix-pattern-write-it-right-not-post-patch.md` — **P0 fix pattern**: when data must be persisted with correct values, modify the function signature to accept the value at write time, never patch the file after the fact. Race conditions + silent failures proven in prediction_log price=0 case (2026-06-21).

## Recent References

- `references/r2-self-heal-patterns-2026-06-30.md` — R2 自愈模式：行情守望重启·Deribit期权超时+缓存降级·Protections TypedDict len()错误·sentiment_search stub·R2桥接集成·Git锁定流程。对应 2026-06-30 审计修复5项P0/P1。
- `references/v7.5-system-evolution-2026-06-21.md` — **v7.5 全量系统进化**：全量中文化(zh_locale.py)·TV截图管线(tv_screenshot.py·加密15m主/黄金5m主)·话题路由(BTC→386/XAU→385/山寨→416)·每日学习引擎(daily_learn.py·10+社区·三维度轮换)·10+社区融合清单。2ad04be · 583行新增·101/101通过。
- `references/v7.3-community-audit-fixes-2026-06-21.md` — **v7.3 P1+P2全量修复记录**：五项改动（止损升级·连亏缩仓·余额守卫·CVD冰山·多资产相关）的完整代码、社区来源、验证结果。00cc113。
- `references/v7.2-community-audit-consensus-2026-06-21.md` — **v7.2 六大社区联网审计共识**：20条共识对照表（16已对齐·3差距·1缺失）、P1止损哲学/连亏缩仓/余额膨胀守卫、TV桥v7.2架构、棠溪6项独特优势。
- `references/v7.1-mobile-adaptation-2026-06-21.md` — **v7.1 手机格式适配**：Telegram手机38字符/行约束、完整卡25→20行、极简10→8行、警报8→6行、拆行规则、`_p()`反引号剥离。
- `references/tv-cron-noise-fix-2026-06-21.md` — **TV cron噪音修复**：旧cron实际agent模式→LLM诊断报告投递Telegram、重建显式--no-agent、wrapper v1.2完全静默（异常仅单行⚠）。v7.2已演进为TV CLI直连架构（见SKILL.md TV信号实时推送架构）。
- `references/tv-bridge-symbol-contamination-2026-06-22.md` — **TV桥品种污染审计模式**：BTC zero-token TV桥必须强制切到 `BINANCE:BTCUSDT.P` 并校验 active symbol；缓存新鲜+脚本exit 0不代表语义正确，必须查 symbol、价格尺度、必需指标字段。
- `references/v7.0-template-simplification-2026-06-21.md` — **v7.0 模板精简完整记录**：社区信号格式基准（Telegram 4-6行/X 6-8行/机构8-12行）、压缩比3.2x(80→25行)、代码变更(367删235增)、新铁律⑨⑩、删除vs保留对照。
- `references/watchdog-popen-poll-fix-2026-06-21.md` — **P0 Windows Popen.poll() AttributeError fix**: subprocess.Popen with CREATE_NO_WINDOW may return incomplete object; try/except AttributeError with pid_alive() fallback. Guard reset recipe post-storm.
- `references/vwap-ema-cvd-integration-2026-06-21.md` — **VWAP+EMA+CVD local engine (v1.0, 333 lines) + full pipeline**: auto_card(环境⑧⑨/结构VWAP带) + monitor alert injection + template v6.9.16(iron laws ⑬⑭). Community-confirmed 2026 gold standard.
- `references/2026-06-21-runtime-hard-gate-evolution.md` — **运行态硬闸进化教训**：CLI `-q` 参数污染 symbol、crypto B/75 一致快照误杀、monitor 非法 symbol 入口过滤、watchdog `blocked` 状态语义；附回归测试与验证 bundle。
- `references/2026-06-21-rigorous-community-audit-lessons.md` — **严苛多渠道社区审计新增教训**：文本风控不等于硬闸（R:R<1:2 仍输出A预案=P0）、源码直测与运行日志相反=P1运行态漂移、Binance价格链路正常不代表账户链路健康、watchdog冷却必须可见；附六源社区共识映射与报告写法。
- `references/2026-06-21-f-round-monitor-engine-closure.md` — **F轮监控+引擎闭环强化**：render_message 注入宏观 DXY/US10Y 到警报正文、run_all_models(symbol)+所有调用方接 asset_weight_adapter、session_filter has_min_liquidity 门槛 + process_block 集成。模拟警报验证 macro 显示、权重适配实测、0泄漏卡片+编译+功能测试全通过 + commit/push。
- `references/2026-06-21-e-round-data-flow-closure.md` — **E轮数据流闭环**：render入口强制enrich_engine_data、bridge结构化DXY/US10Y、资产行真实宏数据输出、_score13宏观加分、行情守望集成。连续“全部一起”轮次验证bundle + commit/push。含可复用代码模式和证据。
- `references/2026-06-21-d-round-multi-asset-batch-optimization.md` — **D轮“全部一起再来一轮”模式**：session_filter 全资产时段门控、行情守望集成 asset_macro_enrich + should_trade、multi_model_engine asset_weight_adapter、模板时段铁律。验证 bundle + commit/push 作为锁定。含完整可复用代码模式和 bundle 命令。
- `references/2026-06-21-screenshot-driven-platform-naming.md` — **final corrected** screenshot + name correction driven platform naming iron law: "TradingView不是交易所，是交易所的名字" → XAU 品种行必须用实际经纪商 OANDA（用户常使用）；TradingView 仅图表来源，绝不作为平台值；品种行与风控杠杆分离；"全部一起"批量 + 验证 bundle + git 锁定。
- `references/2026-06-21-platform-broker-naming-convention.md` — 平台/经纪商名显示铁律（已更新为 TradingView 品种行 + OANDA 杠杆分离）。
- `references/2026-06-21-template-monitor-alert-format-audit.md` — 模板监控策略专项审计：移除"交易所"（监控警报/Feishu侧统一"平台"）、短卡周期逐行+无**、XAU get_close守卫扩展、watchdog调优、批量"全部一起"验证bundle+git锁定。
- `references/2026-06-21-live-audit-evidence.md` — concrete live state from full 2026-06-21 audit run (template monitoring strategy check): exactly 3 no-agent crons confirmed healthy, watchdog rate-limit interpretation (blocking vs crash), XAU kline collector leakage despite get_price guards, card **bold** + cycle formatting drift (BTC vs XAU), 0 machine leaks + A/A- snapshots + git clean, executed verification bundle results.
- `references/multi-asset-symbol-api-audit-2026-06-20.md` — multi-asset rendered symbol mapping, header fidelity checks, API live-readiness distinctions, and verification bundle for 棠溪 trading cards.
- `references/template-slimming-v694-2026-06-20.md` — v6.9.4 template slimming rules: keep master template as 120–160 line output skeleton, move model/scoring/monitor/closure rules to dedicated references, preserve detailed operation section.
- `references/concise-multi-asset-card-1500.md` — 1500字左右多资产交易卡优化模式：只保留可执行字段，资产字段隔离，期权权利金目标不得为负；关键字段选择性加粗，禁止整卡满屏加粗，含验证 bundle。
- `references/concise-multi-asset-card-800.md` — 800字多资产执行卡压缩模式：保留①-⑩锚点和五段正文，非操作段极简，操作段保留A/B预案，含字段隔离与长度/泄漏验证 bundle。
- `references/card-legibility-preferences-2026-06-20.md` — 棠溪交易卡可读性偏好：1500字左右优先于800字过度压缩；Telegram正文禁用 Markdown `**` 加粗符号；回退排版时必须保留多资产字段隔离与期权权利金保护。
- `references/template-alert-audit-lessons-2026-06-20.md` — session lessons for template slimming, separate symbol/venue display, `.P` only for crypto perpetuals, and atomic watchdog/monitor locks for alert runtime audits.

## Multi-Asset Card Audit Addendum

- Always compare rendered card output against `references/master-template-v68.md`; a correct template file is not enough if `auto_card.py` drifts.
- Verify display symbols by asset class as separate fields: crypto perpetuals display `品种：BTCUSDT.P · BINANCE`; gold uses `品种：XAUUSD · OANDA` (final after user correction "TradingView不是交易所，是交易所的名字" + "我经常使用oanda的"; TradingView is charting tool only and must never be used as the platform value); forex `品种：EURUSD · OANDA`, stocks `品种：AAPL · NASDAQ`, options `品种：AAPL250117C · OPRA`. When user provides "品种已截图，你看到的" or explicit name correction, the last stated broker name is authoritative for 品种行. Leverage line may retain broker-specific text (OANDA 1000x). Screenshot + correction always overrides.

## 2026-06-21 Multi-Asset Strategy Extension (Community Optimization)

**Renderer vs Core Strategy Gap** (critical finding this session):
- Renderer (auto_card + display_symbol): Already excellent for all 5 classes (crypto/gold/forex/stock/option) with branched data, flow, catalyst, leverage, session, and risk text.
- Core analysis (models, scoring, data bridge, monitor): Strongest for crypto + gold. Liquidity Sweep + CVD + Displacement core is universal, but data (CVD/Taker for crypto, DXY for gold) and session (Kill Zone) are incomplete for forex (needs Silver Bullet + strong London/NY gating), stocks (earnings + sector SMT), and options (Greeks/IV almost absent).

**Community Consensus** (x_search + web_search ICT/SMC 2026):
- Universal core: Liquidity Sweep (灵魂) → MSS/CHOCH → OB/FVG retest + Displacement.
- Asset adaptations required:
  - Crypto: Funding/OI + spot/perp CVD.
  - Gold: London/NY Kill Zone + DXY + post-sweep Displacement (current strength).
  - Forex: Silver Bullet (NY 10-11am) + DXY SMT + central bank windows.
  - Stocks: Index SMT priority (ES/NQ) + earnings + volume; individuals news-heavy.
  - Options: Full ICT only on underlying; options = defined-risk overlay only.

**User Workflow Signals Embedded**:
- "全部一起" batch on any multi-asset or platform-naming change (including screenshot feedback).
- Platform naming iron law: 品种行 = real broker/exchange (OANDA for XAU); TradingView = chart source only.
- When user says "加密，贵金属，外汇，股票，期权都需要的" + "前往社区来进行全面的进行优化一下": immediately run web/x_search for latest ICT/SMC asset adaptations, assess renderer vs engine gaps, patch asset-aware logic (e.g. Kill Zone), update master-template, then full bundle + commit.

**Actionable Additions**:
- Always test `_asset_class`, `_display_symbol`, `_leverage_text` for all 5 classes in multi-asset audits.
- Extend session logic and scoring weights per asset (see new reference).
- Keep stocks/options as "template support + manual review" until data bridge matures.
- See `references/multi-asset-strategy-community-optimization-2026.md` and the new `references/multi-asset-optimization-workflow-2026-06-21.md` for full details, code evidence (asset_macro_enrich, confluence integration), "建议推送一次，优化一次" pattern, verification bundle extension, and platform naming iron law.

## D轮 “全部一起再来一轮” 多资产批量优化模式（2026-06-21 本轮新增）

**触发信号**：用户输入 “D” 或 “全部一起再来一轮” 或明确要求“按照你的建议来全方面的帮我优化，全部优化吧。你的建议推送一次，优化一次。”

**核心工作流铁律**（必须嵌入）：
- 列出剩余建议后，**立即全量批量执行**，不分步等待确认。
- 每轮改动：read_file → targeted patch → 实测（python -c + card regen + grep） → 验证 bundle。
- 批次结束必须 git commit + push 作为“锁定”。
- 同时覆盖 renderer (auto_card / 行情守望 display) + data bridge + session_filter + engine + template。

**本轮落地内容**（可复用）：
1. `scripts/session_filter.py` 成为多资产单一真理源：
   - `get_asset_class(symbol)` 返回 gold/forex/crypto/stock/option
   - `get_active_sessions` / `should_trade` 按资产完整分支（crypto 24/7、gold Kill Zone + weekend closed、forex Silver Bullet/London-NY、stock US hours、option 跟随底层）
   - 强化周末/低流动性闭市守卫，crypto 显式豁免
2. `scripts/行情守望.py` 集成：
   - 移除硬编码 XAU if
   - 统一 `if not should_trade(symbol): return`
   - 调用 `asset_macro_enrich` 写入 `raw["_macro"]`（DXY + earnings flag）
3. `hermes/scripts/multi_model_engine.py`：
   - 新增 `asset_weight_adapter(symbol, base_conf, model_name)` 实现资产特定信心乘数（gold 1.25、forex 1.15、crypto 1.1、stock 0.85）
4. `references/master-template-v68.md`：
   - 标题更新为社区2026全面多资产优化版
   - 新增“时段门控”铁律段落（引用统一 session_filter）

**验证 bundle（铁律，不可跳过）**：
- py_compile 所有修改文件
- python -c 测试 5 类资产 should_trade + get_asset_class
- asset_macro_enrich 实测（XAU/EUR/AAPL）
- 再生 BTC + XAU 卡 + 0 machine leaks grep
- git status clean 后 commit+push

**新增支持文件**：`references/2026-06-21-d-round-multi-asset-batch-optimization.md`（完整命令、patch 锚点、坑点、bundle）

此模式已证明适用于多资产扩展、平台命名修正、模板升级等“全部一起”场景。

## E轮 数据流闭环 + 连续批量执行模式（2026-06-21 本会话）

**触发信号**：用户说 “我继续全部一起批量执行 + 推送” 或 “继续” 紧接上一轮后。

**核心铁律**（D轮“全部一起”模式的延续）：
- 识别数据流缺口后，**立即全量批量 patch** 所有相关层（bridge + render入口 + 资产行函数 + scoring + monitor）。
- 每轮结束必须执行完整验证 bundle + git commit + push 作为锁定。
- 连续轮次（D→E）时，上一轮 commit 后本轮从干净 git 状态开始，不等用户新确认。

**本轮落地内容（数据流闭环）**：
1. `scripts/system_data_bridge.py`：
   - `get_us10y_proxy()`（Yahoo ^TNX 兜底）
   - `asset_macro_enrich` 返回结构化 dict（dxy + us10y + macro_note + event_flag + asset_class）
   - 新增 `enrich_engine_data(symbol, engine_data)` 合并器，把 macro 注入到 engine_data（含 _macro、直接 dxy/us10y 键）
2. `hermes/scripts/auto_card.py`：
   - `render_card_locked` 最顶层强制调用 `enrich_engine_data`（sys.path 兜底到 scripts/）
   - `_asset_data_line` / `_asset_flow_line` / `_asset_catalyst_line` 全面替换占位逻辑，真实输出：
     - gold/forex: `Spot/美元(DXY `100.85`)`、`DXY `100.85` US10Y `4.45``
   - `_score13` 增加宏观加分：gold/forex DXY 对齐 +1，股票财报窗口 -1
3. `scripts/行情守望.py`：
   - 快照循环中调用 enrich，写入 raw["_macro"]

**验证 bundle 扩展（本轮新增检查项）**：
- python -c "from scripts.system_data_bridge import asset_macro_enrich, enrich_engine_data; print(asset_macro_enrich('XAUUSD'))"
- python scripts/auto_card.py XAUUSD && BTCUSDT
- grep 卡片必须出现真实值：
  - "DXY `100.85`"
  - "US10Y `4.45`"
  - "Spot/美元(DXY"
  - 评分变化体现宏观贡献（如 6→7）
- 仅检查主卡片 `data/auto_card_*.md`（历史 _full.md 忽略）
- 0 machine leaks + git status clean → commit + push

**观察证据（本轮真实输出）**：
- XAU 卡片环境段：
  ⑩ 数据：B · Spot/美元(DXY `100.85`) · CVD C
  ② 资金：CVD ?C · DXY `100.85` US10Y `4.45`
- 评分 7/13（宏观 +1）
- BTC 卡片无 DXY（正常，crypto 不触发）
- 全程 0 机器字段泄漏

**可复用模式**：
render 层自动富集 macro 是数据桥落地的**关键闭环**。以后任何宏观/财报/外部数据源扩展，都先在 bridge 实现结构化 enrich，再在 render 入口强制调用，最后在资产函数里消费。

**连续轮次偏好**：用户“继续全部一起”时，直接进入下一轮，不重新列建议。上一轮已提交的变更视为基线。

**新增支持文件**：`references/2026-06-21-e-round-data-flow-closure.md`（完整代码模式、验证命令、坑点、证据截取）

此轮完成了“数据桥 → 渲染自动注入 → 真实卡片宏观字段 + 加分”的全链路闭环。

## F轮 监控+引擎闭环强化（2026-06-21 本轮新增）

**触发信号**：用户说 "F" 或 "继续" 紧接 E 轮后，要求"全部一起批量执行 + 推送"。

新增参考：`references/2026-07-01-monitor-contamination-pipeline-lessons.md` — 监控污染清理·btc_signal price_consensus API·X情绪桥接·深度采集·孤儿信号展示

**核心铁律**（D/E 模式的延续）：
- 识别监控警报 + 引擎 + filter 缺口后，**立即全量批量 patch** 所有相关层（render_message、process_block、run_all_models 及其所有调用方、session_filter）。
- 每轮结束必须执行完整验证 bundle + git commit + push 作为锁定。
- 连续轮次从干净 git 状态开始，不等用户新确认。

**本轮落地内容（可复用）**：
1. `scripts/行情守望.py`：
   - render_message 增加 `macro_text` 参数，在 extras 区输出 “⑤ 宏观：DXY `xx` · US10Y `xx`”
   - process_block 实时构造 macro_text 并传所有 render 调用（expired/invalidated/breach/near）
   - 集成 `has_min_liquidity` 门槛
2. `hermes/scripts/multi_model_engine.py`：
   - run_all_models(data, symbol=...) 内部调用 asset_weight_adapter
3. 所有调用方同步更新传 symbol（auto_card.py、system_data_bridge.py、main 入口）
4. `scripts/session_filter.py` 新增 `has_min_liquidity(symbol, snapshot=None)`（gold 用 Kill Zone、crypto 用 snapshot quality、其他 True）

**验证 bundle（铁律，不可跳过）**：
- py_compile 所有修改文件（5 个）
- python -c 测试 asset_macro_enrich + has_min_liquidity + asset_weight_adapter（XAU/BTC/AAPL）
- 模拟 render_message 验证宏观行出现在警报正文
- python scripts/auto_card.py XAUUSD && BTCUSDT + grep 主卡片 0 machine leaks
- git status clean → commit (db3993c) + push

**新增支持文件**：`references/2026-06-21-f-round-monitor-engine-closure.md`（完整变更、验证命令、坑点、证据截取）

**可复用模式**：
- 监控闭环：render_message 支持额外 text 参数 + 主循环实时富集 + 全调用点传入
- 引擎自动适配：必须在核心 run_all_models 内部做 per-symbol 调整，并强制更新所有上游调用方
- 轻量门槛：session_filter 提供 has_min_liquidity，monitor 决策点立即调用
- “F”/“继续” = 直接进入下一轮批量，不重新列建议

此轮把宏观和权重从卡片/数据桥扩展到实时监控警报和模型执行层，完成更完整的 monitor+engine 闭环。





## Purpose
- Distinguish template support from live readiness: stocks/options can be represented in the template but should remain template-only until quote, index, options-chain, IV, and Greeks feeds are reliable.
- Audit Binance account endpoints separately from market-data endpoints; a `-1021` timestamp/recvWindow error can coexist with working prices and should be flagged as P1 if recurring.
- Check snapshot freshness separately from source availability, especially XAU: fresh 金十/gold-api quotes do not guarantee `source_snapshot_XAUUSD.json` is current.


## Purpose

Perform a comprehensive, critical audit of the 棠溪 trading infrastructure.
Output is a **structured P0/P1/P2 report** — no praise, only findings.

## Pipeline Step Tracking — engine_data 优先于卡文本匹配（2026-06-30 新增铁律）

当需要检测管线步骤是否已完成时，**必须使用 `engine_data` 键值判断**，而非在渲染后的卡片文本中搜索关键字。

**问题**：管线步骤的数据（CoinGecko Top10、X情绪查询、深度数据、相关性乘数）只在 BUILD LOG（stdout）中输出，不进入 `render_card_locked()` 渲染的卡片正文。用 `if \"CoinGecko\" in card` 检测会漏掉实际已执行完成的步骤，产生「假 ⚠️」。

**铁律**：
```python
# ❌ 错误：卡文本匹配（脆弱·漏检）
if \"CoinGecko\" in card: completed_steps.add(\"cg_pro\")

# ✅ 正确：engine_data 键值检测（可靠）
if engine_data.get(\"cg_top\") or \"CoinGecko\" in card: completed_steps.add(\"cg_pro\")
if engine_data.get(\"x_sentiment\"): completed_steps.add(\"x_sent\")
if engine_data.get(\"depth\"): completed_steps.add(\"depth\")
if engine_data.get(\"_advanced\",{}).get(\"orphan\",{}).get(\"corr_multiplier\") is not None: completed_steps.add(\"corr\")
```

**数据采集→engine_data 注入模式**（采集步骤必须写回 engine_data）：
```python
# 采集深度数据 → 写回 engine_data["depth"]
import urllib.request, json
_depth = json.loads(urllib.request.urlopen(f\"https://api.binance.com/api/v3/depth?symbol={sym}&limit=5\").read())
engine_data[\"depth\"] = {\"bid_price\": float(_depth[\"bids\"][0][0]), ...}
```

**适用场景**: 任何管线完成度审计、`render_card_locked` 调用后的步骤追踪。具体 4 个数据源的上游注入代码模式见 `references/auto-card-4-data-source-upstream-2026-06-30.md`。

## "先测试，不假设" 数据源可用性审计原则（2026-06-30 新增）

审计时若发现管线步骤标注 ⚠️（如 CoinGecko Pro、X情绪、深度、相关性），**不可假设它们是不可用的外部依赖**。必须逐个实测：

```bash
# 1. 检查数据缓存是否存在
cat data/x_sentiment_context.json | python -c "import sys,json; d=json.load(sys.stdin); print(list(d.keys())[:5])"
# 2. 直接调用 API
curl -s "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=5"
# 3. 运行独立脚本验证现货状态
python -c "from coingecko_collector import community_dashboard; print(community_dashboard()[:100])"
# 4. 读取孤儿模块输出（已落盘）
cat data/orphan_signals_BTCUSDT.json | python -c "import sys,json; d=json.load(sys.stdin); print('corr_multiplier:', d.get('corr_multiplier'))"
```

**常见数据源可用性对照表**（2026-06-30 实测）：
| 数据源 | 实际通道 | 管线注入方式 |
|--------|---------|-------------|
| CoinGecko | `coingecko_collector.community_dashboard()` / `multi_source_collector.cg_top_coins()` | 已在 Step 1 采集，`engine_data["cg_top"]` |
| X情绪 | `data/x_sentiment_context.json`（cron `x_sentiment_context.py` 每 N 分钟更新） | 新增步骤读缓存文件 |
| 深度 | `curl https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=5` | 新增步骤写 `engine_data["depth"]` |
| 相关性 | `data/orphan_signals_{symbol}.json`（orphan_integration.py 实时生成） | 通过 `_advanced_orderflow` 的 `out["orphan"]["corr_multiplier"]` 获取 |

验后若数据源确实不可用（非管线未读），再标为外部依赖问题。

## Output Format Rules (铁律)

- Pure vertical layout, no tables, no emoji, no `|`
- Prices in backticks
- Numbered critical list grouped by severity
- Chinese output for 棠溪
- **P0** = 立即修复 (system broken/invisible)
- **P1** = 核心功能缺陷 (feature non-functional)
- **P2** = 需要关注 (degraded but not blocking)
- Each finding: problem → evidence → impact
- End with prioritized fix checklist

### 审计报告推送到任务话题 846 时的精简格式

当审计结果需要推送到 Telegram 任务话题（846），用简化编号版，格式对齐分析卡头部风格：

```
◷ YYYY-MM-DD HH:MM CST

① 心跳：PID xxxx · 状态 · 时间 ✅/⚠
② 警报路由：BTC→386 / XAU→385 · 近N小时推X次
③ Cron：N个任务 · 逐条摘要 · last_run状态
④ 脚本清单：核心N个 · 按职能分组（监控/引擎/分析/维护）
⑤ 脚本路径：单路径/双路径 · 同步状态
⑥ 近期活动：警报次数 · 降噪拦截 · 异常事件
⑦ 数据流：端到端管线简述
⑧ 持仓状态：当前有无持仓 · 持仓监测状态
```

**铁律**：
- 编号按实际内容灵活增减，但最多 ⑧ 条
- 每条一行，圈号 + 冒号对齐，破折号解读
- 不逐条展开审计细节，只写核心结论
- 细节保留在会话内以备追问
- 禁止方括号/表格/emoji/｜分隔

### Analysis/Monitor Card Template Lock

When auditing or modifying 棠溪 trading cards, treat the card templates as part of system correctness:

- **出卡/审计卡合规前第一步**：必须 `read_file("references/master-template-v68.md")` 加载当前锁定底板。**绝不能依赖记忆、旧会话、或 SKILL.md 中的格式示例**。当前锁定版本为 **v7.1**（2026-06-21 手机适配版：完整卡≤20行·极简卡≤8行·警报≤6行·每行≤38字符）。旧 v6.9.x / v7.0 格式已废弃。
- **表格驱动偏好同步（2026-06-29）**：用户当前更偏好全表格驱动分析输出（多周期定位表 + 关键位矩阵 + 多源交叉验证表 + 执行预案表）。如果 `references/master-template-v68.md` 或渲染器仍写“禁止表格”/纯叙事风格，而当前用户偏好要求表格，判 P1 模板源头冲突，修复权威模板而不是临时改一条回复。细则见 `references/table-driven-analysis-template-sync-2026-06-29.md`。
- **Analysis card v7.1** = `references/master-template-v68.md` v7.1 手机适配版。核心铁律：每行≤38字符Telegram手机不折行、完整卡①②③④四段结构+预案AB+闸门、VWAP/EMA/CVD拆行、价格用`_p()`剥离反引号。
- **多资产操作完整性**（2026-06-20 新增）：操作段必须完整①-⑦（加密/贵金属/外汇/股票/期权）。环境/结构/博弈/风控允许精炼。详见 `tradingview-indicator-analysis/references/multi-asset-complete-operations.md` 和统一 asset_class 适配。
- Analysis card body must be human-readable only. **No machine fields or machine enum labels may appear anywhere in the rendered card body**, including: `setup_id`, `model_id`, `entry_tag`, `exit_tag`, `monitor_write`, `critical`, `warning`, `info`, and their concrete values.
- Human-readable strategy/model names such as `VWAP反抽` may appear, but never prefixed or described as `model_id`.
- Machine fields may still exist in local metadata/logs for monitoring and review; they must not leak into Telegram/card text.
- Monitor cards are shorter alerts. Tail action must be Chinese, not machine status.
- **v7.5 rendering standard**: display_name priority, no double-prefix, space-separated labels, N/A→Chinese, no hardcoded analysis, dual-compatible taker direction. See references/v7.5-card-rendering-standards.md
- **监控警报专属铁律（2026-06-21 最终版）**：监控短卡（行情守望.py 路径）品种行必须使用实际经纪商/交易所名称（禁止“交易所”字，也禁止把 TradingView 当成交易所名）。用户说“品种已截图，你看到的。需要需要。”、“EXNESS换成tradingview的交易所，我经常使用oanda的”或“TradingView不是交易所，是交易所的名字”时，**最后一次明确的名字为准**（XAU 用 OANDA）。必须同时全路径批量更新（"全部一起"）： scripts/行情守望.py display_symbol()、hermes/scripts/auto_card.py _display_symbol() + _leverage_text()、references/master-template-v68.md 示例、scripts/multi_symbol_templates.py。验证 bundle 必须包含平台名精确检查 + 0 残留。风控行可保留 OANDA 1000x。
- Always add or keep regression tests that render a sample card and assert machine-field tokens are absent before claiming the template is locked.

**v6.9.2 Perfect Community Fusion Optimization（2026-06-20）+ v7.0 精简（2026-06-21）**：
- v6.9.2: Liquidity Sweep灵魂 + CVD背离/吸收 + Displacement 确认 + Confluence打分 + XAU Kill Zone序列
- **v7.0**: 社区驱动精简——完整卡80行→25行（3.2x压缩）、五段删标题、预案B一行、风控闸门一行。详见 `references/v7.0-template-simplification-2026-06-21.md`。
**“全部一起”批量执行偏好（2026-06-21 强化）**：用户说“一起修复了”、“全部一起给我最完美的优化”、“其他的一起全部修复了”、提供平台名修正（“EXNESS换成...” 或 “TradingView不是交易所...”）或截图反馈时，立即识别所有受影响路径（模板 + 代码显示/渲染 + 杠杆文本 + metadata + 注释 + 推送描述）后**全量批量 patch**，不分步等待确认。执行后必须跑完整验证 bundle（read_template → regen cards → grep 0 leaks/目标字样/旧经纪商名 → 平台显示函数测试 → git status clean → commit + push）。本会话即按此执行了“交易所”移除 + EXNESS/OANDA/TradingView 命名澄清 + 渲染/杠杆/模板一致化。

**“你的建议推送一次，优化一次”工作流铁律（本会话新增）**：当用户要求“按照你的建议来全方面的帮我优化，全部优化吧。你的建议推送一次，优化一次。”时：
- 先列出清晰的高/中优先建议（数据桥扩展、时段资产化、confluence资产化打分、SMT模块等）。
- 对每条建议：**立即执行**（read_file → targeted patch → 实测验证如 python -c 调用新函数 + card regen + grep → git add/commit/push）。
- 每轮结束后总结已完成的 + 剩余建议。
- 当用户说“我继续全部一起批量执行 + 推送”或“继续”时，直接进入下一轮（D→E 连续），不重新列建议，上一轮提交视为基线。
- 特别适用于多资产策略扩展：必须同时覆盖 renderer (auto_card) + data bridge (system_data_bridge) + template (master-template-v68.md) + monitor display + multi_symbol_templates。
- 验证必须包含 asset_macro_enrich 实测 + 宏观注入到卡片环境/资金段 + 评分加分验证 + 5类资产测试。
- 批次结束时必须 git commit + push 作为“锁定”。

**多资产数据桥 + Confluence 扩展模式（2026-06-21 实战）**：
- 在 system_data_bridge.py 添加：
  - get_dxy()（Yahoo DX-Y.NYB 实时拉取，用于 gold/forex SMT）。
  - get_basic_earnings_flag(symbol)（股票财报窗口占位，后续接 calendar）。
  - asset_macro_enrich(symbol) → 返回 {"dxy": ..., "macro_note": ..., "event_flag": ...} 按 asset_class 分支。
  - _get_asset_class_simple（支持 crypto/gold/forex/stock/option）。
- 在 hermes/scripts/auto_card.py 的 _compute_perfect_signals 中集成：
  - 尝试 import asset_macro_enrich（带 sys.path 兜底到 scripts/）。
  - SMT 加分：if macro.get("dxy") and (is_xau or forex)：conf += 1。
  - 财报降分：if "财报" in event_flag：conf -= 1。
  - 时段 boost：主要交易时段对非BTC +1。
- 验证 bundle 必须包含：
  python -c "from system_data_bridge import asset_macro_enrich; print(asset_macro_enrich('XAUUSD'), asset_macro_enrich('AAPL'), asset_macro_enrich('EURUSD'))"
  + card regen + confluence 字段检查。
- 铁律：数据桥扩展必须同时服务 renderer 和未来 monitor 决策。stocks/options 仍以模板为主，直到 feeds 成熟。
- 模板 bump 到 v6.9.2，铁律更新：每次必须 read_file 确认；正文零机器；每张卡带 MEDIA 截图；真实成交走闭环。
- 验证证据（本会话）：_compute_perfect_signals 产出 BTC: 已扫 VAH... CVD卖背离... 5/8高概率；XAU: 已扫需求OB... Displacement强 + Kill Zone... 8/8高概率。auto_card 增强后 98 pytest pass，git clean push。
新增支持文件：`references/v6.9.2-perfect-optimization-pattern.md`（记录 helper 代码、patch 锚点、bundle 命令）。
- 博弈段③ 订单流锚定结构 拆为子项：流动性扫荡状态 + CVD背离判定（价格HH+CVD LH 等假突破预警） + 现货vs永续CVD分化（BTC专属）。
- 环境段新增⑪ 时段（XAU优先）：London/NY Kill Zone 内/外 + 优先级。
- 结构段④价值区增加 Naked POC 状态；⑤流动性增加扫荡 {已扫/待扫}。
- 5m触发新增④ 流动性扫荡确认 子项。
- 模型清单（扫流动性回收、突破接受等）明确要求 “+ 流动性扫荡确认” + “无背离”。
- 头部版本 bump 到 v6.9.1 并列 deltas。
验证铁律：`read_file` 后用 `python -c "with open('references/master-template-v68.md') as f: c=f.read(); print('流动性扫荡' in c and '现货vs永续' in c and '时段（XAU优先）' in c and 'Naked POC' in c and '扫荡确认' in c)"` 必须全 True。

- `references/v6.9.1-community-template-enhancements.md` (prior community template notes)
- Cross-reference: `tradingview-indicator-analysis/references/community-2026-ict-smc-cvd-fusion.md` for 2026 fusion (Liquidity Sweep soul, XAU Kill Zone sequences, CVD divergence + Displacement anchoring, real 50-65% backtest rates) derived via web-access + x_search in audit+optimization sessions.

## Audit Checklist (11 Domains)

### 0. 静态+动态双重验证（v7.5b 铁律 · 2026-06-22）
静态扫描可以发现代码规范问题，但**无法发现运行时错误**（函数不存在、变量未定义）。每次审计必须以实测跑管线收尾：
```bash
# Step 1: 静态扫描
python -c "compile(open('hermes/scripts/auto_card.py').read(),'a','exec')"
python -m pytest tests/ -q
# Step 2: 实测跑管线（不可跳过！）
python hermes/scripts/auto_card.py BTCUSDT
python hermes/scripts/auto_card.py XAUUSD
```
实案（2026-06-22）: 101/101测试+compile通过，但auto_card NameError崩溃→警报静默。静态审计完全漏检。

Execute these checks in order. Each produces findings or a pass.

### 1. 进程状态

⚠ **git-bash 探查铁律**：审计在 Windows git-bash 跑。`python -c` 含嵌套引号会被 bash 吞引号 → `SyntaxError`；`wmic` 在 Win11 返回空输出；`powershell` 遇 `D:\Hermes agent` 空格路径报 `CommandNotFoundException`。读 JSON 用 `read_file` + `json.loads`（去 `行号|` 前缀），查进程用 `tasklist //FI ... //V //FO CSV`。完整对照表 + 进程构成判读见 `references/audit-pitfalls.md`「git-bash 下进程/JSON 探查陷阱」。

⚠ **文件路径铁律**：核心脚本主要在 `scripts/` 目录（非 `hermes/scripts/`），但 `auto_card.py` 当前在 `hermes/scripts/auto_card.py`。`hermes/scripts/` 还包含 `multi_model_engine.py` 等引擎/卡片模块。
审计前先验证路径：`ls scripts/行情守望.py scripts/watchdog.py scripts/trading_system.py hermes/scripts/auto_card.py hermes/scripts/multi_model_engine.py`
如果 `scripts/auto_card.py` 被调用而不存在，标为 P1 路径漂移：建议创建薄 wrapper 或统一迁移路径。

```bash
# Check if 行情守望 is running
ps aux | grep -E "(行情守望|monitor)" | grep -v grep

# Check watchdog
ps aux | grep watchdog | grep -v grep

# Cross-reference heartbeat
cat data/monitor_heartbeat.json
```

- Compare PID in heartbeat vs process list
- Check heartbeat timestamp freshness (<120s = alive)
- Read `data/monitor_state.json` → last巡检提醒
- **Pitfall**: On Windows/MSYS, `ps aux` may not show all processes.
  Use `tasklist | grep python` as fallback.
- **重复进程陷阱**: count MCP server instances — `binance-mcp`/`finance-mcp`/`dashboard`/`monitor` should each be 1. Hermes restarts often leave orphaned MCP副本 (seen: 4×binance, 4×finance). Wastes memory, not功能-breaking. Detection + safe-cleanup procedure: `references/provider-proxy-and-process-hygiene.md`.
- **重复 monitor/watchdog 实例（P0 · TOCTOU 锁竞态）**: 若数出两个 `行情守望` 或两个 `watchdog`（启动时间戳相差几十毫秒），根因是 `acquire_lock()` 非原子的 check-then-write，不是偶发。逐个 taskkill 是打地鼠，杀完还会再生。必须改原子锁（`os.open(..., O_CREAT|O_EXCL)`）。检测命令、原子锁修法、重启程序铁律见 `references/duplicate-process-toctou-lock.md`。
- **cron 任务命名**: 棠溪 wants cron job names in Chinese. After creating jobs (which often default to English IDs like `gold_monitor`), rename via `cronjob(action='update', name='中文名')`.
- **Pitfall**: watchdog.log 反复出现"进程已死·重启"+"心跳停滞Ns·PID存活=True"
  = 行情守望主循环串行网络请求累积超时（非进程崩溃）。
  根因：`scripts/行情守望.py` L1032 `while True` 内多个 requests.get(timeout=10/15)
  + subprocess(timeout=15) 串行执行，单轮可能 >90s 心跳超时。
  诊断：看 watchdog.log 中"心跳停滞 Ns"的 N 值，若 90-200s 范围且"存活=True"
  → 串行阻塞；若 N>200 且"存活=False" → 进程崩溃。
  **串行阻塞来源排查**：除 requests.get 外还要查推送路径。若同时段 monitor.log 有次通道（Discord）timeout 抖动，怀疑 push subprocess 重试阻塞（`10s×3=30s`）拖死串行 push worker → 主循环心跳停滞。判读见 §5.3。

### 2. API 连通性

```python
# Binance account (spot + futures)
mcp_binance_get_account_summary()

# Check for timestamp errors (recvWindow)
mcp_binance_get_futures_positions()

# TradingView CDP
mcp_tradingview_tv_health_check()
```

- Binance recvWindow error = server clock drift → sync NTP
- **Pitfall**: simple price endpoints (`get_price`) may work even when account endpoints fail. Don't assume API is healthy just because price queries succeed.
- **主模型"时好时坏"陷阱**: if the main model (micu / any provider) flakes intermittently, suspect PROXY ROUTING, not a dead endpoint. 国内中转 API forced through clash → foreign exit node → intermittent timeout. Diagnose direct-vs-proxy and fix NO_PROXY. Full procedure: `references/provider-proxy-and-process-hygiene.md`.
- **Pitfall**: `w32tm /resync` must run from PowerShell or cmd, NOT git-bash (GBK encoding garbles output)
- Spot asset errors may be OK if only futures used
- TradingView `cdp_connected: false` = desktop not running

### 3. 数据质量

#### 3.0 硬编码静态价位检查（P0 · 2026-06-22 新增）

**症状**：多模型/评分引擎产生看似合理的置信度输出，但所有计算基于过时静态价格，与实际行情无关。

**检测**：
```bash
# 搜索所有引擎/模型脚本中的硬编码价位模式
grep -rn "vwap_s\s*=" --include="*.py" hermes/scripts/ scripts/
grep -rn "\(val\|vah\|poc\)\s*=" --include="*.py" hermes/scripts/ scripts/ | grep -v "\.get\|\["
# 检查 EMA 硬编码
grep -rn "ema[0-9]\+\s*=" --include="*.py" hermes/scripts/ scripts/ | grep -v "\.get\|\["
# 检查月VWAP/周VWAP硬编码
grep -rn "\(m_vwap\|w_vwap\|monthly_vwap\|weekly_vwap\)\s*=" --include="*.py" hermes/scripts/ scripts/ | grep -v "\.get\|\["
```

**判读**：如果任何 VWAP/VAH/VAL/POC/EMA 是 `= 12345.6`（数字字面量）而非从数据字典或 TV 桥读取的，标 P0。硬编码价位在行情移动后使整个引擎输出不可信。

**实案（2026-06-22）**：`multi_model_engine.py` 中 8 个关键位硬编码（vwap_s=66054, val=65601, poc=65847, vah=66692, ema9=65153等），与实际行情偏差 1,000–2,200 点。所有 8 个模型的置信度计算基于错误参考点。静态编译通过，但输出完全无用。

**修法**：从 TV 数据桥缓存（`btc_tv_data.json`）或 TV MCP 实时拉取动态值替代硬编码。参见 `references/hardcoded-price-pattern-2026-06-22.md`。
**修法参考**: `references/dynamic-model-engine-fix-2026-06-22.md` — 完整的三段式修复模式（TV数据加载器 + 模型函数改造 + upstream数据合并），含 load_tv_data()、_compute_dynamic_atr()、_sf() 辅助函数和社区架构依据。

#### 3.1 脚本双目录检查（P1 · 2026-06-22 新增）

**症状**：同一组脚本存在于两个目录，修改一个后另一个目录的旧版本仍在运行。

**检测**：
```bash
# 列出两个目录的脚本清单，交叉比对
ls scripts/*.py | xargs -n1 basename | sort > /tmp/scripts_a.txt
ls hermes/scripts/*.py | xargs -n1 basename | sort > /tmp/scripts_b.txt
diff /tmp/scripts_a.txt /tmp/scripts_b.txt
```

**判读**：交集列表中的脚本如果内容不同（`diff` 有差异），标 P1。需要确定哪个是权威版本，清理另一个目录。如果 cron 作业混用两个路径，标 P0。

**实案（2026-06-22）**：脚本同时存在于 `C:/Users/Administrator/AppData/Local/hermes/scripts/`（30+）和 `D:/Hermes agent/scripts/`（50+）。部分 cron 引用 AppData，部分引用 repo 脚本。修改 repo 的 `topic_router.py` 后 AppData 仍运行旧版。

**根治**：建目录联接（Junction）使 AppData/hermes/scripts → repo scripts，消除双路径同步问题。

Read latest source snapshots:
```
data/source_snapshots/<today>/BTCUSDT-*.json
data/source_snapshots/<today>/XAUUSD-*.json
```

Check:
- Price source count (3+ = A, 2 = B, 1 = C)
- Spread % between sources (>0.5% = degraded)
- CoinGecko null occurrences
- 金十 vs Yahoo systematic bias for XAUUSD (typically 0.3-0.5%)
- **TV bridge semantic identity**: for BTC, `btc_tv_data.json` must contain `symbol=BINANCE:BTCUSDT.P` and BTC-scale VWAP/POC; fresh cache + exit 0 is not enough. If user recently viewed XAU, assume contamination risk and run the bundle in `references/tv-bridge-symbol-contamination-2026-06-22.md`.
- XAUUSD quality tier chain: OANDA+金十+Yahoo→A(92) | 金十+gold-api+Yahoo→A(88-92) | 金十+Yahoo→B(75-78) | 金十 only→C(60)
- **No OANDA token?** Use gold-api.com (free, no auth): integrate via `gold_api_price()` function in `trading_system.py`, add probe in `price_consensus()`, add quality tier for 金十+gold-api+Yahoo → A(88-92)

### 4. 交易执行状态

```
data/trade_plans.jsonl      # Count by state (B等待/待触发/已执行/已取消)
data/trade_events.jsonl     # Check push_sent distribution
data/trade_reviews.jsonl    # Actual executed trade count
data/monitor_levels.json    # ⚠ ALSO check this — executable plans live here
```

- **Pitfall**: `trade_plans.jsonl` may be all "B等待" while `monitor_levels.json` has active executable plans. This is NOT a bug — `trade_plans.jsonl` stores both analysis-only plans (智能结构更新, null entries) and trade plans. Executable plans are often written directly to `monitor_levels.json` by the analysis card pipeline.
- Distinguish: "智能结构更新" plans with `entry: null` = monitoring refreshes (B等待 is correct). Plans with real entry/stop/targets = actual trade plans.
- push_sent=false with push_reason containing "降噪" = over-filtering
- Reviews count vs executable plans count = execution rate

### 5. Cron 与推送

#### 5.0 Cron agent模式噪音（P1 · 2026-06-21实案）
**症状**：cron `hermes cron list` 显示 `Mode: no-agent`，但实际运行在 **agent模式**。脚本失败时LLM生成30行诊断报告投递到Telegram。
**检测**：查看Telegram是否收到详细LLM风格文本（"已修复"、"建议"、markdown格式化等）
**修法**：删除cron后用 `--no-agent` 显式重建。见 `references/tv-cron-noise-fix-2026-06-21.md`

```bash
# Hermes native cron
hermes cron list
hermes cron status

# jobs.json (separate system)
cat hermes/cron/jobs.json

# v6.7: Check prediction verification rate
python -c "
import json
lines=open('data/prediction_log.jsonl').readlines()
verified=sum(1 for l in lines if json.loads(l).get('verified'))
print(f'Predictions: {len(lines)} total, {verified} verified')
"

# v6.7: Check event_ban status in engine
python -c "
import json; data=json.load(open('data/source_snapshot.json'))
from hermes.scripts.multi_model_engine import check_event_ban
banned, reason = check_event_ban(data, data.get('symbol','BTCUSDT'))
print(f'Event ban: {banned} ({reason or \"无禁做\"})')
"
```

- Hermes cron jobs ≠ jobs.json entries = registration drift
- Check each job's last_run status
- Verify deliver targets match actual channels
- **Known risk**: Discord bot configured AND integrated into push() (v6.3.4), verify both channels receive
- **Cron creation recipe**: see `references/cron-management.md`

#### 5.2 推送测试漏发真实消息（测试咽喉 + kill-switch）

**症状**：Telegram/Discord 收到 `test message · 紧急`、`timeout test · 触发` 等明显的测试字样消息，但当时并没有真实告警。来源是单元测试（如 `tests/test_push_async.py`）把假消息漏发到了生产频道。

**根因（两个缺陷叠加）**：
1. 测试只 monkeypatch 了 `subprocess.run`，但 `行情守望.py` 的 `_send_one` 里 Telegram 这条路走的是 `telegram_direct.send_telegram_direct`（直连 Bot API 的 HTTP 请求），**根本不碰 subprocess** → monkeypatch 形同虚设，真消息直接发出去。
2. `push()` 是异步的：消息入队后由后台 **daemon worker 线程** 串行发送。worker 往往在测试函数退出、monkeypatch 还原**之后**才执行 → 用的是真实发送通道。`target=None` 还会回落到默认警报话题 `416` 并顺带发一份到 Discord。

**修法（双保险，缺一不可）**：
- **代码层 kill-switch**：在 `_send_one` 顶部加进程级开关 `HANGQING_NO_SEND`。`os.environ.get("HANGQING_NO_SEND") == "1"` 时只写日志后 `return True`，在触达任何真实通道（telegram_direct / subprocess）前短路。测试/CI 默认开启，从根上杜绝漏发。
- **测试层 stub 咽喉**：monkeypatch **`watch._send_one`**（所有通道的唯一出口），不要再 patch `subprocess.run`。验证非阻塞契约时让 stub 自身 `time.sleep(N)`，再断言 `push()` 在 1 秒内返回。
- **退出前排空队列**：测试结束前调用 `watch.drain_push_queue(timeout=20)`，确保 daemon worker 在 monkeypatch 仍生效时跑完，避免还原后竞态外发。

**通用教训**：任何「入队 + 后台线程发送」的异步推送，patch 最底层的 `subprocess.run` 不够 —— 必须 patch 发送咽喉函数本身，且在 patch 还原前 drain 队列。多通道发送（Telegram 直连 HTTP + subprocess 兜底 + Discord）尤其要找唯一咽喉，不能假设所有通道都走 subprocess。

#### 5.3 推送通道超时 ≠ 通道损坏（错误计数陷阱）

**症状**：monitor.log 里某通道（Discord/Telegram）出现大量 `推送失败 ... timeout` 条目，第一反应想标 P1「通道实际不通」。

**陷阱**：原始错误条数会误导。2026-06-19 审计曾因 28 条 Discord timeout 直接判「频道不通 P1」，但实际复核发现这 28 条全部集中在 10:42–19:30，19:30 之后所有推送（19:42/20:39/20:55/21:15...）以及当场的 4s 实弹 send 测试全部成功 —— 是早间网络/代理抖动，已自愈。频道是活的。

**正确诊断顺序（任何「通道坏了」结论前必走）**：
1. **看时间分布**，不是看总数：`grep 'timeout\|推送失败' data/monitor.log | tail -40`，确认错误是集中在某时间窗（抖动，会自愈）还是持续到当前（真损坏）。
2. **跑一次实弹 send 测试**：用 `hermes` CLI 或 `telegram_direct` 当场发一条测试到目标频道，看 exit code + 耗时。成功 = 通道活着，降级为抖动脆弱性，不是损坏。
3. 只有「错误持续到当前 + 实弹测试也失败」才判通道损坏（P1）。其余判「抖动脆弱性」。

**抖动的真正危害（这才是要修的）**：单条推送走串行 worker，每条先 Telegram 直连 HTTP（快且稳）再 Discord subprocess 兜底。Discord subprocess 配 `10s timeout × 3 retries = 30s` 最坏阻塞 → 抖动期间把串行 push worker 拖死 → 主循环心跳停滞 → watchdog 误判卡死强杀重启。这条因果链（推送重试阻塞 → 心跳停滞 → watchdog 重启）就是早间反复重启的根因，比「通道不通」更值得修。

**修法方向**：缩短次通道超时/重试而非删通道。Telegram `telegram_direct` 已是可靠主通道，Discord 偶尔 2 次重试后失败可接受（告警已由 Telegram 送达，不丢）。把 Discord 从 `10s×3=30s` 降到 `6s×2=12s`，最坏阻塞落到心跳容忍阈值（~15-20s）以下。删通道是最后手段。

### 6. 安全与健康评分

```
data/system_health_score.json
data/security_audit.json
data/strategy_model_stats.json
```

- health_score < 80 = investigate findings
- security_score < 90 = review recommendations
- Strategy stats: sample count < 20 = insufficient for model tuning

### 7. 日志异常

```bash
data/monitor.log    # Last 30 lines, scan for repeated errors
data/watchdog.log   # Check restart frequency
```

**Pitfall: `monitor_events.json` 是 JSONL 格式** — 每行一个独立 JSON 对象，不是单个 JSON 数组。
`cat data/monitor_events.json | python -m json.tool` 会报 `Extra data`。
正确读法：`for line in open('monitor_events.json'): event = json.loads(line)`。
不要用 `json.load(open(...))` — 它只读第一行，跳过所有后续事件。

- Repeated identical errors = unresolved bug (e.g., `model_dir_text`)
- Frequent restarts = process instability (but may be watchdog correctly restarting a crashing monitor — check root cause first). Restart-pattern 判读（心跳停滞 vs 真崩溃 vs 速率限制）见 `references/audit-pitfalls.md`「watchdog 频繁重启判读」。
- watchdog.log lacks date prefix (known P2 issue)
- **技能完整性已自动护栏**：`scripts/清理守护.py` 的 `check_skill_integrity()` 每 6 小时扫全部 SKILL.md/references 检测行号污染 + frontmatter 损坏（no-agent 零 token，报警走 Telegram 846）。审计时确认清理守护 cron `last_run` 正常即可，不必手动全库扫描。背景与诊断见 `references/audit-pitfalls.md`「技能文件完整性已自动护栏」。改 repo 的清理守护.py 须同步 `%LOCALAPPDATA%/hermes/scripts/` 副本。

### 7b. Git untracked files = changes invisible（P0）

**"我改了但没生效"的第一嫌疑人不是代码逻辑 — 是文件没有被 git 跟踪，或者用户说"锁定"但你只存了盘没 commit。**

棠溪说"锁定" = git commit + push 到远端。`??` (untracked) 或 ` M` (unstaged) 的文件随时被 `git reset --hard` 丢失。

审计后如果 `git status` 显示关键文件为 `??` (untracked)：
- `git reset --hard` 会丢失所有改动
- `git log` 看不到这些文件
- 远端没有备份
- 用户手动做的 `.gitignore` / `jobs.json` 修改也可能在 unstaged 状态

诊断：`git status --short | grep <关键文件名>`。如果是 `??`，立即 `git add` + `git commit` + `git push`。

还要检查重复文件：`scripts/auto_card.py` 可能是薄 wrapper，`hermes/scripts/auto_card.py` 是主实现。
监控导入其中一个，用户改另一个 → 改动不生效。

完整诊断流程见 `references/git-untracked-diagnostic.md`。

### 7c. Custom provider 不可用 — 系统化排障

不要假设是 User-Agent 或代理问题。按此顺序实证排查：
1. curl 非流式 → 确认 base_url 路径（缺 `/v1` 最常见）
2. curl 流式 → 确认 UA 不触发 Cloudflare
3. SDK 流式 → 抓实际请求头 + URL 确认 SDK 拼的正确路径
4. SDK 带 tools → 确认 api_mode 协议兼容（OpenAI vs Anthropic）

完整调试流程见 `references/custom-provider-debugging.md`。

## 8. Push 抑制率分析

After counting `push_sent` in trade_events.jsonl:

```python
events = [json.loads(l) for l in open('data/trade_events.jsonl')]
by_tier = {}
for e in events:
    t = e.get('tier','unknown')
    p = e.get('push_sent')
    by_tier.setdefault(t, {'total':0,'pushed':0})
    by_tier[t]['total']+=1
    if p: by_tier[t]['pushed']+=1
```

- warning tier suppressed >50% = noise threshold too aggressive
- info/expired tiers always heavily suppressed (STRICT_PUSH_MODE)
- If blocked reason is consistently "位信N% · 数据B级" with N≈68-70: threshold edge case → tune push_allowed
- **Tuning recipe**: add third condition for medium-priority breaches with B+ data:
  ```python
  if breached_like and score >= 68 and data_q in ("A", "B"):
      return True, f"触发且位信{score}% · 数据{data_q}级"
  ```
- After tuning, MUST restart monitor for changes to take effect (watchdog auto-restarts on stale heartbeat >90s, or manual `taskkill`)

### 8b. 警报阈值层级设计（社区共识：接近比突破更严）

审计时必须检查 `scripts/行情守望.py` 中 `MIN_WARNING_LEVEL_SCORE` 与 `MIN_CRITICAL_LEVEL_SCORE` 的关系：

**社区共识（TradingView Confirmation Gate 模式 + r/algotrading）**：
- **突破/触发信号** 已有价格跨过关键位的天然确认 → SNR 高 → 门槛可放低
- **接近信号** 尚无价格确认 → SNR 低 → 门槛应更高
- 因此 `MIN_WARNING_LEVEL_SCORE > MIN_CRITICAL_LEVEL_SCORE` 是合理的

**推荐梯度**：
```
接近  (warning)   75 — 高门槛降噪
突破  (critical)  70 — 价格已跨过，优先推送
失效  (info)      60 — 旧位过期提醒
```\n\n审计时必须检查 `scripts/行情守望.py` 中 `MIN_WARNING_LEVEL_SCORE` 与 `MIN_CRITICAL_LEVEL_SCORE` 的关系：\n- **铁律**: `MIN_WARNING_LEVEL_SCORE >= MIN_CRITICAL_LEVEL_SCORE` — 接近信号 SNR 低，门槛应更严。看似倒挂不是 bug（详见 `references/alert-threshold-design.md`）\n- 棠溪已锁定：warning=75, critical=70, info=60（2026-06-19 社区共识验证，详见 references/alert-threshold-design.md 和 references/2026-06-19-alert-threshold-gradient.md）\n\n\n\n### 8c. 预测回验偏向检测（P0 · 99%+ 胜率 = 过拟合红灯）\n\n**症状**: `monitor.log` 反复出现 `模型胜率：99.8%`。真实市场不可能持续 99%+。\n**审计步骤**:\n1. `cat data/prediction_log.jsonl | python -c \"import json,sys; lines=[json.loads(l) for l in sys.stdin]; verified=[l for l in lines if l.get('verified') and l.get('was_correct') is not None]; correct=sum(1 for l in verified if l['was_correct']); print(f'{correct}/{len(verified)} = {correct/len(verified):.1%}' if verified else 'none')\"`\n2. 若胜率 >80%，排查 `hermes/scripts/prediction_tracker.py::verify_predictions()`:\n   - \"方向不明\" 是否被计为正确（`was_correct = True`）→ 必须排除\n   - 阈值是否过低（0.1% 移动在 4 小时后几乎 100% 发生）→ 提到 0.3%\n   - 是否用了事后价格而非入场后 N 根已完成 K 线做判定\n3. 修复后清空旧 prediction_log.jsonl 重新积累样本\n4. 胜率日志降频：每 30 分钟写一次改为每小时一次\n\n### 8d. 推送合并检测（P2 · 一次触发不应推两条独立消息）\n\n审计时检查 `行情守望.py` 中 `process_block` 的推送逻辑：\n- 如果 `push(警报)` 后又 `push(结构更新)` → 一次突破触发推两条 → 震动行情刷屏\n- 修复模式：把结构重算移到 `render_message` 之前，成功时把通知追加到警报消息末尾，只推一条\n\n### 8e. 驾驶舱 Cron 数据源覆盖验证（P1 · 有数据没规则）

**症状**：系统有多个 cron 在采集数据（如 Deribit 期权 PCR/MaxPain、ETF Flow、Dune 链上、COT 报告），但驾驶舱验证规则中没有引用这些数据源——"有数据采集但无裁决规则"。

**检测**：
1. 列出所有 `no_agent` trading cron 任务的脚本名和频率
2. 读 `references/tangxi-trading-cockpit.md` 的双指标裁决规则和各市场流程段
3. 对每个 cron 数据源，检查是否在驾驶舱规则中被引用
4. 有 cron 采集但无规则引用 = P1 验证缺失

**实案（2026-06-29）**：驾驶舱 v1.0 有 4 个 cron 数据源未入验证规则——Deribit 期权 PCR/MaxPain（15min cron）、ETF Flow（4h cron）、Dune 链上（2h cron）、COT 报告（周六 cron）。另有体制分类器（regime_classifier）和跨资产相关性（correlation_matrix）脚本存在但未纳入驾驶舱模块。修复：驾驶舱升级到 v1.1，新增第 8 模块"体制驾驶舱"，新增 5 条裁决规则（PCR极度偏离+结构顺向→升级、ETF持续流出+BTC多→降B、体制=收敛+A突破→降B、Dune大量流出→增强多头、COT商业净空+技术多→降级），新增 Cron↔驾驶舱映射表。

**通用教训**：审计驾驶舱时不仅要验证运行态健康（心跳/数据新鲜/cron 状态），还要检查"数据采集层和验证规则层是否对齐"——有 cron 采集但驾驶舱规则不引用它 = 验证缺失。每次新增 cron 数据源后必须同步更新驾驶舱规则文档。

### 9. 回测引擎状态 + 模型覆盖率 + Walk-Forward + 测试覆盖

```python
# Run a quick backtest sanity check
python scripts/backtest_runner.py  # imports + basic smoke test

# Check data availability
ls -la data/btc_klines_30d_merged.json  # BTCUSDT 30-day K-lines + futures

# Run walk-forward validation (社区黄金标准)
python -c "
from walk_forward import walk_forward_validate, format_wf_result
# ... load klines ...
wf = walk_forward_validate('BTCUSDT', closes, highs, lows, opens, volumes, timestamps, cfg=cfg)
print(format_wf_result(wf))
print(f'过拟合检测: {check_overfit(wf.train_metrics[\"win_rate\"], wf.test_metrics[\"win_rate\"], 3, cfg)}')
"
```

Check:
- `btc_klines_30d_merged.json` exists with ≥2000 candles
- Model coverage ≥40% (9/13 is current healthy baseline for BTC-only)
- VWAP反抽 always dominates (>90% in trends) — verify that model diversity rules work
- **Pitfall**: Backtest numbers inflated by trend bias. See `references/backtest-honest-interpretation.md`.

**测试覆盖审计（必须执行）**:
```bash
# ✅ 正确：搜索 tests/ 目录（不是 scripts/tests/）
find tests/ -name "test_*.py" 2>/dev/null | wc -l
# ✅ 正确：从项目根目录跑
cd "D:/Hermes agent" && python -m pytest tests/ -q --tb=short
# ❌ 错误：scripts/tests/ 不存在 → 会报 "no tests ran" 误判为零测试
# ❌ 错误：search_files 查 sandbox/ 下其他项目测试 → 会把外部测试计入
```
- **Pitfall**: 过去审计曾因 `pytest scripts/tests/` 路径不存在误判"零回归测试"。
  实际 `tests/` 目录有 15 个测试文件，103/104 passed（2026-06-21）。
  必须从项目根目录跑 `python -m pytest tests/`。

**Model coverage audit**: Some models are BTC-specific (need Binance futures: 费率/LS/Taker/OI), others are XAU-specific (突破接受/M_VWAP磁吸/关联套利). Low coverage on BTC-only backtests is normal. See `references/model-coverage-btc-xau-split.md`.

### 11. GitHub 社区对比

**联网调研工具（2026-06-18 验证）**:
凭据存 `hermes/secrets/search_apis.json`，详见 `references/audit-pitfalls.md` 联网工具表。
- ✅ Brave Search API (2000/月) — 主搜索源，搜Reddit帖子+技术文章+实时结果
- ✅ Exa Search API (1000/月) — 语义搜索，找深度技术文章
- ✅ `web_extract` 直拉 Freqtrade/NautilusTrader/3Commas/Bookmap 官方文档
- ✅ GitHub REST API via curl — 搜索仓库
- ✅ awesome-quant (26.8k star) curated list
- ⚠ Reddit r/algotrading — 需cookie或crawl4ai绕反爬
- ⚠ Google — 需clash代理避CAPTCHA
- 爬取工具：crawl4ai (JS渲染) + Scrapling (反爬)

**有效社区调研路径**: Brave API搜Reddit/X → Exa API搜深度文章 → web_extract拉官方文档 → GitHub API搜仓库 → awesome-quant → 既有档案。

Compare against open-source projects (Freqtrade/Jesse/NostalgiaForInfinity/aurumcrypto/BAKOME) using GitHub REST API or web_extract. Focus on identifying borrow-able modules rather than just star-counting. See `references/github-borrow-workflow.md` for the full methodology.
**GitHub REST API 查询命令**:
```bash
curl -s "https://api.github.com/search/repositories?q=freqtrade&sort=stars&per_page=3" \
  -H "Accept: application/vnd.github.v3+json" -H "User-Agent: TangXi"
```
Extract: stars, forks, pushed_at, description, open_issues
Compare capability matrix: backtesting, dashboard, parameter optimization, multi-exchange, CI/CD
Identify 棠溪 unique advantages: SMC/ICT analysis, Chinese analysis cards, multi-source A/B/C quality grading, Grok AI cross-validation
Credit honestly: numbers that are shared must be verified against their actual source

## Common Findings Reference

See `references/common-findings.md` for a catalog of previously observed
issues with root causes and fixes (including search API availability matrix).
See `references/ntp-windows.md` for the Windows NTP sync recipe (git-bash pitfalls).
See `references/github-fusion-pipeline.md` for verified integration modules and the five-level verification matrix.
See `references/audit-pitfalls.md` for recurring false positives and field-name traps.
See `references/backtest-honest-interpretation.md` for backtest number interpretation rules and common inflation sources.
See `references/backtest-reliability-pytest-2026-06-18.md` for backtest entry-path consistency checks, RR/result-sign sanity constraints, same-bar TP/SL ambiguity handling, and pytest import-mismatch fixes.
See `references/model-coverage-btc-xau-split.md` for the 13-model BTC vs XAU suitability analysis.
See `references/github-borrow-workflow.md` for the methodology to find and integrate open-source trading modules.
See `references/community-recommendations-2026-06-18.md` for aggregated best practices from X/Reddit/GitHub/Freqtrade/QuantConnect.
See `references/audit-to-fix-hardening-2026-06-18.md` for the audit-to-implementation hardening pattern: protective tests before fixes, backtest runtime sanity guards, XAU spot/basis separation, no-agent daily validation, pytest drift cleanup, and live monitor verification after process-resident code changes.

## 🔴 Critical Audit Pitfalls (MUST READ before every audit)

### -1. 过度审计陷阱：文档不一致 ≠ P0/P1（最高优先级）

**铁律**：只把影响实时系统行为的问题判为 P0/P1。以下类型永远不是 P0/P1：
- 模板文档里有 `setup_id` 占位符但实际渲染已剥离 → P2 文档整洁度
- CVD 等级描述过时（代码已用 A 级但文档写 C 级）→ P2 文档滞后
- 话题路由编号在文档中写旧值但实际推送走正确路由 → P2
- 两个文件里同名脚本的路径不一致但导入正常工作 → P2 最坏情况

**判定标准（三问法）**：
1. 这个"问题"会导致用户收不到警报吗？→ 否 → 不是 P0
2. 这个"问题"会导致分析卡错误或交易信号错误吗？→ 否 → 不是 P1
3. 这个"问题"只是文档/代码不够整洁吗？→ 是 → P2，甚至可以不管

**棠溪曾因审计过度标记而反问"这些任务有必要吗"** — 教训：审计报告产出前必须过一遍三问法，砍掉所有文档洁癖项。

**本会话实案（2026-06-19）**：初次审计产出 14 条 P0/P1/P2 问题，棠溪反问"有必要吗"后复查 — 11 条是文档整洁度问题（模板占位符 vs 渲染层剥离、CVD 等级描述过时、话题路由编号文档滞后、脚本路径不一致但导入正常工作、死代码未注册不占 CPU、阶段区间重叠只在废弃的 gold_monitor 场景等）。仅 2 条是真问题：gold_monitor 硬编码价格偏离市场 + 自动标注复盘脚本不存在。教训：**宁可漏报文档问题，不可把文档问题标成 P0/P1 消耗信任**。

### 0. 文件路径验证（最高优先级）

**核心脚本在 `scripts/` 目录，不是 `hermes/scripts/`。**
Memory 和旧审计记录可能引用 `hermes/scripts/行情守望.py` 等路径 — 这些全是错的。`hermes/scripts/` 下仅有 `multi_model_engine.py` 等引擎模块。
审计第一步：`ls scripts/行情守望.py scripts/watchdog.py scripts/auto_card.py scripts/trading_system.py`
如果路径不对，用 `search_files(target='files', pattern='行情守望.py')` 查真实位置。

### 1. Verify field names before flagging as broken

**NEVER query `p.get('win')` on prediction_log entries** — the actual field is `was_correct`.
**NEVER query `r.get('reason')` on structure_refresh_requests** — the actual field is `reasons` (plural).

Before flagging any field as "broken" or "empty":
```python
print(list(entry.keys()))  # ALWAYS print keys first
```

### 2. Source snapshot key structure varies by file

- **Per-symbol files** (`source_snapshot_BTCUSDT.json`): nested dict with `prices.primary`, `quality`, `confidence`, `confidence_label`
- **Unified file** (`source_snapshot.json`): may have different structure
- **Historical snapshots** match the per-symbol structure

Never assume `d.get('data_quality')` or `d.get('source_count')` exist. Print keys first.

### 3. OANDA token placeholder (P0)

Check `hermes/secrets/oanda_token.txt` content. If it starts with `# OANDA personal access token` or contains `PLACEHOLDER`, it's a template, not a real token. XAUUSD will be capped at B(78%) until a real token is configured.

### 4.5 watchdog 重启子进程丢失环境变量（P0 隐形杀手）

**症状**: monitor.log 反复出现 `推送失败 ... missing TELEGRAM_BOT_TOKEN`，但手动启动时推送正常。
**根因**: `watchdog.py` 用 `subprocess.Popen([sys.executable, MONITOR_SCRIPT])` 重启行情守望时
**不继承**父进程环境变量。token 存在 `%LOCALAPPDATA%/hermes/.env`（不是 secrets/，不是 config.yaml），
靠环境变量传入的 token 在 watchdog 拉起的子进程里读不到。
**修法**: 让 `telegram_direct.py` 增加 `.env` 文件兜底读取（`_token_from_env_file()`），
候选路径 `%LOCALAPPDATA%/hermes/.env` → `~/.hermes/.env`，结果缓存避免反复 IO。
这样无论谁拉起进程都能拿到 token。配套测试需 `monkeypatch.setattr(td, "_token_from_env_file", lambda: None)` 才能复现真无 token。

### 4.6 Binance SSL UNEXPECTED_EOF 拖垮主循环

**症状**: monitor.log 出现 `收盘价错误 ... SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]'))`，
裸 `requests.get` 单次失败即返回 None，累积可拖垮主循环判读 → 心跳停滞 → watchdog 误判卡死。
**修法**: 共享 `requests.Session()` + `urllib3.util.retry.Retry(total=2, backoff_factor=0.5, status_forcelist=(429,500,502,503,504))`
挂 HTTPAdapter；再包一层 `_http_get()` 对 SSLError/ConnectionError 短暂退避重试。替换所有裸 requests.get。

### 4.7 watchdog 冷却卡死（旧时间戳）· 快速救活

进程死了很久（如8小时），但 `watchdog_guard.json` 里 restart_times 是几小时前的旧时间戳，
若 watchdog 重新拉起会读到\"6次/小时已达上限\"误判仍在冷却。手动救活前先清冷却：

```bash
# 一行救活（本会话2026-06-21实战验证）
echo '{"restart_times":[],"restart_times_emergency":[]}' > data/watchdog_guard.json
# 然后 watchdog 会在下次巡检时自动恢复（或手动启动）
```

启动 watchdog 必须用 git-bash 友好的方式：写一个 `.sh` 启动脚本（cd 带空格路径要加引号、从 .env grep token export、exec venv python），
用 `terminal(background=true, notify_on_complete=true)` 拉起 — 不要在 python -c 里内嵌引号，bash 会因引号转义炸 `unexpected EOF`。

**重启风暴根因链（2026-06-21 实战验证）**:
1. 次通道推送超时（Discord hermes_cli timeout 6s×2重试=14s）→ 阻塞 worker 线程
2. 主循环其他阻塞（多个 requests.get timeout）累加
3. 心跳停滞 > 90s → watchdog 误判卡死 → 强杀进程
4. 重启后再次触发 → 速率限制触顶 → 全停

**诊断四步**: ① `grep "推送超时" monitor.log | tail -40` 看时间分布 ② 实弹 send 测试 ③ 查 watchdog 日志"真崩溃" vs "卡死"比例 ④ 缩短次通道超时(30s→12s)。

### 4. Fix-in-source ≠ fix-in-process

After patching `行情守望.py` or `trading_system.py`, the running process still uses old code. Verify:
- Compare heartbeat PID against process list start time
- Check `monitor.log` for disappearance of previously-seen error patterns
- **Delete .pyc cache before restart**: `rm -f scripts/__pycache__/trading_system.cpython-311.pyc` — Python may skip recompilation otherwise (see `references/audit-pitfalls.md` for full recipe)
- Watchdog should auto-restart when heartbeat stalls (>90s), but manual `taskkill //F //PID <pid>` + 40s wait is more reliable
- After restart, verify fix actually took effect (e.g., check XAUUSD snapshot quality label)

### 5.1 Cron no-agent 脚本解释器坑（numpy/pandas ModuleNotFoundError）

no-agent cron 脚本通过 `runpy.run_path` 在 **cron 守护进程自己的解释器内** 执行，
而 cron 守护跑在 Hermes 桌面运行时的 python（`~/.hermes-web-ui/desktop-runtime/hermes/<ver>/win-x64/python/python.exe`），
**这个解释器没装 numpy/pandas**。后果：纯 stdlib 的 no-agent 脚本正常，但任何
import numpy 的脚本（回测/walk-forward/run_daily_validation）会 `ModuleNotFoundError: numpy`
并 `last_status: error code 1`。
- 诊断：`hermes cron list` 看哪个 job `last_status: error`，读 traceback 是否 numpy/pandas。
  对比 venv python（`~/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`，装有 numpy）
  vs 桌面运行时 python（无 numpy）。
- 修法：把 wrapper 从 `runpy.run_path`（进程内执行，继承坏解释器）改成
  `subprocess.run([venv_python, target])` 出去执行，强制用带依赖的 venv python。
  回退链：venv python → sys.executable。验证：跑完查 `data/validation/` 有无新时间戳产物，
  退出码=0。

### 5. Cron source location

`hermes cron list` reads from `~/.hermes/cron/`, NOT from `D:/Hermes agent/hermes/cron/jobs.json`. Both must be checked. An empty `hermes cron list` is a P0 even if `jobs.json` was recently populated.

### 5a. Cron CLI uv trampoline 故障时的直接管理（P0 · 2026-06-21 实案）

**症状**: `hermes cron list/create/delete` 全部报 `error: uv trampoline failed to canonicalize script path`。但 cron 引擎本身正常运行。

**根因**: Hermes CLI 入口点的 Python 打包问题（uv trampoline 无法解析脚本路径）。不影响 crond 守护进程和任务执行，只影响管理命令。

**绕过方法** — 直接编辑 `%LOCALAPPDATA%/hermes/cron/jobs.json`：
```python
import json
jobs_path = "C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json"
with open(jobs_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 添加新 cron（模仿现有条目格式）
new_job = {
    "id": "ae" + hex(int(datetime.now(TZ).timestamp()))[2:12],
    "name": "cron中文名",
    "script": "wrapper脚本.py",
    "no_agent": True,
    "schedule": {"kind": "cron", "expr": "30 8 * * *", "display": "30 8 * * *"},
    "schedule_display": "30 8 * * *",
    "repeat": {"times": None, "completed": 0},
    "enabled": True,
    "state": "scheduled",
    "created_at": datetime.now(TZ).isoformat(),
    "next_run_at": "2026-06-22T08:30:00+08:00",
    "deliver": "telegram:-1003733144325:416",
    "workdir": "D:\\Hermes agent\\scripts"
}
data["jobs"].append(new_job)
data["updated_at"] = datetime.now(TZ).isoformat()
with open(jobs_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

**注意**: 
- `script` 字段从 `%LOCALAPPDATA%/hermes/scripts/` 解析（非 workdir）。需在 AppData 目录创建同名 wrapper 或建 Junction。
- cron 守护进程会在下次 tick 时自动加载 jobs.json 变更，无需重启。
- 验证: 直接读 jobs.json 确认条目存在 · 等下一个 scheduled time 查 last_status。

### 5a. 数据桥"未接"——嵌套函数 ImportError（P1 · 2026-06-21 实案）

**症状**: `monitor.log` 显示 `数据桥未接`，但手动 `python -c "from system_data_bridge import ..."` 全部成功。`_HAS_BRIDGE = False` 只在进程启动时设定，后续不重试。

**根因**: `system_data_bridge.py` 的 `event_ban()` 被错误地嵌套在 `_get_asset_class_simple()` 内部。`__all__` 列出 `event_ban`，但它不在模块命名空间 → `ImportError: cannot import name 'event_ban'` → `_HAS_BRIDGE = False` 静默降级。

**诊断**:
```bash
# 重现行情守望的导入路径
cd D:/Hermes agent && python -c "import sys; sys.path.insert(0,'scripts'); from system_data_bridge import cvd_dir, deriv_text, snapshot, event_ban, dir_flip, enrich_engine_data; print('OK')"
# ImportError → P1 数据桥未接
grep "^def \|^    def " scripts/system_data_bridge.py
# 缩进为 '    def' 者 = 嵌套函数，不可导入
```

**修法**: 将 `event_ban()` 移出为模块级函数（去缩进一行），同时删除内部重复的嵌套 `get_dxy`/`get_basic_earnings_flag`/`asset_macro_enrich` 死代码（模块级已有正确版本）。验证：重启后 monitor.log 显示 `数据桥已接`。

**通用教训**: 任何 `_HAS_BRIDGE = False` 静默降级都是 P1——它不等于 bridge 真不可用，可能是单个导入项名错误或嵌套。审计时不能看 `_HAS_BRIDGE` 布尔值就下结论，必须 `python -c` 重现导入路径定位具体 ImportError。

### 5b. 悬挂 cron 配置（P0 · YAML 文件存在但未注册）

**症状**: `hermes/cron/tv_signal_monitor.yaml` 文件存在且配置完整，但 `hermes cron list` 中没有对应任务。功能从未执行。

**根因**: 手动创建 YAML 文件 ≠ cron 注册。Hermes cron 从 `~/.hermes/cron/` 数据库读取，不从 repo 的 `hermes/cron/*.yaml` 自动导入。YAML 只是配置模板，必须通过 `hermes cron create` 或 Studio API 正式注册。

**审计手段**:
```bash
# 列出所有 repo YAML
ls hermes/cron/*.yaml
# 交叉验证已注册任务
hermes cron list | grep -c "<名字关键字>"
# 数量不匹配 = P0 悬挂配置
```

**修法**: `hermes cron create --name "TV信号监控" --script "tv_signal_monitor.py" --workdir "D:\\Hermes agent\\hermes\\scripts" "*/5 * * * *"`

**通用教训**: 任何手动创建的 cron YAML 必须在审计中交叉验证已注册。宁可多跑一条 `hermes cron list`，不可假设 YAML 存在即生效。

### XAU kline 400 泄漏（P0 · 不同于 ticker 泄漏）

**症状**: `monitor.log` 出现 `收盘价错误 XAUUSD 15m: 400 Client Error: Bad Request for url: https://api.binance.com/api/v3/klines?symbol=XAUUSD`

**根因**: `行情守望.py` 的 `get_price()` 有 XAU 守卫（`if "XAU" in sym or not sym.endswith("USDT"): return None`），但 klines 调用（`行情守望.py:225,247`）没有同类守卫。Binance 不接受 XAUUSD 作为 klines symbol → 每次循环一个 400。

**与 ticker 泄漏区别**:
- Ticker 泄漏：`get_price("XAUUSD")` → Binance ticker → 400（已在 2026-06-19 修）
- Kline 泄漏：`_http_get(klines, symbol="XAUUSD")` → Binance klines → 400（本会话发现）
- 两处守卫必须分别加，共享同一个守卫函数

**审计手段**:
```bash
grep -n "XAU" scripts/行情守望.py | grep -iE "binance|klines|kline"
grep "400.*XAUUSD.*kline" data/monitor.log | tail -3
```

**修法**: 在 klines 调用前加硬守卫 `if "XAU" in symbol or not symbol.endswith("USDT"): return None`。所有 Binance 数据路径（price/klines/ticker/futures）必须有 XAU 守卫。

### Watchdog 重启风暴分析（2026-06-21 下午实案）

**症状**: `watchdog.log` 15:52–17:22 连续出现「重启速率限制[真崩溃]：6次/小时已达上限」和「重启速率限制[卡死/环境未就绪]：3次/小时已达上限」。每个小时都触发冷却，系统几乎无监控覆盖。

**诊断四步**:
1. 看时间分布：错误集中在某时间窗（15:52–17:22）还是持续到当前
2. 看「真崩溃」vs「卡死/环境未就绪」比例：前者 = 进程真死了，后者 = 进程活着但心跳停滞
3. 看 monitor.log 同时段：是否有串行阻塞（多 requests.get timeout 累加）
4. 看 push 通道：次通道（Discord）10s×3=30s 重试是常见拖死原因

**修法方向**:
- 降次通道超时/重试：Discord 10s×3→6s×2，最坏阻塞从 30s 降到 12s
- 让阻塞落在心跳容忍阈值（~15-20s）以下
- 串行 request 改 Session 复用 + Retry + 并发 futures（不是本条修复范围）

**手动救活**: 当 watchdog 冷却时，先 `taskkill` 杀旧进程 → `rm data/monitor.lock` → 清理 `watchdog_guard.json` 冷却时间戳 → 重新启动。详见 `references/watchdog-storm-recovery.md`。

### 5.5 Hermes cron 管理陷阱（路径/语法/同步）

**`hermes cron create` 语法**：
```bash
# ✅ schedule 是 POSITIONAL 参数，不是 --schedule
hermes cron create --name "持仓与信号" --script "持仓与信号.py" --no-agent \
  --workdir "D:\\Hermes agent\\scripts" --deliver "telegram:-1003733144325:846" \
  "every 5m"

# ✅ cron 表达式支持时间范围：只在 8-23 点执行
hermes cron edit <id> --schedule "*/5 8-23 * * *"

# ❌ 错误：--schedule 不存在
hermes cron create --name "..." --schedule "every 5m" --mode no-agent ...
# → error: unrecognized arguments: --schedule --mode
```

**时段门控原则（铁律）**：用 cron 调度管时段，不在脚本里写复杂时间判断。
- ✅ `*/5 8-23 * * *` — cron 管 23-8 静默，干净
- ❌ 脚本里写 `if hhmm not in [(800,925),(1135,1255),(2205,2255)]: sys.exit(0)` — 难读、难调、窗口一变要改两处
- 本会话棠溪先要求避开 A 股和黄金时段，导致只剩 3 个窄窗口，脚本门控复杂化。最终棠溪说"按你觉得最合适的来"→ 回到 cron 级简化为 `*/5 8-23`。教训：时段需求频繁变化，cron 表达式改一行即可，脚本门控改完还要测试。

**脚本查找路径陷阱（P0）**：
- no-agent cron 的 `--script` 参数从 **`%LOCALAPPDATA%/hermes/scripts/`** 解析，不从 `--workdir` 解析
- `--workdir` 只设执行时的 cwd，不影响脚本定位
- **根治方案：目录联接（Junction）** — 让 AppData/hermes/scripts 指向 repo scripts，消除双路径：
  ```python
  # Windows Python 建联接（比 mklink / PowerShell 更可靠）
  import ctypes, os
  appdata = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'scripts')
  target = r'D:\Hermes agent\scripts'
  kernel32 = ctypes.windll.kernel32
  CreateSymbolicLinkW = kernel32.CreateSymbolicLinkW
  CreateSymbolicLinkW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
  CreateSymbolicLinkW.restype = ctypes.c_bool
  CreateSymbolicLinkW(appdata, target, 0x1)  # 0x1 = directory
  ```
- 建联接前：`rm -rf AppData/hermes/scripts/__pycache__` → 等锁释放 → `rmdir` 空目录 → 建联接
- 注意：AppData 目录可能被 cron runner 锁定，需等待锁释放后重试
- 建好后：`ls "$LOCALAPPDATA/hermes/scripts/"` 应显示 repo 所有脚本
- **不再需要手动 `cp` 同步** — 联接使两个路径指向同一份文件

**Cron 任务合并模式（7→3 实战验证）**：

当 cron 列表膨胀（7+ 个），合并重叠任务的标准步骤：
1. 列出所有 cron，逐个读脚本，找出职责重叠的任务
2. 创建轻量 wrapper 脚本（`subprocess.run` 串行调用原脚本）
3. 注册新 cron（wrapper）→ 验证能跑 → 逐个删除旧 cron
4. 清理 AppData 死脚本（如 `auto_label_bridge.py`）
5. 删除 paused 状态的废弃 cron（jobs.json 残留）

**合并案例分析**：
- 信号巡检(3m) + 持仓监测(5m) → 持仓与信号(5m) — 两个都高频，空仓时都静默，合并后每天轮询从 768 次降到 288 次
- 凌晨三连(3:20+3:50+4:10) → 日间维护(8:30) — 三个凌晨任务串行执行，一条日报
- 清理守护 6h → 每天 12:00 一次 — 够用

**脚本不存在但 cron 指向它（P1 静默失败）**：
- 症状：`hermes cron list` 显示 `last_run: ok` 但脚本文件不存在
- 原因：Hermes cron 不验证脚本是否存在，`last_status: ok` 可能是最后成功跑时的旧记录
- 案例：`auto_label_bridge.py` 从不存在，但 cron「自动标注复盘」注册了 2 天（每次空跑无输出 = 看起来正常）
- 审计手段：`ls "$LOCALAPPDATA/hermes/scripts/<script>.py"` 逐个验证 cron 引用脚本存在

**其他 cron CLI 要点**：
- `hermes cron tick` — 强制执行所有到期 job（无到期则静默）
- `hermes cron run <id>` — 将指定 job 排入下一次 scheduler tick
- `hermes cron delete <id>` — 删除 job
- 修改 script 内容后 cron 自动用新代码（每次 run 时重新读取）

**cron 清单膨胀时的合并判定（2026-07-07 棠溪 20→17 实战）**：
- 读真实脚本路径：`hermes cron list --json` 无输出 → 直读 `%LOCALAPPDATA%/hermes/cron/jobs.json`，遍历 `d['jobs']` 取 `name/schedule.expr/script/deliver/id`。
- 合并模式 A（import-chain bundle）：N 个脚本各自 `main()+print(report)`、无依赖 → 新建 bundle 脚本顺序 `import` 各 `main` 调用、try/except 隔离、拼接输出一次推 TG，删 N 个旧 cron 建 1 个。示例：每日运维聚合（技能更新+审计+备份+模型同步 4→1）。
- 合并模式 B（collector 末尾 import 分析卡）：采集脚本落盘 json + 独立分析卡 cron 读 json 渲染 → 在 collector `main()` 末尾 `importlib.util.spec_from_file_location` 动态 import 分析卡并调其 `main()`，collector `deliver` 改 tg、删独立分析卡 cron。示例：Orion 采集+分析 2→1。
- 保留不动：数据源不同/功能不重叠（X情绪采集 vs LLM 分析）、看门狗监控对象/重启逻辑不同（BTC/行情守望/数据新鲜度）、各独立采集 cron。
- 完整模式+判定树+冒烟验证见 `references/cron-merge-and-junction.md`（2026-07-07 补）。
- 社区 skill 获取补全能力缺口（如期权 Greeks、多源情绪）的流程见 `references/community-skill-acquisition-2026-07-07.md`。

### 6. Memory test counts may be wrong

Memory may record "31 test" or "24项pytest" but the trading system may have **zero** pytest files.
sandbox/ directories contain test files from OTHER projects (feedgrab, feishu-streaming-card, etc.)
that are unrelated to the trading system. Always verify with:
```bash
find scripts/ tests/ -name "test_*.py" 2>/dev/null  # excludes sandbox/
ls pytest.ini pyproject.toml conftest.py 2>/dev/null
```
If this returns nothing, the system has no regression tests regardless of what memory says.

### 7. 模板合规性：master-template-v68.md 是唯一权威源
### 7. 模板合规性：master-template-v68.md 是唯一权威源

**铁律（2026-06-19 强化）**：
- **出卡/审计卡合规前第一步**：必须 `read_file("references/master-template-v68.md")` 加载当前锁定底板。**绝不能依赖记忆、旧会话、或 SKILL.md 中的格式示例**（它们可能已滞后）。棠溪曾因未加载模板直接输出导致格式错误被纠正。
- 分析卡 v6.9 = `references/master-template-v68.md` 完整内容底板 + 速读编号骨架。
- 分析卡正文（头部 + 五段）**必须零机器字段泄漏**：禁止出现 `setup_id`、`model_id`、`entry_tag`、`exit_tag`、`critical`、`warning`、`info` 及其具体值。仅允许中文人读模型名（如 `VWAP反抽`）。
- 机器字段只允许存在于本地 meta、trade_plans.jsonl、monitor_levels.json 的结构化存储中，绝不渲染进用户可见卡片。

**`auto_card.py` 的 `render_card_locked()` 产出的卡片必须严格匹配 `references/master-template-v68.md` 底板。**

**变更后验证铁律（v7.0）**：
任何涉及 `auto_card.py`、渲染逻辑、价格数据桥、或 monitor 推送格式的改动后：
1. `python -c "from hermes.scripts.auto_card import render_card_locked; print('OK')"` — 语法导入
2. `python -m pytest tests/test_card_render_locked.py -q` — 卡片格式测试
3. `grep -E "(setup_id|model_id|entry_tag|exit_tag)" data/auto_card_*.md || echo "0 leaks OK"` — 机器字段泄漏
4. `git status --short → git commit + push`

**v7.1 格式检查点**（替换旧 v7.0 检查）：
- 卡片含 ①-④ 序列（状态/现价/指标/关键位） + 预案AB + ⑩闸门
- 含 `预案A`、`预案B`、`止损`、`止盈`、`闸门`
- **不含** `一、环境` `二、结构` `三、博弈` `四、操作` `五、风控`（v7.0+已删除）
- 卡片行数 ≤ 22 行（含空行·v7.1手机版上限）
- 每行 ≤ 38 字符（手机不折行·`len(line) <= 38`）

**速读版是独立格式，不能替代完整版。** 监控警报用监控自有格式，分析卡调用必须输出完整底板。

**两套渲染系统并存陷阱**：`auto_card.py` 有 `render_card_locked()`，但监控 `行情守望.py` 有独立的 `render_message()` 不调用 auto_card。改了 auto_card 的排版 ≠ 监控推送的卡片格式改变。审计时必须分别检查两条渲染路径的输出格式是否都符合底板。

**源码回退/大 diff 陷阱（P0）**：全面审计时不能只看运行心跳和日志；必须同时看 `git diff --stat` 与针对性回归测试。若 `scripts/行情守望.py` 出现数百行 diff，且 `tests/test_push_async.py` 报缺 `_send_one` / `drain_push_queue`，或 `tests/test_monitor_setup_trace.py` 报缺 `enrich_event_with_setup`，说明监控核心从异步 v7.x 回退到同步旧版。判 P0：推送可能阻塞主循环、分品种话题路由失效、setup metadata 无法进入事件复盘。审计命令：`python -m pytest tests/test_push_async.py tests/test_monitor_setup_trace.py -q --tb=short`；修复前不要宣称监控链路健康。

**模板源头冲突陷阱（P1）**：即使 `auto_card.py::render_card_locked()` 已经把机器字段从正文中剥离，也要检查 `references/master-template-v68.md` 自身是否仍示例化 `setup_id/model_id/entry_tag/exit_tag/机器字段`。若权威模板仍要求正文机器字段，而技能/记忆要求“正文零机器字段”，未来手排卡或跨渠道出卡会被模板误导。判 P1：模板源头与渲染实现不一致；修法是模板正文仅写中文人读字段，机器字段只作为本地 meta / trade_plans / monitor_levels 的结构化落盘说明。

### 8. "锁定" = git commit + push，不是文件存盘

棠溪说"锁定"意味着**代码必须进入 git 历史且推到远端**。`??` (untracked) 或 ` M` (unstaged) 的文件随时可能被 `git reset --hard` 丢失。审计后修复了大量代码但未 commit → 用户说"没有生效" → 不是因为逻辑错，是因为文件不在 git 里。

审计收尾必须：
```bash
git status --short          # 确认所有关键文件是 M 或 A
git add <所有改动>
git commit -m "lock: ..."
git push origin main
```

### XAU 风控字段陷阱：source spread ≠ 24h volatility

- **Never pass `price_spread_pct` into `check_constitution(..., volatility_24h_pct=...)`.** `price_spread_pct` is a cross-source data-quality spread expressed as a percent value (e.g. `0.6` means 0.6%), while `risk_constitution` expects 24h volatility as a decimal ratio (e.g. `0.01` means 1%).
- Symptom: trade events show impossible risk text such as `24h波动 47.4% ≥ 1% XAU波动禁做` even though the value came from source spread.
- Audit check: inspect `行情守望.py` call to `check_constitution`; if it uses `snapshot.get("price_spread_pct")`, flag P0 because XAUUSD can be falsely forbidden.
- Fix pattern: keep separate fields:
  - `source_spread_pct` / `price_spread_pct` → data quality only
  - `volatility_24h_pct` → real 24h move or ATR/BB-width-derived volatility converted to decimal ratio
  - if true volatility is unavailable, pass `0` or a clearly named fallback; do not substitute source spread.

### XAUUSD Binance blind fallback (P1 · 无效请求浪费)

- **症状**: `monitor.log` 反复出现 `价格错误 XAUUSD: 400 Client Error: Bad Request for url: https://api.binance.com/api/v3/ticker/price?symbol=XAUUSD`
- **根因**: `scripts/行情守望.py` 的 `get_price()` 先调 `ts.template_price()`，异常后**无差别回退**到 Binance API。XAUUSD 不在 Binance 上，每次循环一个冗余 400。
- **修法**: 加硬守卫（if "XAU" in symu or not s.endswith("USDT"): early return template_price or None）。**绝不让非USDT/XAU对进入任何 binance_* price 调用**。
- **2026-06-19 已实施并验证**：
  - 同时修三处：`scripts/行情守望.py:get_price()` 顶部、`scripts/system_data_bridge.py:_price()`、`scripts/trading_system.py:binance_spot_price()`。
  - 验证命令：`python -c "from scripts.行情守望 import get_price; print(repr(get_price('XAUUSD')))"` → None（守卫命中，无400）。
  - 同时 `find . -type d -name __pycache__ -exec rm -rf {} +` 清理缓存。
  - 杀旧进程后 watchdog 重启，确认新进程无 XAU 400 日志。
  - **铁律**：任何价格路径变更后，必须用 python -c 直调验证守卫 + 观察 monitor.log 10min + 刷新 source_snapshot 质量。
  - 完整可复用验证 bundle 见 `references/2026-06-19-fix-verification-bundle.md`。
- **审计检查**: `grep -n "价格错误.*400.*XAUUSD" data/monitor.log`（旧日志可存在，新进程必须无）；`grep -n "XAU" scripts/行情守望.py scripts/system_data_bridge.py scripts/trading_system.py` 确认守卫存在。

**价格守卫模式（可复用）**：对任何非标准USDT现货/期货品种（XAU、指数、股票等），在所有 price() 入口最早位置做符号类型守卫，优先 template/专用源，绝对阻断 Binance ticker 调用。

**2026-06-21 审计更新**：get_price + system_data_bridge 守卫已到位，但 indicator_feed.py、trading_system 等 kline 收集器仍可能对 XAU 发起 binance 调用导致 400。审计时必须额外执行 `grep -rn "XAU" --include="*.py" scripts/ hermes/scripts/ | grep -E "(kline|klines|binance_)"` 并在所有收集路径加同类守卫。验证 bundle 必须包含 kline 路径测试 + 观察 monitor.log 无新 400。

### XAU 操作段单位/杠杆污染（P1）
- **症状**: XAUUSD 分析卡操作段出现 `仓位：... BTC` 或 `风控：100x` / 旧 `Exness 1000x`。
- **根因**: `auto_card.py` 操作段硬编码 BTC 单位和 Binance 100x，或旧经纪商名残留于 _leverage_text()，没有按 symbol 映射。监控警报的 display_symbol 也可能不同步。
- **修法**: 渲染前按品种生成 `leverage_text` 与 `qty_unit`。XAU 品种行用 TradingView（截图驱动），杠杆用 OANDA 1000x（用户常用经纪商）。**必须同时 patch** 行情守望.py display_symbol、auto_card.py 两处 + master-template 示例 + multi_symbol_templates。用户提供“品种已截图”时，按截图精确字符串更新品种平台名。
- **验证**: `python hermes/scripts/auto_card.py XAUUSD` 后 grep `风控：`/`品种：`，确认 `TradingView`（品种）+ `OANDA 1000x`（风控）；同时 python -c "from scripts.行情守望 import display_symbol; print(display_symbol('XAUUSD'))" 验证短卡一致。
- **审计铁律**: 任何平台名/经纪商名变更或用户截图反馈都视为模板合规 P0，必须全路径批量修复并验证。品种行平台（TradingView）和风控经纪商（OANDA）是分离的。

### Equity tracking audit (P1 · 净值口径不一致）

### Equity tracking audit (P1 · 净值口径不一致)

- **症状**: `data/equity_curve.json` 显示 `current_balance: 100`，但 `mcp_binance_get_account_summary()` 返回 `futures_total_wallet: 67.52`。差值 $32.5 无人追踪。
- **根因**: `equity_curve.json` 是本地快照，不自动同步 Binance 实盘钱包。上次更新可能已过时。
- **审计步骤**: 
  1. `cat data/equity_curve.json` 读本地快照
  2. `mcp_binance_get_account_summary()` 读实盘钱包
  3. 比对差值 → 标注为 P1（净值失准）或 P2（最近无交易可忽略）
- **注意**: 差值也可能是初始入金并非 $100 导致。equity_curve 初始值应与首笔入金对齐。
- 详见 `references/equity-tracking-audit.md`

### XAU 周末休市门控缺失（P1 · 周末误报警）

- **症状**: 黄金（XAUUSD）在周末（市场闭市）仍持续触发 Telegram 警报/分析卡，明明没有真实行情。
- **根因**: `scripts/session_filter.py` 的 `get_active_sessions` **只按 UTC 小时判定时段**（hour 12 → "ny" 等），**从不检查星期几**。黄金真实休市窗口（周五 21:00 UTC 收盘 → 周日 22:00 UTC 开盘）完全缺失，于是周末任意小时仍被映射到某个活跃时段。
- **审计检查**: `grep -n "weekday\|weekend\|closed" scripts/session_filter.py` — 若 `get_active_sessions` 内只有 `hour` 判断、无 `weekday()` 分支，标 P1。
- **修法（最小触点）**: 新增 `is_weekend_closed()`（周六全天 closed · 周五 hour≥21 UTC closed · 周日 hour<22 UTC closed），在 `get_active_sessions` 的 XAU 分支后、时段循环前调用，命中则直接 `return ["closed"]`。
  - **放在 `get_active_sessions` 而非 `should_trade`**：所有下游（`should_trade` / `is_gold_trading_time` / `session_status`）自动继承，单点修复。
  - **BTC 显式排除**：加密 24/7 不受门控影响（守卫仅作用于 XAU / 非 USDT 永续）。
  - UTC 为基准（对齐文件既有约定，本地时区只用于显示）。
- **验证**: `python -c` 打多个 UTC 时点：周六14:00→closed · 周五20:00→ny · 周五21:30→closed · 周日18:00→closed · 周一13:00→london/ny/overlap · BTC周六14:00→24/7。再 `should_trade("XAUUSD")` 周末应返回 `False` 原因="闭市/低流动性时段"。
- **通用教训**: 任何对周末/节假日休市品种的时段门控，**只判 hour 不判 weekday 是典型漏洞**。实时测试要等到对应周末才能复现，所以靠 UTC 时点单测覆盖周五晚/周六/周日早三个边界。
- **遗留**: GOLD_SESSIONS 在 22:00–24:00 UTC 有时段空洞（无 session 分配），周日 22:00 后那一小段仍显示 closed —— 这是既有设计非本修引入，低流动性时段通常不交易，可忽略。

### 卡片改版后残留旧格式历史摘要（P2 · 排查误导陷阱）

- **症状**: 用户报告卡片里有某个字样（如 `品种：XAUUSD · 交易所：EXNESS` 带"交易所："前缀），但 grep 整个源码库找不到这个字符串。
- **根因**: 卡片格式改版（如去掉"交易所："前缀、精简排版）后，**当前渲染器已经不再产生旧字样**，但有两处历史残留会让旧格式继续出现：
  1. **Telegram 聊天记录**：改版前推送的旧卡停留在频道历史里，Telegram 不会回溯改写已发消息。用户翻到旧卡 → 以为代码还在产生旧格式。
  2. **`data/trade_plans.jsonl` 的 `card_excerpt` 字段**：每张卡生成时 `auto_card.py` 把 `card[:500]` 摘要落盘。改版前的记录里冻结着旧格式文本。
- **排查顺序（任何"代码里搜不到但卡片有"的字样必走）**:
  1. 先搜源码：`LC_ALL=C grep -rn "目标字样" --include="*.py" .` — 搜不到说明不是当前代码产生。
  2. 再搜数据/产物：`LC_ALL=C grep -rln "目标字样" . | grep -v /.git/` — 定位到 `trade_plans.jsonl` / 落盘 .md / 日志。
  3. 看时间戳确认是改版前的历史记录：解析 `card_excerpt` 的 `◷` 时间或记录 `created_at`，对比渲染器改动时间。改版后的新记录应已是新格式。
  4. 确认当前渲染器输出：重新生成卡片，grep 品种行，确认新格式。
- **修法**: 历史 `card_excerpt` 是日志快照，不影响未来推送。如需保持日志干净，就地替换字符串而非删整条记录（保留所有结构化字段）：
  ```python
  import json, shutil
  from pathlib import Path
  p = Path("data/trade_plans.jsonl"); shutil.copy(p, p.with_suffix(".jsonl.bak"))
  out = []
  for line in p.read_text(encoding="utf-8").splitlines():
      if not line.strip(): continue
      r = json.loads(line)
      ex = r.get("card_excerpt")
      if isinstance(ex, str) and "交易所：" in ex:  # 替换成实际旧字样
          r["card_excerpt"] = ex.replace(" · 交易所：", " · ").replace("· 交易所：", "· ").replace("交易所：", "")
      out.append(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
  p.write_text("\n".join(out) + "\n", encoding="utf-8")
  ```
  验证：`LC_ALL=C grep -c "旧字样" data/trade_plans.jsonl` → 0。确认无残留后删备份（`trade_plans.jsonl` 被 .gitignore，历史日志不入库）。
- **通用教训**: 卡片/消息格式改版后，"代码改对了"只是第一步。必须同时确认三处：① 当前渲染器输出 ② 已落盘的产物/日志快照（trade_plans.jsonl card_excerpt、auto_card_*.md）③ 已推送的历史消息（无法回改，向用户说明是历史残留）。源码 grep 搜不到某字样时，第一反应是查数据/日志快照，而不是怀疑自己漏看了代码。

### XAU spot/futures basis scoring pitfall

- Yahoo `GC=F` / `MGC=F` are futures proxies and often differ systematically from spot. Do not let them dominate spot consensus for XAUUSD.
- Preferred scoring:
  - Spot primary: `金十Quote + gold-api.com + OANDA` when available.
  - Without OANDA: cap at `A-`/`88` or `B+`, even if 金十 and gold-api agree.
  - Treat Yahoo futures as a separate `basis` context, not as equal spot-price voters.
- If `price_spread_pct > 0.5` but the spread is caused by GC/MGC basis while 金十 and gold-api agree, mark data as "spot一致 · futures basis偏离" rather than a clean `A92`.

### Watchdog restart-limit visibility

- If `watchdog.log` contains repeated `重启速率限制：3次/小时已达上限`, flag P1 unless a push alert is already emitted.
See `references/auto-card-monitor-review-traceability.md` for the full production pattern that propagates `setup_id/model_id/entry_tag/exit_tag` from auto-card generation through monitor trigger events into `trade_reviews.jsonl` for model statistics.
See `references/auto-card-plan-direction-consistency.md` for the B等待 operation-section pitfall: A/B plans can be complete but direction, stop, targets, and failure text can diverge unless A uses normalized primary bias and B uses the opposite bias throughout.
See `references/xau-risk-data-quality-2026-06-18.md` for the XAU-specific source-spread vs volatility and spot/futures basis pitfalls.
See `references/provider-proxy-and-process-hygiene.md` for the "时好时坏" provider diagnostic (proxy NO_PROXY routing for 国内中转 vs GFW-blocked endpoints), duplicate-MCP-process detection/cleanup, and Chinese cron-naming.
See `references/proven-fix-patterns.md` for the six reusable fix patterns proven in 2026-06 audit-to-fix sessions: (1) process-tree diagnosis; (2) closed-loop field-mismatch; (3) triple-barrier auto-labeling; (4) Telegram Bot API direct push; (5) ATR-scaled adaptive position; (6) CVD aggTrades A-grade upgrade.
See `references/git-untracked-diagnostic.md` for the "改动没生效" git diagnostics (untracked files, duplicate paths, stale processes).
See `references/custom-provider-debugging.md` for systematic custom provider troubleshooting (base_url path, UA, api_mode, proxy, SDK-level reproduction).
See `references/final-audit-2026-06-19.md` for the final full-system audit runbook: v6.9 header order, XAU snapshot refresh pitfall, watchdog stale-noise interpretation, daily-validation cron wrapper verification, and risk-gate interpretation.
See `references/audit-closure-runtime-sync-2026-06-19.md` for the audit-fix closure checklist: sync repo fixes to AppData no-agent runtime copies, force cron green-state runs, verify XAU snapshots/heartbeat/test results, and commit+push before claiming fixed.
See `references/alert-threshold-design.md` for the community-confirmed design principle (confirmation gate pattern, SNR-based tiering).
See `references/equity-tracking-audit.md` for the equity-curve-vs-wallet sync check: diagnosing stale local snapshots, Binance wallet cross-reference, and initial-balance alignment.
See `references/runtime-connectivity-recovery.md` for runtime repair patterns proven during audit closure: Binance REST retry wrappers, Windows MSIX TradingView CDP launch, monitor-core restoration, and closure verification bundle.
See `references/v6.9.3-multi-asset-template-runtime-audit.md` for the comprehensive v6.9.3 pattern: audit live runtime first, review both analysis-card and monitor-card renderers, simplify non-operation sections, keep multi-asset operation plans detailed, verify auto-updated levels, recover watchdog/heartbeat, run full bundle, then commit+push when locking.

## Auto-card → Monitor → Review Traceability

When optimizing the analysis-card pipeline, verify that machine-readable setup fields are not trapped inside the rendered markdown card.

Required propagation chain:
1. `auto_card.py` generates `setup_id`, `model_id`, `entry_tag`, `exit_tag`, direction/status/confidence/risk fields.
2. The card appends a `机器字段` block after template sanitization.
3. The same metadata is appended to `trade_plans.jsonl`.
4. The same metadata is written to `monitor_levels.json -> symbols.<symbol>.latest_setup`.
5. `行情守望.py` enriches monitor events from `latest_setup` before writing events/logging to `trading_system`.
6. Review/statistics code can then group by model/setup/entry tag instead of only by price level.

Pitfall: implementing only steps 1–3 creates a "pretty but untraceable" card. The monitor must inherit setup metadata at trigger time, including `trigger_kind`, `trigger_price`, `trigger_level`, `trigger_levels`, and `setup_trace`.

TDD expectations for this class of change:
- Add RED tests for card metadata generation and render.
- Add RED tests for template guards (`B等待` cannot output concrete entry prices; `R:R < 1:2` must be flagged).
- Add RED tests that monitor events inherit `latest_setup` fields and that legacy/manual plans without `latest_setup` remain compatible.
- Verify with `py_compile` plus focused pytest and full pytest.


When new modules are integrated from GitHub projects, audit them separately
before declaring them "integrated". The verification matrix has five levels:
See `references/github-fusion-pipeline.md` for the full methodology and
`references/fix-patterns-catalog.md` for reusable fix patterns discovered
during audit sessions (heartbeat-at-top, numpy vectorization, Crash-Only
validation, Meta-Labeling gate, configurable drawdown, broad-except
replacement, unified logging, test coverage, profit_factor null).

```
代码存在    逻辑正确    实弹跑通    已接入管线    产生交易信号
   ✅         ✅         ❌          ❌            ❌  ← 花架子
   ✅         ✅         ✅          ❌            ✅  ← 半成品
   ✅         ✅         ✅          ✅            ✅  ← 真正有用
```

### Verification Steps

1. **代码存在** — file exists, imports succeed, no syntax errors
2. **逻辑正确** — run with demo/test data, output makes sense
3. **实弹跑通** — feed REAL Binance/TradingView data (not demo values), verify output
4. **已接入管线** — called by existing pipeline scripts (行情守望/auto_card/智能更新结构)
5. **产生交易信号** — output flows into monitor_levels.json or trade_plans.jsonl

### Common Integration Failures

- **SMC library read-only bug**: `SmartMoneyConcepts` monkey-patches a DataFrame
  that pandas returns as read-only. Error: `assignment destination is read-only`.
  Workaround: Use `df.copy()` before injection. Requires ≥50 bars for structure
  detection; 5-bar test always returns 0 results.
- **yfinance dependency**: SMC fetches data via yfinance internally.
  For Binance crypto data, inject a pre-built DataFrame directly.
- **Freqtrade needs Docker**: `pip install freqtrade` may hang or fail.
  The Docker approach (`docker run freqtradeorg/freqtrade:stable backtesting`)
  is more reliable but requires Docker Desktop.
- **Module not connected to pipeline**: Most integration modules produce correct
  output when tested standalone, but `行情守望.py`/`auto_card.py`/`智能更新结构.py`
  still use old hardcoded logic. The integration step (connecting module output
  to pipeline input) is the hardest and most frequently skipped.

## Follow-up Audit（复查审计）

When re-auditing after a previous fix session:

1. **Verify previous P0 fixes first** — don't re-discover them
   - Check `monitor.log` for old error patterns that should be gone
   - Verify process start time vs file modification time
   - Re-test endpoints that previously failed
2. **Trend key metrics** against last audit
3. **Check for new P0s** that emerged since last fix cycle
4. **Run full post-fix verification bundle** (2026-06-19 实战闭环，必须执行，不能跳过)：
   ```bash
   # 价格守卫验证（XAU 绝不 400）
   python -c "from scripts.行情守望 import get_price; print('XAU:', repr(get_price('XAUUSD'))); print('BTC:', get_price('BTCUSDT'))"

   # 清理缓存 + 卡片再生 + 合规扫描
   find . -type d -name __pycache__ -exec rm -rf {} +
   python scripts/auto_card.py BTCUSDT
   python scripts/auto_card.py XAUUSD
   # 检查：0 machine leaks + 头部10段 + 正文5段完整
   grep -E "setup_id|model_id|entry_tag|exit_tag" data/auto_card_*.md || echo "0 leaks OK"

   # 快照质量
   python -c '
   import json
   for s in ["BTCUSDT", "XAUUSD"]:
       d = json.load(open(f"data/source_snapshot_{s}.json"))
       print(s, d.get("quality"), d.get("confidence_label"))
   '

   # 心跳 & 进程
   cat data/monitor_heartbeat.json
   tasklist //FI "IMAGENAME eq python.exe" //V //FO CSV | grep -E "行情守望|watchdog"

   # Git 锁定（棠溪 "锁定" 定义）
   git status --short
   git add -A
   git commit -m "fix: ..."
   git push origin main
   ```
5. **确认**：新进程无历史错误、卡片合规（0泄漏）、快照质量 A/A-、变更已进入 git 历史并推远端。

**Run auto_card pipeline** if no fresh executable plans exist (as part of the bundle above).

**Audit closure iron law**: 只有当上面 bundle 全部真实执行并输出预期结果后，才能在报告中说“已修复 / 合规”。描述性修复不算。

## 2026-06-20 综合审计执行模式（本轮新增）

**铁律第一步：先验明运行态（不要假设配置）**

审计任何系统前，必须先用实测数据建立当前真实状态：
- mcp_binance_* + mcp_tradingview_tv_health_check 直接调用
- read_file data/monitor_heartbeat.json + data/source_snapshot_*.json + monitor.log (tail)
- hermes cron list + 实际 last_status
- tasklist / git status / ps 交叉验证进程
- 只有在实测后才读 config / jobs.json / 记忆

**验证 bundle 不可跳过（每次变更后必须全跑）**

任何涉及行情守望、auto_card、价格桥、cron、预测验证的改动后，必须执行：
1. 读模板：read_file references/master-template-v68.md（确认当前 v6.9 底板）
2. 再生卡：python scripts/auto_card.py BTCUSDT && python scripts/auto_card.py XAUUSD
3. 零泄漏扫描：grep -E "(setup_id|model_id|entry_tag|exit_tag|critical|warning|info)" data/auto_card_*.md
4. pytest 全量（或至少 test_auto_card_* + test_push_*）
5. 价格守卫实测（XAU 必须无 400，质量 A/B）
6. 心跳/进程/日志确认新进程无旧错误模式
7. git status --short → commit + push（棠溪“锁定”定义）

**本轮发现的可复用 P0 模式**

- Cron “持仓与信号”脚本路径漂移（Windows）：hermes cron 解析 %LOCALAPPDATA%/hermes/scripts/，即使 --workdir 指向 repo。根治用 Junction（CreateSymbolicLinkW）或 wrapper。修后必须 hermes cron run 验证 last_status=ok 且脚本真实存在。快速冗余：显式 cp 关键脚本到 AppData 目录 + recreate。
- XAUUSD 价格守卫必须绝对（绝不 fallback Binance）：在 get_price / system_data_bridge / trading_system 最早位置加 `if "XAU" in sym or not sym.endswith("USDT")` 直接走 gold-api+金十。任何遗漏都会产生持续 400 拖垮循环。验证：python -c "from scripts.行情守望 import get_price; print(repr(get_price('XAUUSD')))" → None。
- 预测胜率 99%+ 一定是 trivial move 计入：verify 时只计 >0.5% 或 0.5x ATR 的已完成 bar；用 triple_barrier / meta_labeler 真实标签；清旧 log 重积累（本轮清至 2 行新鲜）。胜率日志降频。

**“一起修复了”批量执行偏好（嵌入工作流）**：
用户说“一起修复了”时，立即将全部已识别 P0 批量处理 + 完整验证 bundle + git 锁定（通常 1-2 个 commit）。不分步等待用户确认每个修复。执行后必须报告真实工具输出（守卫测试结果、0 leaks、日志行数、cron 状态、git clean）。本轮执行了 XAU 守卫 + 预测阈值+清空 + cron 重建+拷贝 + pyc + 测试 + 卡片扫描 + 2 commits + push + kill stale PID。

**社区融合审查模式**

审计时必须联网拉：
- x_search + web_search 拉 CVD / ICT / Volume Profile / Freqtrade 最新共识（2026）
- 重点提取"只有锚定结构才有效""吸收/背离""MTF top-down"
- 映射到 scoring_engine / five_model_matcher / regime_classifier / 博弈段
- 同时 read_file master-template-v68.md 确认当前格式铁律
- 在报告中单独一节"分析监控策略 & 模板审查" + "应接入什么还差什么"

**代理判别铁律（2026-06-21 新增）**：
当用户说"我说不一定对，你要有判别能力"时：
1. 主动联网（不等指令）
2. 三方交叉验证（≥2独立源）
3. 诚实指出差距（不默认用户正确）
4. 社区标准 > 个人偏好
5. 提修复后立即执行，不确认

- `references/v6.9.13-community-standard-alignment.md` — 社区标准对齐完整记录（止损哲学、时间止损、分批止盈、日周限收紧）

**v6.9.1 模板增强具体流程（本轮实战）**：
1. 社区研究后识别 gap（liquidity sweep + CVD divergence anchoring, XAU Kill Zone, BTC spot/perp CVD, Naked POC）。
2. read_file("references/master-template-v68.md") 加载最新。
3. patch 5 处（环境⑪时段、结构 Naked POC+扫荡、博弈③子项拆分、5m扫荡确认、模型清单补充）。
4. 验证：python -c 检查关键短语（流动性扫荡、现货vs永续、时段（XAU优先）、Naked POC、扫荡确认）全 True。
5. 再生卡 + 0 leaks 扫描 + git commit + push。
6. 更新本技能 + 新 references/v6.9.1-community-template-enhancements.md 记录 deltas + 验证命令 + 社区 rationale。

- `references/v6.9.1-community-template-enhancements.md` (prior community template notes)
- Cross-reference: `tradingview-indicator-analysis/references/community-2026-ict-smc-cvd-fusion.md` for 2026 fusion (Liquidity Sweep soul, XAU Kill Zone sequences, CVD divergence + Displacement anchoring, real 50-65% backtest rates) derived via web-access + x_search in audit+optimization sessions.

详细可复用模式与命令见 `references/2026-06-20-comprehensive-audit-patterns.md`。

**报告结构铁律**

P0（立即修复，系统不可见/不可信）→ P1（本周）→ P2（优化）
每条：问题 → 证据（具体命令/文件/日志片段）→ 影响 → 修法（含验证命令）
最后附“验证 bundle 执行结果”。

此模式已在 2026-06-20 全面审计中完整走通并产出 actionable 结果。

## v6.9.13 社区标准对齐 + 代理人判别（2026-06-21 本轮新增）

**触发信号**：用户说"联网社区建议，我说的不一定对，你要有判别能力"。

**代理判别铁律**：
1. 主动联网搜索社区标准（不被动等指令）
2. 三方交叉验证（至少两个独立源：Tradeciety/CrossTrade/X专业社区）
3. 诚实指出差距（不因"用户说了"而默认正确）
4. 社区标准优先于个人偏好
5. 提出修复后立即执行，不分步确认

**本轮落地（三条P0/P1修复）**：
| 改 | 之前 | 之后 | 依据 |
|----|------|------|------|
| 日回撤 | 10% | 3% | 社区2-3%标准 |
| 周回撤 | 15% | 6% | 社区5-6%标准 |
| 时间止损 | 无 | 第4根减半·第6根全平 | CrossTrade 3-5 candle rule |
| 分批止盈 | 无 | +1.5R出一半→移损保本 | X社区 scale-out |

**社区源**：
- Tradeciety: 多周期top-down方法论
- CrossTrade: 止损哲学 "Stops are where this trade is wrong, not how much you're willing to lose"
- X专业社区: BTC系统架构 + 日周限标准 + 分批止盈

**已对齐项（社区验证✅）**：ATR×2+结构锚定止损、止损先于仓位、4h继承偏向、R:R≥1:2、CVD+Taker+Funding三维验证

完整记录见 `references/v6.9.13-community-standard-alignment.md`

## v6.9.12 三层架构（高周期继承+低周期触发+催化剂验证）

**架构**：
1. **高周期继承**: `_primary_plan_bias()` 接受 k4h_direction — 4h偏空时引擎中性也优先空
2. **低周期实时**: 极简卡新增 "5m扫荡 · 15m描述 — 低周期触发" 行
3. **催化剂验证**: Grok/搜索定位从"信号确认"改为"催化剂已验证"+"市场热点"，不做信号源

## v7.3 日内止损止盈算法（对手方流动性池后方·社区2026共识）

**核心函数**: `_calc_stop_target_atr(price, direction, klines, symbol, atr_mult=2.0) → {stop, target, rr, stop_reason, target_reason, atr}`

**v7.3规则**：
- ATR×2 夹层（日内 1.5-2.5×）+ 0.5×ATR 对手方流动性池缓冲
- 收集三周期结构位（VAH/VWAP/POC/VAL/high/low/EMA）
- 0.3%以内视为噪音跳过
- Short止损 = max(p+ATR距离, 最近阻力+0.5×ATR缓冲) — 止损在猎杀区后方
- Long止损 = min(p-ATR距离, 最近支撑-0.5×ATR缓冲)
- 止盈 = 最近顺向结构位
- R:R不足标注⚠而非伪造数字
- 极简卡+完整卡+AB预案共用

**哲学转变**：棠溪是"人控交易系统"——系统是决策驾驶舱，他是最终踩油门的人。不是自动交易，是决策支持。

**核心设计**：
- **极简决策卡**（8-9行）：价格锚定关键位时输出，只含：品种+模型+方向+现价+最亲关键位+CVD/Taker/Funding+双预案(独立R:R计算)+社区共识(F&G标签)+风控底线+决策提示
- **完整分析卡**（78行）：始终输出完整的⑩段头+五段正文，保存在 `auto_card_{symbol}_full.md`
- 双卡同时生成：`render_card_locked(symbol, ..., force_full=True)` 生成完整卡，`force_full=False` 自动判断极简/完整
- 用户先看极简卡做决策，需要深挖时看完整卡

**极简卡铁律**：
- B等待 / X禁做 + 价格锚定关键位（≤0.4%距离）→ 自动切换到极简模式
- 两条预案：破位方向 + 守位方向，每条独立计算 `rr = abs(tp-p)/abs(stop-p)` 并显示 `R:R 1:X.X`
- 社区共识标签：`F&G {value}{classification}` 从 fg dict 提取，周末标记 `⚠周末`
- 末行固定：卡片末尾自然收尾，不追加决策提示行（"你来选方向"已删除·v7.5b）
- 仅当 `_find_nearest_key_level()` 找到关键位且 `_near_key_level()` 检查通过时才触发

**Cron 监控恢复三件套**：
- `hermes/cron/positions_monitor.yaml`：每5分钟 · no_agent · `monitor_positions.py` — 检查价格告警+Protections状态+新信号
- `hermes/cron/cleanup_daemon.yaml`：每6小时 · no_agent · `cleanup_daemon.py` — 清理7天前旧卡+30天前过期日志+Protections状态
- `hermes/cron/daily_maintenance.yaml`：每天3:20 · no_agent · `daily_maintenance.py` — 日度快照+本周PnL统计+周度宪法限制告警(≥10U)
- 全部 YAML 格式，`no_agent: true`，零 token 消耗

**TV 指标交叉验证审计步骤（2026-06-21 新增·P1潜在大坑）**：
审计时必须执行 TV `data_get_study_values()` → 对比 `auto_card` 产出的值：
- **VAL 不一致检测**：TV SVP 计算的 VAL 可能与 auto_card 从 K线计算的 VAL 差 200+ 点。TV 是棠溪主源 → TV 值为准
- **XAU 失效线异常检测**：自动卡 XAU 的 4h 失效线若为 4,292（当前金价 4,157）→ 数据来自 Yahoo GC=F 期货的跨期异常价，需降权或跳过
- **CVD 恶化检测**：两次读 TV CVD 值（间隔 10+ 分钟），斜率变化 >50% 说明卖压加速/减速 → 写入极简卡的 Taker 方向冲突检测
- **EMA 排列实况**：TV EMA 9/21/34/55 值 vs 价格位置 → 快速判定多头/空头排列是否还在

**可复用代码模式**：
1. `_compact_card()` → 8行极简输出（含独立R:R计算+社区F&G标签+周末检测）
2. `_find_nearest_key_level()` → 三周期(15m/1h/4h)扫描 VAH/VAL/POC/VWAP/高低 → 返回最近关键位
3. `render_card_locked(force_full=True/False)` → 双卡模式控制参数
4. 双卡文件分离：`.md`=极简或完整 · `_full.md`=始终完整
5. `auto_card()` 主流程：force_full=True 跑一次 → 存 `_full.md` → force_full=False 跑一次 → 存 `.md`
6. 验证 bundle：pytest 98/98 + 双卡文件存在 + 极简<12行 + 完整>50行 + grep 0 机器字段泄漏

**P1 潜在大坑**：TV VAL ≠ auto_card VAL（265点差异 2026-06-21 实测）。TV SVP 指标用 session 内 tick 数据算 VAL，auto_card 用 K 线 OHLC 算。棠溪以 TV 为价格主源 → TV 的 VAL 是权威值。若 auto_card 的 VAL 偏了 265 点，整个价值区判断（回收/突破/拒绝）全错。审计时必须交叉验证。

新增支持文件：`references/v6.9.10-decision-cockpit-dual-card.md` · `references/v6.9.13-community-standard-alignment.md`

## v2.0 六大社区联网审计方法论（2026-06-21 本轮新增）

**触发信号**：用户说"联网社区，多个社区，那些重要的社区全面的进行看一遍，提取精华，审计我们的系统，来一次完完全全的审计"

**六源矩阵**（必须全量并行搜索）：
| 源 | 搜索方向 | 工具 |
|-----|---------|------|
| **Freqtrade + X** | 策略优化/WFO/Protections/仓位/止损 | `web_search` + `x_search` |
| **Reddit r/algotrading** | 散户实战教训/过拟合/风险管理 | `web_search` + `web_extract` |
| **X/Twitter (ICT/SMC)** | 2026最新SMC/ICT实战共识 | `x_search` |
| **NautilusTrader** | 架构/pre-trade风险检查 | `web_search` |
| **Bookmap** | CVD/冰山水/吸收/订单流 | `web_search` + `web_extract` |
| **TradingView Pine v6** | 新API/footprint/多TF | `web_search` + `web_extract` |

**审计流程**（四步铁律）：
1. **并行联网**：6源同时搜索，每条返回至少3-5个结果
2. **提取共识表**：25条社区共识 → 逐条对照棠溪系统 → 标记 🟢已对齐 / 🟡差距 / 🔴缺失
3. **差距分析**：P1=战略缺口（Freqtrade Protections/ATR止损/仓位缩放）· P2=增强方向（Bookmap冰山水/相关性矩阵/渐进上线）
4. **全量执行**：用户说"全量执行"立即批量修复全部P1 → 实测 → pytest → git commit+push

**本轮实战落地（v2.0风险宪法 + Protections + ATR夹层）**：

| 模块 | 变更 | 社区源 |
|------|------|--------|
| `risk_constitution.py` v2.0 | MAX_RISK 3%→1% · KELLY 0.25→0.20 · ATR上限2.5× · Protections类 | X/Reddit 1%标准+Freqtrade+NautilusTrader |
| `hard_stop.py` v2.0 | position_size ATR夹层(0.5×∼2.5×) | Freqtrade ATR trailing stop |
| `readiness_report.py` 新 | 8维48h就绪报告 | Freqtrade 48h readiness |
| `行情守望.py` | Protections接入apply_risk_constitution | Freqtrade Protections |
| `auto_card.py` | Protections状态注入meta | 社区共识 |
| `position_sizer.py` v2.0 | 删除硬编码DEFAULT_ACCOUNT·对接宪法自适应 | X/Reddit fixed fractional |

**可复用代码模式**：
- `Protections.check_all(symbol, current_bar)` → StoplossGuard(12根)+Cooldown(3根)+MaxDrawdown(10%/15%)
- `adaptive_risk_usd(balance, atr_pct)` → 波动率自适应风险金额
- `position_size(atr_value=...)` → ATR夹层止损自动修正

**验证铁律**：pytest 98/98 + Protections持久化实测 + ATR夹层4场景 + readiness_report产出 → git commit+push

新增支持文件：`references/community-audit-methodology-2026.md`（25条共识表+差距映射+落地代码）


**Execution Closed-Loop & Governance Feedback (Phase 2, this session)**
The audit and optimization workflow now encompasses the full execution layer: use `成交记录.py` + `成交复盘.py` as the canonical closed-loop mechanism (drives risk_state + trade_reviews.jsonl), enhanced `策略治理.py` (aggregates reviews for samples/avg_r/win_rate + conditional weight adjustment), and extended `日间维护.py` (daily validation + governance automation). Bootstrap with sim trades (`*-sim*` plan-ids) to reach meaningful sample counts (≥20 per model). CVD A-grade pipeline (BTC) and XAU alternatives are integrated. 

**Mandatory**: After any changes in this layer, execute the extended verification bundle including sim record→review flow, governance refresh check, risk_state validation, 0-leak card regeneration, pytest, and git commit+push. 

**最新社区共识核对**: `references/community-gap-analysis-2026-06-21.md` — 13项共识·10已对齐·3差距·3缺失·13项系统缺陷。包含悬挂cron配置/klines泄漏/重启风暴分析的坑点。

### TV Desktop 缺失时的 Cron Agent 回退模式

当 cron agent 启动且 TV Desktop 未安装时，MCP tradingview 工具全部不可用。完整回退流程（诊断步骤、数据源、推送判定铁律、cache 写入格式）见 `references/tv-desktop-missing-fallback.md`。

**核心铁律**：
- monitor（行情守望.py）独立运行，**不依赖 TV Desktop** — 它通过 HTTP/API 获取数据
- cron agent 回退路径**永不触发 A/B 级推送** — 无 TV 实时数据 = 信号不可信
- 每次 cron 执行后必须写入 `tv_dmi_cache.json`（含错误状态 + 保留上次有效快照）

### TV DMI 死代码路径（P0 · 2026-06-21 实案）


### TV 信号实时推送架构（v7.2 · TV CLI直连 · 零token常驻）

**v7.2 架构**: 不再用cron→agent→TV MCP间接管道。行情守望.py每5分钟通过 `subprocess` 调用 `tv_data_bridge.py`，该脚本通过TV CLI (`tv values` / `tv data tables` / `tv data lines` / `tv quote`) 直读TV数据，写缓存。零stdout，零token。

```
行情守望.py (10s循环·零token)
    │ 每5分钟
    ▼
tv_data_bridge.py (subprocess·静默)
    │ tv values / tv data tables / tv data lines / tv quote
    ▼
tv_dmi_cache.json
    │
    ▼
_check_tv_grade_change(state)
    ├─ 仅A多/A空/X → 触发推送 (v7.2: B/C静默)
    ├─ A → async subprocess.Popen(auto_card) + 通知
    └─ 无变化 → 静默
```

**置信度铁律（v7.2）**: 仅A多/A空/X等级变化触发推送。B多/B空和C等待一律静默。用户要求"置信度高的才会警报"。

**tv_data_bridge.py** (182行): `tv_available()` 检查CDP连接 · `read_indicators()` VWAP/EMA/CVD/POC/V/H · `read_dmi_table()` DMI决策表 · `read_pine_lines()` 12关键位 · `read_quote()` 实时报价 · `collect_and_cache()` 全量采集写缓存。

**TV CLI路径**: `tools/tradingview-mcp/src/cli/index.js` — 命令行工具，支持 `tv values` `tv data tables` `tv data lines` `tv quote` `tv status` 等子命令。

**症状**: 卡片从不显示 TV DMI 等级（`TV:C等待`），尽管 v6.9.14 声称已集成。

**根因**: 三个独立 bug 叠加致全管线虚设 —— 缺一不可独立修复：
1. auto_card 从未读取 TV 数据（`_tv_pine` 无写入方）
2. `_parse_tv_dmi_table` 嵌套级错误（MCP 需拆两层，代码只拆一层）
3. 局部变量 `status` 在 TV 覆盖前捕获，覆盖后不再同步

**检测**: `grep -rn \"_tv_pine\" --include=\"*.py\" .` — 若只有读方无写方 → Bug1。构造 MCP 数据测试解析函数 → 若返回 `{}` → Bug2。检查 status 变量更新时机 → 若在 TV 覆盖前捕获 → Bug3。

**缓存格式漂移**: 三个写入方用三种互不兼容的 JSON 结构。读端必须兼容所有格式（键名回退: `action`/`treatment`, `bias`/`background`, `cvd`/`cvd_state`, 优先 `table_raw`（Pine 原样行））。写端不应重写字段名。检测: `python -c \"import json; c=json.load(open('data/tv_dmi_cache.json')); print(list(c.keys()))\"` → 对比已知格式。详见 `references/tv-dmi-dead-code-path-2026-06-21.md`。

**C等待 不应伪装 B等待**: TV DMI 的 C等待 ≠ B等待。C等待 = 观望/不做，B等待 = 等触发/可做。`_apply_tv_dmi_override` 中 `grade not in (A多/A空/B多/B空/X)` → `meta[\"status\"] = \"C等待\"` 独立状态。不可写死为 `\"B等待\"`。

**v7.2 置信度铁律**: 仅A多/A空/X等级变化触发Telegram推送。_check_tv_grade_change() 中 B多/B空 和 C等待 一律 `return False`。用户明确要求"置信度高的才会警报"。

**v7.5 crash→silence pipeline bug (P0 · 2026-06-22 实案)**: 
When auto_card.py has a syntax/NameError bug (e.g. undefined function `_near_key_level`, undefined variable `qty_unit`), the chain is:
1. Monitor detects expired levels → tries to call auto_card to refresh
2. auto_card crashes with NameError → levels NOT refreshed
3. All levels expire → no alerts can trigger → COMPLETE SILENCE
4. User asks "警报是没有触发了吗？" — root cause is invisible from process/heartbeat

**Iron Rule**: Static scan MUST be followed by live pipeline run — `python auto_card.py BTCUSDT` + `XAUUSD`. Static tools (compile, lint, pytest) CANNOT catch undefined names. Full pattern in `references/crash-silence-pipeline-2026-06-22.md`.

**v7.5b "你来选方向" removal (2026-06-22)**: 棠溪 explicitly asked to remove "—— 你来选方向 ——" from all card/alert output. Removed from auto_card.py (×2) and 行情守望.py (×1). Cards/alert end naturally without appended decision prompt.

**用户信号**: "太难看了，部分英文都看不懂" · "还是有问题，你看看其他的，渲染出问题了"

**渲染审计铁律（5条·已固化到 references/v7.5-card-rendering-standards.md）**:
1. **display_name 优先** — monitor_levels.json 每层有 `display_name`(人读中文) 和 `name`(内部ID)，渲染必须优先前者
2. **禁止双层前缀** — 数据源已含"引擎判"时渲染器不得再加"引擎" → 防止"引擎引擎"
3. **Taker方向中文化** — buy/sell→买/卖
4. **N/A → 中文兜底** — 所有工具函数返回 `待确认` / `—` 代替 `N/A`
5. **禁止硬编码分析** — `_tf_verdict` 等函数基于实际EMA21数据动态生成
6. **Funding/Spot 保持英文** — 用户明确偏好: Funding标签和Spot/美元用英文·Kill Zone中文化·K线指标中文

**关键修复（479d55f·9add52e）**:
- `render_message()`: name→display_name · 引擎去重 · Taker中文化 · `CVD{val}`→`CVD {val}`(空格)
- `_find_nearest_key_level()`: VAH→价值上沿 · VAL→价值下沿 · POC→控制点 · VWAP→量价均值
- `_tf_verdict()`: 硬编码假分析→基于EMA21动态判语
- `_sr_level/_chase_ok/_exec_line`: N/A→待确认/—
- `_compact_card()`: taker_dir双兼容 · Taker N/A→Taker 无
- 4文件添加 `# -*- coding: utf-8 -*-` · print→sys.stderr

**代码质量审计发现**:
- 58处裸except（auto_card.py）→ P1技术负债·关键位置已加固
- Cron CLI uv trampoline故障 → 直接编辑jobs.json绕过
- TV缓存周末空 → 正常·周一自动恢复

**社区对标**: 10+源全对齐。独特优势: TV DMI六合一·中文自然语言卡·零token监控·手机格式v7.1

详见 `references/v7.5-card-rendering-standards.md`

## v7.3 社区审计修复（2026-06-21 · 已完成 00cc113）

v7.2六大社区联网审计发现的三项P1+两项P2已全量实施（用户"p1p2都做"→全量执行）：

1. **P1-1 止损升级→对手方流动性池后方**: `_calc_stop_target_atr()` 结构位 ± 0.5×ATR缓冲 → 止损在猎杀区后方。
2. **P1-2 连亏自动缩仓**: `_consecutive_losses()` 追踪trade_events.jsonl → ≥3笔半仓·≥5笔暂停。
3. **P1-3 余额膨胀守卫**: `MAX_RISK_USD_CAP = INITIAL_BALANCE × 1%` 硬上限。
4. **P2-1 CVD冰山检测**: `analyze_cvd_iceberg()` 碎单方向>65%+价未动→冰山。
5. **P2-2 多资产相关性**: `check_correlation_warning()` BTC+XAU双持警告·Pearson相关48根4h。

六源社区共识: X/ICT · Freqtrade · Reddit · Bookmap · NautilusTrader · TradingView。
101/101 pytest passed。

See `references/v7.3-community-audit-fixes-2026-06-21.md` for full implementation details.

See dedicated support file `references/execution-closed-loop-and-governance.md` (added this phase) for exact commands, evidence (e.g. risk_state trades=1/pnl=2.8/unreviewed=0, "策略治理 updated from reviews", 50.3% win / PF 2.71 backtest, 98 pytest, git clean), pitfalls, and reusable workflow. Combine with the "一起修复了" batch mode and full hygiene verification bundle.

## Fix Priority Template

```
立即（P0）
├── [list]
本周（P1）
├── [list]
优化（P2）
└── [list]
```
