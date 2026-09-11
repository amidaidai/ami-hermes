---
name: html-ppt
category: community
description: "HTML PPT Studio: professional HTML presentations with multiple styles and animations."
---

# HTML PPT — HTML Presentation Studio

Create professional HTML presentations with multiple built-in styles, animations, and transitions. Single-file HTML slides that work in any modern browser.

## When to use

- You need a quick, beautiful presentation without PowerPoint
- You want to share slides as a single HTML file (no dependencies)
- You need custom animations and interactive elements in your slides
- You want version-controllable presentations (markdown+HTML)

## Quick Start

Generate a minimal HTML presentation:

```html
<!DOCTYPE html>
<html>
<head>
<title>My Presentation</title>
<style>
  body { margin: 0; font-family: system-ui; }
  .slide { width: 100vw; height: 100vh; display: flex; 
           align-items: center; justify-content: center; 
           flex-direction: column; page-break-after: always; }
  h1 { font-size: 3em; }
  .bg-dark { background: #1a1a2e; color: white; }
  .bg-light { background: #f8f9fa; color: #333; }
</style>
</head>
<body>
  <div class="slide bg-dark">
    <h1>HTML PPT Studio</h1>
    <p>Professional presentations in HTML</p>
  </div>
  <div class="slide bg-light">
    <h2>Features</h2>
    <ul>
      <li>Single file — zero dependencies</li>
      <li>Multiple styles and themes</li>
      <li>Smooth animations</li>
      <li>Works offline in any browser</li>
    </ul>
  </div>
  <div class="slide bg-dark">
    <h2>Thank You</h2>
    <p>Press → or Space to navigate</p>
  </div>
  <script>
    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        window.scrollBy({ left: window.innerWidth, behavior: 'smooth' });
      } else if (e.key === 'ArrowLeft') {
        window.scrollBy({ left: -window.innerWidth, behavior: 'smooth' });
      }
    });
    // Snap to nearest slide
    window.addEventListener('scrollend', () => {
      const idx = Math.round(window.scrollX / window.innerWidth);
      window.scrollTo({ left: idx * window.innerWidth, behavior: 'smooth' });
    });
  </script>
</body>
</html>
```

## Built-in Styles

### Style 1: Dark/Light Minimal
- `bg-dark` — dark background, white text
- `bg-light` — light background, dark text
- `bg-accent` — accent color background

### Style 2: Gradient Themes
```css
.bg-gradient-blue { background: linear-gradient(135deg, #667eea, #764ba2); }
.bg-gradient-warm { background: linear-gradient(135deg, #f093fb, #f5576c); }
.bg-gradient-tech { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }
```

### Style 3: Card Layout
```css
.card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); 
        border-radius: 16px; padding: 2em; max-width: 800px; }
```

## Animations

```css
@keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.animate { animation: fadeIn 0.6s ease-out; }

@keyframes slideIn { from { transform: translateX(-100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.slide-in { animation: slideIn 0.5s ease-out; }
```

## Navigation Features

- **Arrow keys** ← → for navigation
- **Space** to advance
- **Home/End** to jump to first/last slide
- **Number + Enter** to go to specific slide
- **F** for fullscreen (browser feature)
- **P** to enter presenter mode (show notes)

## Code Slide

```html
<div class="slide bg-dark">
  <h2>Code Example</h2>
  <pre style="background: #2d2d2d; padding: 1em; border-radius: 8px; text-align: left; max-width: 80%;">
<code>function hello() {
  console.log("Hello, World!");
}</code></pre>
</div>
```

## Pitfalls

- Image paths in single-file HTML must be base64-encoded or linked to external URLs
- Fonts: use system fonts or include Google Fonts via `@import` for offline capabilities
- Very many slides (>100) may cause sluggish scroll performance
- CSS `page-break-after: always` helps with printing but isn't perfect in all browsers

## Verification

Open the HTML file in Chrome, Firefox, and Edge (or Chromium-based browser). Verify navigation keys work, animations play, and content renders correctly at 1920×1080.
