---
name: ascii-art
category: creative
description: 'ASCII art: pyfiglet, cowsay, boxes, image-to-ascii.'
tags:
  - ascii-art
  - pyfiglet
  - cowsay
  - terminal
  - image-to-ascii
---

# ASCII Art

Generate ASCII art using pyfiglet, cowsay, boxes, and image-to-ASCII conversion tools.

## Tools & Commands

### pyfiglet (Python)
Generate text banners in various fonts:
```python
import pyfiglet
result = pyfiglet.figlet_format("Hello", font="slant")
print(result)
```

**Popular fonts:** `slant`, `big`, `banner`, `block`, `bubble`, `digital`, `epic`, `graffiti`, `isometric1`, `letters`, `mini`, `script`, `shadow`, `smkeyboard`, `smslant`, `standard`, `starwars`, `stop`, `thin`, `3-d`

List all fonts:
```python
pyfiglet.FigletFont.getFonts()
```

### cowsay
Classic ASCII animals with speech bubbles:
```bash
cowsay "Hello world"
cowsay -f tux "Linux!"
cowsay -f dragon "Fire"
```

**Common cowfiles:** `default`, `tux`, `dragon`, `dragon-and-cow`, `elephant`, `bunny`, `koala`, `moose`, `sheep`, `stegosaurus`, `turkey`, `turtle`

### boxes
Draw boxes around text:
```bash
echo "Hello" | boxes -d ada-cmt
boxes -l  # list available designs
```

### image-to-ascii (Python)
Convert images to ASCII using `pillow`:
```python
from PIL import Image

ASCII_CHARS = "@%#*+=-:. "

def image_to_ascii(path, width=80):
    img = Image.open(path).convert('L')  # grayscale
    ratio = img.height / img.width * 0.55
    height = int(width * ratio)
    img = img.resize((width, height))
    pixels = img.getdata()
    chars = "".join(ASCII_CHARS[p // 32] for p in pixels)
    return "\n".join(chars[i:i+width] for i in range(0, len(chars), width))
```

## CLI Quick Reference

| Tool | Install | Usage |
|------|---------|-------|
| pyfiglet | `pip install pyfiglet` | `pyfiglet "text"` |
| cowsay | `apt install cowsay` | `cowsay "text"` |
| boxes | `apt install boxes` | `echo "text" \| boxes` |
| jp2a | `apt install jp2a` | `jp2a image.jpg` |
| chafa | `apt install chafa` | `chafa image.png` |

## Projects & Examples

- **Terminal splash screens** — pyfiglet + color formatting
- **README badges** — ASCII art for repo headers
- **Loading spinners** — animated ASCII frames
- **Minecraft maps** — block-based pixel art
- **System monitoring** — cowsay with system stats

## Pitfalls

- Unicode characters may not display correctly in all terminals
- Some pyfiglet fonts don't support all characters
- Image-to-ASCII works best with high-contrast images
- Cow file paths vary by OS (check with `cowsay -l`)
