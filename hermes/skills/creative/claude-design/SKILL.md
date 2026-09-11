---
name: claude-design
category: creative
description: Design one-off HTML artifacts (landing, deck, prototype).
tags:
  - design
  - html
  - landing-page
  - prototype
  - presentation
---

# Claude Design — HTML Artifacts

Design one-off HTML artifacts including landing pages, slide decks, interactive prototypes, and visual demonstrations.

## Overview

Create complete, self-contained HTML files that serve as:
- **Landing pages** — Product/feature showcases with hero sections, CTAs, feature grids
- **Slide decks** — Presentation-style HTML with slide navigation
- **Interactive prototypes** — Click-through product demos and wireframes
- **Visual artifacts** — Data visualizations, concept art, mood boards

## Design Principles

1. **Self-contained** — Single HTML file, no external dependencies (CDN allowed for libraries)
2. **Responsive** — Works on mobile, tablet, desktop
3. **Accessible** — Semantic HTML, ARIA labels, keyboard navigation
4. **Performant** — Minimal CSS, efficient JS, smooth animations
5. **Visually polished** — Clean typography, consistent spacing, intentional color

## Template Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Design</title>
  <style>
    /* CSS Reset + Design System */
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    /* Typography, colors, spacing */
    :root {
      --primary: #...
      --font: 'Inter', system-ui, sans-serif;
    }
    
    /* Layout & components */
  </style>
</head>
<body>
  <!-- Content -->
  <script>
    // Interactivity
  </script>
</body>
</html>
```

## Common Design Patterns

### Hero Section
- Full-width, centered content
- Large headline + supporting text
- Primary CTA button
- Optional background image/gradient/animation

### Feature Grid
- 2-4 column grid layout
- Icon + title + description per card
- Hover effects (subtle elevation)

### Slide Deck
- Full-viewport slides
- Navigation arrows + keyboard controls
- Progress indicator
- Slide transitions (fade, slide)

### Modal/Overlay
- Centered card with backdrop
- Close button (X) + click-outside-to-close
- Focus trapping for accessibility

## CSS Tips

- Use `clamp()` for fluid typography: `font-size: clamp(1rem, 2.5vw, 2rem)`
- Use CSS Grid for layout: `grid-template-columns: repeat(auto-fit, minmax(300px, 1fr))`
- Prefer `gap` over margins for spacing in flex/grid
- Use `@media (prefers-color-scheme: dark)` for dark mode support
- Animations via `@keyframes` + `animation` or CSS transitions

## JavaScript Interactivity

- Vanilla JS (no frameworks unless specified)
- Event delegation for dynamic content
- `requestAnimationFrame` for smooth animations
- `IntersectionObserver` for scroll-triggered effects
- History API for SPA-like navigation in decks

## Pitfalls

- Don't over-animate — users prefer clarity over flash
- Test color contrast (WCAG AA minimum: 4.5:1)
- Include a skip-to-content link for accessibility
- Don't forget `alt` text on all images
- Test keyboard navigation through all interactive elements
