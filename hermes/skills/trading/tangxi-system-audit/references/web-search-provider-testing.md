# Web Search Provider Connectivity Testing

> 所属 Skill: `tangxi-system-audit`
> 建立: 2026-06-28
> 来源: 全系统审计时发现 Tavily 免费额度耗尽 + DDGS 不可用，但无排查流程

## 原则

- 审计 Step 0 必须先验证至少 1 个 provider 可用
- 测试用 `--noproxy '*'` 绕过 Clash 代理（`HTTPS_PROXY=http://127.0.0.1:7897` 可能干扰某些 API）
- 禁止假设 provider 可用——必须实弹

## 逐个测试脚本

### Firecrawl
```bash
curl -s --connect-timeout 10 --noproxy '*' \
  "https://api.firecrawl.dev/v1/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <FIRECRAWL_API_KEY>" \
  -d '{"query":"BTC test","limit":1}'
# 期望: {"success":true,"data":[...]}
# 失败: {"success":false,"error":"Unauthorized: Invalid token"} → Key过期
```

### Exa
```bash
curl -s --connect-timeout 10 --noproxy '*' \
  "https://api.exa.ai/search" \
  -H "Content-Type: application/json" \
  -H "x-api-key: <EXA_API_KEY>" \
  -d '{"query":"BTC","numResults":1}'
# 期望: {"requestId":"...","results":[...]}
```

### Tavily
```bash
curl -s --connect-timeout 10 --noproxy '*' \
  "https://api.tavily.com/search" \
  -H "Content-Type: application/json" \
  -d '{"api_key":"<TAVILY_API_KEY>","query":"BTC price","max_results":1}'
# 期望: {"results":[...]}
# 额度耗尽: {"detail":{"error":"This request exceeds your plan's set usage limit..."}}
# 速率限制: HTTP 432
```

### Brave
```bash
curl -s --connect-timeout 10 --noproxy '*' \
  "https://api.search.brave.com/res/v1/web/search?q=BTC&count=1" \
  -H "Accept: application/json" \
  -H "X-Subscription-Token: <BRAVE_SEARCH_API_KEY>"
# 常见失败: Connection timed out（IPv6→IPv4 回退慢或代理干扰）
```

## 回退链优先级

`web_search_registry.py` L19-23 定义的旧回退顺序：
```
firecrawl → parallel → tavily → exa → searxng → brave-free → ddgs
```

但实际由 `config.yaml` 的 `web.search_backend` 决定主 provider。
配置方法：
```bash
hermes config set web.search_backend firecrawl   # 已验证可用
hermes config set web.extract_backend firecrawl  # 内容提取
```

## 标记

- 当前已注册但无插件的 provider：Metaso、AnySearch、Felo —— Key 在 `.env` 中但不会被 Hermes 调用，需自建插件
- DDGS 历史问题：`web.search_backend: ddgs` → 无响应 → 搜索全链断裂
