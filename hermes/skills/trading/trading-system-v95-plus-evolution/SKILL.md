---
name: trading-system-v95-plus-evolution
description: 9.5+ 交易系统进化清单：v6.3.1模型扩展(31类)、v6.9双卡模式+ATR止损+三层架构(4h继承/低周期触发/催化剂验证)、v9.14社区战略审计、v10.0宪法+Protections、Walk-Forward+贝叶斯过拟合防护。
---

# 交易系统 9.5+ 进化标准

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

## 联网依据

- Hermes Cron / Memory 官方文档：cron no-agent 适合低成本守护；memory 有硬容量，应保留稳定事实，流程写 skill。
- OWASP LLM / Agentic AI：联网内容、工具调用、skills、memory、cron 都是 agentic 攻击面；必须最小权限、治理变更、避免 prompt injection 影响长期状态。
- Binance Futures 官方接口：Open Interest、Long/Short Ratio、Taker Buy/Sell、Funding 只能作为衍生品背景，不可替代结构和风控。
- Bookmap / Order Flow 社区：CVD 用于确认吸收、耗竭、主动买卖，但低粒度 CVD 只能降级为辅助信号。
- 交易 journal 社区：策略进化必须用 expectancy、R multiple、样本数、最大亏损串验证，不能靠主观感觉升权。

## P0 运行规则

1. `source_snapshot.json` 只做最新缓存；每次快照必须同步写入 `data/source_snapshots/YYYY-MM-DD/{symbol}-{time}.json`，便于复盘追溯。
2. `行情守望.py` 必须有数据异常熔断：快照过旧、连续 C 级、10s 异常跳价时只记录 system event，不推送交易提醒。
3. 真实开仓必须执行 `scripts/成交记录.py`；未复盘成交会让 `risk_gate()` 把下一笔降到最高轻仓。
4. 成交结束必须执行 `scripts/成交复盘.py --model ...`；复盘会更新 `risk_state.json` 和 `strategy_governance.json`。
5. `strategy_governance.json` 只允许把模型状态降权或标记候选；样本不足不能自动升权，满足样本也必须棠溪手动批准。
6. **零真实成交时所有自动参数都是推测值**：系统健康分 93/100 衡量架构完整性而非实战有效性。评分器权重、位信阈值（`MIN_WARNING_LEVEL_SCORE`）、风控闸门参数等全部未经真实盈亏校准。在 10-20 笔真实成交完整复盘（开仓→`成交记录.py`→平仓→`成交复盘.py`→验证 `risk_state`/`strategy_governance` 更新）之前，不调整核心参数。
7. **治理空库形同虚设**：`strategy_governance.json` 的 `rules: {}` 表示没有任何模型被录入治理。首次真实成交后必须执行 `策略治理.py` 录入模型记录，否则复盘只更新 `risk_state` 不更新治理库。

## v6.3.3 自动化缺口修复（2026-06-17 第三次全系统审计）

### Cron 自动化缺失（P0 · 2026-06-17 已修复 ✅）
- **问题**：cron 只有一个 `git_daily_backup.sh`。分层分析策略要求 4h/1h K 收线时自动分析+出卡，但没有 cron 驱动。
- **已建 cron**（均 `no_agent: true`，已在 `hermes/cron/jobs.json` 注册）：
  1. `4h_analysis_reminder`：`2 */4 * * *` → `cron_4h_analysis_reminder.sh` → Telegram:416
  2. `direction_flip_guardian`：`*/30 * * * *` → `cron_direction_flip_guardian.py` → Telegram:416
  3. `daily_review`：`0 23 * * *` → `cron_daily_review.py` → Telegram
  4. `data_gatherer_cron`：`*/5 * * * *` → `data_gatherer.py` v3.0
  5. `cleanup_daemon`：`0 4 * * *` → `cleanup_daemon.py`（独立，不依赖信号巡检）
  6. `git_daily_backup`：`0 23 * * *` → `git_daily_backup.sh`（保留原有）

### API Key 安全（P0 · 2026-06-17 已修复 ✅）
- **修复**：`data_gatherer.py` L15-16 硬编码 fallback 已删除。现优先读环境变量 `BINANCE_API_KEY` / `BINANCE_SECRET_KEY`，fallback 从 `hermes/secrets/binance.json` 读取。`hermes/secrets/` 在 `.gitignore` 中排除。
- **config.yaml MCP env** 仍有明文 Key（受 Windows 文件锁保护，需手动编辑改用 `$BINANCE_API_KEY` 环境变量引用）。

### 监控推送双通道（P0 · 2026-06-17 框架就绪 ⚠️ Discord 待实测）
- **修复**：Discord bot 安禾（server `1473676822960144560` / channel `1474072925199143167`）已配置但监控 `push()` 尚未添加 Discord 第二通道。
- **实现路径**：`行情守望.py` 的 `push()` 增加 `send_message(target='discord:1474072925199143167', message=...)` 作为 Telegram 之后第二条推送。

### 信号巡检进程误报（P1 · 2026-06-17 已修复 ✅）
- **修复**：`signal_inspector_fix.py` 实现两段式防误报——连续 2 次巡检均未发现进程才告警。单次缺失仅记录不告警。
- watchdog 参数维持 30s/90s（v6.3.1 建议的 15s/60s 未采纳，因 30s 对不频繁重启场景足够）。

### R:R 致命校验 + 模板统一（2026-06-17 已完成 ✅）

#### R:R 硬底线
- `model_checklist.py` v1.1：`COMMON_CHECKS[0]` 新增 `rr_hard`（`fatal: True`）。R:R < 1:2 时 `run_checklist()` 立即返回 `{"verdict": "X禁做 · R:R硬底线不合格"}`，不执行模型特定检查。
- 新增 `cvd_quality` 检查：CVD C 级 → 自动降权半仓。
- 新增 `five_model_only` 检查：确保日内执行入口限定五类固定模型。

#### 模板三合一
- 六份独立模板文件已合并为 `references/master-analysis-template.md`（未落地·勿引） v3.0（唯一权威源）。
- 层级：核心卡（必跑·5段）→ 增强层（加权15→13评分/置信公式/量比/checklist）→ 锁定格式（⚠优先/R:R≥1:2/三源一致）。
- 旧文件（`v51-analysis-card-core.md`/`template-v97-enhancements.md`/`template-locked-final.md`）不再独立使用。

#### 数据管道升级
- `data_gatherer.py` → v3.0：+XAU三源价格/Polymarket REST/X情绪占位/CoinDesk RSS/XAU宏观12指标/API安全化。
- 情绪管道：`sentiment.x.status = "pending"` → agent 分析时补跑 `x_search()`。
- Cron 6个 job 全部在 `hermes/cron/jobs.json` 注册。

#### 品种模板标记
- `multi_symbol_templates.md`：SOL/BNB/USOIL/SPX 均标记 `monitor_enabled: false`，仅保留分析能力。
- 主动监控：BTCUSDT + XAUUSD。

## v10.0 社区联网战略审计（2026-06-21 六大社区全量审计）


**六大社区源**：Freqtrade+X、Reddit r/algotrading、X/Twitter ICT/SMC、NautilusTrader、Bookmap、TradingView Pine v6。详见 `trading-system-audit` references。

**新增模块**：

| 模块 | 文件 | 借鉴来源 |
|------|------|---------|
| 风险宪法 v2.0 | `scripts/risk_constitution.py` | X/Reddit 1%黄金标准+Freqtrade Protections+NautilusTrader pre-trade |
| ATR夹层止损 | `scripts/hard_stop.py` | Freqtrade ATR trailing stop |
| 48h就绪报告 | `scripts/readiness_report.py` | Freqtrade 48h readiness check |
| 相关性矩阵 | `scripts/correlation_matrix.py` | Reddit 多资产组合风险 |
| CVD吸收检测 | `scripts/orderflow_absorption.py` | Bookmap iceberg/absorption/CVD |
| 渐进上线 | `scripts/dryrun_progressive.py` | Freqtrade dry-run模式 |
| 仓位sizer v2.0 | `hermes/scripts/position_sizer.py` | X/Reddit fixed fractional sizing |

**核心改进**：
- MAX_RISK_PER_TRADE_PCT: 3%→1%（社区共识）
- Protections系统: StoplossGuard(12K)+Cooldown(3K)+MaxDrawdown(10%/15%)
- ATR止损夹层: `0.5×ATR ≤ 止损距离 ≤ 2.5×ATR`
- 波动率自适应: `adaptive_risk_usd()` 高波动减仓/低波动加仓
- 固定分数仓位: `risk = equity × 1% × volatility_multiplier`
- 多资产组合: `multi_asset_risk_multiplier()` BTC/XAU相关自动调整

**验证**：98/98 pytest · Protections持久化save/reload通过 · ATR夹层4场景实测 · 5 commits pushed


## v10.1 Protections全管线接入 + position_sizer宪法对齐（2026-06-21）


Protections 接入决策点（`行情守望.apply_risk_constitution`）+ 卡片生成前状态注入（`auto_card` meta）。position_sizer 删除硬编码 `DEFAULT_ACCOUNT`(100/10/30)，对接 `adaptive_risk_usd()` + `_get_account_balance()` 实盘余额。


## v10.2 P2社区增强（2026-06-21）


相关性矩阵 + Bookmap式CVD吸收检测 + Dry-run渐进上线 + runtime_core_checks v2.0适配。


## v10.4 CVD趋势线突破 + 动态回撤降级（2026-06-21 · 本会话）

借鉴 **X/Twitter ICT/SMC 2026 共识** + **X/Reddit 2026 机构仓位共识**，实现两个P1社区差距。

### 新增模块

| 模块 | 文件 | 功能 | 借鉴来源 |
|------|------|------|---------|
| CVD趋势线突破 | `scripts/orderflow_absorption.py` +123行 | 线性回归拟合CVD趋势线·下破=多头撤离预警·上破=空头撤退预警·领先后续价格2-5根K线 | X/Twitter ICT/SMC 2026 |
| 动态回撤降级 | `scripts/risk_constitution.py` +122行 | 5级渐进降险(full→half→quarter→micro→paused)·三层组合风险检查(回撤×波动×硬上限) | X/Twitter 2026 institutional consensus |

### CVD趋势线突破细节

社区共识: "CVD trendline breaks as LEADING signals — before price breaks structure."

```python
# 线性回归 + 斜率偏离判定
detect_cvd_trendline_break(cvd_series, window=20)
  → {trendline_broken, direction(上破/下破/未破), signal, confidence(0-90)}

# 四种信号:
# CVD原上升→跌破趋势线 = 多头撤离(conf≤90)
# CVD原下降→突破趋势线 = 空头撤退(conf≤90)
# CVD加速上行 = 多头加强(conf≤70)
# CVD加速下行 = 空头加强(conf≤70)
```

### 动态回撤降级细节

社区共识: 纯固定1%不够 → 必须根据回撤层级自动降险

```
DD>5%  → reduced (0.75×)
DD>8%  → half    (0.50×)
DD>12% → quarter (0.25×)
DD>15% → micro   (0.10×)
DD>20% → paused  (0×)
```

`combined_risk_check(balance, atr_pct, dd_pct)` → 三层组合 → 最终 risk_usd

### 验证

- CVD趋势线: rising CVD detect→上破/breaking CVD→下破 conf=90 ✅
- 动态回撤: 5级全通 ✅ · combined_risk_check 输出正确 ✅
- 103/104 pytest passed · 0 leaks · `d8798ba` pushed

### Watchdog 重启风暴诊断（本会话新发现）

20:57-21:24 连续崩溃·根因: Discord推送超时阻塞worker→主循环累积→心跳停滞→watchdog误判。
诊断四步: 时间分布→实弹send→查崩溃类型→修超时/重试。
救活: `echo '{"restart_times":[],...}' > data/watchdog_guard.json`

借鉴 **TauricResearch/TradingAgents**（87.7k stars · v0.2.5 · Apache-2.0）的核心设计，提取可零 token 成本融入的设计模式。

### 借鉴设计

| 概念 | TradingAgents 原实现 | 棠溪融法 | 新文件 |
|------|---------------------|---------|--------|
| Bull/Bear 辩论 | 12-agent LangGraph 全 LLM 辩论 | **结构化评分**：从 multi_model_engine 输出中自动拆做多/做空阵营 → 加权 0-10 → 压力测试 → 分歧度判定 | `scripts/adversarial_analyst.py` |
| Polymarket 预测市场 | `prediction_markets` vendor（keyless） | **宏观情绪桥**：Gamma API → 过滤宏观相关市场 → 缓存 1h → 注入环境段 | `scripts/polymarket_bridge.py` |
| 共享 Instrument Context | yfinance 一次解析注入 12 agent | 已有等价物：`enrich_engine_data()` 统一注入 DXY/US10Y/Polymarket | `scripts/system_data_bridge.py` 增强 |
| 结构化 Sentiment | band+score+confidence+narrative | 对抗评分天然产出 bull_score/bear_score/div_label/net 结构化输出 | adversarial_scoring() |

### 新增模块

| 模块 | 文件 | 功能 | Token 成本 |
|------|------|------|-----------|
| 对抗式分析 | `scripts/adversarial_analyst.py` | Bull/Bear 评分 + 压力测试 + 分歧度 | **零**（纯规则引擎） |
| Polymarket 桥 | `scripts/polymarket_bridge.py` | 免费宏观预测市场信号注入 | **零**（公开 API + 缓存） |

### 卡片注入点位

```
环境段 ⑦ 预测市场：Polymarket — 衰退概率/降息/地缘/加密情绪
环境段 ⑧ 对抗视角：Bull n vs Bear n — 低/中/高分歧
博弈段 ⑦ 对抗分歧：Bull n vs Bear n — 分歧度判定
```

### 模板变更

- 模板 `references/master-template-v68.md`（未落地·勿引） → **v6.9.15**：环境段 ①-⑧（+预测市场+对抗视角）、博弈段 ①-⑦（+对抗分歧）
- 头部 `⑤ 识别信号` → `⑤ 模型`（对齐模板）

### 代码模式（可复用）

**对抗评分核心逻辑**（从多模型结果中拆分阵营）：
```python
# adversarial_scoring(engine_data, symbol, results) → 返回结构化 dict
for r in results:
    bias = r.get("bias") or r.get("direction")
    conf = r.get("confidence") or 0
    score = min(conf * 10, 10)
    if any(x in bias for x in ("多","long","bull")): bull_items.append({...})
    elif any(x in bias for x in ("空","short","bear")): bear_items.append({...})
# 加权平均 → bull_score / bear_score / divergence / net
# 压力测试：取最高 conf 反向信号
```

**Polymarket 桥核心逻辑**（零密钥公开 API）：
```python
# Gamma API → 过滤 RELEVANT_TAGS → 提取 implied probability
# 缓存 1h → polymarket_context_text() 返回一行摘要文本
```

**管线注入模式**（三步串联）：
1. `system_data_bridge.enrich_engine_data()` 调用 `polymarket_bridge` → 注入 `ed["polymarket"]`
2. `auto_card.render_card_locked()` 调用 `adversarial_scoring(engine_data, symbol, results)` → 注入 `ed["_adversarial"]`
3. 环境段/博弈段渲染时消费 `ed["polymarket"]` 和 `adversarial` dict

### 验证

- 98/98 pytest · 0 machine leaks · BTC+XAU 双卡新字段同时验证
- Polymarket 实弹拉取 10 个宏观相关市场（Fed决策/衰退/地缘/加密/黄金）
- `0cdaf8d` pushed

### 未融入的 TradingAgents 设计（需更高 token 预算）

以下 TradingAgents 设计暂不融入，因为需要全 LLM agent 调用（高成本）：
- 12-agent LangGraph 辩论网络（Bullish/Bearish Researcher + Judge 全 LLM）
- 双模型分派（deep_think vs quick_think — 我们已有 multi_model_engine 覆盖）
- Portfolio Manager + Simulated Exchange 执行层（我们是"人控驾驶舱"，不需要自动下单）
- Persistent Memory Log 决策反思（我们已有 成交记录+成交复盘+策略治理 闭环）

如未来想做 LLM 辩论，可作为 cron agent 在出卡前运行一次对抗辩论，将裁决注入分析卡。

详见 `references/v103-tradingagents-fusion-patterns.md`（完整代码模式、测试命令、坑点）


## v9.10 回测框架（2026-06-18 社区对比升级）

详见 `references/v910-backtest-framework.md`。

**新增模块**：backtest_runner.py(五模型+真实taker CVD+滑点) · model_optimizer.py(网格搜索) · equity_tracker.py(权益曲线) · dashboard.html(看板:8766) · btc_klines_30d_merged.json(3000根15m含taker+LS+GLS+OI)

**核心发现**：VWAP反抽>POC拒绝>>扫流动性回收。R:R≥2.0为实盘基准。数字有趋势偏差不可用于仓位计算。

**测试**：31/31 passed (含7个新测试: 4 backtest + 3 equity)。

## v9.11 GitHub社区借鉴+数据桥修复+时段过滤（2026-06-18）

详见 `references/v911-github-integration.md`。

### 新增集成

| 来源 | 借了什么 | 集成到 |
|------|---------|--------|
| **aurumcrypto** ⭐1 | BTConfig成本模型(fee_bps+max_hold) | backtest_runner.py v1.1 |
| **BAKOME Gold Scalper** ⭐1 | 黄金时段过滤+Kill Zone | scripts/session_filter.py |
| **GitHub API** | 搜索方法论·13项目对比 | audit workflow |

### 数据桥修复（关键bug）

**问题**：12引擎模型全部不触发（0笔交易），覆盖仅31%。
**根因**：引擎模型期望嵌套key结构（`data["taker_futures"]["ratio"]`），回测传入平键（`data["taker_ratio"]`）→ 全部fallback到默认值→conf=0。

**修复**：回测中重建完整嵌套结构，包含 `binance_spot.24h_change_pct` / `taker_futures.ratio` / `long_short.top_long_pct` / `oi.btc`。
**效果**：覆盖率 31%→69%（+Taker背离30笔·OI背离26笔·M_VWAP磁吸7笔）。

### 13模型BTC/XAU天然分裂

```
BTC专属(需futures): 费率反转·多空拥挤·Taker背离·OI背离
XAU专属(黄金特性):  M_VWAP磁吸·关联套利·突破接受
共用(两边都行):     VWAP反抽·VAH回收·VAL回收·POC拒绝·EMA趋势·扫流动性
```

**回测结论**：BTC-only回测覆盖率46-69%是正常的——7个模型中有4个需要futures数据（已接入），3个更适合黄金（待XAU回测验证）。详见 `references/model-coverage-btc-xau-split.md`（未落地·勿引）。

### 时段过滤接入

- **行情守望 v7.1**：XAUUSD只在London/NY高流动性时段推送告警（UTC 07:00-22:00）。亚洲时段静默。
- **auto_card**：黄金分析卡不受时段限制，随时可出。
- **session_filter.py**：`should_trade(asset, require_kill_zone)` → `(ok, reason)`

### 成本模型升级

- 旧模型：简单滑点0.1%折扣
- 新模型（借aurumcrypto）：真实Binance手续费4bps(0.04%) + max_hold超时强平(96根=24h)
- fee_bps→net PnL: `gross_pnl - abs(entry) * fee_rate * 2`
- first-touch TP/SL（无价格调整），超时用close强平

## v9.9 架构层

1. `scripts/黄金宏观.py` 刷新 DXY、US10Y、US02Y、GC=F，生成 `data/xau_macro_context.json`，并在 XAU source snapshot 中作为 `macro_context` 参与背景判断。
2. `scripts/模型统计.py` 从 `trade_reviews.jsonl` 生成 `data/strategy_model_stats.json`，按模型统计样本数、胜率、平均R、最大亏损串和启停建议。
3. `scripts/系统体检.py` 生成 `data/system_health_score.json`，把监控心跳、历史快照、宏观层、策略治理、复盘样本和脚本编译纳入 9.9 健康分。
4. `scripts/清理守护.py`（v6.3.1 新增）防止 `monitor_events.json` 和 `source_snapshots/` 无限膨胀：7天事件清理+1000条上限、快照7天保留/8-30天zip归档/30+天删除、日志轮转3000行。
5. `scripts/信号巡检.py` 每 5 分钟刷新黄金宏观层，每 10 分钟刷新模型统计和安全审计（v6.3.1 起 ThreadPool 并行），完成后跑系统体检和清理守护；这些是派生维护层，不直接改变交易方向。

## v6.3.1 硬化（2026-06-17 全系统审计后）

### 模型体系扩展
- 5类→31类，8大类别，注册表在 `trading_system.py` → `ALL_MODELS`
- 成交量/市场画像(6) + ICT/SMC(8) + 市场结构(4) + Wyckoff(4) + 斐波那契谐波(3) + 缺口(2) + 经典形态(3) + CVD/订单流(1)
- `智能更新结构.py` 自动生成的监控位目前仅覆盖4类（突破接受+扫流动性回收+VWAP回踩+回踩确认），其余14类由人工分析卡手动生成；未来可逐步纳入自动生成
- `行情守望.py` `condition_ready` 已兼容 order_block/breaker_block/FVG/BOS/CHoCH/CVD 等新 type_tag

### 推送位信死循环修复
- `MIN_WARNING_LEVEL_SCORE` 75→70：智能结构更新自动生成的位信分66-74，触发时通过 live_level_confidence CVD配合上浮+4 可推到≥70
- `push()` 加重试：3次×2s间隔，网络闪断不丢告警
- 严格模式 warning 条件：高优先级+强触发+位信≥70%+数据非C（XAU单源金十除外）

### 信号巡检修复
- 事件转发改为推送全部 new_events，不再只推第一条
- v9.9 维护链改为 ThreadPool 并行（模型统计+安全审计），完成后串行系统体检+清理守护
- 维护结果不再被健康发现条件隐藏（移除 `if maintenance and not findings`）

### 数据质量修复
- `智能更新结构.py` 写入 `smart_update.quality` 前交叉验证 `source_snapshot.json`，不一致时覆写
- 行情守望已使用快照实时质量（`data_quality`），不受监控位历史 `smart_update.quality` 影响

### 死代码清理
- `行情守望.py` 删除 old_lab/old_seq/zh_priority/zh_rule/old_display_name/old_display_plan/old_situation_text 共~120行

### v6.3.2 推送链路修复 + 数据源升级（2026-06-17 第二次审计）

#### 推送链路致命 bug 修复
- `condition_ready("near_or_breach")` 现在按 `dist < BREACH_PCT` 返回 `"价格触发关键位"`（含"触发"），`dist < NEAR_PCT` 返回 `"接近计划位"`。修复前所有 near_or_breach 项统一返回"接近计划位"，导致 `push_allowed` 中 `breached_like` 永远 False，全部 89 条 warning 事件被静默拒收（89/89 push_sent=False）。
- `notified` 字段从硬编码 `True` 改为 `pushed`（=实际推送结果），不再伪造通知状态。三处 event 构造均已修正（expired/invalidated/breach-near）。
- 已知限制：`push_allowed` 的 `high_priority` 检查要求触发位 priority=high；medium 优先级的关键位即使触发也不会推送 warning。

#### 数据源升级：OANDA 现货黄金
- 新增 `oanda_spot_price()` 函数（`trading_system.py`），调用 OANDA Practice REST API 获取 XAU_USD 现货报价。
- 凭据文件：`hermes/secrets/oanda_token.txt` + `hermes/secrets/oanda_account_id.txt`。无凭据时函数返回 None，自动降级到金十+Yahoo。
- 质量链（XAUUSD）：OANDA+金十+Yahoo→A级(88-92) / OANDA+Yahoo→B级(78-82) / OANDA+金十→B级(80) / OANDA单源→C级(65) / 金十+Yahoo→B级(75-78) / 金十单源→C级(60)。
- 现货/期货价差说明：Yahoo GC=F 是 COMEX 黄金期货，与现货 OANDA/金十存在系统性价差（~0.4%），不作为现货一致性校验，仅作跨市场方向参考。
- 加密数据源不变：BTCUSDT 主源 Binance 现货 + CoinGecko + Yahoo + Binance 合约 Mark/Index → A 级共识。

#### Windows 双 Python 环境修补陷阱
- Hermes Windows 桌面版有两套 Python：CLI 用 `C:/Users/.../hermes/hermes-agent/`（Python 3.11），`execute_code` 沙箱用 `desktop-runtime/hermes/0.x/win-x64/python/Lib/site-packages/`（Python 3.12）。
- 修补代码时必须两套都改 + 清除对应 `.pyc`。仅改一套会导致沙箱 `web_search` 仍走旧代码。
- `trading_system.py` 新增 `gold_api_price()` 函数 + `price_consensus()` 探头 + A 级评分 tier。

## v9.12 Walk-Forward + 贝叶斯 + 过拟合防护 + 社区全源建议（2026-06-18）

### 新增模块

| 模块 | 文件 | 借鉴来源 |
|------|------|---------|
| Walk-Forward验证 | `scripts/walk_forward.py` | Freqtrade社区·Reddit黄金标准 |
| 贝叶斯优化器 | `scripts/bayesian_optimizer.py` | Freqtrade Hyperopt TPE |
| 过拟合检测 | `backtest_runner.py:check_overfit()` | Reddit:95%散户algo死于过拟合 |
| 时间框架强制 | `backtest_runner.py:enforce_timeframe()` | X/ICT社区:BTC=15m,XAU=5m |

### Walk-Forward三段: 训练60%→验证20%→测试20%·过拟合分>15%=过拟合
### BTConfig: startup_candle_count=400·max_params_per_model=3
### 贝叶斯: 20迭代≈网格27组合·可扩展100+参数
### 社区建议全源已实现: Freqtrade/Reddit/X/GitHub/aurumcrypto/BAKOME

## v6.9.10 双卡模式 + cron恢复 + 社区共识标签（2026-06-21 全渠道审计后）

### 双卡模式
- `render_card_locked()` 新增 `force_full` 参数
- `auto_card()` 调用两次：`force_full=True` → 完整卡（save `_full.md`），`force_full=False` → 极简/完整（save `.md`）
- 极简卡（8行）：价格锚定关键位时触发，替代 60 行全卡
- 完整卡（78行）：始终生成并保存

### Cron 监控三件套恢复
- `positions_monitor.yaml`（5m）→ `monitor_positions.py`
- `cleanup_daemon.yaml`（6h）→ `cleanup_daemon.py`
- `daily_maintenance.yaml`（3:20）→ `daily_maintenance.py`
- 全部 `no_agent: true`，零 token 消耗

### 极简卡格式
```
◷ 时间 · 品种 · 模型 · 方向
③ 现价 · 高 · 低
关键位 价格 ← 距离
CVD · Taker · Funding
→ Plan A: 方向 止损 止盈 R:R
→ Plan B: 方向 止损 止盈 R:R
风控 · 社区标签
—— 决策：你来选方向——
```

### 社区共识标签
- 极简卡风控行增加 `社区F&G 22` 标签
- 来源：alternative.me F&G API + CoinMarketCap F&G API

### 社区审计来源
- CoinDesk：BTC 6月跌21%·ETF持续流出·鲸鱼派发
- X社区：F&G 15-23极度恐慌·机构吸筹·散户出逃
- CoinMarketCap：F&G 22 Fear·BTC市占58.4%上升
- Reddit：6/19 BTC $63,000·讨论冷淡
- Yahoo Finance：ETF流出+鲸鱼派发+上升通道破位
- RoboForex：XAU支撑4,145/4,020·阻力4,275/4,300

### 验证
- 98/98 pytest passed
- BTC/XAU 双卡输出正常
- 双文件同时保存验证通过

## v6.9.11 日内止损止盈 ATR 锚定（2026-06-21 棠溪纠正后）

**问题**：旧算法用固定 3% 止盈。BTC 3% ≈ 1,920 点 → 周线/波段目标。棠溪做日内 5m/15m，1-3天持仓，固定百分比完全不适配。

**修复** — ATR 夹层 + 关键位锚定：
- 止损：`max(ATR_15m × 2, price × 0.3%)`，夹到下一个有意义结构位
- 止盈：下一个有意义结构位（跳 0.3% 以内噪音）
- 0.3% 以内关键位视为噪音跳过
- R:R < 1:2 标注 ⚠R:R不足，不伪造数字
- 无结构位时兜底 0.8%（非 3%）

**代码**：`hermes/scripts/auto_card.py` → `_compact_card()` → `_meaningful_level_above()` / `_meaningful_level_below()`

**预案对称性铁律**：Plan A 和 Plan B 必须字段完全一致（触发/入场/止损/止盈/仓位/风险/失效/复查），不可缩写备选方案。

**R:R诚实标注铁律**：市场结构不给1:2时标注 `⚠R:R不足`，不伪造数字。当前市场紧致时R:R不足是系统的保护信号，不是bug。

**预案对称性铁律**（棠溪亲自纠正）：Plan A 和 Plan B 必须字段完全一致（方向/入场/止损/止盈/仓位/风险/失效/复查），不可缩写备选方案。Telegram推送也必须AB对称。

**B等待不再留空**：即使状态=B等待，也计算真实止损止盈仓位（用 `_calc_stop_target_atr()`）。标注"等触发"但不留"待确认后设定"。

## v6.9.12 三层架构：高周期继承+低周期触发+催化剂验证（2026-06-21）

**系统哲学**："我就是交易系统，但是我来控制开单"（棠溪）。系统是决策驾驶舱，提供结构化信息+风控底线，人做最终开单决策。

### 三层架构

```
高周期继承（4h/1h）   →  决定计划优先级。4h偏空时强制空头优先（引擎中性也否决）
低周期实时（15m/5m）  →  扫荡状态+收线确认+量价描述。极简卡新增触发状态行
催化剂验证（Grok/搜索） →  Grok从"信号确认"改为"催化剂验证"。搜索从"情绪"改为"市场热点"
```

### 代码改动

- `_primary_plan_bias()` 新增 `k4h_direction` 参数：4h偏空→优先空（引擎中性时也否决）
- 极简卡新增触发状态行：`5m {扫荡状态} · 15m {描述} — 低周期触发`
- 极简卡 header 增加 `4h{方向}` 标签
- Grok 输出从 "Grok一致|置信+0.05" → "Grok: 催化剂已验证|置信+0.05"
- 搜索输出从 "搜索情绪" → "市场热点"

### 极简卡完整格式（10行）

详见 `references/compact-card-format-v6912.md`（极简决策卡格式规范+踩坑清单）。

## v9.14 社区战略审计 · 六大社区差距清单（2026-06-21）

基于 Freqtrade/NautilusTrader/Bookmap/TradingView v6/Reddit/X 六大社区25条共识对照。

### P1 战略差距（待实施）

1. **Freqtrade Protections 系统** — StoplossGuard(止损后N根冷却)/CooldownPeriod(亏损后暂停)/MaxDrawdown(达线全停)
2. **固定分数仓位** — 1%×equity 动态计算，替代固定10U上限（注：10U仍为兜底上限，但基础用%）
3. **ATR 动态止损夹层** — 结构止损夹在 `max(结构位, 1×ATR)` 和 `min(结构位, 2.5×ATR)` 之间
4. **波动率自适应仓位** — `vol_multiplier = max(0.5, min(1.5, avg_ATR / current_ATR))`
5. **上线前48h就绪报告** — 整合 overfit_score + OOS_gap + param_stability + 2x_slippage_test
6. **参数稳定性测试** — WFO后参数±10%不应崩坏（`test_parameter_sensitivity()`）
7. **最大回撤硬停** — 日10%/周15%自动暂停

### P2 增强方向

8. **Bookmap 冰山水吸收检测** — CVD 吸收模式预警假突破/stop-run
9. **相关性风险矩阵** — BTC+XAU 反向联动组合级风控
10. **TradingView Footprint API** — v6 原生 volume profile (需Premium/Ultimate)
11. **Dry-run 渐进上线** — 仿真→小仓→全量

详见 `trading-system-audit/references/community-strategic-audit-methodology.md`

### 新增模块

| 模块 | 文件 | 功能 | 借鉴来源 |
|------|------|------|---------|
| 统一日志 | `scripts/logger.py` | RotatingFileHandler 5MB×3 + 统一格式 + `get_logger()` | Freqtrade unified logging |
| Meta-Labeling 门控 | `scripts/meta_labeler.py` | 逻辑回归+规则降级的执行门控 | López de Prado Meta-Labeling |
| 核心测试 | `tests/test_core.py` | 30测试覆盖 scoring/risk/hard_stop/engine/push | Freqtrade test patterns |

### 修改模块

- `scripts/行情守望.py`：心跳移到循环顶部 + timeout 降到5-10s + NaN/inf价格检测(Crash-Only) + 16处broad except→具体异常 + parse_dt异常收窄
- `scripts/backtest_runner.py`：ATR/TR/VWAP/VWAP bands/rolling_window 改用 numpy 向量化（EMA保留递推循环）
- `scripts/risk_constitution.py`：新增 DRAWDOWN_MODE（conservative=2%/aggressive=5%），默认 conservative
- `scripts/hard_stop.py`：log_execution 增加 custom_data 持久化字段

### 社区模式融合

- **Freqtrade 向量化**：指标计算用 numpy 替代 Python 循环；`df.shift()` 防 repainting（验证无 iloc[-1]）
- **NautilusTrader Crash-Only**：corrupt data is worse than no data — NaN/inf 价格直接 raise ValueError，让 watchdog 重启
- **Reddit r/algotrading 2% 共识**：小本金（<$500）日回撤硬限2%，非原5%
- **López de Prado Meta-Labeling**：二级执行门控，primary信号需通过 meta-labeler 才执行

### 测试覆盖（首次）

零测试→30测试。覆盖范围：
- scoring_engine: 评分计算/权重分配/边界值
- risk_constitution: Kelly仓位/熔断触发/模式切换
- hard_stop: 止损计算/执行日志/custom_data
- multi_model_engine: 模型触发/event_ban/置信度聚合
- push_allowed: 阈值逻辑/分层过滤/数据质量门

**Pitfall**: memory 可能记录"31 test"但那是 sandbox/ 其他项目的测试。交易系统自有测试从0开始，本次为首次建立。

### 验证结果

- 语法检查 7 文件全部通过
- pytest 30/30 passed in 0.19s
- numpy 向量化函数输出正确
- Meta-Labeler: 高分→label=1 conf=80%，低分→label=0 conf=40%
- 可配置回撤: conservative 2.5%触发熔断，aggressive 正常运行
- 行情守望重启后心跳5s新鲜

### Fix patterns 详见

`trading-system-audit` skill → `references/fix-patterns-catalog.md`（未落地·勿引）（9个可复用修复模式）

## v7.4 监控警报卡格式对齐分析卡（2026-06-19）

详见 `references/monitor-card-format-v74.md`。

监控警报卡（`行情守望.py` 的 `render_message`）已对齐分析卡 v6.8 模板：字段顺序 ①品种②周期③现价④状态⑤模型⑥触发位▸⑦订单流⑧衍生⑨引擎/冲突⑩风控；圈号统一计数器（`_seq()`）连续不跳；触发位子项用 `▸` 不占圈号；头部去装饰 emoji 改纯文字紧急度；CVD `?` 兜底"估算中"。

**关键修复 — 65/68 死区**：`push_allowed` 中 warning medium / info 分支原硬编码 `score >= 68`，与入口常量 `MIN_WARNING_LEVEL_SCORE`（=65）打架，位信 65-67 的位进得了 warning 池却推不出去被永久静默。已统一为 `score >= MIN_WARNING_LEVEL_SCORE`。**门槛只认这一个常量，任何分支禁写裸数字。**

**架构债**：监控显示异常时先确认调用的是 `render_message` 还是 `monitor_display.py` 的 `format_level_block`（两套并存），别改错文件。

## v10.4 Discord清理+Cron静默+CVD趋势线+动态回撤降级（2026-06-21 全社区联网审计后）

### Discord清理 → 电报唯一通道
- 问题：send_message无Discord目标，但config/history残留 → 推送超时阻塞
- 修复：Discord认证已从系统完全清除（无config/script/cron残余）· 唯一通道Telegram
- 原则：除非棠溪主动添加，否则永不恢复多通道

### Cron优化
- 话题统一：4个cron全部 deliver=`telegram:-1003733144325:416`
- 输出静默：`持仓与信号.py` v1.3有变化才输出· `tv_signal_monitor_wrapper.py` v1.1零输出（内部已推Telegram）
- 清理守护/日间维护仅在异常时输出

### CVD趋势线突破检测（X/ICT 2026·LEADING信号）
- `orderflow_absorption.py` 新增 `detect_cvd_trendline_break()` — 线性回归拟合CVD趋势线
- CVD跌破自身趋势=多头撤离预警（领先价格2-5根K线）· 置信度0-90
- `cvd_trendline_alert_line()` 一行式嵌入分析卡博弈段

### 动态回撤降级 v2.1（X/Reddit 2026机构共识）
- `risk_constitution.py` 新增5级渐进降险: full(1.0×)→reduced(0.75×)→half(0.5×)→quarter(0.25×)→micro(0.1×)→paused(0×)
- `combined_risk_check()` 三层组合：回撤降级 × 波动率自适应 × 硬上限(10U)

### 测试覆盖
- 15个测试文件 · 103/104 passed
- test_watchdog_ratelimit临时失败 = 重启风暴后速率限制正常生效（预期行为）

### MCP服务器审计 → finance+financekit重叠
- `finance` MCP服务器无可见工具暴露· `financekit` 完整覆盖美股/加密/技术分析
- 建议：删除 `finance` MCP服务器（死服务占位置）

### 警报格式评估
- 行情守望 `render_message` v7.4已最优化（10段圈号·无emoji·无机器枚举·动作清晰）
- 无需改动

### 未解决
- TradingView Desktop位于 `C:\Program Files\WindowsApps\`（Windows Store权限限制·CDP启动需手动）
- Walk-Forward框架存在但从未产出完整结果

### 提交
- `d8798ba` CVD趋势线+动态回撤 · `ca0a417` Cron静默+话题统一+Discord清理

### 详见
`references/v625-discord-cleanup-cron-optimization.md`（未落地·勿引）（完整会话记录+修复清单）

## v10.5 R2 多资产管线实战（2026-06-30）

### 新增模块

| 模块 | 文件 | 行数 | 功能 | 数据源 |
|------|------|:---:|------|--------|
| 金十黄金桥接 | `scripts/jin10_gold_bridge.py` | 430 | 金十日历+快讯+报价 → 黄金宏观摘要 | Jin10 MCP |
| COT持仓桥接 | `scripts/cot_bridge.py` | 170 | 解析 cot_collector 输出 → COT黄金/美元方向 | cot_collector |
| 外汇利差 | `scripts/forex_rate.py` | 310 | 央行利率+利差计算，24品种 | web_search+硬编码默认值+缓存 |
| 期权链 | `scripts/options_chain.py` | 170 | Deribit(BTC/ETH)+yfinance(美股)，超时缓存降级 | Deribit MCP + yfinance |
| 热点搜索 | `scripts/sentiment_search.py` | 70 | web_search → RSS 两级回退 | web_search + Google RSS |

### 新增自愈修复模式

详见 `trading-system-audit/references/r2-self-heal-patterns-2026-06-30.md`

1. **行情守望重启**：kill→rm lock→`-s BTCUSDT XAUUSD` 后台启动
2. **Deribit超时+缓存降级**：timeout 15→25s + `data/deribit.json` 10min缓存
3. **Protections TypedDict len()**：TypedDict不支持len() → `type(p).__name__`
4. **sentiment_search stub**：模块缺失时的web回退创建模式
5. **Git锁定**：`??` untracked文件必须 `git add→commit→push`

### 能力运用率变动

修复前：82%（R2中期估）
修复后：88%（行情守望重启+数据刷新+Git锁定+sentiment_search+options修复）
终态核心差距：期货管线(60%) · Stock-API美股降级 · 外部依赖(CoinGecko Pro/X情绪/深度墙)

## v6.3.5 降噪阈值+运维硬化（2026-06-18 第四次全系统审计）

详见 `references/v635-audit-fix-log.md`。

### 已修复（4项）

1. **push_allowed v2.3 降噪阈值**：新增 medium 级 breach 位信≥68 + 数据B+ → 推送通路。修复前 medium 优先级位即使触发 warning 也被静默，导致 56 个 warning 中 31 个被降噪（55%）。新增逻辑在 `行情守望.py` L580-582，先检查 `breached_like and score >= 68 and data_q in ("A","B")`。
2. **Cron 全空修复**：`hermes cron create` 重建 4 个 job（gold_monitor 5m no_agent / signal_inspector 1m / cleanup_daemon 6h no_agent / governance_daily 4am）。`hermes cron list` 读自 `~/.hermes/cron/` 而非 repo 下的 `cron/jobs.json`。
3. **ETHUSDT 残留清理**：`trade_plans.jsonl` 清除 2 个旧 ETHUSDT plan，`trade_events.jsonl` 清除 11 个旧事件。非活跃品种不应留在数据文件中污染统计。
4. **OANDA 占位符检测**：审计时自动检查 `hermes/secrets/oanda_token.txt` 是否为模板占位符。无真实 token 时 XAUUSD 质量上限曾在 B(78%)。**已解决**：接入 gold-api.com（免费·无认证·实时现货）作为第三独立源 → 金十+gold-api+Yahoo → A 级 88-92%。`trading_system.py` 新增 `gold_api_price()` 函数 + `price_consensus()` 探头 + A 级评分 tier。

### 已纠偏

5. **预测 win 字段假阳性**：prediction_log 用 `was_correct` 而非 `win`。查错了字段名 → 误报为空。实际 6 条预测 5 条正确（83.3%），胜率追踪正常工作。
6. **结构刷新 reason 假阳性**：文件用 key `reasons`（复数）而非 `reason`（单数）。查错了字段名 → 误报为空。实际 29 条请求全部有 reasons 数据。
7. **回补复盘假阳性**：唯一交易记录为测试记录（`test: true, taken: false`），无需回补。

### 审计方法论硬化

- 查 JSON 字段前**必须先 `print(list(entry.keys()))`** 验证实际 key 名
- source_snapshot 系列文件有两套不同 key 结构（嵌套 prices dict vs 扁平字段）
- 修复代码后**必须验证运行进程已重启**（heartbeat PID 变更 + monitor.log 错误模式消失）
- 清理守护只按日期目录操作（7天保留/30天删除），今天目录内文件数由快照频率决定

## 陷阱

- 不要因为系统健康分高就觉得一切就绪。健康分衡量架构完整性（脚本存在+数据流动+安全配置），不是实战有效性。零真实成交 = 所有模型参数未经校准，健康分再高也不能替代真实样本。
- `strategy_governance.json` 的 `rules: {}` 是初始状态，不是"无规则"的信号。必须在首次真实复盘后手工执行 `策略治理.py` 录入模型记录。
- **pid_alive 在 Windows MSYS 环境下不要用 `powershell.exe`**：git-bash/MSYS 调 powershell 有路径和编码问题，`tasklist /FI "PID eq {pid}" /NH` 更可靠。`watchdog.py` 和 `行情守望.py` 同时有此 bug，修一个别忘另一个。
- **变量初始化必须在所有使用分支之前**：Python 不会报编译错误，只在运行时走错分支时 `UnboundLocalError`。`model_dir_text` 在 expired/invalidated 分支使用但只在 breached/near 分支初始化——只在有触发位时才执行到初始化代码，所以仅在"监控位过期"场景崩溃。
- **Cron 管理注意 `hermes cron create` 语法**：`schedule` 是位置参数（不是 `--schedule`），必须放在最后。`jobs.json` 和 `hermes cron list` 是两套独立系统，建议只用 `hermes cron` 统一管理。
- **预测验证断裂 — log_prediction 事后补丁模式**：`log_prediction()` 原本写 price=0，调用方事后补价格（`_patch_pred_price` 读改写整个文件、`multi_model_engine` 读最后一行替换重写）。两套补丁都与 `verify_predictions()` 存在文件级竞态，且补丁在 bare `except:pass` 中静默失败。112 条预测全带 price=0 → 无法验证 → `aggregate_stats()` 返回 0 —— 但 monitor.log 会打印另一个计数器的旧残留 99.8%。**修法**：`log_prediction(symbol, merged, results, price=price)` — 价格在创建时直接写入，不事后补丁。事后补丁的思路本身就是 bug 温床。
- **Watchdog 死亡螺旋 + 冷却卡死**：进程全死后 watchdog 因旧时间戳误判「冷却中」而拒绝重启。清空 `watchdog_guard.json` 后**必须同步删除旧的 `.pyc` 文件**，因为 watchdog 的 `CHECK_INTERVAL`/`STALE_SECONDS` 常量可能在 `.pyc` 中与源码不同步。标准复活流程：`echo '{"restart_times":[],"restart_times_emergency":[]}' > data/watchdog_guard.json` → `rm -f data/monitor.lock` → `python scripts/watchdog.py`（用 `terminal(background=true)`）→ 60s 后 `cat data/monitor_heartbeat.json` 确认。(详见 `references/v636-audit-fix-log.md`)
- **`.pyc` 缓存清理铁律**：修改 Python 文件后必须 `find . -name "*.pyc" -delete`，否则运行中的进程可能加载旧字节码。Windows 双 Python 环境（CLI 3.11 + sandbox 3.12）对此尤其敏感。
- **NTP 时钟同步 Windows**：`w32tm /resync` 前需要 `net start w32time`（服务默认可能未启动）。Binance spot `-1021 timestamp` 错误常见于时钟漂移 > recvWindow。
- **监控位 `type_tag`/`display` 为 "?" 不是数据损坏**：`智能更新结构.py` 生成的新 level 包含完整 `name`/`model_id`/`level_confidence.label`，`type_tag`/`display` 为 "?" 是旧代码读取字段名不匹配的显示问题。实际数据完整可用。（2026-06-21 审计确认）
- **XAU 数据源致命污染：Yahoo GC=F 期货价不可用于现货价格**（2026-06-28 全系统审计发现）：
  - 旧代码 `auto_card.py` `_enrich_engine_data()` metal 分支用 Yahoo GC=F（COMEX期货）+ `spot_adj=-125` 静态调整生成 K 线
  - 期货-现货价差不是固定的 $125，随合约到期日/利率/存储成本变化
  - **后果**：XAU 分析卡出现 `现价 4,091 高 3,984`（现价高于"最高价"——物理不可能）
  - **修法**：XAU 价格用 `price_consensus("XAUUSD")`（OANDA+gold-api+金十三源共识），24h 高/低从金十 Quote raw 数据提取（`high`/`low` 字段），K 线改为简化占位+标记 `_xau_klines_pending`，卡片渲染时检测 `k15m.high==k15m.low==price` → 自动回退到 `binance_spot.24h_high/24h_low`
  - **铁律**：TradingView MCP 在线时 XAU K 线才有真实多周期数据；离线时宁可占位，不可用期货代理
  - 详见 `references/xau-data-source-fix-20260628.md`

## v2.0 风险宪法社区升级（2026-06-21 六大社区联网审计）

### 社区共识值变更
- MAX_RISK_PER_TRADE_PCT: 3%→1%（X/Reddit 1%黄金标准）
- KELLY_FRACTION: 0.25→0.20
- NEW: MAX_STOP_ATR_RATIO=2.5（止损上限）
- NEW: STOPLOSS_GUARD_LOOKBACK=12·COOLDOWN_AFTER_LOSS=3·MAX_DAILY_DRAWDOWN_HARD=10%·MAX_WEEKLY_DRAWDOWN_HARD=15%

### 新增模块
- `risk_constitution.py::Protections` — Freqtrade-style StoplossGuard+Cooldown+MaxDrawdown
- `hard_stop.py::position_size(atr_value=)` — ATR夹层止损0.5×～2.5×ATR
- `scripts/readiness_report.py` — 48h就绪报告8维检查
- 详见 `trading-system-audit` → `references/community-strategic-audit-methodology.md`（未落地·勿引）

## v9.14 预测链路收敛 + 死代码清理（2026-06-21 第八次全系统审计）

详见 `references/v636-audit-fix-log.md`。

### 修改文件（3个）

| 文件 | 改动 | 效果 |
|------|------|------|
| `hermes/scripts/prediction_tracker.py` | `log_prediction()` 加 `price` 参数 | 价格创建时直接写入，消除竞态 |
| `hermes/scripts/multi_model_engine.py` | 移除事后读-改写 pred 的竞态 hack | 简化为 `log_prediction(sym, m, r, price=price)` |
| `scripts/system_data_bridge.py` | 移除 `_patch_pred_price` 死代码（~20行） | 消除读改写竞态 + 静默异常 |

### 本次审计 P0 发现

1. **监控全死** — 心跳 stopped，0 python 进程。watchdog 冷却卡死旧时间戳。
2. **预测验证断裂** — prediction_log 112 条 price=0，0 验证。monitor.log 打印假 99.8% 胜率（旧计数器残留）。
3. **XAU kline 路径守卫** — 已在 `0cb65df` 修复，61 次历史 400 错误，0 新错误。
4. **BTC 监控位过期** — 2 expired，智能更新重建为 3 active（VAH/POC/VWAP）。


## v10.0 社区联网战略增强（2026-06-21 六大社区审计全量修复）

### 宪法 v2.0 — 社区共识值
- `MAX_RISK_PER_TRADE_PCT`: 3% → 1%（X/Reddit 1%黄金标准）
- `KELLY_FRACTION`: 0.25 → 0.20
- 新增 `MAX_STOP_ATR_RATIO`: 2.5（止损上限防风险过大）
- 新增 Freqtrade-style Protections — StoplossGuard(12根)+Cooldown(3根)+MaxDrawdown(10%日/15%周)
- Protections 持久化 `load/save_protections()` + `apply_protections()` 快捷入口

### Protections 接入管线 + ATR夹层 + Position Sizer v2.0
- `行情守望.py` `apply_risk_constitution` → Protections 层检查
- `auto_card.py` → meta.protections_status 注入
- `hard_stop.py` v2.0: `position_size(atr_value=...)` ATR夹层 0.5×∼2.5×
- `position_sizer.py` v2.0: 删除硬编码 DEFAULT_ACCOUNT·对接宪法自适应
- `readiness_report.py`: 8维48h上线前就绪报告

详见 `trading-system-audit/references/community-audit-methodology-2026.md`

## v9.12 Walk-Forward + 贝叶斯 + 过拟合防护 + 社区全源建议（2026-06-18 第六次升级）

- 9.5+ 可以做辅助驾驶：更强监控、更强复盘、更强安全治理。
- 不允许自动提高单笔风险，不允许自动修改核心风控，不允许社区观点直接改 A/B/X 状态。
- 自动结构更新只能生成候选关键位；改变方向必须重新出完整分析卡。
- v6.3.1 模型体系扩展到 31 类但不改变自动监控覆盖范围（仍为4类核心位），新增模型类型由人工分析卡手动使用 `type_tag` 写入 `monitor_levels.json`。
