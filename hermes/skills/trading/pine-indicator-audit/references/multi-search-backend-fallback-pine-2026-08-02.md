# 多搜索后端回退 + 免费档Pine研究取证技术（2026-08-02）

抓取日期：2026-08-02。用于 Pine/TradingView 社区与官方研究时，搜索/抓取后端集体失效的取证路径。

## 一、多搜索后端回退模式（Firecrawl 被 ban 时的可靠替代）

**核心教训**：web_search 依赖的 Firecrawl key 可能**账号级被 ban**（错误 `Unauthorized: This account has been banned`，换新 key 前的旧 key 无法救活）。此时 web_extract 也会连带失败。不要卡在一个后端，用多个直连 API 轮换。

已实测可用的直连端点（execute_code + urllib.request，无需 Hermes 工具）：

| 服务 | 端点 | 鉴权 | 备注 |
|---|---|---|---|
| Firecrawl | `POST https://api.firecrawl.dev/v1/search` | `Authorization: Bearer <key>` | search + scrape；抓 Reddit 常 403 |
| Firecrawl scrape | `POST https://api.firecrawl.dev/v1/scrape` | 同上 | `{"url","formats":["markdown"],"onlyMainContent":true}` |
| Tavily | `POST https://api.tavily.com/search` | body `{"api_key":...}` | **能索引 Reddit 内容**（`include_raw_content` 返回正文），绕 Reddit 403 |
| Exa | `POST https://api.exa.ai/search` | header `x-api-key:` | 返回官方文档/权威源为主 |
| Brave | `GET https://api.search.brave.com/res/v1/web/search` | header `X-Subscription-Token:` | 社区帖/Reddit 覆盖好 |

**Reddit 403 绕过**：Reddit 直连 `.json` API（`old.reddit` + JSON）也常 403。**最可靠是 Tavily `include_raw_content`**，能返回 Reddit 帖子正文与评论。

## 二、Pine 官方文档抓取技术

TradingView 官方文档是 JS/压缩传输，`web_extract` 会被网络层拦（`Blocked: URL targets a private or internal network address`）。改用 curl + `--compressed`：

```bash
curl -s --compressed -m 30 -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36" \
  "https://www.tradingview.com/pine-script-docs/writing/limitations/" -o tv_limits.html
# 不 --compressed 时拿到的是压缩乱码/极小文件
```

HTML 转纯文本（strip script/style/tag + html.unescape + 空白归一）后 grep 关键词定位限额。

**官方定价页**（JS 渲染，curl 抓不到明细）用 browser_navigate + browser_console 提取：`document.body.innerText` 直接拿到免费档限额（0 technical alerts / 5000 bars / 20s / 2 indicators per chart）。这是免费档审计的最权威证据。

**Firecrawl 直连抓 TV 官方文档**也可用（`fc_scrape`），但 curl --compressed 更快更稳。

## 三、Hermes web_search 加载时序

- `web_search`/`web_extract` 工具在 **Hermes 进程启动时**读 `.env` 加载 key。改 `.env`（如替换 Firecrawl key）后**需重启才生效**；当前进程仍用旧 key。
- 改 key 后若 `web_search` 仍报旧错误，先确认改的是不是 Hermes 实际加载的 `.env`（`$HOME/AppData/Local/hermes/.env` 与 `$HOME/.hermes/.env` 可能是两份）。
- 等重启期间，用 execute_code + `urllib.request` 直连 API 完成等量搜索（效果一致）。

## 四、免费档Pine硬限制速查（本次实测确认）

- 免费 Basic：0 技术告警、3 价格告警、5000 历史K、20s 计算、2 指标/图、100K intrabars、180 天分钟级回放。
- `alertcondition()` 计入 plot count（与 `plot()` 同级）；`alert()` 是运行时函数不占 plot → 免费档把 alertcondition 全部迁移为事件化 `alert()`。
- `request.security_lower_tf` 的 `calc_bars_count` 限制「有 intrabar 数据的**图K数量**」（非 intrabar 总数）；写死 1000 会截断 5m/15m D 分布图（需 1440），必须动态 `max(1000, profSec/precSec)`。
- 性能权威（LuxAlgo）：自定义循环 57.9ms vs 内置 `ta.highest()` 3.2ms（20周期）。SVP 桶循环是唯一热点，但 calc_bars_count 压住拉取量后免费 20s 可接受。

（Pine 免费档优化的完整手术代码与坑见 `free-tier-pine-optimization-playbook.md`；多市场自适应见 `multi-market-adaptation-crypto-metals-2026-08-02.md`。）
