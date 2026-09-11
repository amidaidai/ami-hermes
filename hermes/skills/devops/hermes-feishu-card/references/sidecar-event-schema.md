# Sidecar Event Format Reference

## POST /events

Endpoint: `http://127.0.0.1:8765/events`

### Required fields (all events)

| Field | Type | Notes |
|-------|------|-------|
| schema_version | string | Must be `"1"` |
| event | string | One of: message.started, thinking.delta, answer.delta, message.completed, message.failed |
| conversation_id | string | Non-empty |
| message_id | string | Non-empty, unique per message |
| chat_id | string | Non-empty, Feishu chat ID |
| platform | string | Must be `"feishu"` exactly |
| sequence | int | Non-negative, increment per event |
| created_at | float | Unix timestamp |
| data | object | Event-specific payload |

### Event-specific data

**message.started**: Minimal. Sidecar ignores `text` here.
```json
{"data": {}}
```

**answer.delta**: Contains the card text content.
```json
{"data": {"text": "card content here"}}
```

**message.completed**: Finalizes. Must include `answer` for MEDIA: attachment parsing.
```json
{
  "data": {
    "answer": "card text with MEDIA:/path/to/file.png",
    "duration_ms": 1500,
    "input_tokens": 2000,
    "output_tokens": 300
  }
}
```

### Critical pitfalls

1. **Text only from answer.delta**: Sidecar reads card text from `answer.delta.data.text`, NOT from `message.started.data.text`.
2. **MEDIA only from message.completed.answer**: Attachment references (`MEDIA:path`) are ONLY parsed from `message.completed.data.answer`. Adding MEDIA to answer.delta text has no effect on attachments.
3. **platform must be "feishu"**: Any other value → 400 "platform must be feishu".
4. **Sidecar cannot upload local images**: Even with correct MEDIA references, the sidecar doesn't have filesystem access to upload files to Feishu. For images, use gateway `send_message` instead.
5. **Event sequence matters**: Always send message.started → answer.delta → message.completed in order with incrementing sequence numbers.
