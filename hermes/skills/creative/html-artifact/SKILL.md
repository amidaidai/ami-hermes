---
name: html-artifact
category: creative
description: Build self-contained HTML files to explain, plan, or review.
tags:
  - html
  - artifact
  - prototype
  - documentation
  - self-contained
---

# HTML Artifact

Build self-contained, single-file HTML artifacts for explaining concepts, planning projects, or reviewing designs.

## Principles

1. **Single file** — Everything in one `.html`, no external resources except CDN libraries
2. **Works offline** — No server required, just open in browser
3. **Fully styled** — Clean, readable, visually appealing
4. **Self-documenting** — The artifact itself is the deliverable

## Common Use Cases

| Purpose | Structure | Key Features |
|---------|-----------|-------------|
| **Concept explainer** | Narrative scroll | Interactive diagrams, code samples, callouts |
| **Project plan** | Dashboard layout | Timelines, task lists, progress bars |
| **Design review** | Gallery + annotations | Image comparison, side-by-side views, notes |
| **API reference** | Two-panel layout | Navigation sidebar, code blocks, live examples |
| **Report/case study** | Article format | Charts, data tables, citations |

## Template Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Artifact Title</title>
  <style>
    /* Reset, typography, layout, components */
  </style>
</head>
<body>
  <!-- Navigation / header -->
  <!-- Main content -->
  <!-- Footer / metadata -->
  <script>
    // Interactivity, data, rendering
  </script>
</body>
</html>
```

## CSS Architecture

- Use CSS custom properties for theming
- `@media (prefers-color-scheme: dark)` for dark mode
- Responsive grid layout with `minmax()`
- Sticky headers/sidebars for navigation
- Print-friendly styles via `@media print`

## JavaScript Patterns

- `DOMContentLoaded` for initialization
- `IntersectionObserver` for scroll interactions
- `Element.scrollIntoView({ behavior: 'smooth' })` for nav
- Local storage for user preferences (theme, collapsed sections)
- Canvas/SVG for custom graphics without external images

## Pitfalls

- Avoid external dependencies that break offline use
- Test in multiple browsers (Chrome, Firefox, Safari)
- Keep file size reasonable (< 1MB ideal, < 5MB acceptable)
- Include a clear title and description in the HTML metadata
- Use semantic HTML for accessibility and SEO
