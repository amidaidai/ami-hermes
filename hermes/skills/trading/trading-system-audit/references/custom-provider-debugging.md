# Custom Provider 调试排障流程

当用户说"XX provider 不可用"时的系统化排查路径。以 micu (www.micuapi.ai) Claude 为例。

## 排查优先级

按此顺序逐层排除，每层都有实证验证，不做猜测。

### 1. 直连 curl 验证（排除网络/认证问题）

```
# 先测非流式 — 这是最基础的通断测试
curl -s -X POST https://www.micuapi.ai/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-opus-4-8","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

- 200 + 正常 JSON = 认证和网络没问题
- 403 + Cloudflare HTML = 代理/IP/UA 被拦
- 200 + HTML 首页 = **base_url 路径错误**（最常见根因）

### 2. base_url 路径验证（最容易漏）

OpenAI SDK 在 base_url 后拼 `/chat/completions`。如果 base_url 是 `https://www.micuapi.ai`（不带 `/v1`），SDK 拼出 `https://www.micuapi.ai/chat/completions` — 这是错误路径，返回 HTML 首页（状态码 200 但内容是 HTML），SDK 解析成空流。

正确写法：
```yaml
custom_providers:
  - name: www.micuapi.ai
    base_url: https://www.micuapi.ai/v1    # 必须有 /v1
```

验证：对比 `/chat/completions` vs `/v1/chat/completions` 的 curl 响应。

### 3. 流式 vs 非流式

非流式能过不代表流式能过：
```
# 流式测试
curl -s -X POST https://www.micuapi.ai/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-opus-4-8","messages":[{"role":"user","content":"hi"}],"stream":true,"max_tokens":5}'
```

### 4. User-Agent 不是第一嫌疑人

micu 文档说要 `User-Agent: claude-cli/2.0.76`，但实测：
- `OpenAI/Python 2.24.0` + 全套 `X-Stainless-*` 头 → 200 OK
- `Python-urllib/3.11`（裸UA）→ 403 Cloudflare

**结论**：UA 只需要不是可疑的裸脚本 UA，OpenAI SDK 默认头通常能过。先排除 base_url 再怀疑 UA。

### 5. api_mode 协议兼容

用 OpenAI 兼容协议（`/v1/chat/completions`）带 tools 时，Claude 后端可能拒绝：
```
HTTP 400: tools.0: Input tag 'function' does not match expected tags
```

这些 expected tags 是 Anthropic 原生类型（`bash_20250124`、`text_editor_20250124` 等）。非 agent 模式（无 tools）的简单对话能过，agent 模式带 tools 就降级。

解决方案：对 Claude 模型用 `api_mode: anthropic_messages`：
```yaml
custom_providers:
  - name: www.micuapi.ai
    base_url: https://www.micuapi.ai/v1
    api_key: sk-xxx
    model: claude-opus-4-8
    api_mode: anthropic_messages
```

### 6. 代理路由验证

国内中转 API 如果被 clash 代理路由到境外出口 → 可能被 Cloudflare 拦。
```bash
grep -i proxy ~/.hermes/.env
```
- micu（国内中转）→ 必须加 NO_PROXY
- x.ai / api.anthropic.com（GFW 封锁）→ 必须走代理

### 7. 用 OpenAI SDK 精确复现

最终验证用 Hermes 实际使用的 SDK：
```python
from openai import OpenAI
c = OpenAI(api_key=key, base_url="https://www.micuapi.ai/v1")
# 抓 SDK 实际发出的请求头
# patched httpx.Client.build_request ...
s = c.chat.completions.create(model="claude-opus-4-8", messages=[...], stream=True)
```

## 诊断决策树

```
用户说"XX provider 不可用"
├─ curl 非流式 → 200? 
│  ├─ 200 + HTML → base_url 路径错误（加 /v1）
│  ├─ 403 + Cloudflare → 代理/IP/UA
│  └─ 200 + JSON → 继续
├─ curl 流式 → 200?
│  └─ 403 → UA 缺失（加任意 User-Agent）
├─ SDK 流式 → OK?
│  └─ "empty stream" → base_url 路径（确认带 /v1）
└─ SDK 带 tools → OK?
   └─ 400 tools format → api_mode 错误（切 anthropic_messages）
```

## 已知 provider 特殊性

| Provider | base_url | api_mode | 特殊要求 |
|----------|----------|----------|---------|
| micu GPT | `https://www.micuapi.ai/v1` | chat_completions | 需 /v1 |
| micu Claude | `https://www.micuapi.ai/v1` | anthropic_messages | 需 /v1 + anthropic协议 |
| timicc | `https://timicc.com` | chat_completions | 接受根路径 |
| cctq | `https://www.cctq.ai/v1` | chat_completions | 需 /v1 |
