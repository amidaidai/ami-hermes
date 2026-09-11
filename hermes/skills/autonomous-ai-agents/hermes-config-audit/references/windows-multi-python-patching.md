# Windows Multi-Python Patching — Hermes Web Search Routing

When Hermes Desktop (Web UI) is installed alongside the CLI, **two separate Python
environments** exist on the same machine. Modifying Hermes source code requires
patching BOTH locations and clearing compiled bytecode in both.

## Why Two Environments?

| Environment | Python | Code Source | Used By |
|---|---|---|---|
| CLI | 3.11 | `%APPDATA%/hermes/hermes-agent/` | Main CLI process, `terminal` tool calls from CLI sessions |
| Desktop Runtime | 3.12 | `%USERPROFILE%/.hermes-web-ui/desktop-runtime/hermes/<version>/win-x64/python/Lib/site-packages/` | Hermes Web UI, `execute_code` sandboxes, gateway child processes |

The `execute_code` tool spawns sandbox processes using the **desktop runtime's
Python 3.12**. When `hermes_tools.web_search` is called inside a sandbox, it
forwards via RPC to the main process — but the sandbox's own imports (like
`agent.web_search_registry`) resolve from the runtime site-packages.

## Key Files to Update

### Config (one location)
```
%APPDATA%/hermes/config.yaml
```
- `plugins.disabled` — remove entries (restore providers, don't disable)
- `plugins.enabled` — ensure the provider is listed
- `web.search_backend` — set explicit preferred provider
- `web.extract_backend` — set extract provider

### Source Code (TWO locations)

| File | CLI (3.11) | Runtime (3.12) |
|---|---|---|
| `agent/web_search_registry.py` | `%APPDATA%/hermes/hermes-agent/agent/web_search_registry.py` | `%USERPROFILE%/.hermes-web-ui/desktop-runtime/hermes/<version>/win-x64/python/Lib/site-packages/agent/web_search_registry.py` |
| `tools/web_tools.py` | `%APPDATA%/hermes/hermes-agent/tools/web_tools.py` | `%USERPROFILE%/.hermes-web-ui/desktop-runtime/hermes/<version>/win-x64/python/Lib/site-packages/tools/web_tools.py` |

## Patch Checklist

### 1. `config.yaml`
```yaml
plugins:
  disabled: []          # REMOVE disabled entries, don't add them
  enabled:
  - web/brave_free
  - web/ddgs
  - web/exa
  - web/firecrawl      # KEEP firecrawl — don't disable!
  - web/searxng
  - web/tavily

web:
  search_backend: ddgs # or your preferred primary
  extract_backend: tavily
```

### 2. `_LEGACY_PREFERENCE` order in `web_search_registry.py`
Reorder so free/unlimited providers come first, paid ones follow as fallback:

```python
_LEGACY_PREFERENCE = (
    "ddgs",          # free, unlimited — primary
    "brave-free",    # free 2k/month — secondary
    "tavily",        # paid — fallback
    "exa",           # paid
    "searxng",       # self-hosted
    "parallel",      # paid
    "firecrawl",     # paid, last resort
)
```

Patch BOTH the CLI source and the runtime site-packages copy.

### 3. `web_tools.py` — add try/except around provider.search()
The fallback chain in `web_search_tool()` iterates providers. If a provider's
`.search()` raises an uncaught exception (not returning `{"success": False}`),
the entire chain breaks. Wrap it:

```python
try:
    result = provider.search(query, limit)
except Exception as exc:  # noqa: BLE001 - provider failures must fall through
    result = {"success": False, "error": str(exc)}
```

Patch BOTH copies.

### 4. Clear `.pyc` caches

```bash
# CLI .pyc (3.11)
rm -f "$APPDATA/hermes/hermes-agent/agent/__pycache__/web_search_registry.cpython-311.pyc"
rm -f "$APPDATA/hermes/hermes-agent/tools/__pycache__/web_tools.cpython-311.pyc"

# Runtime .pyc (3.12)  
rm -f "$USERPROFILE/.hermes-web-ui/desktop-runtime/hermes/"*/win-x64/python/Lib/site-packages/agent/__pycache__/web_search_registry.cpython-312.pyc
rm -f "$USERPROFILE/.hermes-web-ui/desktop-runtime/hermes/"*/win-x64/python/Lib/site-packages/tools/__pycache__/web_tools.cpython-312.pyc
```

### 5. Restart Hermes

The running process has stale imports in `sys.modules`. Changes won't take
effect until:
- **CLI session**: type `/reset` or restart the CLI
- **Gateway**: restart with `hermes gateway restart`
- **Web UI**: restart the Web UI process

## Verification

After restart, test web_search:

```python
# From inside Hermes CLI:
web_search("test query")

# From Python directly:
python -c "
import sys, json
sys.path.insert(0, r'C:\Users\<user>\AppData\Local\hermes\hermes-agent')
from tools.web_tools import web_search_tool
print(json.loads(web_search_tool('test', limit=1)).get('success'))
"
```

Success result will show DDGS/Brave/configured provider, NOT Firecrawl
"Payment Required".

## Common Misdiagnosis

- **"I updated the config but web_search still fails"** → Config changes take
  effect immediately for new sessions, but the running session's tool handlers
  were imported at session start. Need `/reset`.
- **"I patched the source code but it doesn't work"** → Did you patch BOTH the
  CLI source AND the runtime site-packages? The sandbox uses the runtime copy.
- **"I cleared .pyc but still getting old behavior"** → Python's `sys.modules`
  cache in the live process. Must restart the process.
- **"Firecrawl is disabled in plugins, why does it still show up?"** → A
  disabled plugin means it's removed from the provider registry entirely. To
  keep it as a fallback (never disable!), it must be in both `plugins.enabled`
  and the `_LEGACY_PREFERENCE` chain.
