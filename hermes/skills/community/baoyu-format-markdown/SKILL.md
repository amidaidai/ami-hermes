---
name: baoyu-format-markdown
description: Format markdown files with frontmatter, titles, headings, lists, tables, and consistent styling. Use when user asks to format a markdown file, clean up markdown styling, ensure consistent heading hierarchy, or apply markdown best practices.
---

# Markdown Formatter

Format markdown files for consistency, readability, and best practices.

## Formatting Rules

### Frontmatter
- Always use YAML frontmatter delimited by `---`
- Fields: `title`, `description`, `date` (ISO 8601), `tags` (array)
- No trailing whitespace in frontmatter values
- Optional fields: `author`, `status` (draft/published/archived)

### Heading Hierarchy
- Only one H1 (# Title) per document — the title
- H2 (##) for major sections
- H3 (###) for subsections
- H4 (####) sparingly — consider restructuring if you need H4
- No skipped levels (don't go H1 → H3)
- Headings have a blank line before and after

### Paragraphs and Line Breaks
- One blank line between paragraphs
- No trailing spaces (except for intentional line breaks = two spaces + newline)
- No tabs — use spaces only

### Lists
- Unordered: Use `- ` (not `* ` or `+ `)
- Ordered: Use `1. ` (markdown auto-numbers)
- Nested: Indent 2 spaces per level
- Blank line before and after lists

### Code Blocks
- Fenced with triple backticks: ```language
- Always specify language for syntax highlighting
- Inline code: Use single backticks for `code` references
- No indented code blocks (use fences)

### Tables
- Use pipes and dashes
- Align columns with consistent widths
- Header separator row: `|---|---|---|`
- Blank line before and after tables

### Links and Images
- `[text](url)` for links
- `![alt](url)` for images
- Use reference-style links for repeated URLs: `[text][ref]` and `[ref]: url`

### Emphasis
- **Bold**: Double asterisks (not underscores)
- *Italic*: Single asterisk
- ~~Strikethrough~~: Double tilde
- No mixed formatting unless necessary

## Process

1. Read the input markdown file
2. Apply formatting rules above
3. Preserve all original content — only change formatting
4. Output the formatted markdown
