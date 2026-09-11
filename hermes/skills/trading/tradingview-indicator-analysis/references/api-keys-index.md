# API 密钥清单

| 密钥文件 | API | 用途 | 额度类型 |
|---------|-----|------|---------|
| `jin10_token.txt` | 金十数据 MCP | 快讯+日历+报价 | MCP 无限 |
| `fmp_api_key.txt` | Financial Modeling Prep | 全球宏观+财报 | 免费层 |
| `tushare_token.txt` | Tushare | A 股+中国宏观 | 免费层 |
| `brave_api_key.txt` | Brave Search | 网页搜索 | 免费有限 |
| `tavily_api_key.txt` | Tavily | AI 搜索 | 免费有限 |
| `exa_api_key.txt` | Exa | AI 搜索 | 免费有限 |
| `anysearch_api_key.txt` | AnySearch | 聚合搜索 | 免费有限 |
| `felo_api_key.txt` | Felo | AI 研究搜索 | 免费有限 |
| `metaso_api_key.txt` | Metaso | 中文搜索 | 免费有限 |
| `firecrawl_api_key.txt` | Firecrawl | 网页抓取 | 免费有限 |

## 搜索优先级

1. DDGS (免费无限) — 主搜索，插件 `web-ddgs`
2. Brave — DDGS 失败时备用
3. Tavily/Exa — 仅重大事件交叉验证

## 环境变量

搜索 API 密钥配置在 `~/.hermes/.env`：
- `BRAVE_API_KEY`
- `TAVILY_API_KEY`
- `EXA_API_KEY`
- `FIRECRAWL_API_KEY`
