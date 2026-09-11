# Windows Hermes Repair Runbook

Use this after a Windows + Hermes audit finds configuration or dependency issues. Keep secrets redacted in reports; only record presence/length.

## MCP servers and environment variables

Hermes stdio MCP subprocesses inherit a filtered environment. API keys in `.env` may not reach an MCP server unless they are explicitly configured under `mcp_servers.<name>.env` or the server loads the Hermes `.env` itself.

For a local MCP server that needs credentials:

1. Locate config and env paths with `hermes config path` and `hermes config env-path`.
2. Confirm key presence/length in the Hermes `.env` without printing values.
3. Add explicit env entries to `config.yaml`, for example:

```yaml
mcp_servers:
  binance:
    command: "python"
    args: ["D:/Hermes agent/tools/binance-mcp/server.py"]
    enabled: true
    env:
      BINANCE_API_KEY: "..."
      BINANCE_SECRET_KEY: "..."
```

4. Optionally add a server-side fallback that reads `%LOCALAPPDATA%/hermes/.env`, `~/AppData/Local/hermes/.env`, then `~/.hermes/.env` and sets only the needed keys with `os.environ.setdefault`.
5. Validate with `hermes mcp test <server>`.
6. Restart gateway or start a fresh Hermes session; already-loaded MCP connections in the current agent process may still use the old environment.

## OpenRouter endpoint quirk

If `api.openrouter.ai` fails DNS resolution but `hermes doctor` still passes OpenRouter, test the root API endpoint:

```bash
curl -k -L -s -o /dev/null --connect-timeout 8 --max-time 20 \
  -w 'code=%{http_code} err=%{errormsg} total=%{time_total}\n' \
  https://openrouter.ai/api/v1/models
```

When this returns `200`, set these in the Hermes `.env`:

```dotenv
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
```

Do not record a durable claim that OpenRouter is broken; the actionable fix is to prefer the working base URL when the `api.` host is unresolved.

## npm audit remediation on Hermes source tree

Run `hermes doctor --fix` first. If npm reports an arborist crash such as `Cannot read properties of null (reading 'edgesOut')`, inspect the audit JSON and apply the specific package bump instead of repeating the same failing fix command.

Useful pattern:

```bash
cd "$(cygpath "$LOCALAPPDATA")/hermes/hermes-agent"
npm audit --workspaces=false --json > /tmp/audit-root.json 2>&1 || true
npm audit --workspace web --json > /tmp/audit-web.json 2>&1 || true
npm audit --workspace ui-tui --json > /tmp/audit-tui.json 2>&1 || true
```

Examples seen in practice:

```bash
npm install esbuild@0.28.1 vite@latest --save-dev --workspaces=false
npm audit fix --workspace web
```

Then verify with `hermes doctor`; the desired output is `All checks passed!` plus `no known vulnerabilities` for Browser tools, web workspace, and ui-tui workspace.

## Gateway restart caveat

`hermes gateway restart` may stop the manual gateway and then prompt to install a service if no Windows Scheduled Task is installed. If avoiding extra side effects, do not install the service unless requested; just verify that the manual process is running afterward with `hermes gateway status`.
