# 实际测试案例 — 2026-06-18

配置环境：Hermes Agent on Windows 11, MSYS bash, Python 3.11 via uv

## 已配置 Providers

| Provider | Type | 模型 |
|----------|------|------|
| timicc.com | custom_providers | gpt-5.5 |
| DeepSeek | .env API key | deepseek-chat, deepseek-v4-pro, deepseek-v4-flash |
| OpenRouter | .env API key | openrouter/free (及各种路由) |
| Xiaomi | auxiliary vision | mimo-v2.5-pro |

## 测试结果

| Provider | 路径 | 延迟 | HTTP | 内容 | 状态 |
|----------|------|:----:|:----:|------|:----:|
| timicc.com | `/v1/chat/completions` | 1,674ms | 200 | "hello" | ✅ |
| timicc.com | `/chat/completions` | 1,860ms | 200 | "hello" | ✅ |
| DeepSeek (chat) | `api.deepseek.com/chat/completions` | 872ms | 200 | "hello" | ✅ |
| DeepSeek (v4-pro) | 同上 | 859ms | 200 | (空reasoning) | ⚠️ |
| OpenRouter (free) | `openrouter.ai/api/v1/...` | 3,303ms | 200 | "hello" | ✅ |
| Xiaomi | `api.xiaomi.com/v1/...` | 超时 | FAIL | 连接失败 | ❌ |
| OpenRouter qwq-32b:free | 同上 | 8,039ms | 404 | — | ❌ |
| OpenRouter deepseek-chat:free | 同上 | 5,377ms | 404 | — | ❌ |

## 发现的问题

### 1. Xiaomi endpoint 配置有误
`api.xiaomi.com` 连接超时。需要确认 MiMo API 的真实 endpoint。

### 2. OpenRouter free 模型失效
`qwen/qwq-32b:free` 和 `deepseek/deepseek-chat:free` 返回 404。这些模型已被 OpenRouter 下架或改名。

### 3. DeepSeek v4-pro 返回空内容
HTTP 200 但无输出文本。可能是 reasoning-format 模型，输出在 `reasoning` 字段而非 `content`。

### 4. TIMICC 双路径均工作
更推荐 `/v1/chat/completions`（更快，1,674ms vs 1,860ms）。

## 测试代码片段

```python
import time, requests, yaml

# 读取配置
with open("C:/Users/Administrator/AppData/Local/hermes/.env") as f:
    env = dict(line.strip().split("=", 1) for line in f 
               if "=" in line and not line.startswith("#"))
with open("C:/Users/Administrator/AppData/Local/hermes/config.yaml") as f:
    cfg = yaml.safe_load(f)
for cp in cfg.get("custom_providers", []):
    env[f"{cp['name']}_KEY"] = cp["api_key"]
    env[f"{cp['name']}_URL"] = cp["base_url"]

def test(url, key, model, extra_h=None):
    h = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    h.update(extra_h or {})
    t0 = time.time()
    r = requests.post(url, headers=h, 
        json={"model": model, "messages": [{"role":"user","content":"Say: hello"}], "max_tokens": 5},
        timeout=30)
    return round((time.time()-t0)*1000), r.status_code, r.json()
```
