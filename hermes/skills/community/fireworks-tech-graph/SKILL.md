---
name: fireworks-tech-graph
category: community
description: "Create technical diagrams: architecture, flow, sequence: export as SVG+PNG."
---

# Fireworks Tech Graph — Technical Diagrams (SVG+PNG)

Create professional technical diagrams — architecture diagrams, flowcharts, sequence diagrams — and export them as both SVG and PNG.

## When to use

- You need to document system architecture
- You want to visualize a workflow or process
- You're creating sequence diagrams for API or service interactions
- You need diagrams for documentation, presentations, or whitepapers

## Quick Start

### Architecture Diagram (SVG)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" font-family="system-ui, sans-serif">
  <defs>
    <linearGradient id="db" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea"/>
      <stop offset="100%" style="stop-color:#764ba2"/>
    </linearGradient>
    <linearGradient id="api" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f093fb"/>
      <stop offset="100%" style="stop-color:#f5576c"/>
    </linearGradient>
    <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" orient="auto">
      <path d="M0,0 L10,5 L0,10 Z" fill="#666"/>
    </marker>
  </defs>
  
  <!-- Background -->
  <rect width="800" height="500" fill="#1a1a2e" rx="12"/>
  
  <!-- Title -->
  <text x="400" y="40" fill="white" font-size="20" font-weight="bold" text-anchor="middle">
    System Architecture
  </text>
  
  <!-- Client -->
  <rect x="300" y="70" width="200" height="60" rx="8" fill="url(#api)"/>
  <text x="400" y="100" fill="white" font-size="14" text-anchor="middle" font-weight="bold">Client App</text>
  <text x="400" y="118" fill="rgba(255,255,255,0.7)" font-size="11" text-anchor="middle">React / Next.js</text>
  
  <!-- Arrow: Client to API -->
  <line x1="400" y1="130" x2="400" y2="180" stroke="#666" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="415" y="160" fill="#aaa" font-size="10">HTTP/HTTPS</text>
  
  <!-- API Gateway -->
  <rect x="300" y="180" width="200" height="60" rx="8" fill="url(#db)"/>
  <text x="400" y="210" fill="white" font-size="14" text-anchor="middle" font-weight="bold">API Gateway</text>
  <text x="400" y="228" fill="rgba(255,255,255,0.7)" font-size="11" text-anchor="middle">Express / Fastify</text>
  
  <!-- Arrow: API to Service -->
  <line x1="400" y1="240" x2="400" y2="290" stroke="#666" stroke-width="2" marker-end="url(#arrow)"/>
  
  <!-- Service Layer -->
  <rect x="300" y="290" width="200" height="60" rx="8" fill="#2d3748" stroke="#4a5568" stroke-width="1"/>
  <text x="400" y="320" fill="white" font-size="14" text-anchor="middle" font-weight="bold">Service Layer</text>
  <text x="400" y="338" fill="rgba(255,255,255,0.7)" font-size="11" text-anchor="middle">Business Logic</text>
  
  <!-- Arrow: Service to DB -->
  <line x1="350" y1="350" x2="170" y2="400" stroke="#666" stroke-width="2" marker-end="url(#arrow)"/>
  
  <!-- Database -->
  <ellipse cx="150" cy="430" rx="80" ry="40" fill="#2d3748" stroke="#667eea" stroke-width="2"/>
  <ellipse cx="150" cy="410" rx="80" ry="40" fill="#1a202c" stroke="#667eea" stroke-width="2"/>
  <text x="150" y="415" fill="#667eea" font-size="14" text-anchor="middle" font-weight="bold">Database</text>
  <text x="150" y="440" fill="rgba(255,255,255,0.6)" font-size="10" text-anchor="middle">PostgreSQL</text>
  
  <!-- Arrow: Service to Cache -->
  <line x1="450" y1="350" x2="630" y2="400" stroke="#666" stroke-width="2" marker-end="url(#arrow)"/>
  
  <!-- Cache -->
  <rect x="560" y="400" width="140" height="60" rx="8" fill="#2d3748" stroke="#f093fb" stroke-width="2"/>
  <text x="630" y="430" fill="#f093fb" font-size="14" text-anchor="middle" font-weight="bold">Cache</text>
  <text x="630" y="448" fill="rgba(255,255,255,0.6)" font-size="10" text-anchor="middle">Redis</text>
  
  <!-- Legend -->
  <rect x="30" y="20" width="12" height="12" rx="2" fill="url(#db)"/>
  <text x="48" y="32" fill="#aaa" font-size="11">Core Services</text>
  <rect x="140" y="20" width="12" height="12" rx="2" fill="url(#api)"/>
  <text x="158" y="32" fill="#aaa" font-size="11">Client Facing</text>
</svg>
```

### Flowchart (SVG)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 600" font-family="system-ui">
  <rect width="500" height="600" fill="#f8f9fa" rx="8"/>
  
  <!-- Start -->
  <ellipse cx="250" cy="50" rx="80" ry="25" fill="#4CAF50"/>
  <text x="250" y="56" fill="white" font-size="14" text-anchor="middle" font-weight="bold">Start</text>
  
  <!-- Arrow -->
  <line x1="250" y1="75" x2="250" y2="110" stroke="#666" stroke-width="2" marker-end="url(#arrow)"/>
  
  <!-- Decision -->
  <path d="M250,110 L320,155 L250,200 L180,155 Z" fill="#fff3cd" stroke="#ffc107" stroke-width="2"/>
  <text x="250" y="152" fill="#856404" font-size="12" text-anchor="middle">Is valid?</text>
  
  <!-- Yes -->
  <line x1="320" y1="155" x2="400" y2="155" stroke="#4CAF50" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="360" y="148" fill="#4CAF50" font-size="11">Yes</text>
  
  <!-- Process -->
  <rect x="360" y="130" width="120" height="50" rx="6" fill="#c8e6c9" stroke="#4CAF50" stroke-width="2"/>
  <text x="420" y="158" fill="#2e7d32" font-size="12" text-anchor="middle">Process</text>
  
  <!-- No -->
  <line x1="180" y1="155" x2="100" y2="155" stroke="#f44336" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="140" y="148" fill="#f44336" font-size="11">No</text>
  
  <!-- Error -->
  <rect x="20" y="130" width="120" height="50" rx="6" fill="#ffcdd2" stroke="#f44336" stroke-width="2"/>
  <text x="80" y="158" fill="#c62828" font-size="12" text-anchor="middle">Error</text>
</svg>
```

### Sequence Diagram (text-based → SVG)

```python
# Simple sequence diagram generator
def sequence_to_svg(steps):
    participants = set()
    for s in steps:
        participants.add(s[0])
        participants.add(s[1])
    parts = list(participants)
    
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" font-family="monospace">']
    svg.append(f'<rect width="800" height="500" fill="#1a1a2e" rx="8"/>')
    
    # Participant headers
    for i, p in enumerate(parts):
        x = 150 + i * 200
        svg.append(f'<rect x="{x-40}" y="20" width="80" height="30" rx="6" fill="#2d3748"/>')
        svg.append(f'<text x="{x}" y="40" fill="white" font-size="12" text-anchor="middle">{p}</text>')
        # Lifeline
        svg.append(f'<line x1="{x}" y1="55" x2="{x}" y2="480" stroke="#4a5568" stroke-width="1" stroke-dasharray="4"/>')
    
    # Messages
    y = 80
    for sender, receiver, msg in steps:
        sx = 150 + parts.index(sender) * 200
        rx = 150 + parts.index(receiver) * 200
        svg.append(f'<line x1="{sx}" y1="{y}" x2="{rx-20}" y2="{y}" stroke="#64ffda" stroke-width="1.5" marker-end="url(#arrow)"/>')
        svg.append(f'<text x="{(sx+rx)//2}" y="{y-6}" fill="#aaa" font-size="10" text-anchor="middle">{msg}</text>')
        y += 40
    
    svg.append('</svg>')
    return '\n'.join(svg)

# Example usage
steps = [
    ("Client", "API", "HTTP POST /login"),
    ("API", "Auth", "validate credentials"),
    ("Auth", "DB", "SELECT user"),
    ("DB", "Auth", "user data"),
    ("Auth", "API", "JWT token"),
    ("API", "Client", "200 OK + token"),
]
print(sequence_to_svg(steps))
```

## Exporting SVG to PNG

```bash
# Using Inkscape (CLI)
inkscape diagram.svg --export-png=diagram.png --export-width=1200

# Using ImageMagick
convert diagram.svg -resize 1200x diagram.png

# Using Python (cairosvg)
pip install cairosvg
python -c "import cairosvg; cairosvg.svg2png(url='diagram.svg', write_to='diagram.png', output_width=1200)"
```

## Pitfalls

- SVG text rendering depends on system fonts — use web-safe fonts or embed fonts
- For complex diagrams, use `viewBox` instead of fixed width/height for responsiveness
- Dark-mode SVGs may be unreadable on light backgrounds — consider a `prefers-color-scheme` media query
- Very large SVGs may render slowly in some viewers — split into multiple files
- CSS `font-family: system-ui` ensures the best cross-platform text rendering

## Verification

Open the SVG in a browser and verify: all elements render correctly, text is legible, arrows point in the right direction, and the diagram conveys the intended information at a glance.
