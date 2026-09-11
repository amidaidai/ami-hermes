---
name: baoyu-slide-deck
category: community
description: Generate professional slide deck images from content.
tags:
  - slide-deck
  - presentation
  - visual-content
  - professional
  - design
---

# Baoyu Slide Deck Generator

Generate professional slide deck images from structured content. Create presentation-ready slides with consistent branding and visual hierarchy.

## Overview

Transform structured content into professionally designed slide images. Supports various slide types, aspect ratios, and visual themes suitable for business presentations, pitch decks, educational content, and conference talks.

## Slide Types

| Type | Purpose | Layout |
|------|---------|--------|
| **Title Slide** | Opening impression | Centered title + subtitle + branding |
| **Section Divider** | Topic transition | Large text + minimal visual |
| **Content Slide** | Main information | Header + body + optional media |
| **Data Slide** | Numbers and stats | Charts + key figures |
| **Quote Slide** | Emphasis | Large quote + attribution |
| **Two-Column** | Comparison | Split layout, text on both sides |
| **Image-Heavy** | Visual showcase | Large image + short caption |
| **Timeline** | Process/progress | Horizontal or vertical timeline |
| **Call to Action** | Closing | Strong message + contact info |

## Aspect Ratios

- **16:9** — Standard widescreen (1920×1080)
- **4:3** — Classic projection (1024×768)
- **9:16** — Mobile/Stories (1080×1920)
- **1:1** — Square social media (1080×1080)

## Theme System

Each theme defines:
- **Color palette** — Primary, secondary, accent, background, text
- **Typography** — Font family, sizes, weights
- **Spacing** — Margins, padding, grid
- **Decorations** — Dividers, icons, shapes

## Content Structure

```yaml
slide_deck:
  title: "Presentation Title"
  subtitle: "Optional subtitle"
  author: "Name"
  theme: "professional-blue" | "minimal-dark" | "warm-creative" | "corporate"
  
  slides:
    - type: "title"
      title: "..."
      subtitle: "..."
    
    - type: "content"
      header: "Slide Title"
      body: |
        - Point 1
        - Point 2
        - Point 3
    
    - type: "data"
      header: "Key Metrics"
      figure: "85%"
      label: "Growth rate"
```

## Design Principles

1. **One idea per slide** — Clear, focused message
2. **Visual hierarchy** — Title > subtitle > body > footnote
3. **Consistent spacing** — Grid alignment throughout
4. **Minimal text** — Slides support the speaker, not replace them
5. **High contrast** — Readable on projectors and screens

## Pitfalls

- Don't use more than 3 font sizes per slide
- Avoid large blocks of text — 6 lines max per slide
- Charts need clear labels and legends
- Test with projected lighting conditions (brighter = lower contrast)
- Keep animations minimal for business contexts
