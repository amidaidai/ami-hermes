#!/usr/bin/env python3
"""Skill integrity guard.

Scans a skill tree for two classes of corruption that silently break skill
discovery (the skill vanishes from skills_list / skill_view):

  1. Line-number pollution: lines prefixed with `\\d+|` because a SKILL.md was
     read via a line-numbered reader (LINE_NUM|CONTENT) and written back
     verbatim. The first line becomes `1|---` so `startswith("---")` fails and
     the YAML frontmatter never parses.
  2. Broken frontmatter: missing opening `---`, missing closing `---`, or a
     frontmatter block that doesn't parse as a YAML mapping with name+description.

Usage:
    python skill_integrity_guard.py [ROOT ...] [--json]

ROOT defaults to the two standard skill trees if present:
    ~/.hermes/skills  and  ./skills

Exit codes:
    0 = all clean
    1 = pollution or frontmatter corruption found
    2 = usage / IO error

This is a pure stdlib, statically re-runnable probe. Run it after any bulk edit
to a SKILL.md, or wire it into a daily no-agent maintenance pass.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

LINENO_RE = re.compile(r"^\d+\|")
# Frontmatter close can legitimately sit deep in long community skills; scan a
# generous window before declaring it missing (60 lines was too tight and
# false-positived on skills like last30days).
FRONTMATTER_WINDOW = 150


def find_skill_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("SKILL.md")))
    return files


def check_file(path: Path) -> list[str]:
    """Return a list of problem strings for one SKILL.md (empty == clean)."""
    problems: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return [f"unreadable: {exc}"]

    lines = text.splitlines()

    # 1. Line-number pollution — check the head; one hit is enough to flag.
    polluted = [i + 1 for i, ln in enumerate(lines[:FRONTMATTER_WINDOW]) if LINENO_RE.match(ln)]
    if polluted:
        problems.append(
            f"line-number pollution (e.g. line {polluted[0]} starts with a digit+pipe prefix); "
            f"repair: re.sub(r'^\\d+\\|', '', line) per line after backing up"
        )

    # 2. Frontmatter integrity.
    if not text.startswith("---"):
        problems.append("frontmatter does not start at byte 0 with '---'")
    else:
        # find closing --- within the window
        close_idx = None
        for i in range(1, min(len(lines), FRONTMATTER_WINDOW)):
            if lines[i].strip() == "---":
                close_idx = i
                break
        if close_idx is None:
            problems.append(f"no closing '---' within first {FRONTMATTER_WINDOW} lines")
        else:
            fm = "\n".join(lines[1:close_idx])
            try:
                import yaml  # optional; only needed for deep parse

                data = yaml.safe_load(fm)
                if not isinstance(data, dict):
                    problems.append("frontmatter does not parse as a YAML mapping")
                else:
                    if "name" not in data:
                        problems.append("frontmatter missing 'name'")
                    if "description" not in data:
                        problems.append("frontmatter missing 'description'")
            except ImportError:
                # yaml not available: do a shallow key presence check instead.
                if "name:" not in fm:
                    problems.append("frontmatter missing 'name' (shallow check)")
                if "description:" not in fm:
                    problems.append("frontmatter missing 'description' (shallow check)")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"frontmatter YAML error: {exc}")

    return problems


def default_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path(os.path.expanduser("~")) / ".hermes" / "skills"
    if home.exists():
        roots.append(home)
    local = Path("skills")
    if local.exists():
        roots.append(local)
    return roots


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--json"]
    as_json = "--json" in argv
    roots = [Path(a) for a in args] if args else default_roots()
    if not roots:
        sys.stderr.write("no skill roots found; pass ROOT explicitly\n")
        return 2

    files = find_skill_files(roots)
    report: dict[str, list[str]] = {}
    for f in files:
        probs = check_file(f)
        if probs:
            report[str(f)] = probs

    if as_json:
        print(json.dumps({
            "roots": [str(r) for r in roots],
            "scanned": len(files),
            "corrupt": len(report),
            "problems": report,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"scanned {len(files)} SKILL.md across {len(roots)} root(s)")
        if not report:
            print("all clean")
        else:
            for path, probs in report.items():
                print(f"\nCORRUPT: {path}")
                for p in probs:
                    print(f"  - {p}")

    return 1 if report else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
