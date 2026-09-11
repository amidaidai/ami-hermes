# 棠溪数据新鲜度看门狗排查与降噪

适用场景：用户反馈“数据过期告警还发 Telegram”“怎么还有过期”“看门狗误报”等。

## 核心判断

1. 先查 cron 路由：`hermes cron list --all` 或读 `~/AppData/Local/hermes/cron/jobs.json`，确认 `数据新鲜度看门狗` 的 `deliver`。
2. 对棠溪偏好，数据新鲜度属于后台体检，默认 `deliver=local`；除非用户明确要求基础设施异常进群，否则不要推 Telegram。
3. 手动运行脚本验证：`python scripts/data_freshness_watchdog.py`。健康时 stdout 必须为空。

## 双落盘路径陷阱

棠溪系统有两套常见数据目录：

- 项目目录：`D:/Hermes agent/data/`
- Hermes 运行目录：`C:/Users/Administrator/AppData/Local/hermes/data/`

很多实时文件写在项目目录，而部分采集脚本写在 Hermes 目录。新鲜度检查不能只看其中一个目录；应对每个文件列出候选路径，取存在文件中的最新 mtime。

典型映射：

| 数据 | 优先路径 |
|---|---|
| `btc_ref_levels.json` | 项目目录 + Hermes目录，取最新 |
| `tv_dmi_cache.json` | 项目目录 + Hermes目录，取最新 |
| `monitor_heartbeat.json` | 项目目录优先 |
| `.btc_daemon_heartbeat.json` | 项目目录 |
| `macro_snapshot.json` | Hermes目录优先 |
| `polymarket_sentiment.json` | Hermes目录优先 |

## 废弃/替代文件

- 不要再把 `fast_daemon_state.json` 当 BTC daemon 新鲜度依据；优先看 `D:/Hermes agent/data/.btc_daemon_heartbeat.json`。
- XAU/行情守望心跳仍看 `D:/Hermes agent/data/monitor_heartbeat.json`。

## 真过期的常见补救

- `macro_snapshot.json` / `polymarket_sentiment.json` 真过期：确认是否有本地 no_agent 采集任务，例如 `宏观Poly刷新`：
  - script: `macro_poly_refresh.py`
  - schedule: `14 */4 * * *`
  - deliver: `local`
- `btc_ref_levels.json` 旧：确认 `BTC关键位同步` 是否实际写入项目目录，或让 watchdog 同时读取项目目录。
- `tv_dmi_cache.json` 旧：确认 `行情守望.py` / `tv_data_bridge.py` 是否仍在刷新项目目录。

## Windows Git-Bash PowerShell 进程排查坑

在 Git-Bash 中内联 PowerShell 使用 `$_.CommandLine` 容易被 MSYS/bash 展开，出现 `D:/Hermes agent.$_.CommandLine` 或 `2.CommandLine`。复杂进程过滤优先写临时 `.ps1`，或者用 Python `subprocess.run(['powershell.exe', ...])` 包装，不要直接在 bash 双引号中写 `$_.CommandLine`。

## 验证清单

- `python -m py_compile scripts/data_freshness_watchdog.py`
- `python scripts/data_freshness_watchdog.py | wc -c` 应为 `0`（健康静默）
- `hermes cron list --all` 中 `数据新鲜度看门狗` 应为 `deliver: local`（棠溪偏好）
- 如清理 daemon，多实例检查后只保留一个实际心跳更新的进程，且 `btc_watchdog.py` 健康输出为 0 字节。
