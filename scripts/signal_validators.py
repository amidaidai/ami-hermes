#!/usr/bin/env python3
"""Active signal validation adapters.

The former independent validator lived in the archived workflow and could
fetch a second, drifting data snapshot.  This active module deliberately does
not create a competing execution decision.  It validates the already-produced
``FinalVerdict`` and, when explicitly given a validated TV snapshot, provides
an observational timeframe alignment view for compatibility/reporting.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_ALLOWED_STATES = {"GO-A", "GO-B", "WAIT", "NO-GO"}
_EXECUTION_FIELDS = ("entry", "stop", "target")
_REQUIRED_TIMEFRAMES = ("D", "4h", "1h", "15m", "5m")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, Mapping):
            return dict(converted)
    return {}


def _number(value: Any) -> float | None:
    if value in (None, "", "—", "--"):
        return None
    try:
        return float(str(value).replace(",", "").replace("−", "-").replace("%", ""))
    except (TypeError, ValueError):
        return None


def _direction_code(value: Any) -> int:
    if isinstance(value, (int, float)):
        return 1 if value > 0 else -1 if value < 0 else 0
    text = str(value or "").strip().lower()
    if any(token in text for token in ("待", "观望", "中性", "neutral", "unknown")):
        return 0
    if any(token in text for token in ("偏多", "做多", "多头", "long", "buy", "bull")):
        return 1
    if any(token in text for token in ("偏空", "做空", "空头", "short", "sell", "bear")):
        return -1
    numeric = _number(value)
    return 1 if numeric and numeric > 0 else -1 if numeric and numeric < 0 else 0


def validate_final_verdict(verdict: Mapping[str, Any] | Any | None) -> dict[str, Any]:
    """Validate the execution boundary without changing the verdict."""
    value = _as_dict(verdict)
    blockers: list[str] = []
    warnings: list[str] = []
    state = str(value.get("state") or "")
    executable = bool(value.get("executable", False))
    side = str(value.get("side") or "neutral")

    if state not in _ALLOWED_STATES:
        blockers.append("FinalVerdict状态无效")
    if executable and state != "GO-A":
        blockers.append("仅GO-A允许executable=true")
    if state == "GO-A" and not executable:
        blockers.append("GO-A缺少执行授权")
    if side not in {"long", "short", "neutral"}:
        blockers.append("FinalVerdict方向无效")

    prices = {field: _number(value.get(field)) for field in _EXECUTION_FIELDS}
    rr = _number(value.get("rr"))
    if executable:
        if side not in {"long", "short"}:
            blockers.append("GO-A缺少多空方向")
        if any(prices[field] is None for field in _EXECUTION_FIELDS):
            blockers.append("GO-A执行价位不完整")
        if rr is None or rr < 2.0:
            blockers.append("GO-A的R:R低于1:2")
        if not blockers:
            entry_price = prices["entry"]
            stop_price = prices["stop"]
            target_price = prices["target"]
            if entry_price is not None and stop_price is not None and target_price is not None:
                if side == "long" and not (stop_price < entry_price < target_price):
                    blockers.append("多头Entry/Stop/Target几何关系无效")
                if side == "short" and not (stop_price > entry_price > target_price):
                    blockers.append("空头Entry/Stop/Target几何关系无效")
    elif any(prices[field] is not None for field in _EXECUTION_FIELDS):
        blockers.append("WAIT/NO-GO不得携带执行三件套")

    if state == "WAIT" and value.get("watch_entry") is not None:
        warnings.append("watch_entry仅为人工观察位")
    if value.get("blockers"):
        warnings.extend(str(item) for item in value["blockers"] if item)

    return {
        "pass": not blockers,
        "state": state,
        "executable": executable and not blockers,
        "side": side,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "reason": str(value.get("reason") or ""),
    }


def _snapshot_records(snapshot: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    value = _as_dict(snapshot)
    records: Mapping[Any, Any] = {}
    candidate = value.get("engine_klines")
    if isinstance(candidate, Mapping):
        records = candidate
    else:
        candidate = value.get("timeframes")
        if isinstance(candidate, Mapping):
            records = candidate
    if not records:
        payload = value.get("payload")
        if isinstance(payload, Mapping) and isinstance(payload.get("timeframes"), Mapping):
            records = payload["timeframes"]
    return {
        str(tf): dict(record)
        for tf, record in records.items()
        if isinstance(record, Mapping)
    }


def tf_alignment(symbol: str = "BTCUSDT", snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Read alignment from an explicitly supplied/validated TV snapshot.

    No implicit REST/CDP call is made.  A caller that wants live evidence must
    collect it in the main pipeline and pass that evidence here.
    """
    if snapshot is None:
        # Read-only fallback to the already validated disk snapshot.  This is
        # not a second REST/CDP collection and therefore cannot drift from the
        # main pipeline's evidence boundary.
        try:
            from tv_five_tf_contract import load_five_tf_snapshot
            loaded = load_five_tf_snapshot(symbol)
            snapshot = loaded if loaded.get("usable") else None
        except Exception:
            snapshot = None
    records = _snapshot_records(snapshot)
    directions: list[int] = []
    output: dict[str, int] = {}
    aliases = {"1D": "D", "DAY": "D", "240": "4h", "60": "1h", "15": "15m", "5": "5m"}
    for tf in _REQUIRED_TIMEFRAMES:
        record = records.get(tf)
        if record is None:
            record = next((row for raw_tf, row in records.items() if aliases.get(raw_tf, raw_tf) == tf), None)
        direction = 0
        if isinstance(record, Mapping):
            grid = record.get("tv_action_grid") or record.get("grid")
            if isinstance(grid, Mapping):
                direction = _direction_code(grid.get("方向") or grid.get("direction"))
            if direction == 0:
                direction = _direction_code(record.get("direction"))
            if direction == 0:
                change = _number(record.get("change_pct"))
                direction = 1 if change is not None and change > 0.05 else -1 if change is not None and change < -0.05 else 0
        output[tf] = direction
        directions.append(direction)

    available = any(directions)
    adjacent_conflict = any(
        left and right and left * right < 0
        for left, right in zip(directions, directions[1:])
    )
    aligned = bool(directions and all(direction != 0 and direction == directions[0] for direction in directions))
    names = {1: "多", -1: "空", 0: "中性"}
    note = "/".join(f"{tf}{names[output[tf]]}" for tf in _REQUIRED_TIMEFRAMES)
    if adjacent_conflict:
        note += " · 冲突"
    elif aligned:
        note += " · 同向"
    return {
        "available": available,
        "d1d": output["D"],
        "d4": output["4h"],
        "d1": output["1h"],
        "d15": output["15m"],
        "d5m": output["5m"],
        "conflict": adjacent_conflict,
        "aligned": aligned,
        "regime_label": "trend" if aligned else "range",
        "note": note if available else "周期方向数据不足",
        "source": "validated_tv_snapshot",
    }


def tf_alignment_tv(symbol: str = "BTCUSDT", wait: float = 0.0) -> dict[str, Any]:
    """Compatibility alias; collection remains owned by the main pipeline."""
    del wait
    return tf_alignment(symbol)


def long_short_contra(symbol: str = "BTCUSDT", snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Interpret an already-collected Binance ratio; never fetch a second one."""
    del symbol
    value = _as_dict(snapshot)
    ratio = _number(value.get("ratio") or value.get("lsr"))
    if ratio is None:
        long_value = _number(value.get("long") or value.get("longAccount"))
        short_value = _number(value.get("short") or value.get("shortAccount"))
        if long_value is not None and short_value not in (None, 0):
            ratio = long_value / short_value
    if ratio is None:
        return {
            "available": False, "signal": "neutral", "ratio": None,
            "contra": "", "note": "未提供已采集多空比·不重复请求",
            "source_status": "not_run",
        }
    if ratio >= 2.0:
        signal, contra = "bear_trap", "散户极度拥挤多→反向警惕顶"
    elif ratio <= 0.5:
        signal, contra = "bull_trap", "散户极度拥挤空→反向警惕底"
    else:
        signal, contra = "neutral", ""
    return {
        "available": True, "signal": signal, "ratio": round(ratio, 2),
        "contra": contra, "note": f"多空比{ratio:.2f}",
        "source_status": str(value.get("_source_status") or "live"),
    }


def validate_plan(
    symbol: str,
    side: str,
    tf_override: Mapping[str, Any] | None = None,
    *,
    final_verdict: Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    """Validate a plan only after FinalVerdict exists.

    ``tf_override`` is retained for callers that need an alignment note, but it
    cannot authorize a plan by itself.
    """
    del symbol
    result = validate_final_verdict(final_verdict)
    blockers = list(result["blockers"])
    notes: list[str] = []
    if final_verdict is None:
        blockers.append("FinalVerdict缺失·拒绝独立生成计划")
    expected = _direction_code(side)
    actual = _direction_code(result.get("side"))
    if result.get("executable") and expected and actual and expected != actual:
        blockers.append("计划方向与FinalVerdict不一致")
    if tf_override is not None:
        alignment = tf_alignment("", tf_override)
        notes.append(str(alignment.get("note") or "周期方向未形成"))
        if alignment.get("conflict"):
            blockers.append("周期冲突·不交易")
    return {
        "pass": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "notes": notes,
        "state": result.get("state"),
        "source": "FinalVerdict" if final_verdict is not None else "missing_final_verdict",
    }


# Explicit alias for new callers; the legacy name remains for compatibility.
validate_verdict = validate_final_verdict
