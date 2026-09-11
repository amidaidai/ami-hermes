# Routing & Fallback Patterns for Hermes

## 核心原则 (PRIME DIRECTIVE)

**永远不要禁用失败的服务 — 加降级路由。**

遇到任何单点失败（额度耗尽、403区域限制、超时），正确的做法是：
1. 保持它在降级链中（有额度/恢复后自动可用）
2. 在它后面加一个可用的 provider 兜底
3. 让降级链逐个尝试，失败后自动下一个

**错误的做法**（本条 session 被棠溪纠正）：
- ❌ "Firecrawl 没钱了，禁用它"
- ❌ "Gemini 403，换 DeepSeek 然后停在这里"
- ❌ 遇到问题就砍掉，而不是加降级

正确的做法：
- ✅ Firecrawl 额度耗尽 → 留在链中，后面接 Tavily/Exa/Brave/DDGS 兜底
- ✅ Gemini 403 → 换 DeepSeek，再加 openrouter/free 作第二降级
- ✅ 任何服务失败都自动尝试下一个，而不是报错给用户

## web_search / web_extract 降级链

### 棠溪当前策略口径

- **日常搜索**：DDGS → Brave → Tavily → Exa。DDGS 免费、快、低摩擦，适合作为默认发现入口。
- **深度正文抽取**：Tavily → Exa → Firecrawl → Parallel。DDGS 不适合作为正文抽取主力。
- **重大催化核验**：金十/X_search/官方源优先，搜索引擎只做发现入口；单源必须标注。
- **Firecrawl 不要禁用**：额度不足时应留在 provider 集合中，靠 fallback 自动跳过；额度恢复后自动可用。

### 代码现状与偏好序

`agent/web_search_registry.py` 中的 `_LEGACY_PREFERENCE` 可能仍是历史顺序：

```python
_LEGACY_PREFERENCE = (
    "firecrawl",
    "parallel",
    "tavily",
    "exa",
    "searxng",
    "brave-free",
    "ddgs",
)
```

不要仅凭这个顺序判断运行态。审计时必须同时检查 `config.yaml` 的 `web.search_backend` / `web.extract_backend`、`plugins.disabled`、`tools/web_tools.py` 是否有 fallback loop，以及当前会话是否重启后生效。

### 实现代码

`tools/web_tools.py` 中 `web_search_tool` 和 `web_extract_tool` 需改造为降级链模式：

```python
# 1. 构建降级链
configured = _wsp_get_provider(backend) if backend else None
fallback_chain = []
seen = set()
if configured and configured.supports_search():
    fallback_chain.append(configured)
    seen.add(configured.name)
for name in _LEGACY_PREFERENCE:
    if name in seen: continue
    p = _wsp_get_provider(name)
    if p and p.supports_search() and p.is_available():
        fallback_chain.append(p)
        seen.add(name)

# 2. 逐个尝试
for provider in fallback_chain:
    result = provider.search(query, limit)
    if result.get("success"):
        return result
    logger.warning("'%s' failed: %s — trying next", provider.name, result.get("error"))

return {"success": False, "error": f"All failed. Last: {last_error}"}
```

### 注意事项

- **DDGS 作为日常发现入口优先** —— 免费、无需 key、低摩擦；深度抽取不要依赖 DDGS
- **不要禁用失败的 provider** —— Firecrawl 没钱了留在链中，额度恢复自动可用
- **Brave 需要 `BRAVE_SEARCH_API_KEY`** (不是 `BRAVE_API_KEY`)
- **Firecrawl `is_available()` 只看 key 存在**，不管额度 — 额度耗尽时 `search()` 返回 `success: False`，降级链必须继续跳过
- **DDGS 需要 `pip install ddgs`** — 插件注册 OK 但 `is_available()` 检查导入
- 所有 provider 顺序或配置改动后，需要重启 gateway/CLI 或开启新会话验证运行态

## 主模型 API 降级

```yaml
# config.yaml — 棠溪最终版
model:
  default: deepseek-v4-flash
  provider: deepseek

fallback_providers:
  - provider: xiaomi
    model: mimo-v2.5-pro
```

主模型 deepseek-v4-flash 超时/失败 → 自动切 xiaomi/mimo-v2.5-pro。

## 辅助任务降级链

### 压缩 (compression)

5 级降级链，从快到强，最后 openrouter/free 兜底：

```yaml
auxiliary:
  compression:
    provider: deepseek
    model: deepseek-v4-flash
    fallback_chain:
      - provider: xiaomi
        model: mimo-v2.5
      - provider: deepseek
        model: deepseek-v4-pro
      - provider: xiaomi
        model: mimo-v2.5-pro
      - provider: openrouter
        model: openrouter/free          # 自动路由最优免费模型，永远可用
```

### 视觉 (vision)

```yaml
auxiliary:
  vision:
    provider: xiaomi
    model: mimo-v2.5-pro
    fallback_chain:
      - provider: openrouter
        model: openrouter/free          # 降级到免费模型自动路由
```

## 常见路由诊断速查

| 症状 | 根因 | 修复 |
|------|------|------|
| web_search 全部报 Firecrawl "Payment Required" | 无降级链，单 provider 失败即死 | Patch `web_tools.py` 加降级循环 |
| 压缩报 403 "not in your region" | Gemini Flash 在中国不可用 | 主切 DeepSeek，降级 openrouter/free |
| 主模型超时不切 | `fallback_providers: []` | 配置 xiaomi/mimo 降级 |
| x_search 不可用 | 工具集禁用或模型未配 | `hermes tools enable x_search` + 配 Grok 模型 |
| Brave 搜索不工作 | 需要 `BRAVE_SEARCH_API_KEY` 不是 `BRAVE_API_KEY` | `.env` 中加 `BRAVE_SEARCH_API_KEY` |
| web_search 说 DDGS 配置了但走 Firecrawl | Provider 注册在 session 启动时完成，config 改动需新会话 | `/reset` |
