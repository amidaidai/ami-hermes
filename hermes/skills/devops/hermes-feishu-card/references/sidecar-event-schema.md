# Sidecar 事件格式（用于直接 POST 到 127.0.0.1:8765/events）

> 仅在 gateway hook 不可用时使用（主动推送分析卡、Web UI 会话中发卡等）。
> 正常飞书对话回复走 gateway hook，不需要手动构造事件。

## 必填字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `schema_version` | string | 固定 `"1"` | `"1"` |
| `event` | string | 事件类型，顺序：`message.started` → `answer.delta` → `message.completed` | `"answer.delta"` |
| `conversation_id` | string | 会话 ID，任意唯一值 | `"card_1726543210"` |
| `message_id` | string | 消息 ID，同一对话内唯一 | `"card_1726543210"` |
| `chat_id` | string | 飞书 chat_id（DM 或群） | `"oc_c4500490614a85b9b5db83f3f25b626a"` |
| `platform` | string | **必须硬编码 `"feishu"`**，否则 400 拒绝 | `"feishu"` |
| `sequence` | int | 事件序号，从 0 递增 | `0` |
| `created_at` | float | Unix 时间戳（秒） | `1726543210.123` |
| `data` | object | 事件载荷，随 `event` 变化 | 见下表 |

## data 载荷（随 event 变化）

| event | data 必填字段 | 说明 |
|-------|--------------|------|
| `message.started` | `{}` | 空对象即可，内容不被渲染 |
| `answer.delta` | `{"text": "..."}` | **卡片正文必须放这里**，Markdown 格式 |
| `message.completed` | `{"answer": "...", "duration_ms": 1500, "input_tokens": 2000, "output_tokens": 300}` | `answer` 必须包含全文（用于提取 MEDIA attachment、footer 统计） |

## 完整示例（Python）

```python
import json, time, urllib.request

CID = 'oc_c4500490614a85b9b5db83f3f25b626a'
now = time.time()
mid = 'card_' + str(int(now))
body = "**标题**\n\n| A | B |\n|---|---|\n| 1 | 2 |"

events = [
    ('message.started', {}),
    ('answer.delta', {'text': body}),
    ('message.completed', {'answer': body, 'duration_ms': 1200,
                           'input_tokens': 2000, 'output_tokens': 300}),
]

for i, (evt, data) in enumerate(events):
    payload = {
        'schema_version': '1', 'event': evt,
        'conversation_id': CID, 'message_id': mid,
        'chat_id': CID, 'platform': 'feishu',
        'sequence': i, 'created_at': now + i,
        'data': data
    }
    req = urllib.request.Request(
        'http://127.0.0.1:8765/events',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=10) as r:
        print('seq=%d %-18s -> %s' % (i, evt, r.read().decode()[:120]))
```

## 关键约束

1. **`platform` 必须是 `"feishu"`** —— sidecar 严格校验，其他值直接 400
2. **卡片正文只走 `answer.delta.data.text`** —— `message.started.data.text` 会被忽略
3. **`message.completed.data.answer` 必须包含全文** —— sidecar 从这里提取 MEDIA attachment 和 footer 统计
4. **每次用新 `message_id`** —— 避免 sidecar session 冲突
5. **`message.completed` 的 `answer` 必须重复全文** —— 即使 `answer.delta` 已含全文
6. **截图不能在卡片内展示** —— sidecar 无本地文件上传能力；MEDIA: 引用在卡片 text 中会被解析为 attachment metadata 但不会实际上传。**分离发送**：卡片文字走 sidecar API，截图单独走 gateway `send_message`

## 响应格式

```json
{"ok": true, "applied": true, "delivery": {"outcome": "delivered"}}
```

失败示例：
```json
{"ok": false, "error": "missing required field: platform"}
{"ok": false, "error": "platform must be 'feishu'"}
```
