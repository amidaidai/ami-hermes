# Free Model Audit — 2026-06-23

## Background

User reported Web UI showing 22 free models but remembered 28. Investigation revealed
5 manually-added models in `config.json` that Freerouter never synced, some of which
were dead or not actually free.

## Methodology

### 1. Query live OpenRouter API for all models

```bash
curl -s 'https://openrouter.ai/api/v1/models' > models.json
```

### 2. Filter truly free + tool-supporting

```python
import json
with open('models.json') as f:
    data = json.load(f)

free_tool = []
for m in data['data']:
    pricing = m.get('pricing', {})
    try:
        prompt = float(pricing.get('prompt', '1'))
        completion = float(pricing.get('completion', '1'))
    except (TypeError, ValueError):
        continue
    if prompt != 0 or completion != 0:
        continue
    params = m.get('supported_parameters') or []
    has_tools = 'tools' in params if isinstance(params, list) else True
    if not has_tools:
        continue
    free_tool.append((m.get('context_length', 0) or 0, m['id']))

for ctx, mid in sorted(free_tool, key=lambda x: -x[0]):
    print(f'  ctx={ctx:>7} | {mid}')
```

Result: **26 truly free + tool-supporting models** on OpenRouter (as of 2026-06-23).

### 5. Check openrouter_model_metadata.json (local cache)

```bash
# The local cache has more free models than the gateway uses
python -c "
import json
with open('$HERMES_HOME/cache/openrouter_model_metadata.json') as f:
    d = json.load(f)
free = []
for mid, m in d.items():
    p = m.get('pricing', {}) if isinstance(m, dict) else {}
    try:
        prompt = float(p.get('prompt', 1))
        completion = float(p.get('completion', 1))
        if prompt == 0 and completion == 0:
            free.append(mid)
    except: pass
print(f'Truly free (pricing=0/0) in metadata: {len(free)}')
for mid in sorted(free): print(f'  {mid}')
"
```

Result: **86 truly free models** in `openrouter_model_metadata.json`, including:
- All 22 `:free` models (with and without provider prefix — e.g. both `google/gemma-4-26b-a4b-it:free` and `gemma-4-26b-a4b-it:free`)
- `openrouter/free` ✅ and `openrouter/owl-alpha` ✅
- Google Lyria models (no tool support)
- Date-specific version aliases

Gateway uses a stricter filter (`:free` suffix check) and only shows **22 models**.

## Key Architectural Lesson

The gateway's `allProviders[openrouter].models` is populated by a **dynamic `freeOnly=true` API fetch at runtime**, NOT by:
- `model_catalog.json` (disk cache of remote manifest) — modifying this does NOT add models
- `OPENROUTER_MODELS` in `models.py` — this is a static fallback, not the live source
- `provider_models_cache.json` — this is a credential-scoped cache, filtered by the curated list
- `models_dev_cache.json` — this has 338+ OpenRouter models, but the gateway filters by curated list + `:free` suffix

To verify what the gateway actually sees, use the Studio API:
```python
hermes_studio_api_request(
    method="POST",
    path="/api/hermes/provider-models",
    profile="default",
    body={"base_url": "https://openrouter.ai/api/v1", "provider": "openrouter", "freeOnly": true}
)
# Returns exactly 22 :free models
```

This is the authoritative list that the Web UI provider will display - it cannot be expanded through configuration.

```python
by_id = {m['id']: m for m in data['data']}
for mid in ['tencent/hy3-preview:free', 'inclusionai/ring-2.6-1t:free',
            'openrouter/elephant-alpha', 'openrouter/owl-alpha',
            'openrouter/pareto-code']:
    m = by_id.get(mid)
    if not m:
        print(f'{mid}: NOT FOUND')
    else:
        pricing = m.get('pricing', {})
        print(f'{mid}: prompt={pricing.get("prompt","?")}, '
              f'completion={pricing.get("completion","?")}, '
              f'tools={"tools" in (m.get("supported_parameters") or [])}')
```

### 4. Compare against Freerouter's HERMES_KNOWN_FREE_MODELS

Cross-reference every entry in `HERMES_KNOWN_FREE_MODELS` against the live API.

## Findings

| Model | Status | Action |
|-------|--------|--------|
| All 22 `:free` models | ✅ Confirmed free + tools | Keep |
| `openrouter/free` | ✅ Free, 200K ctx, tools=True | Keep |
| `openrouter/auto` | ⚠️ Variable pricing, 2M ctx, tools=True | Keep (useful route) |
| `openrouter/owl-alpha` | ✅ **Free!** 1M ctx, tools=True | **ADD** to list |
| `tencent/hy3-preview:free` | ❌ Not found in API | **REMOVE** |
| `inclusionai/ring-2.6-1t:free` | ❌ Not found in API | **REMOVE** |
| `openrouter/elephant-alpha` | ❌ Not found in API | **REMOVE** |
| `openrouter/pareto-code` | ⚠️ Variable pricing, no tools, 2M ctx | **REMOVE** |

## Cleaned List (25 → 20 entries after auto-sync)

**2026-06-23 更新**: `sync_custom_free_models()` 自动检测到 5 个 `:free` 模型不再免费，已从 `HERMES_KNOWN_FREE_MODELS` 移除：

| 移除的模型 | 原因 |
|-----------|------|
| `cognitivecomputations/dolphin-mistral-24b-venice-edition:free` | 不再免费 |
| `liquid/lfm-2.5-1.2b-instruct:free` | 不再免费 |
| `meta-llama/llama-3.2-3b-instruct:free` | 不再免费 |
| `nousresearch/hermes-3-llama-3.1-405b:free` | 不再免费 |
| `nvidia/nemotron-3.5-content-safety:free` | 不再免费 |

当前 `HERMES_KNOWN_FREE_MODELS` = 20 个条目（17 个 `:free` + 3 个路由）。

## customModels 同步（新增）

随着 `sync_custom_free_models()` 加入 Freerouter V4，脚本还会：

1. 从 OpenRouter API 获取所有模型
2. 筛选真正免费（pricing=0/0）+ 工具支持
3. 与 `HERMES_KNOWN_FREE_MODELS` 中仅 `:free` 后缀的模型对比（排除路由）
4. 不在内置列表但免费的模型 → 写入 `~/.hermes-web-ui/config.json` 的 `customModels` 字段
5. `customModels` 中不再免费的条目 → 自动移除

当前 `customModels` 结果：`['openrouter/free', 'openrouter/owl-alpha']`

此机制使 Web UI 的 OpenRouter 提供者**实际可用模型 = 22 个内置 + 2 个自定义 = 24 个**。

## Web UI Sync

After updating `HERMES_KNOWN_FREE_MODELS`, there are two sync paths:

### Path 1: Freerouter sync_webui_free_models (writes config.json)

```python
from freerouter import sync_webui_free_models
sync_webui_free_models([])
```

This overwrites `modelVisibility[openrouter]` in `~/.hermes-web-ui/config.json` with the cleaned list.

### Path 2: Studio API (correct way — persists to database)

```python
# Use Hermes Studio MCP tool to PUT visibility
hermes_studio_api_request(
    method="PUT",
    path="/api/hermes/model-visibility",
    profile="default",
    body={
        "mode": "include",
        "models": [ ... cleaned list ... ],
        "provider": "openrouter"
    }
)
```

> ⚠️ **2026-06-23 关键发现**: `config.json` 的 `modelVisibility` 修改在 gateway 重启后**不被 Studio API 采纳**。Freerouter 的 `sync_webui_free_models()` 写入 config.json 后，gateway 重启读取的是旧值。**必须通过 `PUT /api/hermes/model-visibility` Studio API 写入才会被持久化到数据库**。详见 `references/webui-model-sync.md`。

## One-liner for quick verification

```bash
curl -s 'https://openrouter.ai/api/v1/models' | python -c "import sys,json; d=json.load(sys.stdin); free=[m for m in d['data'] if float(m.get('pricing',{}).get('prompt','1'))==0 and float(m.get('pricing',{}).get('completion','1'))==0 and 'tools' in (m.get('supported_parameters') or [])]; [print(f'ctx={m.get(\"context_length\",0):>7} | {m[\"id\"]}') for m in sorted(free, key=lambda x:-(x.get(\"context_length\") or 0))]"
```
