---
name: manim-video
category: creative
description: 'Manim CE animations: 3Blue1Brown math/algo videos.'
tags:
  - manim
  - animation
  - 3b1b
  - math
  - educational-video
---

# Manim Video (Community Edition)

Create mathematical and algorithmic animations using Manim Community Edition — the animation engine behind 3Blue1Brown videos.

## Installation

```bash
pip install manim
# or
uv pip install manim
```

Verify:
```bash
manim --version
```

## Basic Structure

```python
from manim import *

class MyFirstScene(Scene):
    def construct(self):
        text = Text("Hello, Manim!")
        self.play(Write(text))
        self.wait(2)
```

## Rendering

```bash
# Render to 1080p60 MP4
manim -p -ql file.py MyScene        # low quality (480p)
manim -p -qm file.py MyScene        # medium quality (720p)
manim -p -qh file.py MyScene        # high quality (1080p)
manim -p -qk file.py MyScene        # 4K quality

# Render to GIF
manim -p -ql --format=gif file.py MyScene

# Save last frame
manim -p -ql -s file.py MyScene
```

## Common Objects

### Text & Math
```python
Text("Hello")                         # rendered text
MathTex("E = mc^2")                   # LaTeX math
Tex("The integral of $x^2$ is...")    # inline LaTeX
Title("Chapter 1")                    # auto-formatted title
```

### Shapes
```python
Circle(), Square(), Rectangle()
Triangle(), Polygon(*points)
Dot(), Arrow(), Line()
RegularPolygon(n)
ArcBetweenPoints()
```

### Graphs & Axes
```python
axes = Axes()
axes.plot(lambda x: np.sin(x), color=BLUE)
axes.get_graph_label(graph, label="sin(x)")
```

### Coordinate Systems
```python
NumberPlane(x_range=(-7, 7), y_range=(-4, 4))
ComplexPlane()
PolarPlane()
```

## Animation Methods

### Creation Animations
```python
Write(object)         # text/math writing
Create(object)        # shape drawing
DrawBorderThenFill()  # outline then fill
FadeIn() / FadeOut()
GrowFromCenter()      # scale from zero
```

### Transformations
```python
Transform(a, b)       # morph a into b
ReplacementTransform()  # replace a with b
TransformMatchingShapes()  # smart shape matching
```

### Movement
```python
self.play(obj.animate.shift(RIGHT))
self.play(obj.animate.rotate(PI/4))
self.play(obj.animate.scale(1.5))
self.play(obj.animate.move_to(ORIGIN))
```

### Camera
```python
self.camera.frame.save_state()
self.play(self.camera.frame.animate.scale(0.5).move_to(target))
self.play(Restore(self.camera.frame))
```

## Best Practices

1. **Start simple** — get one animation working before combining
2. **Use `self.wait()`** — give viewer time to process
3. **Color code** — consistent colors improve understanding
4. **Annotation** — label important elements
5. **Progressive disclosure** — reveal complexity step by step
6. **Pre-render complex scenes** — use `-a` flag to render all scenes

## Pitfalls

- Manim v0.17+ has breaking changes from older tutorials — check version
- Complex TeX expressions may need manual escaping
- Animation timing is in seconds, not frames
- `self.play()` blocks — use `lag_ratio` for staggered animations
- GPU acceleration varies by platform (cairo backend on Windows can be slow)
