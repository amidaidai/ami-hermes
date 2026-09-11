#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根目录遗留物分类（只读）。判性质 + 查引用 + 给建议动作。

用法: python tools/root_clutter_audit.py
引用检查用 `git grep`（只扫已跟踪文件，快）+ 技能目录 grep。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path("D:/Hermes agent")
SKILLS = Path.home() / "AppData/Local/hermes/skills"
KEEP = {"README.md", ".gitignore", "conftest.py", "pytest.ini", "annualof.txt", "FinComYY.txt",
        "audit_out.json"}

LOGISH = re.compile(
    r"(\.(latest|final|strict-final|strict-run|repair-run|final-run|after|repaired)\.txt$)"
    r"|(\.diag\.(stderr|stdout)$)|(\.wrapper\.(stdout|stderr)$)"
    r"|(\.out$)|(\.err$)|(^tmp_)|(^nul$)")


def tracked(rel: str) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=REPO,
                          capture_output=True).returncode == 0


def repo_refs(name: str) -> int:
    out = subprocess.run(["git", "grep", "-l", "--fixed-strings", name],
                         cwd=REPO, capture_output=True, text=True)
    hits = [ln for ln in (out.stdout or "").splitlines() if ln and not ln.endswith("/" + name)]
    return len(hits)


def skill_refs(name: str) -> int:
    out = subprocess.run(["grep", "-rl", "--fixed-strings", name, str(SKILLS)],
                         capture_output=True, text=True)
    return len([ln for ln in (out.stdout or "").splitlines() if ln.strip()])


def main() -> int:
    files = [p for p in sorted(REPO.iterdir()) if p.is_file()]
    plan: dict[str, list[str]] = {"keep": [], "archive": [], "delete": []}
    print(f"根目录文件 {len(files)} 个\n")
    print(f"{'文件':44} {'大小':>9} {'git':>8} {'仓内':>4} {'技能':>4}  建议")
    print("-" * 104)
    for path in files:
        name = path.name
        if name in KEEP:
            plan["keep"].append(name)
            print(f"{name:44} {path.stat().st_size:>9} {'-':>8} {'-':>4} {'-':>4}  保留（仓库级/真实资产）")
            continue
        is_tracked = tracked(name)
        r, s = (repo_refs(name), skill_refs(name)) if path.stat().st_size < 2_000_000 else (0, 0)
        if LOGISH.search(name):
            action = "delete"
        elif s or r:
            action = "keep"
        elif name.endswith((".pine", ".txt")) or name.endswith((".json", ".png", ".html")):
            action = "archive"
        else:
            action = "keep"
        plan[action].append(name)
        print(f"{name:44} {path.stat().st_size:>9} {('tracked' if is_tracked else 'ignored'):>8} {r:>4} {s:>4}  {action}")

    print("\n=== 汇总 ===")
    for key, items in plan.items():
        print(f"{key}: {len(items)}")
        for item in items:
            print(f"    {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
