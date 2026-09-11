# v6.3.4 全面审计修复日志

> 2026-06-18 · 棠溪触发 · 审计范围：进程状态 + 推送链路 + Cron + API 连接

## 审计发现摘要

| 等级 | 数量 | 核心问题 |
|------|------|----------|
| P0 | 3 | 行情守望进程已死、model_dir_text 崩溃循环、Binance API timestamp 错误 |
| P1 | 3 | push 无 Discord、降噪吞 warning、Cron 未注册到 Hermes |
| P2 | 3 | watchdog 无日期、CoinGecko 间歇 null、金十/Yahoo 价差 |

## 已修复（8项）

### 1. model_dir_text 变量作用域 bug（P0）
- **现象**：monitor.log 05:08-05:15 连续 14 次 `cannot access local variable 'model_dir_text'`
- **根因**：`model_dir_text = ""` 在 line 830（breached/near 分支）初始化，但 expired 分支（line 771）和 invalidated 分支（line 793）先执行并引用了它
- **修复**：在 `confidence_text = confidence_line(snapshot)` 之后（line 751）插入 `model_dir_text = ""`
- **教训**：Python 不会在编译时捕获未初始化变量，只在运行时走错分支时崩溃。只在"监控位过期"时触发

### 2. pid_alive Windows 兼容性（P0）
- **现象**：PID 15000 心跳显示 running 但进程列表查无此 PID，看门狗未检测到
- **根因**：`powershell.exe Get-Process` 在 MSYS/git-bash 环境下有路径/编码问题，返回空字符串被判定为 True
- **修复**：watchdog.py + 行情守望.py 同时改为 `tasklist /FI "PID eq {pid}" /NH`，检查 `str(pid) in out and "No tasks" not in out`
- **教训**：MSYS 调 powershell 不可靠，tasklist 是 Windows 原生命令更稳定

### 3. Binance API recvWindow 修复（P0）
- **现象**：现货余额、合约持仓均返回 `HTTP 400: Timestamp outside recvWindow`
- **修复**：`powershell.exe w32tm /resync /force` 同步 NTP 时间
- **验证**：sync 后 `get_account_summary` 立即恢复正常

### 4. push() Discord 双发（P1）
- **代码变更**：`行情守望.py` push() 函数
- **原逻辑**：仅 Telegram，3 次重试
- **新逻辑**：Telegram 3 次重试（主站）→ Discord 单次尝试（副站，失败不阻塞）
- **Discord target**：`discord:1474072925199143167`（安禾 bot · 频道 1474072925199143167）
- **调用方式**：`subprocess.run([sys.executable, "-m", "hermes_cli.main", "send", "-t", "discord:...", "-q", msg])`

### 5. 降噪阈值调优（P1）
- **原 warning 条件**：`high_priority AND breached_like AND score>=70 AND (data≠C OR xau_ok)` → 过于严格
- **新 warning 条件**：
  - `high_priority AND (breached_like OR score>=70) AND data∈{A,B}` → 数据好时放宽
  - `high_priority AND breached_like AND score>=60 AND (data≠C OR xau_ok)` → 触发时降低位信门槛
- **原 invalidated 条件**：`high_priority AND score>=70`
- **新 invalidated 条件**：`high_priority AND score>=60` OR `score>=70`（非 high_priority 但位信够也推）
- **新增 expired 条件**：`high_priority` 的过期事件可推（原逻辑永远拒收）

### 6. watchdog 日志加日期（P2）
- **原格式**：`[HH:MM:SS] msg`
- **新格式**：`[YYYY-MM-DD HH:MM:SS] msg`

### 7. Cron 全量重建（P1）
- `hermes cron create` 注册 7 个 job（位置参数 schedule，不是 `--schedule`）
- `jobs.json` 同步清空（不再维护两套系统）
- 注册列表：数据采集(5m) / 方向翻转(30m) / 4h提醒 / 每日复盘(23:00) / 事件清理(04:00) / 每日备份(23:00) / 信号巡检(1m)

### 8. 棠溪第二次指令：删除所有 Cron
- 全部 7 个 job 已删除，系统保持零 cron 状态
- 代码修复保留，进程不启动

## 验证状态

| 项目 | 状态 |
|------|------|
| Binance API | ✅ 合约钱包 67.52 USDT 可读 |
| TradingView | ✅ CDP 连接正常，OANDA:XAUUSD 5m |
| BTC 现价 | ✅ $64,598 |
| 行情守望进程 | ❌ 未启动（棠溪指示不启动） |
| 看门狗 | ❌ 未启动 |
| Cron | ⚪ 零 job（棠溪指示清空） |
| 交易计划 | 44 条全为 B等待，零执行 |
| 复盘样本 | 1/20 |

## 会话统计

- 审计覆盖：923行 行情守望 + 137行 watchdog + 65行 jobs.json + 112行 events
- 修复代码量：~30行新增/修改
- Cron 操作：创建 7 + 删除 8（含之前的信号巡检）
- 验证：Binance API 恢复正常 + TradingView 连接正常
