# TV Cron 噪音修复 (2026-06-21)

## 症状
cron "TV信号监控·智能推送" 输出30行详细LLM报告到Telegram，包含：
- 脚本退出码 rc=1
- "已修复"恢复步骤
- DMI决策表详情
- 行动建议

## 根因
旧cron (116223704b57) 实际运行在 **agent模式**（非no-agent）。
脚本失败(rc=1)时LLM自动诊断修复并生成报告→全文投递到Telegram。

`hermes cron list` 显示 `Mode: no-agent` 可能不准确——cron创建时未显式指定`--no-agent`。

## 修复

1. **删除旧cron**：`hermes cron remove 116223704b57`

2. **重建为显式no-agent**：
```
hermes cron create --name "TV信号监控·静默" \
  --script "scripts/tv_signal_monitor_wrapper.py" \
  --workdir "D:/Hermes agent" \
  --no-agent \
  --deliver "telegram:-1003733144325:416" \
  "*/15 * * * *"
```

3. **wrapper v1.2 完全静默**：
```python
# 正常：stdout/stderr全吞，零输出
# 异常：仅单行 "⚠ TV采集失败(rc=N): {reason[:80]}"
# 超时：单行 "⚠ TV采集超时30s"
```

## 通用教训
- 任何cron创建必须显式 `--no-agent` 标志
- `hermes cron list` 显示的Mode可能不反映实际行为
- no-agent模式：空stdout=静默，有stdout=投递
- agent模式：任何响应都会投递（包括LLM诊断文本）

## 验证
```bash
hermes cron list | grep TV信号
# → Mode: no-agent (script stdout delivered directly)
```
