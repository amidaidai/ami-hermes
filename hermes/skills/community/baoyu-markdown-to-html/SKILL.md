---
name: baoyu-markdown-to-html
category: community
description: Convert Markdown to styled HTML with WeChat-compatible themes.
tags:
  - markdown
  - html
  - wechat
  - conversion
  - formatting
---

# Baoyu Markdown to HTML

Convert Markdown content to styled HTML with WeChat-compatible themes for publishing on WeChat Official Accounts (微信公众号).

## Overview

Transform Markdown documents into beautifully formatted HTML that renders correctly within the WeChat ecosystem, including WeChat Official Articles, and other Chinese content platforms with limited CSS support.

## Supported Markdown Features

```markdown
# H1
## H2
### H3

**Bold** *Italic* ~~Strikethrough~~ `Inline Code`

- Unordered list
1. Ordered list

> Blockquote

[Link](url)
![Image](url)

| Table | Header |
|-------|--------|

`code block`
```

## WeChat-Compatible HTML

WeChat Official Articles have limited CSS support. The output follows these constraints:

### Supported CSS
- `color`, `background-color`
- `font-size`, `font-weight`, `font-style`
- `text-align`, `line-height`
- `margin`, `padding`
- `border` (simple)
- `width`, `height` (inline)
- **No** flexbox, grid, absolute positioning, media queries

### HTML Structure

```html
<section style="...">
  <h1 style="...">Title</h1>
  <p style="...">Paragraph with <strong>bold</strong> and <em>italic</em>.</p>
  <blockquote style="...">
    <p>Quote content</p>
  </blockquote>
  
  <!-- Image -->
  <p>
    <img src="url" alt="description" style="max-width:100%;">
  </p>
  
  <!-- Code block -->
  <pre style="..."><code>code content</code></pre>
  
  <!-- Table -->
  <table style="...">
    <thead><tr><th>Header</th></tr></thead>
    <tbody><tr><td>Cell</td></tr></tbody>
  </table>
</section>
```

## Theme Options

| Theme | Description | Best For |
|-------|-------------|----------|
| **WeChat Clean** | White bg, dark text, blue links | Standard articles |
| **WeChat Warm** | Cream bg, brown accents | Lifestyle, culture |
| **Minimal** | Monochrome, clean lines | Professional content |
| **Tech Blue** | Blue highlights, code-friendly | Tech tutorials |
| **Green Reading** | Green tints, easy on eyes | Long-form reading |

## Conversion Rules

| Markdown | HTML | WeChat Notes |
|----------|------|-------------|
| `# Heading` | `<h2>` (skip h1, use h2 for WeChat) | WeChat ignores h1 margin |
| `**bold**` | `<strong>` | Full support |
| `` `code` `` | `<code style="...">` | Needs inline bg-color |
| Code block | `<pre><code>` | Use monospace, bg color |
| Image | `<img src="..." style="max-width:100%">` | WeChat auto-scales images |
| Table | `<table>` | Need inline borders |
| Blockquote | `<blockquote>` | Use left border style |

## Pitfalls

- WeChat strips `<style>` tags — all CSS must be inline
- WeChat ignores `class` attributes — all styling must be inline
- WeChat compresses images > 10MB
- Some emoji render differently on WeChat vs other platforms
- WeChat limits article length (consider splitting very long articles)
- Inline CSS increases HTML size significantly — use short property names
