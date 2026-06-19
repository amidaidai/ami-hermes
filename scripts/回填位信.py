#!/usr/bin/env python3
"""Backfill level confidence into historical monitor/trade events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
LEVELS = DATA / "monitor_levels.json"
EVENTS = [DATA / "monitor_events.json", DATA / "trade_events.jsonl"]


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_level_map() -> dict[tuple[str, str], dict[str, Any]]:
    raw = read_json(LEVELS, {})
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for symbol, block in (raw.get("symbols") or {}).items():
        for level in block.get("levels", []):
            conf = level.get("level_confidence")
            if isinstance(conf, dict):
                out[(symbol, level.get("name"))] = conf
    return out


def patch_event(event: dict[str, Any], level_map: dict[tuple[str, str], dict[str, Any]]) -> bool:
    changed = False
    symbol = event.get("symbol")
    for level in event.get("levels") or []:
        if not isinstance(level, dict) or level.get("level_confidence"):
            continue
        conf = level_map.get((symbol, level.get("name")))
        if conf:
            level["level_confidence"] = conf
            changed = True
    return changed


def patch_json_array(path: Path, level_map: dict[tuple[str, str], dict[str, Any]]) -> int:
    rows = read_json(path, [])
    changed = sum(1 for row in rows if isinstance(row, dict) and patch_event(row, level_map))
    if changed:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed


def patch_jsonl(path: Path, level_map: dict[tuple[str, str], dict[str, Any]]) -> int:
    if not path.exists():
        return 0
    rows = []
    changed = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            rows.append(line)
            continue
        if isinstance(row, dict) and patch_event(row, level_map):
            changed += 1
        rows.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    if changed:
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    level_map = load_level_map()
    print(f"level_confidence_map={len(level_map)}")
    print(f"monitor_events_changed={patch_json_array(DATA / 'monitor_events.json', level_map)}")
    print(f"trade_events_changed={patch_jsonl(DATA / 'trade_events.jsonl', level_map)}")


if __name__ == "__main__":
    main()
