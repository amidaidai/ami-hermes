# MCP Deferred-Tool Call Mechanics (cross-turn re-registration)

Applies to any MCP server whose tools are loaded **on demand** into the Hermes tool registry (the "deferred tool" pattern — `tool_search` / `tool_describe` / `tool_call` bridge). TradingView (`mcp__tradingview__*`) is one concrete instance; the mechanics generalize.

## The core pitfall

Deferred MCP tools **drop out of the tool registry across assistant turns**. A tool that worked last turn is gone this turn.

- **Within one turn** — after `tool_describe(name='mcp__x__y')` loads the schema, you can call `tool_call(name='mcp__x__y', arguments={})` and keep reusing that tool for the rest of the same turn.
- **Across turns (next assistant turn)** — the tool is **unregistered**. A direct `tool_call(name='mcp__x__y', ...)` fails with `Tool 'mcp__x__y' does not exist. Available tools: <only the direct tools>`.

## Verified recovery path

1. See failure `Tool '...' does not exist` (the "Available tools" list shows only `tool_call`/`tool_describe`/`tool_search` + the direct tools — the MCP tools are absent).
2. Re-register: `tool_describe(name='mcp__x__y')` → returns the schema.
3. Call again: `tool_call(name='mcp__x__y', arguments={})` → succeeds.

This is **not** the "MCP server is down" case. `does not exist` = registry-stale, not server-dead. Re-describe fixes it immediately with no relaunch.

## Distinguish from MCP-bridge / CDP disconnects

A *different* error family is the bridge/server actually being down:

| Error | Meaning | Fix |
|------|---------|-----|
| `Tool 'x' does not exist` | deferred tool fell out of registry (stale) | `tool_describe` re-register, then `tool_call` |
| `CDP connection failed after 5 attempts: fetch failed` / `ClosedResourceError` | MCP bridge or underlying app (e.g. TradingView/CDP) disconnected | health-check the bridge, relaunch the app (`tv_launch(kill_existing=true)`), wait ~8s, health-check again |

## Additional call-mechanics traps

- `tool_call` **cannot** invoke `tool_call` (a bridge tool). Error: `tool_call cannot invoke 'tool_call'`. The `name` argument must be a concrete tool name, never the bridge itself.
- After relaunching the underlying app, re-check the specific chart/binding: the app may reset to a default symbol/state (e.g. TradingView relaunches back to whichever chart it was last on). Re-verify `chart_get_state` matches the target symbol before reading data.
- Deferred tool schemas are re-available via `tool_describe`; the tool-search index (`tool_search`) is a separate lookup and may not be needed again once the exact name is known.
