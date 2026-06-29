#!/usr/bin/env python3
"""
棠溪 · Web 搜索/抽取显式降级链 v1.0

Hermes 内置 web_search/web_extract 当前按配置选单一 provider。
这个脚本提供交易分析可直接调用的“编队化”降级链：
- search: Brave → Exa → Tavily → Firecrawl → DDGS
- extract: Firecrawl → Tavily → Exa

注意：这是脚本级补强，不修改 Hermes core。适合 no_agent/交易脚本和 skill 协议引用。
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

HERMES_SRC = Path(os.environ.get("HERMES_SRC", r"C:/Users/Administrator/AppData/Local/hermes/hermes-agent"))
if HERMES_SRC.exists():
    sys.path.insert(0, str(HERMES_SRC))


def _load_env_file() -> None:
    """Load Hermes .env for standalone script runs outside the agent process."""
    candidates = [
        Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes\.env")),
        Path.home() / "AppData" / "Local" / "hermes" / ".env",
        Path.home() / ".hermes" / ".env",
    ]
    for path in candidates:
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = val.strip().strip('"').strip("'")
            return
        except OSError:
            continue


_load_env_file()

PROVIDERS = {
    "brave": "plugins.web.brave_free.provider",
    "brave-free": "plugins.web.brave_free.provider",
    "exa": "plugins.web.exa.provider",
    "tavily": "plugins.web.tavily.provider",
    "firecrawl": "plugins.web.firecrawl.provider",
    "ddgs": "plugins.web.ddgs.provider",
}

DEFAULT_SEARCH_CHAIN = ["brave-free", "exa", "tavily", "firecrawl", "ddgs"]
DEFAULT_EXTRACT_CHAIN = ["firecrawl", "tavily", "exa"]


def _load_provider(name: str):
    module_name = PROVIDERS[name]
    mod = importlib.import_module(module_name)
    # Prefer explicit class names by scanning for provider classes.
    for obj in mod.__dict__.values():
        if (
            isinstance(obj, type)
            and obj.__name__.endswith("WebSearchProvider")
            and obj.__name__ != "WebSearchProvider"
        ):
            return obj()
    raise RuntimeError(f"provider class not found: {name}")


def _is_success_search(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict) or not result.get("success"):
        return False
    web = result.get("data", {}).get("web", [])
    return bool(web)


def fallback_search(query: str, limit: int = 5, chain: list[str] | None = None) -> dict[str, Any]:
    attempts = []
    for name in chain or DEFAULT_SEARCH_CHAIN:
        try:
            provider = _load_provider(name)
            if not provider.supports_search():
                attempts.append({"provider": name, "ok": False, "error": "supports_search=false"})
                continue
            result = provider.search(query, limit)
            ok = _is_success_search(result)
            attempts.append({
                "provider": name,
                "ok": ok,
                "count": len(result.get("data", {}).get("web", [])) if isinstance(result, dict) else 0,
                "error": result.get("error") if isinstance(result, dict) else "invalid result",
            })
            if ok:
                result["provider_used"] = name
                result["attempts"] = attempts
                return result
        except Exception as exc:
            attempts.append({"provider": name, "ok": False, "error": repr(exc)})
    return {"success": False, "error": "all search providers failed", "attempts": attempts, "data": {"web": []}}


def _normalize_extract_items(items: Any) -> list[dict[str, Any]]:
    if isinstance(items, list):
        return [x if isinstance(x, dict) else {"content": str(x)} for x in items]
    return []


def _extract_has_content(items: list[dict[str, Any]]) -> bool:
    return any((item.get("content") or item.get("markdown") or "").strip() and not item.get("error") for item in items)


def fallback_extract(urls: list[str], chain: list[str] | None = None) -> dict[str, Any]:
    attempts = []
    for name in chain or DEFAULT_EXTRACT_CHAIN:
        try:
            provider = _load_provider(name)
            if not provider.supports_extract():
                attempts.append({"provider": name, "ok": False, "error": "supports_extract=false"})
                continue
            raw = provider.extract(urls)
            if hasattr(raw, "__await__"):
                import asyncio
                raw = asyncio.run(raw)
            items = _normalize_extract_items(raw)
            ok = _extract_has_content(items)
            attempts.append({
                "provider": name,
                "ok": ok,
                "count": len(items),
                "errors": [x.get("error") for x in items if x.get("error")][:3],
            })
            if ok:
                return {"success": True, "provider_used": name, "attempts": attempts, "results": items}
        except Exception as exc:
            attempts.append({"provider": name, "ok": False, "error": repr(exc)})
    return {"success": False, "error": "all extract providers failed", "attempts": attempts, "results": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    e = sub.add_parser("extract")
    e.add_argument("urls", nargs="+")
    args = parser.parse_args()
    if args.cmd == "search":
        print(json.dumps(fallback_search(args.query, args.limit), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(fallback_extract(args.urls), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
