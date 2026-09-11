# 棠溪系统：Cron / 守护进程 / 心跳 / TG 投递链 只读审计记录

> 会话：2026-07-11 | 执行：只读审计 cron、daemon、heartbeat、TG delivery chain

---

## 1. Cron 作业全景（`~/AppData/Local/hermes/cron/jobs.json`）

| ID | 名称 | 脚本 | 调度 | 状态 | 交付 | 最近运行 |
|---|---|---|---|---|---|---|
| ada5d94913fd | BTC关键位同步 | btc_ref_levels_sync.py | 0 8,12,16,23 * * * | ok | local | 2026-07-10 16:00 |
| ef4cf5f7cd24 | Orion全市场雷达 | orion_screener_radar.py | 2 8,10,12,14,16,18,20,22 * * * | ok | telegram:455 | 2026-07-10 16:02 |
| 3a8bee120dd4 | Dune链上刷新 | dune_collector.py | 5 */4 * * * | ok | local | 2026-07-10 16:05 |
| b664f56f904c | COT报告刷新 | cot_collector.py | 55 8 * * 6 | ok | local | 2026-07-08 17:21 |
| 0764c6922694 | Deribit期权刷新 | deribit_options.py | 9 8,10,12,14,16,18,20,22 * * * | ok | local | 2026-07-11 10:09 |
| 54661a43c839 | **BTC守护看门狗** | monitor/btc_watchdog.py | */5 * * * * | ok | local | 2026-07-11 11:10 |
| f71dcf102007 | 每日复盘提醒 | daily_trade_review_reminder.py | 0 21 * * * | ok | local | 2026-07-09 21:00 |
| d6247e06ac30 | X情绪数据刷新 | x_sentiment_collector.py | 47 8,11,14,17,20 * * * | ok | local | 2026-07-10 14:47 |
| 5db6dd683b1d | 清算压力监控 | liquidation_collector.py | 12 8,10,12,14,16,18,20,22 * * * | ok | local | 2026-07-11 10:13 |
| 5f7192fd9029 | 稳定币供应监控 | stablecoin_collector.py | 35 */4 * * * | ok | local | 2026-07-10 16:35 |
| 155082fc5e34 | **数据新鲜度看门狗** | data_freshness_watchdog.py | 28 8,12,16,20 * * * | ok | local | 2026-07-10 16:28 |
| fd78e36de132 | QLib因子信号 | qlib_factors.py | 18 8,11,14,17,20 * * * | **error** (code 1) | local | 2026-07-10 17:18 |
| 2bcc03c1f524 | 交易执行桥接 | trade_exec_bridge.py | 27,57 * * * * | ok | local | 2026-07-11 10:57 |
| c6ad11110a80 | X情绪LLM分析 | x_sentiment_context.py | 17 8,11,14,17,20 * * * | ok | local | 2026-07-10 17:17 |
| eccf404b6c0a | 宏观Poly刷新 | macro_poly_refresh.py | 14 */4 * * * | ok | local | 2026-07-10 16:14 |
| 020e260f5ac0 | **行情守望看门狗** | monitor/market_watchdog.py | */3 * * * * | ok | local | 2026-07-11 11:12 |
| cb8a96b39fed | 每日运维聚合 | repo-maintenance/daily_ops_bundle.py | 40 6 * * * | ok | local | 2026-07-10 06:41 |
| 113655ad34b5 | XAU TV现场同步 | xau_tv_sync.py | */15 * * * * | ok | local | 2026-07-11 11:12 |
| 721d5b6e1c66 | 作战室融合信号 | signal_confluence.py | 17 9,12,15,18,21 * * * | ok | local | 2026-07-10 15:18 |
| f171ce3a818a | 黄金宏观刷新 | 黄金宏观.py | 20 */2 * * * | ok | local | 2026-07-11 10:20 |
| b78741992dfd | TV Desktop保活 | tv_keepalive.py | */10 * * * * | ok | local | 2026-07-11 11:10 |
| 8fe56a00eb8b | 影子结果标注 | shadow_outcome_labeler.py | */15 * * * * | ok | local | 2026-07-11 11:02 |

**关键观察**：
- 23 个活跃 cron，仅 `qlib_factors.py` 处于 error 状态（需暂停或修复）
- 多个高频 cron 撞车：`*/5` (BTC守护)、`*/3` (行情守望)、`*/10` (TV保活)、`*/15` (XAU/影子) 在 `:00/:15/:30/:45` 同时触发
- 仅 `Orion雷达` 配置了 `deliver=telegram:455`，其余均为 `local`（但脚本内部可能直连 TG，见下文）

---

## 2. 守护进程与心跳链路

### 2.1 BTC Daemon（`btc_daemon.py`）→ BTC Watchdog（`btc_watchdog.py`）

| 组件 | 角色 | 心跳文件 | 阈值 | 检查频率 | 重启方式 |
|---|---|---|---|---|---|
| btc_daemon.py | 15s 轮询 + 60s 深度评分 + 推送 | `.btc_daemon_heartbeat.json` | 120s | cron `*/5` | `start /B python` 后台拉起 |
| btc_watchdog.py | 读心跳 → 超时杀旧 PID → 重启 | 同上 | 120s | cron `*/5` | 同 |

**心跳样本**（2026-07-11 11:13:22）：
```json
{"ts":"2026-07-11T11:13:22.451759+08:00","zone":"VWAP测试区","score":2,"pid":12928}
```

**问题**：
- Daemon 每 15s 写心跳，Watchdog 5 分钟检查一次 → **最大失联发现延迟 5 分钟**
- 阈值 120s 偏紧，网络抖动易误触发重启
- `btc_watchdog.py` 使用 `start /B` 启动，**不等待进程就绪**，可能出现“心跳文件已写但进程未完全初始化”的竞态

### 2.2 行情守望（`行情守望.py`）→ 双重看门狗

| 看门狗 | 脚本 | 调度 | 心跳文件 | 阈值 | 重启方式 |
|---|---|---|---|---|---|
| market_watchdog.py (cron) | `monitor/market_watchdog.py` | `*/3 * * * *` | `monitor_heartbeat.json` | 300s | `start /B python` |
| watchdog.py (常驻后台) | `watchdog.py` | 守护进程 45s 轮询 | 同上 | 180s | `subprocess.Popen([python, 脚本])` |

**心跳样本**（2026-07-11 11:08:42）：
```json
{"time":"2026-07-11T11:08:42.380872+08:00","pid":1324,"status":"running","symbol":"EURUSD"}
```

**关键问题**：
1. **双看门狗职责重叠**：cron 版 3 分钟检查 + 常驻版 45 秒检查 → 同一心跳文件被两套逻辑读写，竞态条件必现
2. **`watchdog.py` 存在 `Popen.poll()` AttributeError Bug**（第 253-267 行）：
   ```python
   try:
       if proc.poll() is not None:  # Popen 对象在某些 Windows 环境不完整，无 .poll()
   except AttributeError:
       # 降级用 pid_alive(proc.pid) —— 但逻辑分支混乱，可能漏判
   ```
   导致 `启动失败: 'P' object has no attribute 'poll'` 反复出现（见 `watchdog.log` 大量记录）
3. **限流策略过于激进**：`MAX_RESTARTS_PER_HOUR=20` / `MAX_RESTARTS_EMERGENCY=30`，但“环境未就绪/卡死强杀”计入同一桶，导致真崩溃也被限流（日志中 `重启速率限制[卡死/环境未就绪]：3次/小时已达上限` 极其频繁）
4. **重启不等待就绪**：`time.sleep(float(os.environ.get("WATCHDOG_START_GRACE_SECONDS", "3")))` 仅 3 秒，行情守望冷启动需加载 trading_system、建立连接池，3 秒不够 → 心跳文件写入滞后 → 看门狗再次判定失联 → 循环重启

### 2.3 数据新鲜度看门狗（`data_freshness_watchdog.py`）

- Cron：`28 8,12,16,20 * * *`（每日 4 次）
- 检查 20 个数据文件的 mtime，阈值 0.1h~24h 不等
- **双落盘路径问题**：脚本同时检查 `D:/Hermes agent/data/` 和 `~/AppData/Local/hermes/data/`，取最新 mtime。但部分采集脚本只写其中一处 → 误判“过期”
- **TG 推送直连**：脚本内 `push_tg_rich("telegram:-1003733144325:846", output)` 绕过 cron `deliver=local`，**实际会推 TG**（见 pending 队列有 7/9 数据过期告警）

---

## 3. Telegram 投递链路审计

### 3.1 核心组件

| 文件 | 作用 | 关键特性 |
|---|---|---|
| `telegram_reliable.py` | 统一可靠推送入口 | 3 次重试指数退避、RichMarkdown 真表格、失败落盘 `pending_telegram.jsonl`、夜间静默(23-08h)、`flush_pending()` 补发 |
| `telegram_direct.py` | 兼容层，委托 `telegram_reliable` | 从 `.env` 读 token（解决子进程不继承环境变量问题）、默认 `parse_mode=RichMarkdown` |

### 3.2 投递目标路由（棠溪约定）

| 话题 ID | 用途 | 对应脚本 |
|---|---|---|
| 386 | BTC 信号/告警 | `btc_daemon.py`, `btc_push_386.py` |
| 385 | XAU 警报 | `行情守望.py` → `alert_target_for("XAUUSD")` |
| 416 | 其他警报/任务报告 | `行情守望.py` 默认、多数 cron 脚本 |
| 846 | 系统/维护/看门狗告警 | `btc_watchdog.py`, `market_watchdog.py`, `watchdog.py`, `data_freshness_watchdog.py` |

### 3.3 Pending 队列堆积（`data/pending_telegram.jsonl`）

```jsonl
{"created_at":"2026-07-06T17:36:27...","target":"telegram:-1003733144325:416","reason":"network: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]>"}
{"created_at":"2026-07-09T14:29:30...","target":"telegram:-1003733144325:846","reason":"network: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]>"}
{"created_at":"2026-07-09T14:33:33...","target":"telegram:-1003733144325:846","reason":"network: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]>"}
```

**问题**：
- 3 条消息堆积 2-5 天未清理，**无定时 `flush_pending()` 任务**
- 错误均为 SSL `SSL EOF → 网络抖动/代理中断，非 4xx 永久错误，**重试即可恢复**
- `flush_pending(limit=20)` 只在手动运行 `python telegram_reliable.py --flush` 时触发

### 3.4 Cron 脚本直连 TG 绕过 `deliver` 配置

经扫描以下脚本含 `send_telegram` / `telegram_direct` / `telegram_reliable` 直连调用：
- `btc_daemon.py` → `push_tg_rich` / `send_telegram_direct` → **386/385/416**
- `btc_card_gen.py` → `send_telegram_direct` → **386**
- `btc_watchdog.py` → `push_tg_rich` → **846**
- `market_watchdog.py` → `push_tg_rich` → **846**
- `watchdog.py` → `send_telegram_direct` + `hermes_cli.main send` → **416**
- `data_freshness_watchdog.py` → `push_tg_rich` → **846**
- `daily_trade_review_reminder.py` → `push_tg_rich` → **846**
- `orion_screener_radar.py` → `push_tg_rich` → **846**（但 cron 配置 `deliver=telegram:455`，双重投递）
- `btc_ref_levels_sync.py` → `push_tg_rich` → **846**
- `cot_collector.py` → `push_tg_rich` → **846**

**结论**：`deliver=local` 仅控制 cron 框架层的投递，**不拦截脚本内部直连**。审计必须“读 jobs.json + 扫脚本源码”双轨并行。

---

## 4. 发现的高优先级隐患（P0/P1）

| 编号 | 现象 | 根因 | 影响 | 建议修复 |
|---|---|---|---|---|
| P0-1 | `watchdog.py` 频繁 `AttributeError: 'P' object has no attribute 'poll'` | `subprocess.Popen` 返回对象不完整，`poll()` 不存在 | 看门狗误判启动失败 → 限流 → 真崩溃也救不活 | 统一用 `pid_alive(proc.pid)` 判断，移除 `poll()` 调用 |
| P0-2 | 双看门狗竞争同一心跳文件 | cron `*/3` + 常驻 45s 并发读写 `monitor_heartbeat.json` | 心跳解析异常、重启风暴 | 合并为单一看门狗（建议保留常驻 `watchdog.py`，禁用 cron `market_watchdog.py`） |
| P0-3 | 看门狗限流误伤真崩溃 | `emergency` 与普通重启共用小时桶，`MAX_RESTARTS_PER_HOUR=20` 太低 | 连续真崩溃被限流，服务不可用 | 分桶独立计数（已部分实现但阈值需调大），或引入“连续成功重置计数器” |
| P0-4 | 重启不等待就绪 → 心跳滞后 → 再次判死 → 循环 | `WATCHDOG_START_GRACE_SECONDS=3` 远小于冷启动时间 | 守护进程反复重启，日志刷屏 | 增加就绪探针：轮询心跳文件 `status==running` 且 `age<10s` 才算启动成功 |
| P1-1 | Pending TG 队列无自动清理 | 无 cron 定时调用 `flush_pending()` | 网络抖动导致的暂时失败永久堆积 | 新增 cron `5 * * * * python telegram_reliable.py --flush` |
| P1-2 | 高频 cron 同分钟撞车 | `*/5` `*/3` `*/10` `*/15` 全在 `:00/:15/:30/:45` | CPU/网络/API 速率争用，延迟抖动 | 错峰：`*/5→:02/:32`、`*/3→:01/:04/:07...`、`*/10→:03/:13...`、`*/15→:07/:22/:37/:52` |
| P1-3 | `qlib_factors.py` 持续 error | 脚本退出码 1，未暂停、未告警 | 占用调度槽位，日志噪音 | 暂停该 cron 或修复脚本；建议加 `max_consecutive_errors=3` 自动暂停 |
| P1-4 | Windows no_agent cron 编码乱码风险 | 无 `sys.stdout = io.TextIOWrapper(...utf-8...)` 兜底 | 中文/emoji 推送成 `馃煛 绔欏洖` | 所有 no_agent 脚本头部强制 UTF-8 stdout |

---

## 5. 立即可执行的修复清单

```bash
# 1. 修复 watchdog.py poll() Bug（P0-1）
# 编辑 D:\Hermes agent\scripts\watchdog.py 第 253-267 行
# 统一改为：
# if not pid_alive(proc.pid):  # 直接用 pid 判断，移除 try/except poll()

# 2. 禁用冗余 cron 看门狗（P0-2）
hermes cron delete 020e260f5ac0  # market_watchdog.py
# 保留 watchdog.py (常驻后台) 作为唯一守护

# 3. 调整看门狗限流与就绪等待（P0-3, P0-4）
# watchdog.py: MAX_RESTARTS_PER_HOUR=50, MAX_RESTARTS_EMERGENCY=100
# 增加启动后就绪轮询：最多等 30s 直到心跳 status=running 且 age<10s

# 4. 新增 TG pending 自动清理 cron（P1-1）
hermes cron create --name "TG pending flush" \
  --script "telegram_reliable.py" --args "--flush" \
  --no-agent "5 * * * *"

# 5. 错峰高频 cron（P1-2）
hermes cron update 54661a43c839 --schedule "2,32 * * * *"      # BTC守护 :02/:32
hermes cron update 020e260f5ac0 --schedule "1,31 * * * *"      # 已删除
hermes cron update b78741992dfd --schedule "3,13,23,33,43,53 * * * *"  # TV保活
hermes cron update 113655ad34b5 --schedule "7,22,37,52 * * * *"  # XAU TV
hermes cron update 8fe56a00eb8b --schedule "8,23,38,53 * * * *"  # 影子标注

# 6. 暂停故障 cron（P1-3）
hermes cron pause fd78e36de132  # qlib_factors.py

# 7. 补齐 no_agent 脚本 UTF-8 头（P1-4）
# 给所有 cron 脚本加：
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
```

---

## 6. 监控覆盖率矩阵（审计后更新）

| 组件 | 心跳写入 | 外部检查 | TG 告警 | 自动重启 | 备注 |
|---|---|---|---|---|---|
| btc_daemon | ✅ 15s | ✅ btc_watchdog (5min) | ✅ 重启推 846 | ✅ 杀进程重启 | 阈值 120s 偏紧 |
| 行情守望 | ✅ 10s | ⚠️ 双看门狗冲突 | ✅ 重启推 846 | ✅ 双重但冲突 | **需合并为单看门狗** |
| watchdog (元) | ❌ 无 | ❌ 无 | ❌ 无 | ❌ 无 | **单点故障** |
| data_freshness | N/A | N/A (cron) | ✅ 推 846 (直连) | N/A | 4次/天 |
| TG 推送链路 | N/A | ❌ pending 无监控 | N/A | ❌ 无自动 flush | **需补监控** |

---

## 7. 证据文件清单

| 文件 | 说明 |
|---|---|
| `C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json` | 全量 cron 定义 |
| `D:/Hermes agent/scripts/btc_daemon.py` | BTC Daemon 主逻辑 |
| `D:/Hermes agent/scripts/monitor/btc_watchdog.py` | BTC Watchdog (cron) |
| `D:/Hermes agent/scripts/watchdog.py` | 元看门狗 (常驻，**含 Bug**) |
| `D:/Hermes agent/scripts/monitor/market_watchdog.py` | 行情守望 Watchdog (cron，**冗余**) |
| `D:/Hermes agent/scripts/行情守望.py` | 核心监控进程 |
| `D:/Hermes agent/scripts/data_freshness_watchdog.py` | 数据新鲜度看门狗 |
| `D:/Hermes agent/scripts/telegram_reliable.py` | TG 可靠推送核心 |
| `D:/Hermes agent/scripts/telegram_direct.py` | TG 直连兼容层 |
| `D:/Hermes agent/data/.btc_daemon_heartbeat.json` | BTC Daemon 心跳样本 |
| `D:/Hermes agent/data/monitor_heartbeat.json` | 行情守望心跳样本 |
| `D:/Hermes agent/data/pending_telegram.jsonl` | TG 失败队列（3 条堆积） |
| `D:/Hermes agent/data/watchdog.log` | 看门狗历史（含大量限流/重启记录） |
| `C:/Users/Administrator/AppData/Local/hermes/cron/output/*/` | 各 cron 运行输出（silent=健康） |

---

> **下一步**：按优先级执行第 5 节修复清单，验证后再跑一次全量审计确认收敛。