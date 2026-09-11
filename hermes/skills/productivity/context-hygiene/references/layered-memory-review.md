# Layered memory review

Use when a user asks for a comprehensive memory or Studio-memory review.

## Evidence layers

1. Active preference files: `MEMORY.md`, `USER.md`, and the latest explicit user message.
2. Built-in fact store: `memory_store.db`; useful historical facts, but may contain stale workflow, format, model, or routing claims.
3. Repository evidence: current code, tests, generated artifacts, and runtime probes.
4. Studio evidence: only what the Studio API/browser returns in this run.

## Review method

- Read the active preference files in full.
- Query fact-store schema and facts without exposing secrets.
- Compare claims by topic: output format, timeframes, assets, execution authority, data freshness, and routing.
- Mark each claim as active, historical, conflicting, or unverified.
- If Studio calls fail or return no operations, report Studio content as unverified; never infer that it is empty.
- Keep dated prices, expired key levels, and one-run health results out of durable memory.

## Durable lessons

- Current user corrections outrank old facts.
- Current code and tests outrank prose that says a pipeline has been integrated.
- A successful candidate collection does not equal human approval or a healthy monitor.
- A process being alive does not prove the source data or approved configuration is healthy.
