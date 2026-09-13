"""Shared semantic freshness checks for JSON data artifacts.

Filesystem mtime is deliberately not used as market-data evidence.  A file can
be touched by a retry, a formatter, or a failed writer without containing a
new market snapshot.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_STATES = {"live", "cache", "inherited", "stale_cache", "unavailable", "quota_cooldown", "not_run"}
DEGRADED_STATES = {"stale_cache", "unavailable", "quota_cooldown", "not_run"}
TIMESTAMP_KEYS = ("updated_epoch", "updated_at", "timestamp", "ts", "time", "updated")


def parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = float(value)
            if not math.isfinite(number):
                return None
            if number > 100_000_000_000:
                number /= 1000.0
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def payload_timestamp(payload: dict[str, Any]) -> datetime | None:
    for key in TIMESTAMP_KEYS:
        timestamp = parse_timestamp(payload.get(key))
        if timestamp is not None:
            return timestamp
    return None


def canonical_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    text = text.replace(".P", "").replace("PERPETUAL", "").replace("PERP", "")
    return re.sub(r"[^A-Z0-9]", "", text)


def symbol_matches(expected: Any, actual: Any) -> bool:
    expected_key = canonical_symbol(expected)
    actual_key = canonical_symbol(actual)
    return bool(expected_key and actual_key and expected_key == actual_key)


def inspect_payload(
    payload: dict[str, Any] | None,
    *,
    max_age_hours: float,
    expected_symbol: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    contract_value = data.get("_source_contract")
    contract = contract_value if isinstance(contract_value, dict) else {}
    actual_symbol = data.get("symbol") or data.get("ticker") or contract.get("symbol")
    timestamp = parse_timestamp(contract.get("timestamp")) if contract else None
    timestamp = timestamp or payload_timestamp(data)
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds = None if timestamp is None else (now_utc - timestamp).total_seconds()
    identity_valid = expected_symbol is None or symbol_matches(expected_symbol, actual_symbol)
    fresh = age_seconds is not None and -60.0 <= age_seconds <= max_age_hours * 3600.0
    explicit = (
        contract.get("status")
        if contract
        else data.get("_source_status") or data.get("source_status")
    )
    # 2026-09-13：payload 里的 source_status 可能是结构化字典（例如刷新器写的逐项状态），
    # 直接做 `in VALID_STATES` 会抛 unhashable type: 'dict' 并让整个状态判定失败。
    # 只接受字符串，其余一律当作「没有显式状态」。
    explicit_status = explicit if isinstance(explicit, str) and explicit in VALID_STATES else None
    contract_error = contract.get("error") if contract else None
    payload_error = data.get("error") or data.get("_source_error")

    if not data:
        status = "not_run"
        reason = "payload为空"
    elif not identity_valid:
        status = "unavailable"
        reason = f"品种不匹配: expected={expected_symbol}, got={actual_symbol or 'missing'}"
    elif timestamp is None:
        status = explicit_status if explicit_status in DEGRADED_STATES else "unavailable"
        reason = str(contract_error or payload_error or "显式时间戳缺失")
    elif not fresh:
        status = "stale_cache"
        reason = f"数据过期: age={age_seconds:.0f}s"
    elif (
        data.get("stale") is True
        or data.get("usable") is False
        or contract_error
        or payload_error
        or explicit_status in {"stale_cache", "unavailable", "quota_cooldown", "not_run"}
    ):
        status = explicit_status or "stale_cache"
        reason = str(contract_error or payload_error or data.get("reason") or "数据被标记为不可用")
    else:
        # A timestamped legacy payload is usable as a cache, not proof of a
        # live provider response.  Producers with an explicit live status keep
        # that status visible.
        status = explicit_status or "cache"
        reason = "身份/显式时间戳/新鲜度通过"

    return {
        "exists": True,
        "identity_valid": identity_valid,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "age_seconds": age_seconds,
        "age_hours": None if age_seconds is None else max(0.0, age_seconds / 3600.0),
        "fresh": (
            fresh
            and identity_valid
            and bool(data)
            and status not in {"stale_cache", "unavailable", "quota_cooldown", "not_run"}
        ),
        "status": status,
        "symbol": actual_symbol,
        "reason": reason,
    }


def inspect_json_file(
    path: str | Path,
    *,
    max_age_hours: float,
    expected_symbol: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "exists": False,
            "identity_valid": False,
            "timestamp": None,
            "age_seconds": None,
            "age_hours": None,
            "fresh": False,
            "status": "not_run",
            "symbol": None,
            "reason": "文件不存在",
        }
    try:
        payload = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "exists": True,
            "identity_valid": False,
            "timestamp": None,
            "age_seconds": None,
            "age_hours": None,
            "fresh": False,
            "status": "unavailable",
            "symbol": None,
            "reason": f"JSON不可读: {exc}",
        }
    result = inspect_payload(payload, max_age_hours=max_age_hours, expected_symbol=expected_symbol, now=now)
    result["path"] = str(target)
    return result
