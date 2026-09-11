---
name: pretext
category: creative
description: 'Creative browser demos with @chenglou/pretext — DOM-free text layout, kinetic typography.'
tags:
  - pretext
  - kinetic-typography
  - creative-coding
  - text-layout
  - browser-demo
---

# Pretext — Creative Typography Demos

Create browser-based kinetic typography and text layout demos using `@chenglou/pretext` — a DOM-free text layout engine for creative coding.

## Overview

Pretext is a lightweight library for text layout in canvas/WebGL contexts. It provides precise control over character positioning for kinetic typography, text animations, and creative browser demos without touching the DOM.

## Installation

```html
<script src="https://unpkg.com/@chenglou/pretext"></script>
```

Or via npm:
```bash
npm install @chenglou/pretext
```

## Basic Usage

```javascript
import { typeset } from '@chenglou/pretext';

// Typeset text — returns character positions and glyph data
const layout = typeset({
  text: "Hello World",
  font: '48px serif',
  width: 400,
  height: 200,
  x: 0,
  y: 100
});

// layout contains: chars[] with { char, x, y, width, glyph }
```

## Core Concepts

### Layout Object
The `typeset()` function returns a layout object:
- `chars` — Array of character objects with position and glyph data
- `width`, `height` — Dimensions of the laid-out text
- `lines` — Line breaks and line positions

### Character Object
Each char in `chars`:
```javascript
{
  char: 'H',          // The actual character
  x: 0,               // X position
  y: 0,               // Y position  
  width: 24,          // Character width
  glyph: {...}         // Font glyph path data (if available)
}
```

## Animation Patterns

### Wave Animation
```javascript
const chars = layout.chars;
chars.forEach((c, i) => {
  c.y += Math.sin(time * 2 + i * 0.3) * 10;
});
```

### Letter Spread
```javascript
chars.forEach((c, i) => {
  c.x += Math.sin(i * 0.5) * 20;
});
```

### Kinetic Typography
Use character positions as targets for particle systems or physics-based animations. Map audio frequency data to character scale/rotation.

## Canvas Rendering

```javascript
function draw(ctx, layout, time) {
  ctx.clearRect(0, 0, 800, 400);
  ctx.fillStyle = 'white';
  ctx.font = '48px sans-serif';
  
  layout.chars.forEach((c, i) => {
    const wave = Math.sin(time + i * 0.2) * 5;
    ctx.fillText(c.char, c.x, c.y + wave);
  });
}
```

## Tips

- Pretext gives position data — you handle the rendering (canvas, WebGL, SVG)
- Works with any font loaded in the browser
- Combine with requestAnimationFrame for smooth animations
- Use with WebGL for GPU-accelerated particle text effects
- Pair with audio analysis for reactive typography
