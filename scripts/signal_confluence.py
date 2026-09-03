#!/usr/bin/env python3
"""Active compatibility facade for the former signal-confluence entrypoint.

The archived module performed its own network collection, scoring and plan
construction.  That path is intentionally not restored.  This facade keeps
legacy imports usable while making ``FinalVerdict`` the only authority for
execution fields and keeping the source matrix visible in reports.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone, timedelta
from typing import Any

from signal_validators import validate_final_verdict


TZ = timezone(timedelta(hours=8))


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, Mapping):
            return dict(converted)
    return {}


def _side_label(side: Any) -> str:
    return "🟢做多" if side == "long" else "🔴做空" if side == "short" else "⚪观望"


def _blocked_plan(reason: str, *, blockers: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "available": False,
        "qualified": False,
        "side": "⚪观望",
        "entry": None,
        "stop": None,
        "target": None,
        "targets": [],
        "risk_pct": None,
        "risk_usd": 0.0,
        "r_ratio": None,
        "rr": None,
        "blockers": list(dict.fromkeys(str(item) for item in blockers if item)),
        "reason": reason,
        "source": "FinalVerdict",
    }


def compute_plan(
    score: float | None = None,
    *,
    final_verdict: Mapping[str, Any] | Any | None = None,
    verdict: Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    """Project a FinalVerdict into the legacy plan shape.

    ``score`` remains accepted so old callers fail safely rather than raising,
    but it is never used to invent direction or prices.
    """
    del score
    value = _as_dict(final_verdict if final_verdict is not None else verdict)
    if not value:
        return _blocked_plan("FinalVerdict缺失·拒绝独立生成计划", blockers=("final_verdict",))
    validation = validate_final_verdict(value)
    if not validation["pass"] or not validation["executable"]:
        reason = str(value.get("reason") or "FinalVerdict未授权执行")
        return _blocked_plan(reason, blockers=validation["blockers"] or ("not_executable",))

    target = value.get("target")
    risk_usd = value.get("risk_usd")
    risk_pct = value.get("risk_pct")
    return {
        "available": True,
        "qualified": True,
        "side": _side_label(value.get("side")),
        "entry": value.get("entry"),
        "stop": value.get("stop"),
        "target": target,
        "targets": [target],
        "risk_pct": risk_pct,
        "risk_usd": risk_usd,
        "r_ratio": value.get("rr"),
        "rr": value.get("rr"),
        "blockers": [],
        "reason": str(value.get("reason") or "FinalVerdict授权"),
        "source": "FinalVerdict",
    }


def _source_rows(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    matrix = value.get("source_matrix")
    if not isinstance(matrix, Iterable) or isinstance(matrix, (str, bytes, Mapping)):
        matrix = value.get("sources")
    rows: list[dict[str, Any]] = []
    for raw in matrix if isinstance(matrix, Iterable) and not isinstance(matrix, (str, bytes, Mapping)) else []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        label = row.get("label") or row.get("name") or "来源"
        status = row.get("status") or "not_run"
        entered = bool(row.get("entered_final_verdict"))
        if "entered_final_verdict" not in row and row.get("w") is not None:
            entered = False
        rows.append({
            "label": str(label),
            "status": str(status),
            "entered_final_verdict": entered,
            "evidence": str(row.get("evidence") or row.get("sig") or "—"),
            "impact": str(row.get("impact") or row.get("detail") or "辅助验证"),
        })
    return rows


def fuse(
    final_verdict: Mapping[str, Any] | Any | None = None,
    source_matrix: Iterable[Mapping[str, Any]] | None = None,
    *,
    symbol: str = "BTCUSDT",
) -> dict[str, Any]:
    """Build a report payload from active pipeline outputs only.

    No source is fetched here and no score is recomputed.  Callers should pass
    the matrix and FinalVerdict produced by ``auto_card``/``decision_loop``.
    """
    value = _as_dict(final_verdict)
    if source_matrix is not None:
        value["source_matrix"] = list(source_matrix)
    if not value:
        value = {"state": "NO-GO", "executable": False, "reason": "FinalVerdict缺失·拒绝执行"}
    validation = validate_final_verdict(value)
    plan = compute_plan(final_verdict=value)
    rows = _source_rows(value)
    supporting = [row["label"] for row in rows if row["entered_final_verdict"] and row["status"] in {"live", "cache", "inherited"}]
    return {
        "symbol": symbol,
        "score": None,
        "verdict": str(value.get("state") or "NO-GO"),
        "concl": str(value.get("reason") or "FinalVerdict缺失·拒绝执行"),
        "sources": rows,
        "source_matrix": rows,
        "supporting": supporting,
        "contra": list(value.get("blockers") or []),
        "plan": plan,
        "final_verdict": value,
        "validation": validation,
    }


def build_report(fused: Mapping[str, Any], ts: str | None = None) -> str:
    """Render a non-executing compatibility report with explicit authority."""
    value = _as_dict(fused)
    final = _as_dict(value.get("final_verdict"))
    validation = validate_final_verdict(final)
    state = str(final.get("state") or value.get("verdict") or "NO-GO")
    symbol = str(value.get("symbol") or "BTCUSDT")
    marker = "↑" if final.get("side") == "long" else "↓" if final.get("side") == "short" else "○" if state == "WAIT" else "×"
    timestamp = ts or datetime.now(TZ).strftime("%Y年%m月%d日%H：%M")
    lines = [
        f"{marker} {symbol}：FinalVerdict={state}，{'允许人工执行' if validation['executable'] else '不执行'} · {timestamp}",
        "",
        "| 来源 | 状态 | 权限 | 证据 | 影响 |",
        "|:---|:---:|:---|:---|:---|",
    ]
    rows = _source_rows(value)
    if rows:
        for row in rows:
            authority = "已入FinalVerdict" if row["entered_final_verdict"] else "仅展示/辅助"
            lines.append(f"| {row['label']} | {row['status']} | {authority} | {row['evidence']} | {row['impact']} |")
    else:
        lines.append("| 来源矩阵 | not_run | 仅展示/辅助 | 未提供 | 不得越权授权 |")
    lines.extend([
        "",
        f"**裁决**: {value.get('concl') or final.get('reason') or 'FinalVerdict缺失·拒绝执行'}。",
    ])
    plan = _as_dict(value.get("plan"))
    if validation["executable"] and plan.get("qualified"):
        lines.append(f"**计划**: {_side_label(final.get('side'))} · Entry={final.get('entry')} · Stop={final.get('stop')} · Target={final.get('target')} · R:R={final.get('rr')}")
    else:
        lines.append("**计划**: 无执行三件套 · 仅保留观察/等待条件。")
    if validation["blockers"]:
        lines.append(f"**校验**: {'；'.join(validation['blockers'])}")
    return "\n".join(lines)


def main() -> int:
    """Print a fail-closed local report; never fetch or push automatically."""
    print(build_report(fuse()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
