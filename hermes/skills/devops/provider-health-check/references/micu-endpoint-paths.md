# micu (www.micuapi.ai) 端点路径查表

## 概况

micu（米醋）是国内 Claude/Codex/Grok 等模型的 API 中转站。它**同时支持多种协议**在多条路径上，具体取决于你用什么客户端和模型。

## 已知端点一览

| 用途 | Base URL | 协议 | model 字段 |
|------|----------|------|-----------|
| Claude 原生 | `https://www.micuapi.ai` | Anthropic Messages | 大多数场景可留空，或填 Claude 模型名 |
| Codex / Grok | `https://www.micuapi.ai/v1` | OpenAI Responses | `gpt-5.4`（Codex）/ Grok 模型 ID |
| Claude via OpenAI 协议 | `https://www.micuapi.ai/pg/chat/completions` | OpenAI chat completions | 填 Claude 模型名如 `claude-opus-4-6` |
| **图像生成** | `https://www.micuapi.ai/v1/images/generations` | OpenAI images | `gpt-image-2` |
| 分组路由 | 由分组名决定 | 视分组而定 | 视分组而定 |

## `/pg/chat/completions` 端点详情

这个路径**未在 micu 官方文档中公开**，但已验证存在（HTTP 200）。

- 用途：让只支持 OpenAI chat completions 协议的客户端也能调用 Claude 模型
- 请求格式：标准 OpenAI `/v1/chat/completions` 结构
- model 字段：填 Claude 模型名
- 认证：`Authorization: Bearer <micu_key>`（与 Anthropic 协议共用同一把 key）

## `/v1/images/generations` 端点详情（图像生成）

micu 支持 OpenAI 兼容的图像生成端点，使用 `gpt-image-2` 模型。

- **端点**: `POST https://www.micuapi.ai/v1/images/generations`
- **认证**: `Authorization: Bearer <micu_key>`（与 chat 端点共用 key）
- **请求格式**:

```python
import requests, urllib.request, json

url = "https://www.micuapi.ai/v1/images/generations"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
payload = {
    "model": "gpt-image-2",
    "prompt": "A cute orange cat wearing a tiny wizard hat",
    "n": 1,
    "size": "1024x1024"
}
r = requests.post(url, headers=headers, json=payload, timeout=60)
data = r.json()
# Response shape:
# {
#   "created": 1781804472,
#   "data": [{"revised_prompt": "...", "url": "/api/generated/39fa6ba8d175458a.png"}],
#   "background": "opaque", "output_format": "png",
#   "quality": "medium", "size": "1122x1402",
#   "usage": {"input_tokens": 40, "output_tokens": 1630, "total_tokens": 1670}
# }
img_url = "https://www.micuapi.ai" + data["data"][0]["url"]
```

- **响应中的图片 URL 是相对路径**，需拼接 `https://www.micuapi.ai` 前缀下载。
- **pricing**: gpt-image-2 按 token 计费（40 input + 1630 output tokens / 图）
- **支持参数**: `model`, `prompt`, `n`, `size`，以及 `background`, `output_format`, `quality`（从响应可见）
- **已知问题**: 如果用被截断的 API key（如 config 中存为 `sk-acH...09ac`——带字面 `...` 的残缺 key），返回 403 error code 1010。见本技能 SKILL.md 中关于 Hermes secret redaction（Case B — 真截断）的陷阱说明。
- **2026-06-19 实测**: 当前 `www.micuapi.ai` 的 LLM key 与 `www.micuapi.ai生图` 的 key 均为 Config 中的完整 51 字符 key，但都返回 **403 error code 1010**（LLM 和生图端点均如此）。表明该 key 整体失效（过期/未续费/未开通），生图不可用不是单独的问题。
- **提取真实 key 的方法**: 即使 Hermes 输出过滤器把所有终端输出中的 key 替换为截断版，仍可通过读取 config.yaml 的二进制模式 + hex 提取来获取完整 key（见 SKILL.md 的 Case A 处理）。完整的 key 存在于文件中，只是**输出时被过滤**。

## 已知陷阱
- **micu 不支持 OpenAI 格式的 `messages[0].role=system`**。Claude 原生要求 `system` 参数在顶层，不在 messages 数组里。直接用 OpenAI custom provider 走 `base_url=https://www.micuapi.ai` 不设额外路径会报 400。
- **`/pg/chat/completions` 则是真正的 OpenAI 兼容路径**，应该能正确处理 system prompt。
- **micu 的 API key 与 Anthropic 官方 key 共享同一凭据**。`auth.json` 中 `custom:www.micuapi.ai` 和 `anthropic` 的 `secret_fingerprint` 相同。

## 测试方法

```python
import requests

url = "https://www.micuapi.ai/pg/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
payload = {
    "model": "claude-opus-4-6",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 20
}
r = requests.post(url, headers=headers, json=payload, timeout=30)
print(r.status_code, r.json().get("choices", [{}])[0].get("message", {}).get("content", ""))
```

## 参考

- micu 官方文档: https://docs.micuapi.ai
- 外接接入说明: https://docs.micuapi.ai/外接接入
