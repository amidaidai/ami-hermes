# 2026-06-21 Watchdog 限速误判与生产/测试环境污染

## 症状
- Telegram 收到：`安禾监控告警：行情守望重启被限速 — 重启速率限制[真崩溃]：6次/小时已达上限 · 冷却3599s`
- `watchdog.log` 同一时间窗反复出现：`行情守望.py 已启动` 后立刻 `重启速率限制[...]`
- `monitor_heartbeat.json` 显示 `status=running`，但 PID 已不存在。
- `monitor.log` 混入 `NO_SEND 拦截...`，说明测试环境变量污染了运行态。

## 根因组合
1. 陈旧心跳：heartbeat 里的 PID 已死亡，但文件仍写 `running`。
2. 旧冷却/并发误判：guard 旧时间戳 + 多次外部调用 `start_monitor()`，把一次故障放大成 6次/小时。
3. 启动即乐观写状态：watchdog `Popen()` 后未等待/验证子进程是否真正活着，就写 `status=running`。
4. 测试变量污染生产：watchdog 或 TV 异步出卡继承 `HANGQING_NO_SEND=1`，导致真实运行中出现 NO_SEND 拦截。
5. `monitor_levels.json` 残留非法 symbol `-q`，让监控循环继续触发入口防线日志。

## 修复模式
- Watchdog 启动 monitor 时：
  - `env = os.environ.copy(); env.pop("HANGQING_NO_SEND", None)`
  - `proc = subprocess.Popen(..., env=env)`
  - `time.sleep(3)` 后检查 `proc.poll()`、`pid_alive(proc.pid)`、heartbeat
  - 只有子进程真实存活才写 `watchdog_state.status="running"`
  - 否则写 `status="failed"` + 具体原因
- 行情守望 TV 异步 auto_card 子进程同样剥离 `HANGQING_NO_SEND`。
- 救活时清理：`watchdog_guard.json` 两个重启桶、`watchdog.lock`、`monitor.lock`、非法 `-q` symbol。

## 验证 bundle
- `python -m py_compile scripts/watchdog.py scripts/行情守望.py`
- `HANGQING_NO_SEND=1 python -m pytest tests/test_p0_p1_audit_regressions.py -q --tb=short`
- 启动 watchdog 后确认：
  - `monitor_heartbeat.json` 时间持续刷新
  - heartbeat PID 存活
  - `watchdog_state.status == "running"`
  - `monitor_levels.json` 不含 `-q`
  - `monitor.log` 新增真实 `推送成功 ... telegram_direct` 而不是 NO_SEND

## 锁定证据
- commit: `5b371c5 修复行情守望重启限速误判`
