# Cloudflare WAF Custom Provider 配置实录

## 问题描述

自定义 provider `ccapi.us` 返回 HTTP 403 `error code: 1010`，
请求被 Cloudflare WAF 拦截。

## 根因

**三重问题：**

1. **协议配错** — `api_mode: anthropic_messages` 导致 Hermes 用 Anthropic 格式发请求。\
   ccapi 文档明确要求 Hermes 走 **OpenAI-compatible** 协议。
2. **User-Agent 被 Cloudflare 拦截** — OpenAI Python SDK 默认的 `User-Agent: OpenAI/Python ...`、\
   `X-Stainless-*` 等 Header 被 Cloudflare WAF 拒绝。
3. **`hermes config set` 将值存为 YAML 字符串** — `hermes config set model.default_headers '{"User-Agent":"..."}'`\
   把值写成单引号包裹的字符串。`_apply_user_default_headers()` 中的 `isinstance(x, dict)`\
   检查返回 False，整个 User-Agent 配置被**静默跳过**——不报错，不生效。

### 正确的配置

```yaml
custom_providers:
  - name: ccapi.us
    base_url: https://api-direct.ccapi.us/v1    # ccapi 文档推荐
    api_key: sk-****
    model: claude-opus-4-6
    api_mode: chat_completions                   # ← 必须！不要用 anthropic_messages

model:
  default_headers:                               # ← 必须是 YAML dict，不是字符串
    User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
```

### 关键细节

- **`hermes config set model.default_headers` 存的是字符串，不是 dict。**\
  这是 `hermes config set` 的一个已知行为：它把 JSON 值写到 YAML 时会用单引号包裹。\
  必须**直接编辑 config.yaml** 或用 Python 脚本写入正确的 YAML dict 格式。
  
- **YAML dict 的两种正确写法：**
  ```yaml
  # 内联 dict（一行搞定）
  model:
    default_headers: {User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}

  # 块格式（更清晰）
  model:
    default_headers:
      User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
  ```

- **`api_mode: anthropic_messages` 会跳过 `default_headers` 应用**\
  （`run_agent.py` 的 `_apply_user_default_headers()`: `if self.api_mode in ("anthropic_messages", "bedrock_converse"): return`）。

- **`hermes config set` 对 JSON 数组也一样** — `hermes config set custom_providers '[{"name":"...","api_key":"..."}]'`\
  同样存成 YAML 字符串。必须手动编辑或用 Python 直接写 YAML。

## 恢复技巧

当 `hermes config set` 或不当编辑导致 config.yaml 损坏时，Hermes 自动保存备份：

```bash
ls -la "$(hermes config path)".*.bak*
```

- `config.yaml.bak` — 最近一次自动备份
- `config.yaml.corrupt.<timestamp>.bak` — 检测到损坏时的快照

恢复方式：`cp config.yaml.corrupt.<timestamp>.bak config.yaml`，然后修复 YAML 格式。

## 验证命令

```bash
# 完整端到端测试（加 User-Agent 绕过 Cloudflare）
curl -s -w "\nHTTP_CODE:%{http_code}\nTIME:%{time_total}s" \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36" \
  -d '{"model":"claude-opus-4-6","messages":[{"role":"user","content":"回复ok"}],"max_tokens":30}' \
  https://PROVIDER_URL/v1/chat/completions

# 验证 YAML 类型（必须 dict，不是 str）
python -c "
import yaml
with open(r'CONFIG_PATH') as f:
    c = yaml.safe_load(f)
h = c.get('model', {}).get('default_headers', {})
print(f'Type: {type(h).__name__}')
print(f'Is dict: {isinstance(h, dict)}')
if isinstance(h, dict):
    print(f'User-Agent: {h.get(\"User-Agent\", \"MISSING\")}')
else:
    print('!!! 是字符串不是 dict — 配置不会生效 !!!')
"

# 验证 custom_providers 类型
python -c "
import yaml
c = yaml.safe_load(open(r'CONFIG_PATH'))
p = c.get('custom_providers', [])
print(f'custom_providers type: {type(p).__name__}')
print(f'Is list: {isinstance(p, list)}')
if isinstance(p, list) and len(p) > 0:
    print(f'api_mode: {p[0].get(\"api_mode\", \"NOT SET\")}')
"
```

## 代码路径

`model.default_headers` 在以下位置读取：

| 路径 | 适用场景 |
|------|---------|
| `run_agent.py` → `_apply_user_default_headers()` | 主 CLI agent — 构造函数中调用 |
| `agent/agent_init.py` | Studio/MCP agent init |
| `agent/auxiliary_client.py` → `_apply_user_default_headers()` | 辅助客户端（压缩、视觉等） |

所有路径都调用 `cfg_get(load_config(), "model", "default_headers")`，\
要求返回类型为 **dict**。**字符串值和 None 都会被静默跳过。**

Web UI 桌面运行时（Hermes Studio 0.17.0）自带的 Python 包也有 `_apply_user_default_headers`\
方法，所以 CLI 和 Web UI 都受同样规则约束。

### 可能会遇到此问题的常见 Provider / 场景

- **ccapi.us** — 中转站，Cloudflare WAF 严格
- **api.yairouter.com** — XAI Router（已被 cf 屏蔽）
- **任何带 Cloudflare 保护的 OpenAI-compatible 中转站**
- **公司自建 API 网关** — 如果有 WAF 规则拦截非浏览器 User-Agent

## ccapi.us 官方文档要点

取自 https://ccapi.us/docs：

| 配置项 | 值 |
|--------|-----|
| 常规 Base URL | `https://ccapi.us/v1` |
| **Hermes 推荐端点** | **`https://api-direct.ccapi.us/v1`**（长响应/慢任务/大上下文） |
| Hermes 协议 | **OpenAI-compatible**（不是 Anthropic！） |
| 认证 | `Authorization: Bearer *** |
| 验证 | `hermes doctor` — 检查 `model.provider=custom`、`model.base_url`、`model.default` |

### ccapi.us 的两个接口协议

| 协议 | 适用客户端 | Endpoint | 认证方式 |
|------|-----------|----------|---------|
| **OpenAI-compatible** | Hermes、NextChat、OpenCode、Cline | `POST /v1/chat/completions` | `Authorization: Bearer *** |
| **Anthropic** | Claude Code 原生 | `POST /v1/messages` | `x-api-key: sk-...` + `anthropic-version` |

**不要使用 `/v1/messages` 或 `x-api-key`（Anthropic 协议）。**\
Hermes 必须用 OpenAI-compatible 协议。

### 模型名注意事项

ccapi.us 的模型名以"模型广场"展示为准，不一定等于标准 Anthropic/OpenAI 模型名。\
例如 ccapi.us 上的 Claude 模型可能叫 `claude-opus-4-6`，\
也可能是 `claude-sonnet-4-6` 等变体。

## Web UI 额外注意事项

Hermes Studio (Desktop GUI) 有**自己的配置系统**，与 CLI 配置不完全一致：

### 1. `config.json` 模型可见性

路径：`~/.hermes-web-ui/config.json`（Windows）

```json
{
  "modelVisibility": {
    "custom:ccapi.us": {
      "mode": "include",
      "models": ["claude-opus-4-6", "claude-opus-4-7", ...]
    }
  }
}
```

- 如果自定义 provider 没有在 `modelVisibility` 中列出，Web UI 的模型下拉菜单**可能不显示**该 provider 的模型。
- 即使 `custom_providers` 在 `config.yaml` 中配置正确，Web UI 仍需要 `config.json` 里的可见性条目。
- **修复方式**：手动添加条目，或通过 Web UI 的设置界面添加 provider。
- 已有但 API key 失效的旧 provider 也应该清理（`modelVisibility` 中的过期条目会让模型选择器显示无法使用的模型）。

### 2. 配置变更后的启动顺序

```
1. 修改 config.yaml（custom_providers / default_headers 等）
2. 修改 config.json（modelVisibility，如需）
3. 完全退出 Hermes Studio（右键托盘图标退出，或 taskkill）
4. 重新打开 Hermes Studio
5. 新建会话，从模型下拉菜单选择对应模型
```

⚠ 只重启桌面程序而不退出可能不够——托盘后台进程可能缓存旧配置。

### 3. Web UI 后端代码路径

Web UI 聊天走 `bridge_pool.py` → `AIAgent(...)` 路径。该路径也会调用 `_apply_user_default_headers()`，所以 `model.default_headers` 在 Web UI 和 CLI 中都生效。但如果使用的是 Hermes Studio 0.17.0 版本，其自带的 `run_agent.py` 也有 `_apply_user_default_headers` 方法。

### 4. 端口与进程

如果 Web UI 连接不上，检查后台服务：

```bash
# Web UI 默认端口
netstat -ano | grep 8648

# Hermes Studio 进程
tasklist | grep "Hermes Studio"
```

## ccapi.us 已知可用模型（2026-06-23）

来自 `GET /v1/models`（18 个模型）：

| 模型 | 变体 |
|------|------|
| claude-opus-4-6 | low, medium, high, max |
| claude-opus-4-7 | low, medium, high, max, xhigh, thinking |
| claude-opus-4-8 | low, high, max, xhigh |
| cursor-opus-4-8 | — |

```python
# 获取最新列表
import yaml, urllib.request, json
cfg = yaml.safe_load(open("CONFIG_PATH"))
ccapi = next(p for p in cfg["custom_providers"] if p["name"] == "ccapi.us")
key = ccapi["api_key"]
ua = cfg["model"]["default_headers"]["User-Agent"]
req = urllib.request.Request(
    "https://ccapi.us/v1/models",
    headers={"Authorization": f"Bearer {key}", "User-Agent": ua}
)
resp = json.loads(urllib.request.urlopen(req).read())
for m in resp.get("data", []):
    print(m["id"])
```

## 代码路径验证

可以用以下 Python 代码确认 `model.default_headers` 是否被 `AIAgent` 正确读取：

```python
from run_agent import AIAgent
from hermes_cli.config import load_config

# 验证配置类型
cfg = load_config()
headers = cfg.get("model", {}).get("default_headers", {})
assert isinstance(headers, dict), f"default_headers 必须是 dict，实际是 {type(headers).__name__}"

# 验证 AIAgent 应用了 headers
agent = AIAgent(
    model="claude-opus-4-6",
    provider="custom:ccapi.us",
    base_url="https://api-direct.ccapi.us/v1",
    api_key="sk-...",
    api_mode="chat_completions",
    quiet_mode=True, skip_context_files=True, skip_memory=True,
)
h = agent._client_kwargs.get("default_headers", {})
assert "User-Agent" in h, f"User-Agent 未被应用，headers={h}"
print(f"✅ User-Agent 生效: {h['User-Agent'][:40]}...")
```

## Web UI 额外注意事项

Hermes Studio (Desktop GUI) 有**自己的配置系统**，与 CLI 配置不完全一致：

### 1. `config.json` 模型可见性

路径：`~/.hermes-web-ui/config.json`（Windows）

```json
{
  "modelVisibility": {
    "custom:ccapi.us": {
      "mode": "include",
      "models": ["claude-opus-4-6", "claude-opus-4-7", ...]
    }
  }
}
```

- 如果自定义 provider 没有在 `modelVisibility` 中列出，Web UI 的模型下拉菜单**可能不显示**该 provider 的模型。
- 即使 `custom_providers` 在 `config.yaml` 中配置正确，Web UI 仍需要 `config.json` 里的可见性条目。
- **修复方式**：手动添加条目，或通过 Web UI 的设置界面添加 provider。
- 已有但 API key 失效的旧 provider 也应该清理（`modelVisibility` 中的过期条目会让模型选择器显示无法使用的模型）。

### 2. 配置变更后的启动顺序

```
1. 修改 config.yaml（custom_providers / default_headers 等）
2. 修改 config.json（modelVisibility，如需）
3. 完全退出 Hermes Studio（右键托盘图标退出，或 taskkill）
4. 重新打开 Hermes Studio
5. 新建会话，从模型下拉菜单选择对应模型
```

⚠ 只重启桌面程序而不退出可能不够——托盘后台进程可能缓存旧配置。

### 3. Web UI 后端代码路径

Web UI 聊天走 `bridge_pool.py` → `AIAgent(...)` 路径。该路径也会调用 `_apply_user_default_headers()`，所以 `model.default_headers` 在 Web UI 和 CLI 中都生效。但如果使用的是 Hermes Studio 0.17.0 版本，其自带的 `run_agent.py` 也有 `_apply_user_default_headers` 方法。

### 4. 端口与进程

如果 Web UI 连接不上，检查后台服务：

```bash
# Web UI 默认端口
netstat -ano | grep 8648

# Hermes Studio 进程
tasklist | grep "Hermes Studio"
```

## 流程小结：自定义 Provider 调试五步法

```
1. curl 裸测 → 确定 HTTP 状态码和错误
   ├─ HTTP 200: API 本身正常，问题在 Hermes 配置
   ├─ HTTP 403 (error 1010): Cloudflare WAF → 设 User-Agent
   ├─ HTTP 401: API key 无效或过期
   └─ HTTP 404/超时: 路径或端点配错

2. 检查 api_mode
   └─ 确认是 chat_completions（OpenAI 兼容），不是 anthropic_messages

3. 检查 default_headers 类型
   └─ 用 Python 读配置，确认 isinstance(..., dict)

4. 检查 Web UI config.json
   └─ 确认 custom:PROVIDER_NAME 在 modelVisibility 中

5. 实测验证
   ├─ 终端 `hermes` 新会话（CLI）
   └─ 完全退出并重启 Hermes Studio → 新会话（Web UI）
```
   ├─ 终端 `hermes` 新会话（CLI）
   └─ 完全退出并重启 Hermes Studio → 新会话（Web UI）
```
