# Windows + Hermes 任务合并与运行时降噪参考

适用场景：用户反馈 Hermes/Windows 后台任务太多、卡顿，或系统体检后需要执行 P0/P1 修复。

## 关键经验

1. 先盘点再停用：同时采集 Hermes cron、Windows 计划任务、启动项、高频进程、监听端口，避免只凭任务名误删。
2. Hermes cron 优先“合并/降频”，不要一上来删除：重复数据源任务可暂停；高频 agent 任务优先降频；no-agent 脚本任务优先保留。
3. 对交易监控类任务，避免同一品种由多个任务重复轮询。例如 XAUUSD 已由主行情守望进程覆盖时，可暂停单独黄金到价监控。
4. 高频维护任务容易造成卡顿：每 1 分钟跑一次的巡检/治理任务，如果内部还会触发系统体检、智能更新、健康检查，应降为 3 分钟或更低频，并把每日治理合并到每日验证/清理守护。
5. Watchdog 防重启风暴：不要设置过短心跳超时。可采用 `CHECK_INTERVAL=45`、`STALE_SECONDS=180`、普通重启 `2次/小时`、崩溃重启 `4次/小时` 作为保守默认。
6. Dashboard/http.server 必须绑定本机：用 `python -m http.server 8766 --bind 127.0.0.1 --directory data`，并验证 `Get-NetTCPConnection` 只显示 `127.0.0.1:8766`。
7. 业务端口绑定 `0.0.0.0`/`::` 时，优先加显式 Block 防火墙规则，再考虑改服务绑定地址。常见规则名可用 `Anhe Block ...`，方便审计识别。
8. 清理空转进程时要注意 Hermes terminal/background 进程可能形成 bash 包裹 + venv python + uv python 的重复树；验证时用命令行模式过滤，避免把当前审计命令本身误判为残留长期进程。
9. Windows 安全软件与 Defender 并存时，不要硬改注册表。若 `WinDefend` 服务能启动但 `Set-MpPreference` 报 `0x800106ba` 且 `AntivirusEnabled=False`，通常需要用户在 360/Defender 中二选一确认接管关系。

## 典型合并策略

- 保留：持仓监测、核心信号巡检、每日验证、清理守护、自动标注复盘。
- 降频：`every 1m` 的巡检类任务通常先降为 `every 3m`。
- 暂停：与主行情守望重复的单品种到价监控、与每日验证重复的每日治理。
- 禁用开机噪音：非必要远控、Debug 启动项、压缩软件 updater 等。

## 验证清单

- `hermes cron status` 显示 Gateway running。
- `hermes cron list` 中 active job 数下降，且关键任务最近运行 ok。
- `python -m py_compile` 验证修改过的脚本。
- `Get-NetTCPConnection` 验证 8766 为 `127.0.0.1`。
- 本机 curl 验证 dashboard 返回 200。
- `Get-NetFirewallRule` 验证关键 Block 规则 enabled。
- 日志尾部不再新增已修复的数据源错误；历史错误不要当作当前失败。
