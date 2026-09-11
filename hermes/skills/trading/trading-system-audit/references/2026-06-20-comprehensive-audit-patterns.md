# 2026-06-20 综合审计执行模式

本文件记录 2026-06-20 全面系统审计（用户请求“全面检查检查审计我的系统，联网社区看看我的分析监控策略分析模板”）中验证有效、可复用的模式。已合并进 trading-system-audit SKILL.md 主流程。

## 铁律 0：先验明运行态

审计永远从实测开始，不要先读 config / 记忆 / jobs.json。

必须先执行：
- mcp_binance_get_* + mcp_tradingview_tv_health_check
- read_file data/monitor_heartbeat.json + source_snapshot_*.json + tail monitor.log
- hermes cron list + 实际 last_status
- tasklist / git status / ls scripts/ 交叉
- 只有建立当前真实状态后才判断 P0/P1

## 验证 bundle（每次变更后必全跑，不可跳过）

1. 读模板：`read_file("references/master-template-v68.md")`（必须，确认 v6.9 底板）
2. 再生分析卡：`python scripts/auto_card.py BTCUSDT && python scripts/auto_card.py XAUUSD`
3. 零机器字段：`grep -E "(setup_id|model_id|entry_tag|exit_tag|critical|warning|info)" data/auto_card_*.md` （必须 0 泄漏）
4. pytest（至少核心）：`pytest -q --tb=line`
5. 价格守卫实测：`python -c "from scripts.行情守望 import get_price; print(repr(get_price('XAUUSD')))"` （XAU 必须不走 Binance）
6. 快照质量 + 心跳 + 进程确认
7. git status --short → add + commit + push（棠溪定义“锁定”）

只有 bundle 全部真实执行并输出预期结果，才能在报告中说“已修复”。

## 本轮可复用 P0 模式

**Cron 脚本路径漂移（Windows Junction）**
- 症状：hermes cron 指向 `%LOCALAPPDATA%/hermes/scripts/持仓与信号.py` 但 repo 在 D:/Hermes agent/scripts/
- 根治：建目录联接（Junction）或 wrapper。修后 `hermes cron run <id>` 验证 last_status=ok 且文件真实存在。
- 铁律：中文脚本名 + no-agent 更易触发此问题。

**XAUUSD 价格守卫必须绝对**
- 症状：monitor.log 反复 400 Client Error for XAUUSD（Binance 不支持该 symbol）。
- 修法：在所有 price 入口（行情守望、system_data_bridge、trading_system）最早位置加硬守卫：
  ```python
  if "XAU" in symu or not sym.endswith("USDT"):
      return gold_api_or_jin10(...)  # 绝不 fallback Binance
  ```
- 验证：直调 + 观察 monitor.log 10min + 刷新 snapshot 质量。

**预测胜率 99%+ 过拟合检测**
- 症状：monitor.log 反复 99.7%+。
- 修法：
  - verify 只计有意义移动（>0.5% 或 ≥0.5x ATR 的已完成 bar）
  - 排除 “方向不明”
  - 优先 triple_barrier / meta_labeler 真实标签
  - 清旧 prediction_log.jsonl 重积累
  - 胜率日志降频（每小时一次）

## 社区 + 模板审查集成步骤

审计时必须：
1. x_search + web_search 拉 CVD / ICT / Volume Profile / Freqtrade 最新共识（2026）
2. 重点提取“只有锚定结构才有效”“吸收/背离”“MTF top-down”
3. 映射到 scoring_engine / five_model_matcher / regime_classifier / 博弈段
4. 同时 read_file master-template-v68.md 确认当前格式铁律
5. 在报告中单独一节“分析监控策略 & 模板审查” + “应接入什么还差什么”
6. 执行 v6.9.1 增强：具体改动见 `references/v6.9.1-community-template-enhancements.md`
   - 博弈拆子项（流动性扫荡 + CVD背离 + 现货vs永续）
   - 环境⑪ XAU Kill Zone 时段
   - 结构 Naked POC + 扫荡状态
   - 5m + 模型清单补充确认条件
7. 验证关键词 + 卡片 0 leaks + git lock

## 报告输出铁律（对齐本轮）

- P0/P1/P2 严格
- 每条：问题 → 具体证据（命令/文件片段/日志） → 影响 → 修法（含验证命令）
- 结尾附“推荐立即行动清单” + “验证 bundle 执行结果”
- 中文、直接、有结构、细节充分

**“一起修复了”执行证据（2026-06-20 本轮）**：
- XAU 守卫：双重 patch（行情守望.py + system_data_bridge.py），if "XAU" in ... or not endswith USDT → return None；直调验证 XAU: None, BTC 正常。
- 预测：min_move 0.005 + conf<0.5 排除；prediction_log.jsonl 清空（备份 .bak）→ 当前 2 行新鲜。
- Cron：删除旧 job，hermes cron create 用 --workdir "D:\\Hermes agent\\scripts" + --no-agent；cp 脚本到 $LOCALAPPDATA/hermes/scripts/ 作为冗余。
- 清理：find __pycache__ -exec rm；py_compile 全部通过。
- 验证 bundle 全跑：auto_card 再生 + grep 0 machine leaks；pytest 98 passed；git 两次 commit + push（clean）；taskkill stale PID。
- 最终状态：3 cron 活跃、守卫生效、日志重置、卡片合规、git locked。

此证据可复用于未来同类“一起修复”请求。未来同类审计直接复用此 bundle + 批量模式。

## Phase 2: Execution Closed-Loop & Governance Feedback
This session (after the hygiene batch) advanced the system to execution closed-loop. 

See the new dedicated support file `references/execution-closed-loop-and-governance.md` for:
- Canonical use of `成交记录.py` + `成交复盘.py` (record → risk_state update → review → trade_reviews.jsonl)
- `策略治理.py` now aggregates reviews for per-model current_sample / avg_r / win_rate and applies conditional weight adjustment
- `日间维护.py` extension for `run_day_trading_maintenance()` / `python ... day` (daily validation + governance)
- Sim trade bootstrap (`*-sim*` plan-ids) to accumulate samples safely (target ≥20 per model before weights meaningful)
- CVD A-grade integration (BTC A级; XAU 非加密 expected)
- Extended verification mini-bundle that must be run after any loop changes (sim record+review + governance check + risk_state + cards 0 leaks + pytest + git lock)
- Concrete evidence and pitfalls from the phase

Incorporate this pattern into every "继续推进", full audit, and "一起修复了" execution. The closed-loop + sample-driven governance is now a first-class part of the trading system class.