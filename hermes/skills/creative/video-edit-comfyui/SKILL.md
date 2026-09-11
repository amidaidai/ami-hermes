---
name: video-edit-comfyui
description: "AI Video Editing with ComfyUI — video editing, frame interpolation, background removal, upscaling, and batch processing using ComfyUI workflows. AgentSpace.so collection (3.1M total installs) with 10+ video workflows"
version: 2.0.0
author: Hermes Agent (adapted from agentspace-so/runcomfy-agent-skills — 3.1M total installs)
tags: [video, editing, comfyui, ai-video, batch-processing, agentspace]
---

# AI Video Editing with ComfyUI

Professional AI video editing using ComfyUI workflows from the **agentspace-so/runcomfy-agent-skills** collection (3.1M total installs across 10+ skills).

## Installation
```bash
# Install all video skills from AgentSpace
npx skills add agentspace-so/runcomfy-agent-skills

# Or install individually:
npx skills add video-edit
npx skills add frame-interpolation
npx skills add video-upscale
npx skills add background-removal
npx skills add batch-process
```

### Core Editing
| Workflow | Description |
|----------|-------------|
| video-edit | General video editing: trim, merge, transition effects |
| frame-interpolation | Smooth slow-motion, frame rate conversion (RIFE, FILM) |
| background-removal | Remove/replace video backgrounds (SAM, RMBG) |
| video-upscale | 2x/4x video upscaling (Real-ESRGAN, CodeFormer) |
| batch-process | Apply workflows to entire video folders |

### Advanced
| Workflow | Description |
|----------|-------------|
| face-restoration | Restore faces in low-quality video |
| style-transfer | Apply artistic styles to video frames |
| object-removal | Remove objects from video (ProPainter, E2FGVI) |
| color-grading | AI-powered color correction and grading |
| motion-brush | Animate specific regions with brush-selected masks |

## Installation
```bash
# Install ComfyUI (if not already)
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt

# Install video-specific nodes
# ComfyUI-Manager (in custom_nodes/)
git clone https://github.com/ltdrdata/ComfyUI-Manager custom_nodes/

# Within ComfyUI Manager, install:
# - Video Helper Suite
# - ComfyUI-VideoDump
# - WAS Node Suite
```

## Usage with ComfyUI Skill
Load the existing `comfyui` skill for general ComfyUI management (install, launch, node management, workflow execution).

This skill (`video-edit-comfyui`) supplements it with video-specific workflows.

## Workflow
1. Load `comfyui` skill for ComfyUI lifecycle
2. Load this skill for video-specific workflows
3. Install video-specific ComfyUI nodes
4. Run workflow with parameter injection
5. Preview result, iterate if needed
