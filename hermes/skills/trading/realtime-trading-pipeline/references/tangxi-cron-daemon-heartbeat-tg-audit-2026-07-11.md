# 棠溪系统：Cron / 守护进程 / 心跳 / TG 投递链 只读审计记录 (2026-07-11)

> 会话：只读审计 cron、daemon、heartbeat、TG delivery chain
> 关联技能：`system-ops` (完整审计报告见 `references/tangxi-cron-daemon-heartbeat-tg-audit.md`)

---

## 审计对象：realtime-trading-pipeline 架构的实部署情况

本技能描述的「双守护进程 + 看门狗」架构在 2026-07-11 实际部署中存在以下**偏离与隐患**：

| 架构组件 | 设计预期 | 实际部署 | 偏离/风险 |
|---|---|---|---|
| **行情守望** | 单一后台 daemon + 1 个 watchdog | **双看门狗**：cron `*/3` + 常驻 `watchdog.py` 45s 轮询 | ❌ 竞争同一心跳文件 `monitor_heartbeat.json`，导致心跳解析异常、重启风暴 |
| **BTC Daemon** | 15s 轮询 + 60s 深度评分，watchdog `*/5` | 同设计 | ⚠️ 阈值 120s 偏紧，网络抖动易误触发；watchdog 5min 检查 → 最大发现延迟 5min |
| **Watchdog 通用模式** | 杀旧 PID → 启动新 → 等待就绪 | `time.sleep(3)` 固定等待，**无就绪探针** | ❌ 进程启动未完成即判定成功 → 心跳滞后 → 再次被判死 → 循环重启 |
| **watchdog.py** | 标准 `subprocess.Popen` | **`Popen.poll()` AttributeError** (`'P' object has no attribute 'poll'`) | ❌ 导致「启动失败」日志刷屏，触发限流，真崩溃也救不活 |
| **TG 投递** | `deliver=local` 仅框架层 | **脚本直连绕过 `deliver`**：10+ 个脚本含 `telegram_reliable/direct` 直连 | ❌ 审计必须「读 jobs.json + 扫脚本」双轨并行 |
| **Pending 队列** | `flush_pending()` 定时清理 | **无任何 cron 调用 flush** → 3 条 SSL 失败消息堆积 2-5 天 | ❌ 网络恢复后历史告警永不补发 |

---

## P0 级必须修复（阻塞可用性）

1. **合并双看门狗**：禁用 cron `market_watchdog.py` (020e260f5ac0)，仅保留常驻 `watchdog.py`
2. **修复 `poll()` Bug**：`watchdog.py` 统一用 `pid_alive(proc.pid)` 替代 `proc.poll()`
3. **增加就绪探针**：启动后轮询心跳文件 `status==running && age<10s`，最长等 30s
4. **分桶限流**：`emergency`(真崩溃) 与 `normal`(卡死/环境) 独立计数、独立阈值
5. **新增 flush cron**：`5 * * * * python telegram_reliable.py --flush`

---

## P1 级本周修复

| 项 | 现状 | 目标 |
|---|---|---|
| 高频 cron 撞车 | `*/5` `*/3` `*/10` `*/15` 全在 `:00/:15/:30/:45` | 错峰：`*/5→:02/:32`、`*/3→:01/:04...`、`*/10→:03/:13...`、`*/15→:07/:22/:37/:52` |
| qlib_factors 持续 error | `last_status=error` 仍按计划调度 | 暂停或加 `max_consecutive_errors=3` 自动暂停 |
| no_agent 编码乱码风险 | 无 UTF-8 强制头 | 所有 cron 脚本头部加 `sys.stdout = io.TextIOWrapper(..., encoding="utf-8")` |
| 双落盘路径误报 | `data_freshness_watchdog` 取最新 mtime | 统一落盘目录或改「全路径均需满足阈值」 |

---

## TG 投递审计「双轨制」验证清单

| 轨道 | 动作 | 本次审计发现 |
|---|---|---|
| **框架层** | `jq '.jobs[] | select(.deliver=="telegram")'` | 仅 Orion 雷达配置 `deliver=telegram:455` |
| **脚本层** | `grep -r "telegram_reliable\|telegram_direct\|api.telegram.org\|send_telegram" scripts/` | **10+ 脚本直连**，绕过 `deliver=local`，**实际全推 TG** |
| **话题路由** | 核对 `push_tg_rich` 目标参数 | 386/385/416/846 四话题分流已按约定实施 |

> **结论**：不能只信 `jobs.json` 的 `deliver` 字段，**必须双轨并行审计**。

---

## 监控覆盖率矩阵（审计后更新）

| 组件 | 心跳写入 | 外部检查 | TG 告警 | 自动重启 | 备注 |
|---|---|---|---|---|---|
| btc_daemon | ✅ 15s | ✅ btc_watchdog (5min) | ✅ 重启推 846 | ✅ | 阈值 120s 偏紧 |
| 行情守望 | ✅ 10s | ⚠️ 双看门狗冲突 | ✅ 重启推 846 | ✅ 冲突 | **需合并为单看门狗** |
| watchdog (元) | ❌ 无 | ❌ 无 | ❌ 无 | ❌ 无 | **单点故障** |
| data_freshness | N/A | N/A (cron) | ✅ 推 846 (直连) | N/A | 4次/天 |
| TG 推送链路 | N/A | ❌ pending 无监控 | N/A | ❌ 无自动 flush | **需补监控** |

---

## 关键文件速查

| 文件 | 角色 |
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
| `D:/Hermes agent/data/pending_telegram.jsonl` | TG 失败队列 (3 条堆积) |
| `D:/Hermes agent/data/watchdog.log` | 看门狗历史 (大量限流/重启记录) |

---

## 后续行动

按 `system-ops/references/tangxi-cron-daemon-heartbeat-tg-audit.md` 第 5 节「立即可执行的修复清单」逐项执行，验证后再跑一次全量审计确认收敛。