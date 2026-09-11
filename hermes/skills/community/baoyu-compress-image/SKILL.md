---
name: baoyu-compress-image
category: community
description: Compress images to WebP or PNG with automatic tool selection.
tags:
  - image-compression
  - webp
  - png
  - optimization
  - performance
---

# Baoyu Image Compressor

Compress images to WebP or PNG format with automatic tool selection for optimal size/quality balance.

## Overview

Automatically compress and convert images to the optimal format. Supports batch processing, quality control, and format selection based on image content analysis.

## Supported Formats

### Input
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif, non-animated)
- WebP (.webp)
- BMP (.bmp)
- TIFF (.tiff)
- SVG (.svg, rasterized)

### Output
- **WebP** — Best for web (smaller size, supports transparency)
- **PNG** — Best for lossless quality and transparency
- JPEG — Fallback when WebP/PNG not suitable

## Automatic Tool Selection

The system selects the best compression tool based on:

1. **Image type** — Photo vs graphic vs screenshot
2. **Content analysis** — Flat colors, gradients, text
3. **Size target** — File size constraint if provided
4. **Quality requirement** — Lossless vs lossy

### Tool Preference
| Input Type | Recommended Output | Tool |
|-----------|-------------------|------|
| Photo (JPEG) | WebP (lossy, q=80) | cwebp / libwebp |
| Graphic/UI | PNG (lossless) | pngquant / optipng |
| Screenshot | WebP (lossless) | cwebp -lossless |
| Icon/Logo | PNG (lossless) | pngcrush |
| Mixed content | WebP (lossy, q=90) | avifenc / cwebp |

## Quality Settings

```
Quality Range: 0-100

Lossy:
  q=80-95: High quality (default for photos)
  q=60-80: Good quality, smaller size
  q=30-60: Acceptable for thumbnails
  q<30: Poor quality, very small

Lossless:
  WebP: -lossless flag
  PNG: zlib compression level (0-9)
```

## Batch Processing

```bash
# Convert all JPGs to WebP
for img in *.jpg; do
  cwebp -q 80 "$img" -o "${img%.jpg}.webp"
done

# Compress all PNGs
for img in *.png; do
  pngquant --quality=70-90 "$img" --output "${img%.png}-compressed.png"
done
```

## Size Targeting

If a specific file size is needed (e.g., < 100KB):
1. Start with default quality (q=80)
2. Binary search quality (q=40, 60, 70, 75...) until size fits
3. If WebP at q=10 still too large, reduce dimensions

## Pitfalls

- Lossy WebP can show artifacts on text-heavy images — prefer lossless for screenshots
- Animated WebP/PNG requires special handling
- Re-compressing already compressed images degrades quality
- PNG compression is CPU-intensive at max level
- Always preserve originals — compression is destructive for lossy formats
- Check transparency support: WebP and PNG support alpha; JPEG does not
