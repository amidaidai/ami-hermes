# 监控警报 v7.5+ 回归验证与维护笔记

适用场景：修改 `行情守望.py`、监控模板、推送路由、结构更新、持仓监测 cron 后的验证。

## 必查项

1. **渲染卡片不能泄漏机器枚举**
   - `render_message(..., urgency="critical")` 的正文不应出现 `动作：critical`、`warning`、`info` 等机器枚举。
   - 应映射成人读操作建议，例如：`突破/触发后先等回踩确认；未确认前不追第一根`。

2. **新结构 `monitor_levels_v2` 要按 `symbols` 读取**
   - 当前 `data/monitor_levels.json` 结构为：`schema/updated/symbols/{SYMBOL}/levels`。
   - 测试脚本不要再只读旧路径 `raw["levels"]`；守望主循环用 `iter_symbol_blocks(raw)` 兼容新旧结构。

3. **突破后必须原地重算结构**
   - 突破/critical 触发后调用 `auto_refresh_structure()`，直接用 `智能更新结构.build_levels_v2()` 重算并写回当前 symbol 的 `levels`。
   - 成功日志应类似：`突破自动重算 BTCUSDT: 3个新结构位 @ 62612.49`。
   - 设 10 分钟/品种冷却，避免来回突破导致结构反复抖动。

4. **警报路由和任务报告分离**
   - BTC → `telegram:-1003733144325:386`
   - XAU → `telegram:-1003733144325:385`
   - 其他警报 → `telegram:-1003733144325:416`
   - 巡检/复盘/持仓监测/心跳 → `telegram:-1003733144325:846`

5. **Hermes cron no_agent 脚本路径限制**
   - `cronjob(..., no_agent=True, script=...)` 的 `script` 必须是 `~/.hermes/scripts/` 下的相对文件名，不能传 `D:/...` 绝对路径。
   - 如果项目脚本在 `D:/Hermes agent/scripts/`，在 `~/.hermes/scripts/` 写 wrapper：
     ```python
     import runpy
     runpy.run_path(r"D:/Hermes agent/scripts/持仓监测.py", run_name="__main__")
     ```
   - wrapper 直接运行成功后，再等 cron 下一轮确认 `last_status: ok`；不要连续盲跑同一个 cron。

6. **重启验证**
   - 修改 `行情守望.py` 后必须杀旧 PID、删除 lock/heartbeat、用 Hermes venv python 重启。
   - 验证：`monitor.lock`、`monitor_heartbeat.json`、`monitor.log` 同时正常。
   - 启动日志应显示当前版本，例如：`实时监控 v7.5 | 10s | ...`。

## 推荐回归流程

1. `py_compile` 检查改动文件。
2. 用真实 `data/monitor_levels.json` 渲染 BTC/XAU 样例卡。
3. assert 卡片不含 `动作：critical`、`动作：warning` 等枚举。
4. 检查 `关键位全景` 是否显示阻1/阻2/支1/支2，并标出 `◀ 已触发`。
5. 重启守望，等 10 秒以上确认心跳年龄小于 30 秒。
6. 列 cron，确认警报/报告路由和 no_agent 状态。
