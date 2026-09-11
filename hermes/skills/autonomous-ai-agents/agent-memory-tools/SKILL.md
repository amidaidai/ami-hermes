---
name: agent-memory-tools
description: "Agent Memory & Durability Tools — durable offline memory for Claude Code, session recovery, token usage dashboards, and control planes for long-running agent tasks"
version: 1.0.0
author: Hermes Agent
tags: [agents, memory, durability, session, tools, control-plane]
---

# Agent Memory & Durability Tools

Tools for making AI agents persistent, recoverable, and observable across sessions.

## Trending Tools

### Recall (durable memory for Claude Code)
- Offline, persistent memory — never re-explain session context
- SQLite-backed, zero dependencies
- GitHub: `raiyanyahya/recall`
- Install: `git clone https://github.com/raiyanyahya/recall`

### Claude Pulse (dashboard) — 70 stars, trending
- Token usage monitoring
- Session recovery and search
- Phone approval for long-running tasks
- Local, zero-dependency
- GitHub: `nikitadoudikov/claude-pulse`

### CodexPro (MCP coding agent) — 704 stars, #1 trending
- Use ChatGPT Developer Mode as local coding agent
- MCP-based, works with any IDE
- GitHub: `rebel0789/codexpro`

### Agent Apprenticeship — 524 stars, trending #2
- Living ecosystem where AI agents learn from real-world work
- Iterative workflow loops: do → reflect → improve
- Experience accumulation and skill transfer
- GitHub: `Forsy-AI/agent-apprenticeship`

### Foreman (orchestrator TUI) — 73 stars
- Boris-style agentic orchestrator TUI
- Supervises headless Claude Code agents
- Gated pipeline: plan → implement → review → deploy
- GitHub: `VisionForge-OU/foreman`

### UMA Dev (project director) — 90 stars
- AI Coding Project Director — 9-stage delivery pipeline
- Works with Claude Code / Codex / OpenCode
- Stages: spec → design → plan → implement → review → test → deploy → monitor → iterate
- GitHub: `umacloud/umadev`

## Hermes Equivalents
Hermes already has:
- **Persistent memory** via memory tool + fact_store
- **Session recovery** via session_search tool
- **Cron jobs** for scheduled persistent work
- **Background processes** via terminal(background=true)
- **Curator** for skill lifecycle management

## Integration
- For Claude Code memory: use `recall` 
- For monitoring: use `claude-pulse` or Hermes built-in insights
- For orchestration: use Hermes delegation + kanban
