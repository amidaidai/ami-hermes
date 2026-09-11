---
name: gpt-image2-ppt
category: community
description: "Generate PPT slides via gpt-image-2: high-res PNGs and 16:9 PPTX."
---

# GPT Image 2 PPT — Image-to-Presentation Pipeline

Generate presentation slides using `gpt-image-2` (OpenAI GPT Image generation). Create high-resolution PNG slide images and assemble them into a 16:9 PPTX file.

## When to use

- You want AI-generated visuals for each slide of your presentation
- You need consistent, high-quality slide backgrounds or full-slide images
- You want to convert AI-generated images into a standard PPTX format
- You're creating visual-heavy presentations (portfolio, mood boards, concept decks)

## Workflow

### Step 1: Plan slide content

```markdown
## Slide Plan

1. **Title slide** — "AI Innovation 2024" with futuristic tech theme
2. **Content slide** — "Market Growth" with upward trend visuals
3. **Data slide** — "Revenue by Quarter" with chart-friendly layout
4. **Closing slide** — "Thank You" with contact info
```

### Step 2: Generate slide images

Use gpt-image-2 to generate each slide as a high-res PNG:

```python
# Pseudocode — adapt to your image generation API
import openai

SLIDES = [
    {
        "prompt": "Professional presentation title slide, dark blue background, 
                   white text 'AI Innovation 2024', subtle grid pattern,
                   minimalist tech style, 16:9 aspect ratio, high quality",
        "style": "vivid"
    },
    {
        "prompt": "Presentation content slide, light gray background,
                   'Market Growth' heading, clean professional layout,
                   placeholder for charts, 16:9, business style",
        "style": "natural"
    },
]

images = []
for i, slide in enumerate(SLIDES):
    response = openai.images.generate(
        model="gpt-image-2",
        prompt=slide["prompt"],
        n=1,
        size="1792x1024",  # 16:9 high-res
        quality="hd"
    )
    image_url = response.data[0].url
    images.append(image_url)
    print(f"Slide {i+1}: {image_url}")
```

### Step 3: Assemble into PPTX

```python
from pptx import Presentation
from pptx.util import Inches
import requests
from io import BytesIO

prs = Presentation()
# Set 16:9 aspect ratio
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

for i, image_url in enumerate(images):
    # Download image
    resp = requests.get(image_url)
    img_stream = BytesIO(resp.content)
    
    # Add blank slide
    slide_layout = prs.slide_layouts[6]  # Blank layout
    slide = prs.slides.add_slide(slide_layout)
    
    # Add image as full-slide background
    slide.shapes.add_picture(
        img_stream, 
        Inches(0), Inches(0),
        Inches(13.333), Inches(7.5)
    )

prs.save("presentation.pptx")
print(f"Saved presentation.pptx with {len(images)} slides")
```

### Step 4: Alternative — generate background then overlay text

```python
# Generate a background image
bg_prompt = "Professional gradient background, blue to purple, subtle geometric pattern, 16:9"
bg_response = openai.images.generate(
    model="gpt-image-2",
    prompt=bg_prompt,
    n=1,
    size="1792x1024"
)
bg_url = bg_response.data[0].url

# For each slide, download one background and add text overlay in PPTX
# More consistent look across all slides
```

## Image Size Options

| Size | Aspect | Use Case |
|------|--------|----------|
| 1024x1024 | 1:1 | Square slides, social |
| 1792x1024 | 16:9 | Widescreen presentation |
| 1024x1792 | 9:16 | Mobile/portrait |

## PPTX Assembly with python-pptx

```bash
pip install python-pptx requests
```

## Pitfalls

- gpt-image-2 generates slightly different images each time — run multiple times and pick the best
- HD quality costs more credits — use "standard" for draft slides, "hd" for final
- Full-slide images can make the PPTX file very large — consider compressing PNGs
- Text in generated images may have artifacts — use PPTX text overlays for important content
- OpenAI's content policy may reject some prompts — adjust wording if needed

## Verification

Open the generated PPTX in PowerPoint or Google Slides. Verify:
- Slide dimensions are 16:9
- All images loaded correctly
- No visual artifacts or distortion
- Text (if any) is readable
