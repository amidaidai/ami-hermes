#!/usr/bin/env python3
"""Validate the checked-in SVP/AggVol sources against the Python contract.

This is deliberately a source-integrity check, not a Pine compiler. TradingView
compilation and live Data Window verification remain separate acceptance steps.
The script prevents a contract from silently describing a different pair of
Pine files after a manual upload or replacement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = {
    "svp": ROOT / "outputs/pine_20260905/SVP_audit_fixed17_20260910.pine",
    "aggvol": ROOT / "outputs/pine_20260905/AggVol_audit_fixed14_20260910.pine",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plots(text: str) -> list[str]:
    # Pine permits either plot(value, "Title", ...) or plot(value, title="Title", ...).
    titles: list[str] = []
    for line in text.splitlines():
        if "plot(" not in line:
            continue
        match = re.search(r'title\s*=\s*["\']([^"\']+)["\']|,\s*["\']([^"\']+)["\']', line)
        if match:
            titles.append(match.group(1) or match.group(2))
    return titles


def _tables(text: str) -> list[str]:
    return re.findall(r'table\.cell\([^\n]*?,\s*["\']([^"\']+)["\']', text)


def inspect_source(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return {
        "path": str(path),
        "exists": True,
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
        "lines": text.count("\n") + 1,
        "plot_titles": _plots(text),
        "table_labels": _tables(text),
    }


def audit_sources(sources: dict[str, Path] | None = None) -> dict[str, Any]:
    sources = sources or DEFAULT_SOURCES
    result: dict[str, Any] = {"ok": True, "sources": {}}
    for name, path in sources.items():
        if not path.exists():
            result["ok"] = False
            result["sources"][name] = {"path": str(path), "exists": False}
            continue
        result["sources"][name] = inspect_source(path)

    try:
        from tv_indicator_contract import DW_MAIN, DW_SUB, MAIN_ROW_LABELS, SUB_ROW_LABELS
    except ImportError:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from tv_indicator_contract import DW_MAIN, DW_SUB, MAIN_ROW_LABELS, SUB_ROW_LABELS

    svp = result["sources"].get("svp", {})
    agg = result["sources"].get("aggvol", {})
    svp_plots = set(svp.get("plot_titles", []))
    agg_plots = set(agg.get("plot_titles", []))
    # Contract lists include only exported Data Window fields. Pure visual
    # plots are intentionally excluded by the alignment checker.
    result["contract"] = {
        "version": "v15",
        "main_missing_plots": sorted(set(DW_MAIN) - svp_plots),
        "sub_missing_plots": sorted(set(DW_SUB) - agg_plots),
        "main_rows": MAIN_ROW_LABELS,
        "sub_rows": SUB_ROW_LABELS,
    }
    result["ok"] = result["ok"] and not result["contract"]["main_missing_plots"] and not result["contract"]["sub_missing_plots"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit SVP/AggVol source integrity")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()
    result = audit_sources()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("指标源码合同：" + ("通过" if result["ok"] else "失败"))
        for name, item in result["sources"].items():
            print(f"- {name}: {item.get('lines', 0)} 行 sha256={item.get('sha256', 'missing')[:24]}")
        for key in ("main_missing_plots", "sub_missing_plots"):
            missing = result["contract"][key]
            print(f"- {key}: {len(missing)}" + (f" -> {missing}" if missing else ""))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
