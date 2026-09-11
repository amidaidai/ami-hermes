# Telegram 投递审计双轨制清单

> 场景：用户问"我的任务有哪些推到 Telegram / 为什么不推 / 哪些推了"。**不能只看 cron 的 `deliver` 字段**，必须双轨并行审计。

## 双轨审计法

### 轨道 1：Cron 框架层 (`jobs.json`)

```bash
# 1. 拉取全量 cron
cronjob(action='list')

# 2. 筛选 deliver=telegram 的任务
jq '.jobs[] | select(.deliver=="telegram") | {id,name,script,schedule,deliver,origin}'
```

**局限**：`deliver=local` ≠ 不推 Telegram。脚本内部可能直连 Bot API。

---

### 轨道 2：脚本源码层（直连扫描）

对每个 cron 的 `script` 字段，扫描以下特征：

| 特征 | 搜索命令 | 说明 |
|---|---|---|
| `send_telegram` | `grep -r "send_telegram" scripts/` | Hermes CLI 封装 |
| `api.telegram.org` | `grep -r "api.telegram.org" scripts/` | 直连 Bot API |
| `telegram_direct` | `grep -r "telegram_direct" scripts/` | `telegram_direct.py` 兼容层 |
| `telegram_reliable` | `grep -r "telegram_reliable" scripts/` | 可靠推送库 |
| `push_tg_rich` | `grep -r "push_tg_rich" scripts/` | RichMarkdown 真表格推送 |
| `TARGET = "telegram:` | `grep -r 'TARGET = "telegram:' scripts/` | 硬编码目标 |

**输出格式**：
```
脚本路径 | 直连方式 | 目标话题 | 触发条件 | 是否受 deliver 控制
```

---

### 常驻 Daemon 单独审计

Cron 之外，常驻后台进程同样会推 TG，**不在 `jobs.json` 中**：

| 进程 | 心跳文件 | 推送入口 | 目标话题 |
|---|---|---|---|
| `btc_daemon.py` | `.btc_daemon_heartbeat.json` | `push_tg()` → `send_telegram_direct` | 386 |
| `行情守望.py` | `monitor_heartbeat.json` | `push()` → `telegram_direct` | 385/386/416/846 |
| `watchdog.py` | `watchdog_heartbeat.json` (无) | `send_watchdog_alert()` | 416 |

**审计动作**：
1. `ps aux | grep -E "btc_daemon|行情守望|watchdog"` 确认存活
2. 读对应源码，确认推送路径与话题
3. 检查是否有 `HANGQING_NO_SEND=1` 抑制开关

---

### 手动/一次性脚本

搜索项目内所有 `.py` 的 `send_telegram`/`telegram_direct`/`push_tg_rich` 调用，排除上述 cron/daemon 已覆盖的，剩余即为手动/一次性推送入口。

---

## 审计报告模板

```markdown
## Telegram 投递全景审计报告

### Cron 框架层 (deliver=telegram)
| Job ID | 名称 | 脚本 | Schedule | Origin Thread | 受控 |
|---|---|---|---|---|---|
| abc123 | Orion雷达 | orion_screener_radar.py | 2 8,10... | 455 | ✅ |

### 脚本直连层 (绕过 deliver)
| 脚本 | 方式 | 目标 | 触发条件 | 受控 |
|---|---|---|---|---|
| btc_daemon.py | telegram_direct | 386 | 评分≥8 且 非冷却 | ❌ |
| 行情守望.py | telegram_direct | 385/386/416 | 警报/计划触发 | ❌ |
| data_freshness_watchdog.py | push_tg_rich | 846 | 有过期文件 | ❌ |
| btc_ref_levels_sync.py | push_tg_rich | 846 | 关键位更新 | ❌ |

### 常驻 Daemon
| 进程 | 心跳 | 目标话题 | 抑制开关 |
|---|---|---|---|
| btc_daemon.py | .btc_daemon_heartbeat.json | 386 | 无 |
| 行情守望.py | monitor_heartbeat.json | 385/386/416/846 | HANGQING_NO_SEND=1 |

### 结论与建议
- 共有 **N** 条投递路径，**M** 条受 cron `deliver` 控制，**K** 条直连
- 建议：将直连脚本的目标话题统一由 `alert_target_for(symbol)` / `report_target()` 路由
- 增加统一抑制开关 `TELEGRAM_SILENT=1` 供维护窗口使用
```

---

## 检查工具化

```bash
# 一键扫描所有脚本的 TG 直连调用
grep -r -E "send_telegram|telegram_direct|telegram_reliable|push_tg_rich|api\.telegram\.org" \
  --include="*.py" scripts/ | \
  grep -v "__pycache__" | \
  awk -F: '{print $1}' | sort -u
```

将输出逐个读源码确认目标话题与触发条件。