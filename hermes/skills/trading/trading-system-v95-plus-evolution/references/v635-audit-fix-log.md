# v6.3.5 审计修复日志 · 2026-06-18

## 审计假阳性（3项 — 方法论问题，非真实bug）

### 1. 预测 win 字段误报
- **错误查询**: `p.get('win')` — 返回 None
- **正确字段**: `p.get('was_correct')` — prediction_tracker.py 使用此 key
- **实际状态**: 6条预测全部 verified=True, 5条 was_correct=True, 胜率83.3%
- **教训**: 查 JSON 前先 `print(list(entry.keys()))`

### 2. 结构刷新 reason 字段误报
- **错误查询**: `r.get('reason')` — 返回 None
- **正确字段**: `r.get('reasons')` — maybe_request_refresh 用复数 key
- **实际状态**: 29条记录全部有 reasons 数据
- **教训**: 同文件内可能存在单复数变体，先验证 key 名

### 3. 回补复盘误报
- **误认为**: 有1笔未标注模型的真实交易
- **实际情况**: `trade_reviews.jsonl` 唯一记录是 `test: true, taken: false` 的测试记录
- **教训**: 查数量后查内容——count > 0 ≠ 有真实数据

## 真实修复（5项 P0/P1/P2）

### P0① Cron 全空
- **现状**: `hermes cron list` 返回 "No scheduled jobs"
- **根因**: v6.3.4 重建的7个 cron job 被清空（jobs.json 也被清空到 `{"jobs":[]}`）
- **修复**: 用 `hermes cron create` 重建4个核心 job
  - `gold_monitor`: every 5m, no_agent, script=gold_monitor.py, deliver=telegram:416
  - `signal_inspector`: every 1m, script=信号巡检.py
  - `cleanup_daemon`: every 6h, no_agent, script=清理守护.py
  - `governance_daily`: 0 4 * * *, prompt 模式运行4个治理脚本

### P0② OANDA Token 占位符
- **现状**: `hermes/secrets/oanda_token.txt` 内容为模板说明文字
- **影响**: XAUUSD 数据质量永久 B级(78%)，无法达到 A级(88-92%)
- **修复**: 需棠溪手动获取真实 OANDA token（developer.oanda.com → Manage API Access → Generate Token）

### P0③ 清理守护首次运行
- **现状**: monitor.log 中0条清理日志，`source_snapshots/2026-06-18/` 已有2054个文件
- **根因**: 清理脚本从未被 cron 触发
- **运行**: 手动执行 `python scripts/清理守护.py`，但今天目录 0 天龄无旧数据可清理
- **验证**: cleanup_daemon cron 创建后将在 6h 后首次运行

### P1④ 降噪阈值调优
- **问题**: medium 优先级 breach 位信 69% + 数据 B 级 → 被 push_allowed 拒绝
- **根因**: warning tier 两个条件都要求 `high_priority`，medium 位被永久静默
- **修复**: 新增第三条件 `breached_like and score >= 68 and data_q in ("A","B")`
- **代码**: 行情守望.py L580-582，位于 `push_allowed()` warning 分支

### P2⑨ ETHUSDT 数据污染
- **清理**: trade_plans.jsonl 删除2条 + trade_events.jsonl 删除11条 ETHUSDT 记录
- **原因**: ETHUSDT 不在主动监控范围，旧数据来自 auto_card 分析残留

## 环境状态（修复时）

```
行情守望   PID 6496 · v6.6 · 10s · 数据桥已接
看门狗     PID unconfirmed · 30s · 90s超时
TV         BINANCE:BTCUSDT · 15m
Binance    67.52U · 空仓
Cron       4 jobs active (v6.3.5 重建)
测试       24/24 passed
```
