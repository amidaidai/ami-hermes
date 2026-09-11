---
name: feishu-analysis-card-sender
description: 通过 sidecar API 直发飞书卡片（绕过社区 hook），分析文字走卡片，截图走 gateway MEDIA 引用。
---

# 飞书分析卡发送

社区 `hermes-feishu-streaming-card` 的 gateway hook 因兼容性问题不工作（platform 检测/editable install 路径等）。
采用**直发 sidecar API** 方案替代。

## 全渠道格式同步

飞书卡片正文与 Telegram/Discord/本地报告使用同一手机端格式铁律：

| 规则 | 要求 |
|---|---|
| 首行 | 直接给方向/状态/中文时间 |
| 表格 | 恰好3张真实Markdown管道表 |
| 宽度 | 每表≤3列，避免手机横向滚动 |
| 禁止 | 假表格、文字对齐、4列以上宽表、长段落、尾注总结 |
| 图片 | 先发 MEDIA 截图，再发卡片正文 |

飞书 sidecar 会把 Markdown 文本渲染为卡片内容；因此分析文字不要做飞书专用宽表，不要使用文字对齐伪表格。

## 已知 Chat ID

| 目标 | Chat ID |
|------|---------|
| 棠溪 DM | `oc_c4500490614a85b9b5db83f3f25b626a` |
| 分析群 | `oc_1dac3242c001625735760f54c579b7ec` |

用 `send_message(action='list')` 获取完整列表。

## 发送流程（完整）

1. **截图** → gateway `send_message` → `MEDIA:<path>` 到飞书（先发，图需上传时间）
2. **卡片文字** → POST 到 `127.0.0.1:8765/events` → `message.started` → `answer.delta` → `message.completed`

⚠ 顺序重要：先发图再发卡。图走 gateway 上传需要时间，如果先发卡用户会先看到空卡片。

## 事件格式

```python
import json, time, urllib.request

now = time.time()
mid = 'card_' + str(int(now))  # 唯一 ID
cid = 'oc_c4500490614a85b9b5db83f3f25b626a'  # DM chat_id

events = [
    ('message.started', {}),
    ('answer.delta', {'text': card_content}),
    ('message.completed', {
        'answer': card_content,
        'duration_ms': 1500, 'input_tokens': 2000, 'output_tokens': 300
    }),
]

for i, (evt, data) in enumerate(events):
    payload = {
        'schema_version': '1', 'event': evt,
        'conversation_id': cid, 'message_id': mid,
        'chat_id': cid, 'platform': 'feishu',
        'sequence': i, 'created_at': now + i,
        'data': data
    }
    req = urllib.request.Request('http://127.0.0.1:8765/events',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    urllib.request.urlopen(req, timeout=5)
```

## 前提条件

- sidecar 运行中：`python -m hermes_feishu_card.runner --config ~/.hermes_feishu_card/config.yaml`
- `hermes_feishu_card` 已安装到 bundled Python site-packages
- 端口 8765 可访问

## 注意事项

- **截图无法在卡片内展示**：sidecar 无本地文件上传能力。MEDIA: 引用在卡片 text 中会被解析为 attachment metadata 但不会实际上传。**分离发送**：卡片文字走 sidecar API，截图单独走 gateway `send_message`。
- **`message.completed` 的 `answer` 必须包含全文**：sidecar 从 `message.completed.data.answer` 字段提取 attachments 和 footer 统计（tokens/duration/model）。即使 `answer.delta` 已包含全文，`message.completed` 也必须重复 `answer` 字段。
- **`answer.delta` 是文字渲染来源**：sidecar 只从 `answer.delta.data.text` 读取并渲染卡片文字。`message.started.data.text` 会被忽略。
- 每次用新 `message_id`，避免 sidecar session 冲突
- 发往群聊时 chat_id 改为群 chat_id
- sidecar 必须在运行：`python -m hermes_feishu_card.runner --config ~/.hermes_feishu_card/config.yaml`
- **`platform` 必须硬编码为 `"feishu"`**，否则 sidecar 返回 400 拒绝
- **文字必须在 `answer.delta` 事件里发送**，`message.started` 的 data 不会被渲染成卡片内容
- sidecar 必须运行：先用 `python -c "urllib.request.urlopen('http://127.0.0.1:8765/health')"` 确认
- 此方式与 `tradingview-indicator-analysis` 分析模板配套使用
