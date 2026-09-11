---
name: touchdesigner-mcp
category: creative
description: Control TouchDesigner via twozero MCP — create operators, parameters, connections.
tags:
  - touchdesigner
  - mcp
  - twozero
  - generative
  - visual-programming
---

# TouchDesigner MCP (twozero)

Control TouchDesigner via the twozero MCP protocol — create operators, modify parameters, and wire connections programmatically.

## Overview

This skill enables AI-assisted control of TouchDesigner through the Model Context Protocol (MCP). You can build, modify, and inspect TouchDesigner networks using natural language commands.

## Capabilities

### Operator Management
- **Create operators**: `COMP`, `TOP`, `CHOP`, `SOP`, `MAT`, `DAT`
- **Delete operators**: Remove selected nodes
- **Clone operators**: Duplicate with connections
- **Navigate**: Select, view, inspect

### Parameter Control
- **Read parameters**: Get current values
- **Write parameters**: Set values (floats, ints, strings, toggles, menus)
- **Animate parameters**: Set up parameter animations
- **Export parameters**: Component-level parameter interfaces

### Connection Management
- **Wire operators**: Connect output to input
- **Bypass connections**: Temporarily disable
- **Reorder inputs**: Change connection order
- **Multi-instance**: Work with operator arrays

### Network Operations
- **Create networks**: Build sub-networks / containers
- **Organize**: Layout, color-code, comment
- **Export/Import**: COMP (.tox) files
- **Save**: Project-wide saves

## Common Operator Types

| Type | Prefix | Purpose |
|------|--------|---------|
| **COMP** | `container1` | Containers, panels, viewers |
| **TOP** | `moviein1` | Texture/image processing |
| **CHOP** | `noise1` | Channel data, audio, signals |
| **SOP** | `sphere1` | 3D geometry |
| **MAT** | `phong1` | Materials/shaders |
| **DAT** | `text1` | Tables, text, scripts |

## Example Workflows

### Audio-Reactive Visual
```
1. audiofilein CHOP → audio analysis
2. noise CHOP (frequency-driven)
3. feedback TOP + composite TOP
4. geo sphere SOP + phong MAT
5. render TOP
```

### Generative Art
```
1. noise CHOP → speed/position
2. circle SOP (radius modulated by noise)
3. instancing COMP
4. camera COMP + light COMP
5. render TOP + movieout TOP
```

## Tips

- Use `node('name').par.[parameter]` for Python parameter access
- OP snippets can be executed via the Text DAT or Execute CHOP
- Always specify operator types explicitly when creating
- Use viewer COMP for debugging intermediate TOP results
