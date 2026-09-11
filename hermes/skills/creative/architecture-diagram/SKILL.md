---
name: architecture-diagram
category: creative
description: Dark-themed SVG architecture/cloud/infra diagrams as HTML.
tags:
  - architecture
  - diagram
  - svg
  - infrastructure
  - cloud
  - dark-theme
---

# Architecture Diagrams

Create dark-themed SVG architecture, cloud, and infrastructure diagrams rendered as self-contained HTML.

## Overview

Generate professional-looking system architecture diagrams with:
- Dark theme optimized for presentations and docs
- Cloud service groups (AWS, GCP, Azure)
- Service-to-service connections with arrows
- Animated data flows (optional)
- Exportable as SVG/PNG

## Template

```html
<!DOCTYPE html>
<html>
<head>
<style>
  /* Dark theme base */
  body { background: #1a1a2e; margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
  svg { font-family: 'Segoe UI', system-ui, sans-serif; }
  /* Node styles */
  .service { fill: #16213e; stroke: #0f3460; stroke-width: 2; rx: 8; }
  .service-text { fill: #e0e0e0; font-size: 13px; text-anchor: middle; dominant-baseline: middle; }
  .group { fill: #0f3460; stroke: #533483; stroke-width: 1.5; rx: 12; opacity: 0.3; }
  .group-label { fill: #a0a0c0; font-size: 11px; }
  .arrow { stroke: #e94560; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
  .arrow-label { fill: #e94560; font-size: 10px; }
</style>
</head>
<body>
<svg viewBox="0 0 1000 700">
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#e94560" />
    </marker>
  </defs>
  
  <!-- Cloud boundary -->
  <rect class="group" x="50" y="50" width="400" height="600" />
  <text class="group-label" x="70" y="70">AWS</text>
  
  <!-- Services -->
  <rect class="service" x="100" y="150" width="120" height="60" />
  <text class="service-text" x="160" y="180">API Gateway</text>
  
  <!-- Connections -->
  <path class="arrow" d="M 220 180 L 340 180" />
  <text class="arrow-label" x="280" y="170">HTTP</text>
</svg>
</body>
</html>
```

## Diagram Elements

### Service Nodes
- **Rectangle** — Standard service/component
- **Rounded rect** — Database, cache, queue
- **Circle** — User/device, external system
- **Cylinder** — Storage/database

### Groupings
- Dashed rectangles for cloud provider boundaries
- Lighter opacity for VPC/region/zone groupings
- Labeled sections for logical layers (Frontend, Backend, Data)

### Connections
- **Solid arrow** — Synchronous call (HTTP, gRPC)
- **Dashed arrow** — Async/message (event, queue)
- **Double line** — Data stream/replication
- **Curved paths** for crossing connections

## Styling Guide

| Element | Background | Border | Text |
|---------|-----------|--------|------|
| Frontend | #1a1a3e | #0f3460 | #e0e0ff |
| Backend | #16213e | #533483 | #e0e0e0 |
| Database | #1a2e1a | #0f6034 | #e0ffe0 |
| External | #2e1a1a | #603434 | #ffe0e0 |
| Message Queue | #2e2e1a | #606034 | #ffffe0 |

## Tips

- Keep diagrams at 1000-1200px width for readability
- Use consistent node heights (60px standard)
- Label all connection lines
- Add a legend for non-obvious symbols
- Use `rx`/`ry` for rounded corners instead of `<rect rx>`
- Number flows for sequence clarity (1. Request → 2. Process → 3. Store)
