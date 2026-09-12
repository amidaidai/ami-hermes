#!/usr/bin/env python3
"""Normalize TradingView chart evidence for the decision pipeline.

This module deliberately does not make a trading decision.  It records chart
identity, price context, and ICT evidence availability so consumers can fail
closed instead of treating a screenshot or an action-grid row as a complete
chart read.
"""
from __future__ import annotations

from typing import Any


_TIMEFRAME_ALIASES = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
    "1d": "D", "1D": "D", "d": "D", "1w": "W", "1W": "W", "w": "W",
}


def normalize_timeframe(value: Any) -> str:
    raw = str(value or "").strip()
    return _TIMEFRAME_ALIASES.get(raw, raw)


def normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def symbol_matches(actual: Any, expected: Any) -> bool:
    left, right = normalize_symbol(actual), normalize_symbol(expected)
    if not left or not right:
        return False
    return left == right or left.split(":")[-1].removesuffix(".P") == right.split(":")[-1].removesuffix(".P")


def _number(value: Any) -> float | None:
    try:
        result = float(str(value).replace(",", "").strip())
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _levels(lines: Any) -> list[dict[str, Any]]:
    result = []
    if not isinstance(lines, list):
        return result
    for item in lines:
        if isinstance(item, dict):
            price = _number(item.get("price"))
            if price is not None and price > 0:
                result.append({"label": str(item.get("label") or "level"), "price": price})
    return result


def build_chart_evidence(*, state: dict[str, Any] | None = None,
                         quote: Any = None, indicators: dict[str, Any] | None = None,
                         lines: Any = None, boxes: Any = None, labels: Any = None,
                         expected_symbol: str = "", expected_timeframe: str = "") -> dict[str, Any]:
    """Build a conservative, JSON-safe chart evidence record.

    ``partial`` is intentional when the chart is valid but ICT objects are not
    machine-readable.  Only ``verified`` is sufficient for a hard execution
    authority; callers decide whether to require that state.
    """
    state = state if isinstance(state, dict) else {}
    symbol = normalize_symbol(state.get("symbol") or state.get("ticker"))
    timeframe = normalize_timeframe(state.get("resolution") or state.get("timeframe"))
    expected_tf = normalize_timeframe(expected_timeframe)
    identity_errors: list[str] = []
    if expected_symbol and not symbol_matches(symbol, expected_symbol):
        identity_errors.append("symbol_mismatch")
    if expected_tf and timeframe != expected_tf:
        identity_errors.append("timeframe_mismatch")

    indicators = indicators if isinstance(indicators, dict) else {}
    level_rows = _levels(lines)
    box_rows = boxes if isinstance(boxes, list) else []
    label_rows = labels if isinstance(labels, list) else []
    quote_map = quote if isinstance(quote, dict) else {}
    price = _number(quote_map.get("last") or quote_map.get("close")) if quote_map else _number(quote)
    price_context = {
        "last_price": price,
        "open": _number(quote_map.get("open") or indicators.get("open")),
        "high": _number(quote_map.get("high") or indicators.get("high")),
        "low": _number(quote_map.get("low") or indicators.get("low")),
        "close": _number(quote_map.get("close") or indicators.get("close")),
        "day_high": _number(quote_map.get("day_high") or indicators.get("day_high")),
        "day_low": _number(quote_map.get("day_low") or indicators.get("day_low")),
    }
    price_context["complete"] = price is not None

    zone_rows = [x for x in box_rows if isinstance(x, dict)]
    ict = {
        "fvg": [x for x in zone_rows if "FVG" in str(x.get("label", "")).upper()],
        "ob": [x for x in zone_rows if "OB" in str(x.get("label", "")).upper() or "BREAKER" in str(x.get("label", "")).upper()],
        "zones": zone_rows,
        "liquidity": [x for x in level_rows if any(k in x["label"].upper() for k in ("HIGH", "LOW", "LIQ", "SWEEP"))],
        "structure_labels": [x for x in label_rows if any(k in str(x.get("text", "")).upper() for k in ("BOS", "MSS", "CHoCH", "CHOCH"))],
        "objects_readable": bool(box_rows or label_rows or level_rows),
    }
    structure_pack = indicators.get("mcp_struct_pack") or indicators.get("struct_pack")
    ict["struct_pack_present"] = structure_pack not in (None, "")
    ict["fvg_ob_evidence"] = bool(ict["fvg"] or ict["ob"] or ict["zones"] or ict["struct_pack_present"])
    ict["structure_event_evidence"] = bool(ict["structure_labels"] or ict["struct_pack_present"])

    required_studies = {"SVP+ICT+VWAP+CVD", "Volume", "Volume Aggregated Spot & Futures"}
    studies_value = state.get("studies")
    studies = studies_value if isinstance(studies_value, list) else []
    study_names = {str(x.get("name")) for x in studies if isinstance(x, dict)}
    studies_ok = required_studies.issubset(study_names) if studies else False
    if identity_errors:
        status = "identity_mismatch"
    elif not symbol or not timeframe:
        status = "unavailable"
    elif not studies_ok or not price_context["complete"]:
        status = "partial"
    elif not ict["objects_readable"] or not ict["fvg_ob_evidence"] or not ict["structure_event_evidence"]:
        status = "partial"
    else:
        status = "verified"

    return {
        "schema_version": 1,
        "status": status,
        "identity": {"symbol": symbol, "timeframe": timeframe, "chart_type": state.get("chartType"), "studies": sorted(study_names)},
        "identity_errors": identity_errors,
        "price_context": price_context,
        "levels": level_rows,
        "ict": ict,
        "source": "tradingview",
    }


def is_execution_safe(evidence: dict[str, Any] | None) -> bool:
    return isinstance(evidence, dict) and evidence.get("status") == "verified"
