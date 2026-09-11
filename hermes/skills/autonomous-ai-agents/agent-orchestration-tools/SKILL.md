---
name: agent-orchestration-tools
description: "Agent Orchestration & Pipeline Tools — foreman (agentic orchestrator TUI), umadev (9-stage delivery pipeline), codexpro (MCP-based coding agent), codex-control-plane"
version: 1.0.0
author: Hermes Agent (adapted from Agent Skills Hub trending)
tags: [agents, orchestration, pipeline, tui, delivery, control-plane]
---

# Agent Orchestration & Pipeline Tools

Tools for orchestrating multiple AI agents in structured pipelines.

## Foreman (Agentic Orchestrator TUI)
- Boris-style orchestrator TUI
- Supervises headless Claude Code agents
- Gated pipeline: plan → implement → review → deploy
- GitHub: `VisionForge-OU/foreman`
- 73 stars, trending on Agent Skills Hub

## UMA Dev (AI Coding Project Director)
- 9-stage governable delivery pipeline
- Powers Claude Code / Codex / OpenCode
- Stages: spec → design → plan → implement → review → test → deploy → monitor → iterate
- GitHub: `umacloud/umadev`
- 90 stars, trending on Agent Skills Hub

## CodexPro (ChatGPT MCP Coding Agent)
- Use ChatGPT Developer Mode as local coding agent through MCP
- Alternative to Codex CLI with ChatGPT interface
- GitHub: `rebel0789/codexpro`
- 704 stars, #1 trending on Agent Skills Hub

## Codex Control Plane MCP
- Durable MCP control plane for long-running Codex Desktop tasks
- Job queue, status polling, result retrieval
- GitHub: `aresyn/codex-control-plane-mcp`
- 219 stars

## Integration with Hermes

| Tool | Hermes Alternative | When to Use Instead |
|------|--------------------|--------------------|
| Foreman | `delegate_task` + kanban | Need full orchestrator TUI |
| UMA Dev | `writing-plans` + `executing-plans` | Need formal 9-stage pipeline |
| CodexPro | `codex` skill (built-in) | Prefer ChatGPT interface |
| Control Plane | `terminal(background=true)` | Need WebSocket job control |

## Workflow
1. For simple delegation: use Hermes built-in `delegate_task`
2. For structured pipeline: use `foreman` or `umadev`
3. For long-running agents: use Codex Control Plane
4. For MCP-based coding: use CodexPro
