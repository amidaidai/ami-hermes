"""Versioned in-memory contract for optional market-data sources.

The active consumers still read legacy flat fields.  This module adds a
backward-compatible metadata envelope so every optional source can expose the
same source id, semantic status, capture timestamp, payload and safe error
code without granting it decision authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from source_health import VALID_STATES, parse_timestamp, payload_timestamp


SOURCE_CONTRACT_VERSION = 1
DEGRADED_STATES = {"stale_cache", "unavailable", "quota_cooldown", "not_run"}
_METADATA_KEYS = {
    "_source_contract",
    "_source_id",
    "_source_status",
    "_source_timestamp",
    "_source_cached",
    "_source_error",
}


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return parse_timestamp(value)


def _error_code(error: Any) -> str | None:
    if error in (None, ""):
        return None
    text = str(error).strip()
    if text in {"missing_timestamp", "invalid_status", "empty_payload", "cache_missing", "upstream_error"}:
        return text
    lowered = text.lower()
    if any(token in lowered for token in ("429", "rate limit", "quota", "too many")):
        return "quota_or_rate_limited"
    if any(token in lowered for token in ("401", "403", "unauthorized", "forbidden", "api key")):
        return "credential_or_plan_blocked"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    return "request_failed"


def _raw_payload(payload: Any) -> Any:
    existing = payload.get("_source_contract") if isinstance(payload, dict) else None
    if not isinstance(existing, dict) and isinstance(payload, dict) and {"source_id", "status", "timestamp", "payload", "error"} <= set(payload):
        existing = payload
    if isinstance(existing, dict) and "payload" in existing:
        return existing.get("payload")
    if isinstance(payload, dict):
        return {key: value for key, value in payload.items() if key not in _METADATA_KEYS}
    return payload


def _payload_symbol(payload: Any) -> Any:
    if isinstance(payload, dict):
        return payload.get("symbol") or payload.get("ticker")
    return None


def build_source_contract(
    source_id: str,
    payload: Any,
    *,
    status: str | None = None,
    captured_at: Any = None,
    observed_at: Any = None,
    error: Any = None,
    cached: bool = False,
    symbol: Any = None,
) -> dict[str, Any]:
    """Build a safe, serializable source contract.

    ``captured_at`` is the data capture time, not filesystem mtime.  A live,
    cached or inherited source without one is downgraded to ``unavailable`` so
    it cannot be mistaken for fresh evidence.
    """
    raw = _raw_payload(payload)
    requested_status = str(status or "unavailable")
    contract_status = requested_status if requested_status in VALID_STATES else "unavailable"
    contract_error = _error_code(error)
    if requested_status not in VALID_STATES and contract_error is None:
        contract_error = "invalid_status"

    capture_dt = _timestamp(captured_at)
    if capture_dt is None and isinstance(raw, dict):
        capture_dt = payload_timestamp(raw)
    if contract_status in {"live", "cache", "inherited"} and capture_dt is None:
        contract_status = "unavailable"
        contract_error = contract_error or "missing_timestamp"

    observed_dt = _timestamp(observed_at) or datetime.now(timezone.utc)
    source_name = str(source_id or "unknown")
    actual_symbol = symbol if symbol not in (None, "") else _payload_symbol(raw)
    payload_present = raw not in (None, "", False, {}, [])

    return {
        "version": SOURCE_CONTRACT_VERSION,
        "source_id": source_name,
        "status": contract_status,
        "timestamp": capture_dt.isoformat() if capture_dt else None,
        "payload": raw,
        "error": contract_error,
        "observed_at": observed_dt.isoformat(),
        "cached": bool(cached),
        "symbol": actual_symbol,
        "payload_present": bool(payload_present),
    }


def attach_source_contract(
    payload: Any,
    source_id: str,
    *,
    status: str | None = None,
    captured_at: Any = None,
    observed_at: Any = None,
    error: Any = None,
    cached: bool = False,
    symbol: Any = None,
) -> dict[str, Any]:
    """Decorate a source payload while preserving its legacy flat shape."""
    existing = payload.get("_source_contract") if isinstance(payload, dict) else None
    raw = _raw_payload(payload)
    existing_status = existing.get("status") if isinstance(existing, dict) else None
    existing_timestamp = existing.get("timestamp") if isinstance(existing, dict) else None
    existing_error = existing.get("error") if isinstance(existing, dict) else None
    contract = build_source_contract(
        source_id,
        raw,
        status=status if status is not None else existing_status,
        captured_at=captured_at if captured_at is not None else existing_timestamp,
        observed_at=observed_at,
        error=error if error is not None else existing_error,
        cached=cached if status is not None or not isinstance(existing, dict) else bool(existing.get("cached")),
        symbol=symbol,
    )

    if isinstance(payload, dict):
        result = dict(raw) if isinstance(raw, dict) else {"value": raw}
    else:
        result = {"value": raw}
    result["_source_contract"] = contract
    result["_source_id"] = contract["source_id"]
    result["_source_status"] = contract["status"]
    result["_source_timestamp"] = contract["timestamp"]
    result["_source_cached"] = contract["cached"]
    if contract["error"]:
        result["_source_error"] = contract["error"]
    return result


def get_source_contract(value: Any) -> dict[str, Any] | None:
    """Return the normalized contract from a decorated source value."""
    if not isinstance(value, dict):
        return None
    contract = value.get("_source_contract")
    return dict(contract) if isinstance(contract, dict) else None


def source_status(value: Any, default: str = "not_run") -> str:
    """Read a valid semantic source status from either contract or legacy data."""
    contract = get_source_contract(value)
    if contract is None and isinstance(value, dict) and {"source_id", "status", "timestamp", "payload", "error"} <= set(value):
        contract = dict(value)
    if contract and contract.get("status") in VALID_STATES:
        return str(contract["status"])
    if isinstance(value, dict):
        raw = value.get("_source_status") or value.get("source_status")
        if raw in VALID_STATES:
            return str(raw)
    return default


def source_record(
    source_id: str,
    value: Any,
    *,
    status: str | None = None,
    captured_at: Any = None,
    observed_at: Any = None,
    error: Any = None,
    cached: bool = False,
    symbol: Any = None,
) -> dict[str, Any]:
    """Return a standalone contract for aggregators and source matrices."""
    existing = get_source_contract(value)
    if existing and status is None and captured_at is None and error is None:
        return existing
    if existing is None and isinstance(value, dict) and {"source_id", "status", "timestamp", "payload", "error"} <= set(value):
        existing = dict(value)
    return build_source_contract(
        source_id,
        value,
        status=status or (existing.get("status") if existing else None),
        captured_at=captured_at if captured_at is not None else (existing.get("timestamp") if existing else None),
        observed_at=observed_at,
        error=error if error is not None else (existing.get("error") if existing else None),
        cached=cached if not existing else bool(existing.get("cached")),
        symbol=symbol,
    )


def write_source_artifact(
    path: str,
    source_id: str,
    payload: Any,
    *,
    status: str | None = None,
    captured_at: Any = None,
    observed_at: Any = None,
    error: Any = None,
    cached: bool = False,
    symbol: Any = None,
) -> dict[str, Any]:
    """Decorate and atomically publish a source artifact."""
    decorated = attach_source_contract(
        payload,
        source_id,
        status=status,
        captured_at=captured_at,
        observed_at=observed_at,
        error=error,
        cached=cached,
        symbol=symbol,
    )
    from atomic_json import atomic_write_json

    atomic_write_json(Path(path), decorated)
    return decorated
