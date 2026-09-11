# 2026-07-01 全方位复审闭环模式

适用：用户要求“再来一次齐全的全方位审计和检查”或修复后要求复审。

## 必跑证据链

1. 运行态：`hermes --version`、`hermes doctor`、`hermes status --all`、Gateway PID、git status/diff stat。
2. MCP：至少测 `tradingview` 与 `binance`，记录连接耗时和工具数。
3. 守护心跳：`data/monitor_heartbeat.json`、`data/.btc_daemon_heartbeat.json`，要求 <5分钟。
4. cron：列出 total/active/errors/non-ok、LLM cron、脚本路径解析、排期分钟分组。
5. 数据新鲜度：source snapshots、TV live/DMI cache、protections、strategy stats、orion、x_sentiment 等；区分“交易主快照新鲜”和“TV现场缓存过期”。
6. 结构检查：`protections_state.json` 必须 `json.load` 后为 dict；检查关键字段。
7. 回归：`python -m py_compile ...` + `python scripts/regression_system_audit.py`。
8. 实测：`timeout 180 python scripts/auto_card.py BTCUSDT` 和 `XAUUSD`，保存完整stdout，不用 grep 过滤。
9. XAU污染验证：XAU输出必须出现“品种不匹配”拒绝 BTC TV cache，且不得出现 59k/60k BTC价位。
10. 静态质量：重复脚本、UTF-8 stdout候选、硬编码余额、diff新增行安全扫描。
11. 报告：写 `outputs/system-audit/full_<timestamp>/REPORT.md`，最后 `test -s` + `wc -l` + 证据文件列表。

## 关键坑

- 如果 Git-Bash heredoc/引号导致辅助扫描脚本失败，不要沿用失败结果；改用 `execute_code` 或 Python one-liner 重跑并保存证据。
- cron 的 `schedule` 可能是 dict，不要直接 `str(schedule).split()[0]` 当分钟；先取 `schedule['expr']`。
- AppData data 与项目 data 可能分裂：缺文件不等于采集失败，需搜两个位置。
- 审计结论必须把 P0/P1/P2 分开，P0=0 时也要明确写出来。
