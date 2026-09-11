---
name: slack-gif-creator
category: community
description: Create animated GIFs optimized for Slack.
---

# Slack GIF Creator — Animated GIFs for Slack

Create animated GIFs optimized for Slack: proper size limits, frame rates, and color palettes to ensure smooth playback in Slack messages.

## When to use

- You want to share an animated demo or screenshot in Slack
- You need to record a short interaction or workflow for team communication
- You're creating reaction GIFs or status animations for Slack
- Any animated content destined for Slack channels

## Slack GIF Requirements

| Parameter | Limit |
|-----------|-------|
| **File size** | ≤ 32 MB (recommended: ≤ 5 MB for fast loading) |
| **Dimensions** | Max 1280×720 (recommended: 800×450) |
| **Frame rate** | 10-15 FPS (lower for smaller files) |
| **Duration** | ≤ 15 seconds (recommended: ≤ 8 seconds) |
| **Colors** | 256-color palette (use adaptive palette for quality) |
| **Loop** | Should loop (Slack doesn't require it, but it's expected) |

## Creating GIFs from Screen Recordings

### Using FFmpeg

```bash
# Record screen to GIF (macOS)
ffmpeg -f avfoundation -i "1" -t 5 -vf "fps=10,scale=800:-1:flags=lanczos" output.gif

# Record screen to GIF (Windows)
ffmpeg -f gdigrab -i desktop -t 5 -vf "fps=10,scale=800:-1:flags=lanczos" output.gif

# Convert video to GIF (optimal for Slack)
ffmpeg -i input.mp4 \
  -vf "fps=12,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse=dither=bayer" \
  -loop 0 output.gif
```

### Optimize for Slack

```bash
# Reduce file size by lowering FPS and resolution
ffmpeg -i input.mp4 \
  -vf "fps=8,scale=600:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse" \
  -loop 0 output_slack.gif

# Trim duration to 8 seconds for best Slack experience
ffmpeg -i input.mp4 -t 8 \
  -vf "fps=10,scale=800:-1:flags=lanczos,palettegen=max_colors=256[p];[s0][p]paletteuse" \
  -loop 0 output_trimmed.gif
```

## Creating Animated GIFs from Code

```python
from PIL import Image
import os

def create_slack_gif(frames, output_path, fps=10, max_size=(800, 450)):
    """
    Create a Slack-optimized GIF from a list of PIL Image frames.
    """
    processed = []
    for frame in frames:
        # Resize
        frame.thumbnail(max_size, Image.LANCZOS)
        # Convert to 'P' mode (palette) for smaller file size
        frame = frame.convert('P', palette=Image.ADAPTIVE, colors=128)
        processed.append(frame)
    
    duration = int(1000 / fps)  # ms per frame
    processed[0].save(
        output_path,
        save_all=True,
        append_images=processed[1:],
        duration=duration,
        loop=0,
        optimize=True
    )
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"GIF saved: {output_path} ({size_mb:.2f} MB)")
    return output_path

# Create a simple animated GIF
def create_bouncing_ball_gif():
    frames = []
    for i in range(30):
        img = Image.new('RGB', (200, 200), '#f8f9fa')
        y = 100 + int(80 * abs((i / 15) - 1))  # bounce
        for dx in range(-15, 16):
            for dy in range(-15, 16):
                if dx*dx + dy*dy <= 225:
                    img.putpixel((100+dx, y+dy), (100, 150, 255))
        frames.append(img)
    return frames
```

## Tools Comparison

| Tool | Use Case | Quality | File Size |
|------|----------|---------|-----------|
| FFmpeg | Command-line, automatable | Best | Small |
| PIL/Pillow | Programmatic Python | Good | Medium |
| GIPHY Capture | Quick recording | Good | Medium |
| ScreenToGif (Win) | GUI + cropping | Good | Small |
| Gifski (macOS) | High quality video→GIF | Best | Large |

## Best Practices for Slack

1. **Keep it short** — 5-8 seconds is ideal; Slack users won't watch a 30-second GIF
2. **Show the action** — crop tightly around the relevant area (not full screen)
3. **Add a caption** — mention what the GIF demonstrates in the message text
4. **Test the loop** — make sure the GIF loops seamlessly or has a clear start/end
5. **Avoid text-heavy GIFs** — text becomes unreadable at 256 colors
6. **Preview before posting** — download and check how it looks in Slack

## Pitfalls

- Slack compresses GIFs server-side — what you upload may look slightly different after processing
- Some Slack clients (mobile) autoplay GIFs with sound off — but animated content still uses data
- Large GIFs (>5MB) may take a few seconds to load in Slack — optimize aggressively
- Animated PNG (APNG) is not supported in Slack — must be .gif format
- Transparency in GIFs is only 1-bit (fully transparent or fully opaque) — no alpha blending

## Verification

Upload the GIF to a Slack channel or DM. Verify: it plays automatically, loops correctly, the file size is under 5 MB, and the content is clearly visible at the resized dimensions.
