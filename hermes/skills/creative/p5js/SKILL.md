---
name: p5js
category: creative
description: 'p5.js sketches: generative art, shaders, interactive, 3D.'
tags:
  - p5js
  - generative-art
  - creative-coding
  - javascript
  - shaders
  - 3d
---

# p5.js Sketching

Create generative art, interactive visualizations, shader experiments, and 3D scenes with p5.js.

## Getting Started

p5.js sketches follow a standard structure:

```javascript
function setup() {
  createCanvas(800, 600);
  // initialization code
}

function draw() {
  background(0);
  // animation/drawing code
}
```

## Core Drawing Functions

### 2D Primitives
- `ellipse(x, y, w, h)` — circles/ellipses
- `rect(x, y, w, h)` — rectangles
- `triangle(x1, y1, x2, y2, x3, y3)` — triangles
- `line(x1, y1, x2, y2)` — lines
- `arc(x, y, w, h, start, stop)` — arcs/pies

### Transformations
- `translate(x, y)` — move coordinate system
- `rotate(angle)` — rotate (radians)
- `scale(s)` — scale
- `push()` / `pop()` — save/restore transformation state

### Color
- `color(r, g, b)` — create color
- `fill()` / `noFill()` — shape fill
- `stroke()` / `noStroke()` — outline
- `lerpColor(c1, c2, amt)` — color interpolation
- `colorMode(HSB)` — use HSB for easier color cycling

### Noise & Random
- `random(min, max)` — uniform random
- `noise(x, y, z)` — Perlin noise (0-1)
- `noiseSeed(seed)` — reproducible noise
- `randomSeed(seed)` — reproducible random

## Generative Art Patterns

### Recursive Patterns
```javascript
function drawCircle(x, y, r) {
  ellipse(x, y, r, r);
  if (r > 4) {
    drawCircle(x + r/2, y, r/2);
    drawCircle(x - r/2, y, r/2);
  }
}
```

### Particle Systems
Create arrays of objects with position, velocity, acceleration. Apply forces, decay, and regeneration for organic effects.

### Flow Fields
Use Perlin noise to create directional fields that particles follow. Map noise(x, y) to angle, rotate velocity vector.

## WebGL / 3D

```javascript
function setup() {
  createCanvas(800, 600, WEBGL);
}
```

- `box(w, h, d)` — 3D box
- `sphere(r)` — sphere
- `torus(r, tubeR)` — torus
- `orbitControl()` — mouse-driven camera
- `createGraphics()` for off-screen rendering
- `texture()` for mapping images to 3D

## Shaders (GLSL)

Load `.vert` and `.frag` shader files, or create them inline:
- `createShader(vertSrc, fragSrc)`
- `shader.setUniform('name', value)`
- `rect(-1, -1, 2, 2)` for full-screen passes

## Performance Tips

- Use `frameRate(30)` for complex sketches
- Pre-compute noise fields for flow fields
- Use `p5.Graphics` for buffer caching
- Limit `draw()` loops with modulo timing
- Use `millis()` for time-based animations instead of frame counting

## Embedding

p5.js sketches can be embedded as standalone HTML:
```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js"></script>
</head>
<body>
  <script>
    function setup() { createCanvas(400, 400); }
    function draw() { /* your sketch */ }
  </script>
</body>
</html>
```
