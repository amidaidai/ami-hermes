---
name: sketch
category: creative
description: 'Throwaway HTML mockups: 2-3 design variants to compare.'
tags:
  - sketch
  - mockup
  - design
  - html
  - prototyping
---

# Sketch — HTML Mockup Variants

Create throwaway HTML mockups with 2-3 design variants side-by-side for quick comparison and iteration.

## Purpose

Rapid visual exploration of design alternatives before committing to implementation. Unlike polished artifacts, sketches are meant to be:
- **Fast** — Build in minutes, not hours
- **Disposable** — Meant to be thrown away after decisions are made
- **Comparative** — Multiple variants shown together for easy evaluation

## Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>Sketch — Variant Comparison</title>
  <style>
    /* Minimal styling — just enough to convey the idea */
    body { font-family: system-ui; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
    .variant { border: 1px solid #ddd; padding: 16px; }
    .variant-label { text-align: center; font-weight: bold; }
  </style>
</head>
<body>
  <h1>Design Sketch: [Feature Name]</h1>
  <div class="grid">
    <div class="variant">
      <h2>Variant A: [Concept]</h2>
      <!-- Mockup content -->
    </div>
    <div class="variant">
      <h2>Variant B: [Concept]</h2>
      <!-- Mockup content -->
    </div>
    <div class="variant">
      <h2>Variant C: [Concept]</h2>
      <!-- Mockup content -->
    </div>
  </div>
  <script>
    // Optional: toggle highlights, annotation layer
  </script>
</body>
</html>
```

## What to Sketch

- **Layout variants** — Different information hierarchy
- **Navigation patterns** — Tabs vs sidebar vs hamburger
- **Color/theme experiments** — Light vs dark, accent colors
- **Interaction states** — Empty, loading, error, success
- **Component placements** — CTA position, image placement

## Best Practices

- Use placeholder text (lorem ipsum or meaningful but rough text)
- Grey boxes for images ("grey box" technique)
- Include annotations explaining design rationale
- Number or letter variants for easy reference
- Add a short comparison table at the bottom

## Pitfalls

- Don't spend time on pixel-perfect alignment — it's disposable
- Avoid real data or sensitive information
- Don't combine with production CSS — keep styling minimal
- Resist the urge to polish — the goal is comparison, not production
