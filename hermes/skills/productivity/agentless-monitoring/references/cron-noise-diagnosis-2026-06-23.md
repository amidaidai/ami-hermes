# Cron 噪音诊断 + 状态文件修复 (2026-06-23)

## 场景
用户被多个 agent-mode cron 推送的 X 级/冲突信号持续打扰，说"没有确定的机会不要推我"。

## 诊断步骤
1. `cronjob(action='list')` — 列出所有 cron，关注:
   - `deliver: origin` 或 `telegram:*:*` 的（推送到用户群）
   - `last_status: ok` 但不一定是用户想要的输出
   - `schedule` 频率（每2分/5分/15分 → 高频噪音候选）
2. 检查每个候选 cron 的 `prompt_preview` — agent mode 中写了"无事件静默"也可能自发生成分析
3. 用户明确说"不要推" → 直接 `cronjob(action='pause', job_id=...)` 暂停所有噪音源

## 根治方案
1. 市场监控只用 **no_agent 脚本**（确定性条件触发）
2. 深度分析只在用户要求时手动拉 TV MCP
3. 看门狗触发三条件可选：前低/L2/反弹做空区

## 状态文件路径修复
**Bug**: `os.path.join(os.path.dirname(__file__), ".state.json")` 在 cron 环境不可写
**Fix**: `os.path.expanduser("~/AppData/Local/hermes/data/.state.json")`
**验证**: `ls ~/AppData/Local/hermes/data/.state.json` 文件存在则证明路径正确

## 清理清单
| 动作 | 命令 |
|------|------|
| 暂停噪音 cron | `cronjob(action='pause', job_id='xxx')` |
| 停掉的旧脚本 | 确认 `btc_push_cron.py` 依赖的 `mcp` SDK 在 no_agent 下不可用 |
| 清除旧状态文件 | `rm -f ~/.hermes/scripts/.btc_watchdog_state.json` |
| 确认看门狗正常 | `cronjob(action='list')` → `last_status: ok` |
