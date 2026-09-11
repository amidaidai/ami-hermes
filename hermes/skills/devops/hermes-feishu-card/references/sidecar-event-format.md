# Sidecar Event Format

The sidecar accepts events via `POST http://127.0.0.1:8765/events`.

## Required Fields

| Field | Type | Note |
|-------|------|------|
| `schema_version` | string | Must be `"1"` |
| `event` | string | One of: `message.started`, `answer.delta`, `thinking.delta`, `tool.updated`, `message.completed`, `message.failed` |
| `conversation_id` | string | Non-empty |
| `message_id` | string | Non-empty, unique per message |
| `chat_id` | string | Non-empty, Feishu chat ID (e.g. `oc_xxx`) |
| `platform` | string | **Must be `"feishu"`** — sidecar rejects anything else |
| `sequence` | int | Non-negative, increments per event |
| `created_at` | float | Unix timestamp |
| `data` | object | Event-specific payload |

## Event Data by Type

### `message.started`
```json
{"data": {}}
```
Minimal — sidecar creates session but doesn't read text from here.

### `answer.delta`
```json
{"data": {"text": "card content here"}}
```
**This is where the card text goes.** Not in `message.started`.

### `message.completed`
```json
{
  "data": {
    "answer": "full text with MEDIA:C:/path/img.png",
    "duration_ms": 1500,
    "input_tokens": 2500,
    "output_tokens": 350
  }
}
```
The `answer` field triggers `_extract_attachments` for MEDIA: references.

## Python Snippet

```python
import json, time, urllib.request

def send_card(chat_id, text, mid=None):
    now = time.time()
    mid = mid or f"card_{int(now)}"
    events = [
        ('message.started', {}),
        ('answer.delta', {'text': text}),
        ('message.completed', {'answer': text}),
    ]
    for i, (evt, data) in enumerate(events):
        payload = {
            'schema_version': '1', 'event': evt,
            'conversation_id': chat_id, 'message_id': mid,
            'chat_id': chat_id, 'platform': 'feishu',
            'sequence': i, 'created_at': now + i,
            'data': data,
        }
        req = urllib.request.Request(
            'http://127.0.0.1:8765/events',
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=5)
```

## Limitations

- **No local file upload**: MEDIA: references are detected but the sidecar cannot upload local files to Feishu. Use gateway `send_message` for images.
- **Platform gate**: only `"feishu"` platform events are accepted.