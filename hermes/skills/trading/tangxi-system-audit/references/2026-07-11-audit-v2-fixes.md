# 2026-07-11 审计二期 · 会话级修复与验证记录

## 背景
用户要求"现在分析我的系统怎么样，审计"，并在修复后反馈"报告要优化一下，感觉发到电报的报告审美好差"。本文件记录第二期审计（20:00–20:12）的修复、验证命令与最终报告结构，供后续同类审计参考。

## 发现的问题与修复

### 1. BTC守护看门狗无运行时日志（P1→可观测性）
- 现象：新 `btc_watchdog.py` 健康 tick 时静默 exit 0，`data/watchdog.log` 停在 16:17 崩溃记录，`data/watchdog_state.json` 仍是 7月7日旧数据。
- 修复：`btc_watchdog.py` 每次 tick 追加日志并覆写 `data/watchdog_state.json`，schema=`btc_watchdog_state_v2`。
- 验证：
  ```bash
  cd "D:/Hermes agent"
  python scripts/monitor/btc_watchdog.py
  tail -5 data/watchdog.log
  cat data/watchdog_state.json
  ```
- 结果：日志显示 `tick age=1.8 instances=1 pids=[18348]` 和 `heartbeat fresh; no action`；状态文件 healthy。

### 2. XAU TV同步 cron 偶发失败（P1）
- 现象：20:00 cron 触发后 `xau_tv_state.json` 写 `{"stale":true,"error":"同步返回非零状态 1"}`，导致 XAU 依赖 TV 的管线降级。
- 修复：
  - 加 `_run_with_retry(max_attempts=3)`，失败后 sleep 5s 重试。
  - 旧数据保留阈值 15 分钟 → 30 分钟。
  - `_refresh_source_snapshot_if_stale` 阈值 20 分钟 → 30 分钟。
- 验证：手动 `python scripts/xau_tv_sync.py` 成功；20:15 cron 后检查 `xau_tv_state.json` 是否 non-stale。

### 3. psutil 实例计数虚警（P0→诊断）
- 现象：用 `psutil` 查 `btc_daemon.py` 时，审计命令自身的 `python -c "import psutil..."` 和 bash 包装进程被算入实例。
- 修复：过滤 `cmdline` 中含 `bash` 或 `-c import psutil` 的进程。
- 验证命令：
  ```python
  for p in psutil.process_iter(['pid','cmdline']):
      cmd = ' '.join(p.info['cmdline'] or [])
      if str(DAEMON) in cmd and 'bash' not in cmd and '-c import psutil' not in cmd:
          print('REAL', p.info['pid'], cmd)
  ```

### 4. 看门狗 resume 后需验证多个周期（P0→复发验证）
- 做法：20:05 看门狗触发后检查 1 实例；20:10 再次触发后仍为 PID=18348 单实例。
- 结论：新看门狗在多周期 cron 调度下保持单实例，P0 修复有效。

### 5. 报告审美优化（用户纠正）
- 旧问题：报告一上来就是 7 列表格，密度大、无总体状态卡。
- 新版 v2 结构：
  1. 顶部大状态卡（总体健康 / 核心结论）。
  2. 修复项表（4 列：问题/级别/动作/结果）。
  3. 运行态表（3 列）。
  4. 数据新鲜度表（3 列）。
  5. 交易决策表（3 列）。
  6. 剩余观察表（3 列）。
  7. 总体结论段。
- 推 TG：`telegram_reliable.push_tg_rich("telegram:-1003733144325:846", report)`，回执 `rich_sent`。

### 6. EURUSD source_snapshot 刷新（P2）
- 命令：
  ```python
  from trading_system import source_snapshot
  source_snapshot('EURUSD')
  ```
- 结果：quality=C，primary=1.14138；非主战场但已补齐新鲜度。

### 7. 每日复盘提醒 7/10 未跑原因不明（P2→观察）
- cron 显示 `Last run: 2026-07-09T21:00:20`。
- 调查：Hermes 日志中无 `daily_trade_review_reminder` 相关记录；no-agent cron 输出直发本地，调度器无持久 trace。
- 处理：标记为观察项，等 21:00 观察今晚是否正常触发。

## 最终状态（2026年07月11日20：12）

| 检查项 | 结果 |
|----|:--:|
| BTC守护实例数 | 1（PID=18348） |
| 行情守望心跳 | 0.1 分钟 |
| BTC守护心跳 | 0.1 分钟 |
| 看门狗状态 | healthy，20:10 |
| source_snapshot_BTCUSDT | 0.1 分钟 |
| source_snapshot_XAUUSD | 6.0 分钟 |
| source_snapshot_EURUSD | 0.7 分钟 |
| tv_dmi_cache.json | 0.1 分钟 |
| tv_live_XAUUSD.json | 4.3 分钟 |
| xau_tv_state.json | 4.6 分钟 |

## 提交
- Commit: `2f0b1a1 fix(audit-v2): watchdog logging/state, xau tv retry + 30min degradation`
- Push: `main → origin/main`

## 复用提示
下次审计若遇到：看门狗 resume 后无新日志、psutil 实例数虚高、XAU TV 同步 cron 失败、用户对报告审美不满，可直接套用本节模式。
