# Studio「自定义模型」诊断 — customModels

## 何时用

用户问「为什么 <provider> 里有一些自定义模型 / 带自定义角标的是什么」，或要清理由脚本注入模型的残留。**只读诊断优先**：先把四层证据取全，再决定改不改配置；不要凭界面截图臆断。

## 1. 配置层

`~/.hermes-web-ui/config.json`：

- `customModels` — `{"<provider>": ["<model id>", ...]}`，「自定义」角标的唯一来源。
- `modelVisibility` — `{"<provider>": {"mode": "include", "models": [...]}}`，只做过滤，不能新增模型。
- `providerPreferredModels` / `providerLabels` — 界面默认模型与别名显示，与角标无关。
- `config.json.bak*` 可还原历史：某条 customModels 是什么时候加进去的、当时和谁一起加的。

## 2. 运行时层（权威）

认证：所有 `/api/hermes/*` 都带 Bearer，缺失即 401。

```bash
T=$(cat ~/.hermes-web-ui/profiles/default/.model-run-token)
curl -s -H "Authorization: Bearer $T" -H "X-Hermes-Profile: default" \
  "http://localhost:PORT/api/hermes/available-models?profile=default"
```

`PORT` 取自 `~/.hermes-web-ui/logs/server.log` 的 listening 行（常见 8748），不要写死。`~/.hermes-web-ui/.token` 不是该 API 的凭据，用它请求同样 401。

响应字段与含义：

| 字段 | 含义 |
|---|---|
| `custom_models` | 与 config.json 的 `customModels` 同源；界面角标读它 |
| `model_visibility` | include/exclude 结果 |
| `groups[].models` | 经 visibility 过滤后的基线列表 |
| `groups[].available_models` | provider 发现层（已含 customModels 注入的 id） |
| `groups[].model_refreshable` / `model_restore_available` | provider 列表能否刷新/还原 |

界面最终列表 = `groups[].models` ∪ `custom_models[provider]`（前端把不在 models 里的自定义 id 补回去，所以自定义 id 会绕过 visibility 显示）。

服务端路由（可在 `desktop-runtime/webui/<ver>/dist/server/index.js` 查证）：`GET /api/hermes/available-models`、`POST /api/hermes/provider-models`、`POST /api/hermes/provider-models/cache/refresh`、`PUT /api/hermes/model-visibility`、`PUT|DELETE /api/hermes/custom-model`。

## 3. 对 OpenRouter 实盘核验

本机直连 `openrouter.ai` 会 `SSL: UNEXPECTED_EOF_WHILE_READING`，**必须走代理**：`ProxyHandler({'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'})`。key 从 `~/AppData/Local/hermes/.env` 的 `OPENROUTER_API_KEY` 读，不要回显。

1. 存在性 / 免费性：`GET /api/v1/models` → 查 `pricing.prompt == "0"` 且 `pricing.completion == "0"`、`context_length`、`supported_parameters` 是否含 `tools`。
2. 权威可用性（判死必做）：`POST /api/v1/chat/completions`，body `{"model": mid, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}`。
   - `200` → 活，响应 `model` 字段会显示实际落点（路由类 id 会落到具体模型）。
   - `429 ... temporarily rate-limited upstream` → 模型活着，上游限流。
   - `404 ... This model is unavailable for free. The paid version is available now - use this slug instead: <paid>` → `:free` 端点下架，条目是死的。

## 4. 历史用量与审计

`~/.hermes-web-ui/hermes-web-ui.db`（用 `file:...?mode=ro` 只读打开，库较大）：

- `session_usage`：某 id 是否真的被调用过、最后调用时间 —— `select model, count(*), max(created_at) from session_usage group by model order by 3 desc;`。从未出现的死条目优先级最高，直接删。
- `provider_audit_events`：`action ∈ {provider.models.refresh, provider.models.restore, provider.editor.update}`，`details_json` 的 `added` / `model_count` 可还原 provider 列表何时被整表刷新或还原。
- 全库文本搜索条目名时注意：聊天正文（`messages.content`）会命中，别把讨论当成配置记录。

## 5. 清理

`DELETE /api/hermes/custom-model?model=<id>&provider=<provider>`，或从 config.json 的 `customModels` 移除后重载。

删前确认 `config.yaml`、MoA preset、cron、`scripts/` 没有引用该 id —— customModels 只管界面，路由引用要单独收敛。
