# v6.9 模板机器字段与 auto_card 接入

本参考记录棠溪分析卡模板从“人读卡片”升级为“人读 + 机器可追踪协议”的落地方式。

## 核心原则

① 保留五段骨架：环境、结构、博弈、操作、风控。
② 不把模板变长为目的；只增加可验证、可执行、可复盘字段。
③ 每张卡必须能串联：出卡 → 计划 → 监控 → 触发 → 复盘 → 模型统计。
④ 社区情绪、Grok、搜索情绪只验证/挑战结构，不覆盖结构方向。

## 机器字段

每张 auto_card 本地卡片必须生成并保存：

```text
setup_id
model_id
entry_tag
exit_tag
direction
status
priority_plan
data_grade
level_confidence
engine_confidence
confidence_5
risk_usd
rr1
rr2
invalid_price
expires_at
monitor_write
```

推荐 `setup_id` 格式：

```text
{SYMBOL}-{model_id}-{YYYYMMDD-HHMMSS}
```

示例：

```text
BTCUSDT-VAL回收-20260618-205128
```

## auto_card 接入要求

`hermes/scripts/auto_card.py` 或其后续等价出卡管线应具备：

① `build_setup_metadata()`：生成机器字段。
② `render_machine_fields()`：把机器字段写入本地 markdown 卡片。
③ `append_trade_plan()`：追加写入 `data/trade_plans.jsonl`。
④ `update_monitor_metadata()`：写入 `data/monitor_levels.json` 的 `symbols.{symbol}.latest_setup`。
⑤ `validate_card_rules()`：模板铁律检查。
⑥ `sanitize_card_format()`：清理装饰 emoji、方括号热词等格式违规。

## 模板铁律自动检查

至少检查：

① `B等待` 禁止输出具体入场/止损/止盈价格，只能写触发条件。
② `R:R < 1:2` 必须阻断或标记 X禁做。
③ `setup_id/model_id/entry_tag/exit_tag` 必填。
④ 分析卡正文禁止装饰 emoji、方括号标签、表格、`｜`。

## 监控闭环

出卡后 `monitor_levels.json` 应记录：

```json
{
  "latest_setup": {
    "setup_id": "...",
    "model_id": "...",
    "entry_tag": "...",
    "exit_tag": "...",
    "direction": "short",
    "status": "B等待",
    "priority_plan": "无",
    "data_grade": "A",
    "level_confidence": 70,
    "engine_confidence": 0.7,
    "confidence_5": 3,
    "expires_at": "...",
    "monitor_write": true
  }
}
```

下一步链路应让 `行情守望.py` 触发告警时读取 `latest_setup`，并把 `setup_id/model_id/entry_tag/trigger_level/trigger_price/event_type` 写入 `trade_events.jsonl`。

## 验证命令

```bash
python -m py_compile hermes/scripts/auto_card.py
python hermes/scripts/auto_card.py BTCUSDT
python -m pytest tests/test_auto_card_machine_fields.py tests/test_auto_card_format_sanitize.py -q
python -m pytest -q
```

合格信号：

① 卡片含 `**机器字段**`。
② `trade_plans.jsonl` 最新行含 `setup_id/model_id/entry_tag/exit_tag`。
③ `monitor_levels.json` 对应品种含 `latest_setup`。
④ 全量测试通过。
