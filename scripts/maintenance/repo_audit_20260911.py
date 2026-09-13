#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""獖溪脚本僵尸/重复扫描（只读体检，不改文件）。

用法： python tools/repo_audit_20260911.py [--json out.json]

判定：
  · 被 import / 被 subprocess 调用 / 被 cron 引用 / 被文档提到 = 活
  · 三者皆无 = 僵尸候选（需人工确认后再归档，本工具不自动删）
另附：同名近重复脚本、契约漂移残留名、缓存新鲜度。
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path("D:/Hermes agent")
SCRIPTS = REPO / "scripts"
SKIP_DIRS = {"__pycache__", "node_modules", ".git", "_archive", "_disabled",
             "_disabled_20260829", "tools", "backups", "tmp", ".pytest_cache", ".pytest-cache"}


def py_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def import_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def text_refs(path: Path) -> set[str]:
    """字符串里提到的模块名（subprocess 调用、动态 import）。"""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", src))


def main() -> int:
    alive: dict[str, set[str]] = defaultdict(set)
    files = list(py_files(REPO))
    for path in files:
        if str(path).startswith(str(SCRIPTS)):
            continue
        for name in import_names(path):
            alive[name].add(path.name)

    external_text: dict[str, set[str]] = defaultdict(set)
    for path in files:
        if str(path).startswith(str(SCRIPTS)):
            continue
        for token in text_refs(path):
            external_text[token].add(path.name)
    # 非 py 文件（cron 配置 / shell / 文档）里的引用
    for pattern in ("*.sh", "*.md", "*.json", "*.bat", "*.mjs"):
        for path in REPO.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if str(path).startswith(str(SCRIPTS)):
                continue
            try:
                src = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for token in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", src)):
                external_text[token].add(path.name)

    cron_text = ""
    for cron_dir in (Path.home() / "AppData/Local/hermes/cron", REPO / "cron"):
        if cron_dir.exists():
            for path in cron_dir.rglob("*"):
                if path.is_file():
                    cron_text += path.read_text(encoding="utf-8", errors="replace")

    zombies = []
    for path in sorted(SCRIPTS.glob("*.py")):
        mod = path.stem
        if mod.startswith("_"):
            continue
        used_by = (alive.get(mod, set()) | external_text.get(mod, set())) - {path.name}
        if mod in cron_text:
            continue
        if not used_by:
            zombies.append(mod)

    # 同名前缀的近重复（并发竞争脚本）
    groups: dict[str, list[str]] = defaultdict(list)
    for path in sorted(SCRIPTS.glob("*.py")):
        stem = path.stem
        head = re.split(r"[_.]", stem)[0]
        groups[head].append(stem)
    dupes = {k: v for k, v in groups.items() if len(v) > 1}

    # 已废止的指标名残留（契约与测试之外的文件）
    stale_names = ["MCP CVD Value", "OI Total", "Estimated CVD Value", "MCP EMA Length",
                   "MCP Risk Pack", "Bull FVG CE", "Bear FVG CE", "MCP StructPack (FvgQ"]
    contract = (SCRIPTS / "tv_indicator_contract.py").read_text(encoding="utf-8")
    stale_hits: dict[str, list[str]] = defaultdict(list)
    for path in py_files(REPO) if False else list(SCRIPTS.glob("*.py")):
        if path.name.startswith("_"):
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        for name in stale_names:
            if name in src and name not in contract:
                stale_hits[path.name].append(name)

    print(f"扫描 {len(list(SCRIPTS.glob('*.py')))} 个 scripts/*.py")
    print(f"\n== 僵尸候选（无 import / 无 subprocess / 无 cron / 无文档引用）{len(zombies)} 个 ==")
    for name in zombies:
        size = (SCRIPTS / f"{name}.py").stat().st_size
        print(f"   {name:52} {size:>7}B")

    print(f"\n== 同前缀脚本组（潜在竞争/重复）{len(dupes)} 组 ==")
    for head, members in sorted(dupes.items()):
        if len(members) > 2 or any("alert" in m or "watch" in m or "monitor" in m or "daemon" in m
                                   for m in members):
            print(f"   {head:22} → {', '.join(members)}")

    print(f"\n== 废止指标名残留（契约文件之外的 scripts） ==")
    for name, tokens in stale_hits.items():
        print(f"   {name}: {tokens}")

    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps({"zombies": zombies, "dupes": dupes,
                                   "stale": {k: v for k, v in stale_hits.items()}},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
