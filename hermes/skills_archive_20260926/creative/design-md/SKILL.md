---
name: design-md
category: creative
description: Author/validate/export Google DESIGN.md token spec files.
tags:
  - design
  - design-tokens
  - design-md
  - spec
  - google
---

# DESIGN.md — Design Token Spec

Author, validate, and export Google-style `DESIGN.md` token specification files for design systems.

## Overview

`DESIGN.md` is a convention for documenting design tokens — the atomic values (colors, spacing, typography, shadows) that define a design system. Files follow a structured markdown format that can be parsed by automated tools.

## File Structure

```markdown
# Design System Name

## Colors

| Token | Value | Description |
|-------|-------|-------------|
| color-primary | #1a73e8 | Primary action color |
| color-secondary | #185abc | Hover state |
| color-background | #ffffff | Page background |

## Typography

| Token | Value | Description |
|-------|-------|-------------|
| font-family-base | 'Inter', sans-serif | Body text |
| font-size-sm | 0.875rem | Small/caption |
| font-size-base | 1rem | Body text |
| font-weight-normal | 400 | Regular weight |

## Spacing

| Token | Value | Description |
|-------|-------|-------------|
| spacing-xs | 0.25rem | 4px |
| spacing-sm | 0.5rem | 8px |
| spacing-md | 1rem | 16px |
| spacing-lg | 1.5rem | 24px |
| spacing-xl | 2rem | 32px |
```

## Sections

### Required
- `## Colors` — All color tokens with hex/rgb values
- `## Typography` — Font families, sizes, weights, line heights

### Optional
- `## Spacing` — Margin/padding values
- `## Shadows` — Box shadow definitions
- `## Borders` — Border widths, radii, styles
- `## Breakpoints` — Responsive breakpoints
- `## Animation` — Duration, easing curves
- `## Z-Index` — Layer stacking values
- `## Icons` — Icon sizes and metadata

## Token Naming Conventions

Follow BEM-inspired naming:
- `category-property-state` (e.g., `color-primary-hover`)
- `component-property` (e.g., `button-background`)
- Namespace with category prefixes to avoid collisions

## Exporting

### To JSON (for Figma/design tools)
```python
import json
import re

def design_md_to_json(md_content):
    tokens = {}
    current_section = None
    for line in md_content.split('\n'):
        if line.startswith('## '):
            current_section = line.strip('# ').lower()
            tokens[current_section] = {}
        elif '|' in line and line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 2 and parts[0] and not parts[0].startswith('-'):
                category = current_section.rstrip('s')  # colors → color
                tokens[current_section][parts[0]] = {
                    'value': parts[1],
                    'description': parts[2] if len(parts) > 2 else ''
                }
    return json.dumps(tokens, indent=2)
```

### To CSS Custom Properties
```css
:root {
  --color-primary: #1a73e8;
  --spacing-md: 1rem;
  /* ... */
}
```

## Validation Rules

- All colors must be valid hex/rgb/hsl values
- All spacing values must include units (px, rem, em)
- No duplicate token names within the same section
- Descriptions should be meaningful (avoid "used for things")
- Every section should have at least one token

## Pitfalls

- Don't use raw values without documenting them — this defeats the purpose
- Keep token names consistent across the entire system
- Avoid overly specific names (prefer `color-primary` over `color-button-save-background`)
- Document both light and dark mode tokens if applicable
