---
name: ascii-video
category: creative
description: Convert video/audio to colored ASCII MP4/GIF.
tags:
  - ascii-video
  - ffmpeg
  - terminal
  - gif
  - video-conversion
---

# ASCII Video

Convert video and audio files into colored ASCII MP4 or GIF output for terminal playback and creative projects.

## Overview

Transform any video into an ASCII art animation. Each frame is converted to ASCII characters with optional color preservation. Output can be rendered as MP4 (H.264) or GIF.

## Requirements

- `ffmpeg` — video processing
- `python3` with `pillow` and `numpy`

## Core Method

### Frame-by-Frame ASCII Conversion

```python
import subprocess
import os
from PIL import Image
import numpy as np

# Extended ASCII character set (dark → light)
ASCII_CHARS = " .:-=+*#%@BMW"
COLOR_ASCII_CHARS = " .:-=+*#%@BMW"

def frame_to_colored_ascii(frame_path, cols=120):
    """Convert a video frame image to colored ASCII"""
    img = Image.open(frame_path)
    ratio = img.height / img.width * 0.415  # terminal aspect correction
    rows = int(cols * ratio)
    img_small = img.resize((cols, rows))
    
    pixels = np.array(img_small)
    gray = np.mean(pixels[..., :3], axis=2)
    
    result = []
    for y in range(rows):
        line = ""
        for x in range(cols):
            g = int(gray[y, x] / 256 * len(ASCII_CHARS))
            g = min(g, len(ASCII_CHARS) - 1)
            r, gb, b = pixels[y, x, 0], pixels[y, x, 1], pixels[y, x, 2]
            # ANSI true color escape
            line += f"\033[38;2;{r};{gb};{b}m{ASCII_CHARS[g]}\033[0m"
        result.append(line)
    return "\n".join(result)
```

## CLI Workflow

### Using `ffmpeg` + `jp2a` (simple approach)

```bash
# Extract frames
mkdir frames
ffmpeg -i input.mp4 -vf "fps=10,scale=120:-1" frames/frame%04d.png

# Convert frames to ASCII (using jp2a with color)
for f in frames/*.png; do
  jp2a --colors "$f" > "ascii/$(basename $f).txt"
done

# Re-encode ASCII frames back to video
# (Use ffmpeg with a custom script to render text frames)
```

### Using `chafa` (modern, fast)

```bash
chafa input.mp4 --symbols block --colors 256 --scale 0.5 -o output.gif
chafa input.mp4 --symbols all --colors full -o ascii_output.mp4
```

## Rendering Options

| Format | Pros | Cons |
|--------|------|------|
| **MP4 (H.264)** | Small file, wide compat | No transparency |
| **GIF** | Universal, animations | Large file, 256 colors |
| **APNG** | Lossless, transparency | Less supported |
| **Raw text** | Small, copy-paste | No automatic playback |

## Creative Applications

- **Terminal music videos** — sync audio with ASCII streams
- **Live terminal visualizers** — real-time video → ASCII
- **Matrix-style effects** — green-on-black ASCII rain
- **Retro demos** — classic terminal aesthetic with modern video
- **Twitch/stream overlays** — ASCII camera feed

## Pitfalls

- Large resolutions create massive ASCII output (keep cols < 160)
- True color ANSI escapes don't work in all terminals
- Audio sync requires careful frame timing
- GIF generation is slow for long videos
- Font rendering differences affect alignment across systems
