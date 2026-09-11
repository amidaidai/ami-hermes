# Web Search Provider Resolution (Hermes Plugin System)

## Architecture

Web search (`web_search` / `web_extract`) is backed by a **plugin-based provider system**.
Each backend (DDGS, Brave, Exa, Tavily, Firecrawl, SearXNG, Parallel) registers as a
`WebSearchProvider` subclass via `PluginContext.register_web_search_provider()`.

The active provider is resolved by `agent/web_search_registry.py::get_active_search_provider()`:

```
1. web.search_backend (per-capability) → explicit match, ignores is_available()
2. web.backend (shared fallback) → explicit match, ignores is_available()
3. Single-provider shortcut → when only 1 provider registered & available
4. Legacy preference walk → _LEGACY_PREFERENCE order, filtered by is_available()
```

## The Legacy Preference Trap

The default `_LEGACY_PREFERENCE` puts **Firecrawl first**:

```python
_LEGACY_PREFERENCE = (
    "firecrawl",  # ← P0, fails if out of credits
    "parallel",
    "tavily",
    "exa",
    "searxng",
    "brave-free",
    "ddgs",       # ← last, even though it's free & works
)
```

Firecrawl's `is_available()` only checks `FIRECRAWL_API_KEY` presence — it does NOT check
credit balance. So a user with Firecrawl API key but zero credits gets stuck:
`web_search` always hits Firecrawl first → Payment Required → no fallback.

## Fix: Add Fallback Loop (DON'T Disable)

**Step 1:** Keep `_LEGACY_PREFERENCE` as-is (Firecrawl first, DDGS last as safety net):

**Step 2:** Add fallback loop in `tools/web_tools.py` — both `web_search_tool` and `web_extract_tool`:

Instead of picking ONE provider and calling it (original code):

```python
provider = get_active_search_provider()
response_data = provider.search(query, limit)  # fails → error, no retry
```

Replace with a fallback chain that tries each provider in order:

```python
# Build chain: configured first, then _LEGACY_PREFERENCE order
fallback_chain = []
seen = set()
# ... (build from configured + legacy, filtering by supports_search/is_available)

for provider in fallback_chain:
    result = provider.search(query, limit)
    if result.get("success"):
        break  # found a working provider
    # log failure, try next
```

This way Firecrawl (out of credits) fails → Parallel → Tavily → ... → DDGS (always works).

**Step 3:** Ensure env vars for each fallback:
- DDGS: `pip install ddgs` (no API key)
- Brave: `BRAVE_SEARCH_API_KEY=<key>` (free at brave.com/search/api/)
- Exa: `EXA_API_KEY=<key>`
- Tavily: `TAVILY_API_KEY=<key>`

**Step 4:** Restart session (`/reset`) — plugin changes take effect on next session.

## OpenRouter Free Models (for aux tasks)

When using OpenRouter for auxiliary tasks (compression, vision), use the free router model
that auto-selects the best available free model:

```bash
hermes config set auxiliary.compression.provider openrouter
hermes config set auxiliary.compression.model openrouter/free
hermes config set auxiliary.vision.provider openrouter
hermes config set auxiliary.vision.model openrouter/free
```

`openrouter/free` has 200K context, supports tool calling and reasoning.
Top free models include `nvidia/nemotron-3-ultra-550b-a55b:free` (1M ctx),
`nvidia/nemotron-3-super-120b-a12b:free` (262K ctx), and `qwen/qwen3-coder:free` (262K ctx).

## Plugin 'Next Session' Behavior

`hermes plugins disable/enable` writes config but does NOT reload providers in the
current session. Provider registration happens at session startup. Always `/reset`
after plugin changes.

## Pitfalls

- **Firecrawl `is_available()` lies about credits** — it only checks env var presence.
  If Firecrawl is first in the preference chain and has an API key set, it will be
  selected even with zero credits. **Fix: add fallback loop, don't disable.** 棠溪
  explicitly corrected this session: Firecrawl 没钱了 → 留在链中加降级，不是禁用。
- **`web_search` has NO built-in fallback (before this session's fix)** — the
  original `web_search_tool` picks ONE provider and returns its error. Must patch
  `tools/web_tools.py` to build a fallback chain and loop on failure.
