---
name: ppt-image-first
category: community
description: "Build presentation plans with visual direction previews before generation."
---

# PPT Image-First — Visual Direction Before Generation

Build presentation plans with visual direction previews before generating the final slides. Start with concepts and visual references, then generate the full deck.

## When to use

- You want to define the visual direction of a presentation before creating slides
- You need to get stakeholder buy-in on the visual concept early
- You're iterating on slide design and want to preview styles
- You want consistent visual themes across all slides

## Workflow

### Phase 1: Concept Definition

Define the visual direction:

```markdown
## Visual Direction

**Theme**: [Modern Tech / Corporate Professional / Creative Bold / Minimal Clean]
**Color Palette**: 
- Primary: [#0A0A2E] (deep navy)
- Secondary: [#64FFDA] (teal accent)
- Background: [#F8F9FA] (light gray)
- Text: [#1A1A2E] (dark navy)
**Font**: [System UI / Inter / Microsoft YaHei]
**Vibe**: [Professional / Innovative / Friendly / Luxurious]
**Key visual elements**: [Gradients, geometric shapes, icons, photos]
```

### Phase 2: Generate Visual Preview

Generate a sample slide to validate the direction:

```python
# Generate a style reference slide
import openai

style_prompt = f"""
Presentation slide style sample:
- Color scheme: {primary_color} (primary), {accent_color} (accent)
- Style: {style_description}
- Layout: Title on top, content area below
- 16:9 widescreen format
- Professional quality
"""

response = openai.images.generate(
    model="gpt-image-2",
    prompt=style_prompt,
    n=1,
    size="1792x1024"
)
print(f"Style reference: {response.data[0].url}")
```

### Phase 3: Build Slide-by-Slide Plan

```markdown
## Slide Plan

### Slide 1: Title
**Layout**: Centered title + subtitle
**Background**: Dark gradient (primary → darker)
**Elements**: Logo top-left, decorative geometric lines
**Text**:
- "2024 Annual Review" (60pt, white, bold)
- "Growth Through Innovation" (24pt, accent color)

### Slide 2: Agenda
**Layout**: Left sidebar + main content
**Background**: Light solid
**Elements**: Numbered items with accent-colored dots
**Text**:
- "Agenda" (36pt, primary color)
- 4 numbered items

### Slide 3: Key Metrics
**Layout**: 4-card grid
**Background**: Light with subtle pattern
**Elements**: Stat cards with icon + number + label
**Text**: 4 KPI cards

### Slide 4: Thank You
**Layout**: Centered
**Background**: Same as title slide (bookend)
**Elements**: Contact info, social links
**Text**: "Thank You" + contact details
```

### Phase 4: Generate All Slides

For each slide in the plan, generate the image or HTML:

```python
def generate_slide(slide_plan):
    """Convert slide plan entry to prompt for image generation."""
    prompt = f"""
    Professional presentation slide.
    Layout: {slide_plan['layout']}
    Background: {slide_plan['background']}
    Style: {slide_plan.get('style', 'clean professional')}
    Colors: {slide_plan.get('colors', 'blue and white')}
    Text should read: "{slide_plan.get('text', '')}"
    16:9 format, high quality.
    """
    return prompt
```

### Phase 5: Review and Refine

Before final generation:

- [ ] Visual theme is consistent across all slides
- [ ] Color palette is applied uniformly
- [ ] Font hierarchy is clear (titles > subtitles > body)
- [ ] Slide transitions feel natural
- [ ] Each slide has a clear focal point
- [ ] Content fits without overflow

## Preview Templates

### For Content Slides
```
┌─────────────────────────────────┐
│ [Logo]    [Section Title]       │
├─────────────────────────────────┤
│                                 │
│   # Main Heading                │
│                                 │
│   ● Bullet point one            │
│   ● Bullet point two            │
│   ● Bullet point three          │
│                                 │
│   ┌──────┐  ┌──────┐           │
│   │ KPI 1│  │ KPI 2│           │
│   └──────┘  └──────┘           │
└─────────────────────────────────┘
```

## Pitfalls

- Don't skip the visual preview phase — it catches 90% of design issues early
- Beware of prompt drift: the same prompt can produce different results across API calls
- Use a style reference image if available — it dramatically improves consistency
- Leave text out of generated images when possible — overlay text in PPTX for crispness
- Test your visual direction on 2-3 slide types before generating the full deck

## Verification

Generate 3 sample slides with the chosen visual direction. Show them to a colleague and ask: "Do these look like they belong to the same presentation?"
