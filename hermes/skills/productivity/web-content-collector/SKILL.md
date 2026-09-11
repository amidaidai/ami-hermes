---
name: web-content-collector
description: 网页内容采集技能 — 从任意 URL 提取正文内容、采集社交媒体帖子、批量抓取列表页、保存为 Markdown/JSON。首发适配常见中文网站（知乎、微博、雪球、公众号文章）。
category: productivity
---

# Web Content Collector

> 核心工具：requests + BeautifulSoup4 / trafilatura / opencli browser

## 方法选择
| 场景 | 推荐工具 |
|------|---------|
| 静态文章/文档页 | web_extract（最快） |
| 需 JS 渲染的页面 | browser_navigate |
| 需要登录态 | browser_navigate（本地 Chrome CDP） |
| X/Twitter 单帖 | terminal curl（HTML meta 标签免费拿全文，无需登录） |
| 静态 API/JSON/.md | terminal curl（免费，无额度限制） |
| 批量列表页 | requests + bs4 循环翻页 |
| RSS/Feed | blogwatcher-cli |

## 降级链（不可绕过）

当首选工具失败时，**必须静默降级**，不可向用户报告工具层面的错误：

```
web_extract (firecrawl, 付费有限额)
  ↓ 失败 → 静默降级
terminal curl (免费，X meta tags / 纯文本 / API / .json / .md)
  ↓ 失败 → 静默降级
browser_navigate (免费，动态 JS 页面)
  ↓ 失败 → 静默降级
web_search (免费，搜索替代)
  ↓ 全挂
报用户（仅报告"无法获取该页面"，不提及具体哪个工具失败）
```

### 核心规则
- **永远不向用户报工具层面错误**（"没额度了"、"API key 失效"等）。用户不需要知道工具栈的细节。
- **优先想免费资源**：本地浏览器、terminal curl、web_search。不要默认只走付费后端。
- **X/Twitter 帖子**优先用 `terminal curl` 直接从 HTML meta 标签提取全文（og:description 包含完整内容），比 web_extract 和 browser 都更快更省。`curl -s "https://x.com/user/status/ID" | grep -oP '(?<=<meta property="og:description" content=").*?(?=")'`
- **所有失败都在内部消化**，只有全部兜底耗尽后才告知用户结果不可达。

## 通用正文提取（trafilatura）

```python
import trafilatura

# 下载并提取
downloaded = trafilatura.fetch_url(url)
text = trafilatura.extract(downloaded)
# 或保留 Markdown 格式
text = trafilatura.extract(downloaded, output_format='markdown')

# 保存
with open('article.md', 'w', encoding='utf-8') as f:
    f.write(text)
```

## 简单静态页（BeautifulSoup）

```python
import requests
from bs4 import BeautifulSoup
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
resp = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(resp.text, 'html.parser')

# 提取所有文本
text = soup.get_text(separator='\n', strip=True)

# 提取文章正文（通用启发式）
article = soup.find('article') or soup.find(class_=re.compile(r'article|content|post|main'))
if article:
    text = article.get_text(separator='\n', strip=True)
```

## 批量列表页翻页

```python
def scrape_list(base_url, pages=5):
    results = []
    for page in range(1, pages + 1):
        url = f"{base_url}?page={page}"
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.item-title a')  # 根据需要修改选择器
        for item in items:
            results.append({'title': item.text.strip(), 'url': item['href']})
    return results
```

## 保存为结构化数据

```python
import json, yaml

# Markdown
with open('output.md', 'w') as f:
    f.write(f"# {title}\n\n{content}")

# JSON
with open('output.json', 'w') as f:
    json.dump(items, f, ensure_ascii=False, indent=2)

# CSV
import csv
with open('output.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['title', 'url'])
    w.writeheader()
    w.writerows(items)
```

## 中文网站适配备忘

| 网站 | 策略 |
|------|------|
| 知乎文章 | web_extract 通常可用；否则 opencli browser + adapter |
| 雪球 | 可直接 API 或 web_extract |
| 公众号文章 | 需浏览器渲染（opencli browser） |
| 微博 | opencli browser（登录态） |
| X/Twitter | opencli browser（x adapter） |
| 简书/CSDN | web_extract 通常可用 |

## 注意事项
- 尊重 robots.txt，合理设置请求间隔（time.sleep(1-3)）
- 中文编码问题：`resp.encoding = resp.apparent_encoding`
- 需要登录的内容先用 opencli browser 获取登录态
- 反爬严格的站点（限制频率/IP）用浏览器 + 随机延迟
- 这里只是模板，具体选择器需根据目标网站实际情况调整
