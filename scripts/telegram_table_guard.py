#!/usr/bin/env python3
"""Telegram Markdown table guard for Tangxi cron outputs.

Telegram does not render GitHub-style tables into real grids, but the text still
needs to be valid, narrow Markdown pipe-table text so it stays readable on mobile
and can be converted to image cards later.
"""
from __future__ import annotations

from typing import NamedTuple
import re

_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


class TableIssue(NamedTuple):
    line: int
    issue: str
    text: str


def _cols(line: str) -> int:
    s = line.strip()
    if not s.startswith("|") or not s.endswith("|"):
        return 0
    return len([p for p in s.strip("|").split("|")])


def validate_markdown_tables(text: str, max_cols: int = 3) -> list[TableIssue]:
    """Return structural issues for Markdown pipe tables.

    Checks used by cron/report scripts:
    - table header must be followed by separator
    - all rows in a table must have same column count
    - column count should stay <= max_cols for Telegram mobile readability
    """
    issues: list[TableIssue] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not (line.strip().startswith("|") and line.strip().endswith("|")):
            i += 1
            continue
        header_cols = _cols(line)
        if i + 1 >= len(lines) or not _TABLE_SEP_RE.match(lines[i + 1].strip()):
            issues.append(TableIssue(i + 1, "missing_separator", line))
            i += 1
            continue
        if header_cols > max_cols:
            issues.append(TableIssue(i + 1, f"too_many_columns:{header_cols}>{max_cols}", line))
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|") and lines[j].strip().endswith("|"):
            c = _cols(lines[j])
            if c != header_cols:
                issues.append(TableIssue(j + 1, f"column_mismatch:{c}!={header_cols}", lines[j]))
            j += 1
        i = j
    return issues


def md_table(title: str, headers: list[str], rows: list[list[object]], align: list[str] | None = None) -> str:
    """Build a compact Markdown pipe table with escaped pipe characters."""
    if not 1 <= len(headers) <= 3:
        raise ValueError("Telegram mobile tables must use 1-3 columns")
    align = align or [":----"] * len(headers)
    def cell(v: object) -> str:
        return str(v).replace("|", "｜").replace("\n", " ").strip()
    out = [title, "| " + " | ".join(cell(h) for h in headers) + " |", "|" + "|".join(align) + "|"]
    for row in rows:
        row = list(row)[:len(headers)] + [""] * max(0, len(headers) - len(row))
        out.append("| " + " | ".join(cell(v) for v in row[:len(headers)]) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    data = open(path, "r", encoding="utf-8", errors="replace").read() if path else sys.stdin.read()
    issues = validate_markdown_tables(data)
    for it in issues:
        print(f"{it.line}: {it.issue}: {it.text}")
    raise SystemExit(1 if issues else 0)
