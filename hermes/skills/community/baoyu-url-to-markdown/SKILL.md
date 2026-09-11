---
name: baoyu-url-to-markdown
category: community
description: Fetch any URL and convert to markdown using Chrome CDP with site-specific adapters.
tags:
  - url-to-markdown
  - web-scraping
  - chrome-cdp
  - markdown
  - content-extraction
---

# Baoyu URL to Markdown

Fetch any URL and convert the content to clean Markdown using Chrome DevTools Protocol (CDP) with site-specific adapters.

## Overview

Extract readable content from any web page and convert it to well-structured Markdown. Uses Chrome CDP for JavaScript-rendered pages and supports site-specific adapters for optimal extraction from popular platforms.

## Architecture

```
URL → Chrome CDP (render JS) → DOM extraction → Site Adapter → Markdown output
```

## Supported Sites (via adapters)

| Platform | Adapter | Features |
|----------|---------|----------|
| **Medium** | `medium` | Article body, title, author, date |
| **Zhihu** | `zhihu` | Question + answers, comments |
| **WeChat** | `wechat` | Article content, metadata |
| **Jianshu** | `jianshu` | Full article |
| **Wikipedia** | `wikipedia` | Article + infobox |
| **GitHub** | `github` | README, issues, PRs |
| **Blogger/WordPress** | `generic` | Main content, comments |
| **Reddit** | `reddit` | Post + top comments |
| **Twitter/X** | `twitter` | Thread conversion |
| **Any site** | `generic` | Readability extraction |

## Extraction Rules

### Generic Extraction (Readability)
1. Remove navigation, headers, footers, sidebars
2. Identify main content area (`<article>`, `[role="main"]`, `.post-content`)
3. Extract heading hierarchy (h1→h2→h3)
4. Preserve: paragraphs, lists, code blocks, tables, images (with alt text)
5. Convert: links, bold, italic, blockquotes
6. Strip: scripts, styles, ads, tracking elements, social widgets

### Markdown Output Structure
```markdown
# Title
**Author** | *Date*

> Description/summary

## Section 1
Content with [links](url) and **formatting**.

![alt](image_url)

- List items
- More items

## Section 2
...
```

## Chrome CDP Configuration

```python
# Pseudocode
options = {
    "headless": True,
    "viewport": {"width": 1280, "height": 720},
    "timeout": 30000,  # ms
    "wait_until": "networkidle0",  # Wait for all network requests
    "block_resources": ["image", "font", "media"],  # Speed up
}
```

## Pitfalls

- Single-page apps (SPA) may need longer wait times
- Infinite scroll pages require scroll-down automation
- Login-walled content cannot be extracted
- Rate limiting — add delays between requests
- Some sites block headless Chrome — use stealth plugins if needed
- Image relative URLs need to be resolved to absolute
- Tables with merged cells may not convert cleanly
