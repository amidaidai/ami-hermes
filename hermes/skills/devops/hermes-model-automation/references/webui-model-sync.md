# Web UI 免费模型自动同步

## ⚠️ 重要：Web UI 有两层独立的模型体系（且不可扩展）

Web UI 的模型配置分为**两层**，独立运作。

### 层 1: Provider Model Cache（部分可扩展 via `customModels`）

**内置提供者**的模型列表由 Hermes 硬编码决定（`models.py` 中的 `OPENROUTER_MODELS` 或 provider 静态配置）。  
- OpenRouter 内置 provider 暴露 **22 个 `:free` 模型**  
- 内置列表本身**不可修改**（无法通过 API/config 增加内置提供者的 `models` 列表）

**但自 2026-06-23 起**：可以通过 `customModels` 机制**向提供者的 `available_models` 注入额外模型**：
- `PUT /api/hermes/custom-model` → 注册 model ID + provider  
- 效果：模型出现在 `groups[0].available_models` 中，Web UI 可选择和使用  
- 当前已注入：`openrouter/free`、`openrouter/owl-alpha`  
- 数据存储在 `~/.hermes-web-ui/config.json` 的 `customModels` 字段；gateway 重启不丢失

所以**实际可用模型 = 22 内置 + N 自定义**。

> ⚠️ **`modelVisibility` 不能增加提供者不知道的模型**，但 `customModels` 可以。两者是独立的控制面。

### 层 2: Model Visibility（可配置）

通过 `PUT /api/hermes/model-visibility` 设置，或 Freerouter 的 `sync_webui_free_models()` 同步。  
- 只能 **include/exclude** 第 1 层已知（含 customModels 注入）的模型  
- Web UI 页面上显示 "N/M" = N 个可见（include 筛选后） / M 个提供者总模型

**结论**：Web UI 的 OpenRouter 模型选择器内置提供者显示 22 个 `:free` 模型，加上 customModels 注入的 2 个路由（`openrouter/free`、`openrouter/owl-alpha`），共 **24 个可用模型**。OpenRouter API 上的 340+ 免费模型**只能通过 Hermes CLI 使用**（Freerouter 自动选择 + fallback），Web UI 仅列出工具兼容的真免费模型。

### Freerouter V4 的新做法

Freerouter V4 在 `sync_webui_free_models()` 之前新增 `sync_custom_free_models()` 阶段：
1. 从 OpenRouter API 抓取所有模型
2. 筛选真免费（pricing=0/0）+ 工具支持
3. 对比内置提供者列表（22 个 `:free`），找出需要 customModels 的模型
4. 写入 `~/.hermes-web-ui/config.json` 的 `customModels` 字段
5. 自动清理不再免费的 customModels 条目

当前 `customModels` 结果：`['openrouter/free', 'openrouter/owl-alpha']`

> **2026-06-23 更新**: 5 个原 `:free` 模型已不再免费，被 `sync_custom_free_models()` 自动从 `HERMES_KNOWN_FREE_MODELS` 移除。剩余 17 个 `:free` + 3 个路由 = 20 条 modelVisibility 条目，加上 2 个 customModels = 24 个可用模型。详见 `references/free-model-audit-2026-06-23.md`。

## 手动管理

### 正确方式：Studio API（推荐）

#### 更新 modelVisibility（筛选可见性）

通过 Hermes Studio MCP 直接更新可见性：

```python
# 使用 mcp_hermes_studio_api_request 工具
hermes_studio_api_request(
    method="PUT",
    path="/api/hermes/model-visibility",
    profile="default",
    body={
        "mode": "include",
        "models": [
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
            # ... 全部免费模型 ...
            "openrouter/free",
            "openrouter/auto",
            "openrouter/owl-alpha",
        ],
        "provider": "openrouter"
    }
)
```

返回 {"success": true, "model_visibility": {...}} 表示成功。

#### 注入 customModels（增加提供者不认识的模型）

当某个模型是免费的但不在内置提供者列表里（如 openrouter/free、openrouter/owl-alpha），可以用 custom-model 端点注入：

```python
# 方式 A: Studio API（立即生效）
PUT /api/hermes/custom-model
body: {"model": "openrouter/free", "provider": "openrouter"}

# 方式 B: 直接写 config.json（Freerouter 的方式，gateway 重启后读入）
# 写入 ~/.hermes-web-ui/config.json 的 customModels 字段
config.setdefault("customModels", {})
config["customModels"].setdefault("openrouter", [])
config["customModels"]["openrouter"].append("openrouter/free")
```

删除：
```python
# API
DELETE /api/hermes/custom-model?model=openrouter/free&provider=openrouter

# config.json
config["customModels"]["openrouter"].remove("openrouter/free")
```

与 modelVisibility 不同，customModels 在 config.json 中持久化（customModels 字段），gateway 重启不丢失。这是 Freerouter V4 `sync_custom_free_models()` 使用的同步方式。

> ⚠️ Freerouter 的 `sync_custom_free_models()` 最初使用 HTTP API（`_webui_request`），但因为 Web UI 的 localhost API 需要 Bearer token（auth.json 中没有全局 token），导致 401 错误。V4 已改为直接读写 config.json。因此不需要在 cron 脚本中处理认证。

### 错误方式：写 config.json

```python
# ❌ 不要用这个方法 — Web UI 运行时维护自己的内部状态
with open("~/.hermes-web-ui/config.json", "w") as f:
    json.dump(config, f)
```

`~/.hermes-web-ui/config.json` 的 `modelVisibility` 在 gateway 重启后不会被采纳。**只有通过 Studio API `PUT /api/hermes/model-visibility` 写入才会持久化到数据库**。

### 获取 Web UI Bearer Token

token 在 Web UI profile 目录下：

```bash
cat ~/.hermes-web-ui/profiles/default/.model-run-token
```

这是一个 JWT，用于 `Authorization: Bearer *** 头。

### 2. Freerouter 自动同步

Freerouter 在每次运行时自动执行 `sync_webui_free_models()`（写入 `~/.hermes-web-ui/config.json` 的 `modelVisibility[openrouter]`），无需手动操作。

触发时机：  
- 每次 Freerouter 运行（无论 DRY_RUN）  
- 默认每日 06:00 cron  

注意：此同步只影响 `modelVisibility` 配置，不影响提供者缓存的模型列表（始终 22 个）。Web UI 重启 gateway 后读取新配置。

> **2026-06-23 发现**: 写入 `~/.hermes-web-ui/config.json` 的 `modelVisibility` 在 gateway 重启后**不被 Studio API 采纳**。即使 config.json 正确更新，`GET /api/hermes/available-models` 返回的 `model_visibility` 仍然是旧值。必须通过 **`PUT /api/hermes/model-visibility`**（Hermes Studio API）写入才会生效。详见上方"正确方式：Studio API"。

### 手动同步

```python
from freerouter import sync_webui_free_models
sync_webui_free_models([])
```

然后重启 gateway 生效：
```bash
# Windows
taskkill //F //PID <gateway_pid>
# Linux/macOS
pkill hermes-gateway
# Hermes 会自动重启
```

> ⚠️ Gateway 重启后 **MCP deferred 工具会失效**。之前 loaded 的 `mcp_hermes_studio_*` 工具不再可用，需要重新 `tool_search` + `tool_describe` 再调用。这是 Hermes MCP 协议的正常行为。

## Key Paths

| 路径 | 说明 |
|------|------|
| `~/.hermes-web-ui/profiles/default/.model-run-token` | Web UI bearer token |
| `http://127.0.0.1:8748/api/hermes/model-visibility` | PUT 设置可见性 |
| `http://127.0.0.1:8748/api/hermes/provider-models/cache/refresh` | POST 刷新缓存 |
| `http://127.0.0.1:8748/api/hermes/available-models` | GET 查询当前配置 |
| `https://hermes-agent.nousresearch.com/docs/api/model-catalog.json` | Hermes 官方模型目录（定义 OpenRouter 可用模型） |
