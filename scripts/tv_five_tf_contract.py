"""TradingView five-timeframe snapshot contract.

This module is deliberately a data-boundary helper.  It does not infer a
trade direction and it does not promote candidate levels to approved levels.
It only makes the D/4h/1h/15m/5m snapshot explicit before a full card may
consume it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any, cast


REQUIRED_TIMEFRAMES = ("D", "4h", "1h", "15m", "5m")
_TIMEFRAME_ALIASES = {
    "D": "D",
    "1D": "D",
    "DAY": "D",
    "240": "4h",
    "4H": "4h",
    "4HR": "4h",
    "60": "1h",
    "1H": "1h",
    "1HR": "1h",
    "15": "15m",
    "15M": "15m",
    "15MIN": "15m",
    "5": "5m",
    "5M": "5m",
    "5MIN": "5m",
}


def _as_mapping(value: Any) -> dict[str, Any]:
    """Narrow JSON dictionaries for static type checkers."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def normalize_timeframe(value: Any) -> str | None:
    """Return the canonical display timeframe for a TV/cache alias."""
    text = str(value or "").strip().upper().replace(" ", "")
    return _TIMEFRAME_ALIASES.get(text)


def _canonical_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1]
    raw = raw.replace(".P", "").replace("PERPETUAL", "").replace("PERP", "")
    return re.sub(r"[^A-Z0-9]", "", raw)


def _symbol_matches(expected: Any, actual: Any) -> bool:
    expected_key = _canonical_symbol(expected)
    actual_key = _canonical_symbol(actual)
    return bool(expected_key and actual_key and expected_key == actual_key)


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 100_000_000_000:
            number /= 1000.0
        try:
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


def _payload_timestamp(payload: dict[str, Any], source_path: Path | None) -> datetime | None:
    for key in ("updated_epoch", "updated_at", "ts", "time", "updated"):
        parsed = _parse_timestamp(payload.get(key))
        if parsed is not None:
            return parsed
    # A file mtime only proves that a file was touched.  It is not evidence
    # that the market snapshot itself was collected at that time.
    return None


def _canonical_timeframes(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("timeframes")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for raw_tf, value in raw.items():
        tf = normalize_timeframe(raw_tf)
        if tf is not None and isinstance(value, dict) and value:
            result[tf] = dict(value)
    return {tf: result[tf] for tf in REQUIRED_TIMEFRAMES if tf in result}


def _numeric_positive(value: Any) -> bool:
    if value in (None, "", "—", "--"):
        return False
    text = str(value).replace(",", "").replace("\u202f", "").replace("\u00a0", "").replace(" ", "").strip()
    multiplier = 1.0
    if text[-1:].upper() in {"K", "M", "B"}:
        multiplier = {"K": 1e3, "M": 1e6, "B": 1e9}[text[-1:].upper()]
        text = text[:-1]
    try:
        number = float(text) * multiplier
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def _record_validation_reason(symbol: str, timeframe: str, record: dict[str, Any]) -> str:
    """Validate one layer without assuming every market uses OHLCV."""
    chart_state = _as_mapping(record.get("chart_state"))
    state_symbol = chart_state.get("symbol") or chart_state.get("ticker")
    if state_symbol and not _symbol_matches(symbol, state_symbol):
        return f"嵌套图表品种不匹配: got={state_symbol}"
    state_tf = chart_state.get("timeframe") or chart_state.get("resolution")
    if state_tf and normalize_timeframe(state_tf) != timeframe:
        return f"嵌套图表周期不匹配: got={state_tf}"

    has_price = any(_numeric_positive(record.get(key)) for key in ("price", "close", "lastPrice"))
    if not has_price:
        return "缺少有效价格/收盘证据"

    has_ohlcv = all(_numeric_positive(record.get(key)) for key in ("open", "high", "low", "close"))
    study_values = _as_mapping(record.get("sv"))
    study_keys = {str(key).upper().replace(" ", "_") for key in study_values}
    has_profile = any(
        key.startswith(prefix)
        for key in study_keys
        for prefix in ("POC", "VAH", "VAL", "S_VWAP", "M_VWAP", "W_VWAP")
    )
    action_grid = _as_mapping(record.get("grid"))
    has_action_grid = bool(action_grid)
    if not (has_ohlcv or has_profile or has_action_grid):
        return "缺少OHLCV、SVP结构或行动格证据"
    return ""


def validate_five_tf_payload(
    payload: dict[str, Any] | None,
    symbol: str,
    *,
    max_age_minutes: float = 30.0,
    now: datetime | None = None,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate identity, freshness and actual five-layer payload content."""
    payload = payload if isinstance(payload, dict) else {}
    path = Path(source_path) if source_path else None
    actual_symbol = payload.get("symbol") or payload.get("ticker")
    identity_valid = _symbol_matches(symbol, actual_symbol)
    timestamp = _payload_timestamp(payload, path)
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds = None if timestamp is None else (now_utc - timestamp).total_seconds()
    fresh = age_seconds is not None and -60.0 <= age_seconds <= max_age_minutes * 60.0
    timeframes = _canonical_timeframes(payload)
    invalid_timeframes = {
        tf: reason
        for tf, record in timeframes.items()
        if (reason := _record_validation_reason(symbol, tf, record))
    }
    # Context updated_at is the card save time, not the observation time.
    # Never rejuvenate compact observations when a full card is saved again.
    if payload.get("source") == "inherited_context":
        for tf, record in timeframes.items():
            observed = _parse_timestamp(record.get("tv_timestamp"))
            observed_age = None if observed is None else (now_utc - observed).total_seconds()
            if observed_age is None or not -60.0 <= observed_age <= max_age_minutes * 60.0:
                invalid_timeframes[tf] = "继承观测时间戳缺失/过期/未来"
    present = [tf for tf in REQUIRED_TIMEFRAMES if tf in timeframes and tf not in invalid_timeframes]
    missing = [tf for tf in REQUIRED_TIMEFRAMES if tf not in timeframes]
    usable = identity_valid and fresh and not missing and not invalid_timeframes

    if not identity_valid:
        reason = f"TV五周期品种不匹配: expected={symbol}, got={actual_symbol or 'missing'}"
    elif timestamp is None:
        reason = "TV五周期时间戳缺失"
    elif not fresh:
        reason = f"TV五周期过期: age={age_seconds:.0f}s" if age_seconds is not None else "TV五周期过期"
    elif missing:
        reason = f"TV五周期缺层: {','.join(missing)}"
    elif invalid_timeframes:
        reason = "TV五周期层内容无效: " + ";".join(
            f"{tf}·{detail}" for tf, detail in invalid_timeframes.items()
        )
    else:
        reason = "TV五周期身份/新鲜度/五层内容通过"

    return {
        "usable": usable,
        "identity_valid": identity_valid,
        "fresh": fresh,
        "symbol": actual_symbol,
        "expected_symbol": symbol,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "age_seconds": age_seconds,
        "timeframes": present,
        "missing": missing,
        "invalid_timeframes": invalid_timeframes,
        "coverage": len(present),
        "reason": reason,
        "source": payload.get("source") or "tradingview_mcp",
        "source_path": str(path) if path else "",
        "payload": payload,
    }


def _number(value: Any) -> float | None:
    if value in (None, "", "—", "--"):
        return None
    text = str(value).replace(",", "").replace("−", "-")
    text = text.replace("\u202f", "").replace("\u00a0", "").replace(" ", "").strip()
    multiplier = 1.0
    if text[-1:].upper() in {"K", "M", "B"}:
        multiplier = {"K": 1e3, "M": 1e6, "B": 1e9}[text[-1:].upper()]
        text = text[:-1]
    try:
        return float(text) * multiplier
    except (TypeError, ValueError):
        return None


def _pick(mapping: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _number(mapping.get(key))
        if value is not None:
            return value
    return None


def _normalise_record(tf: str, record: dict[str, Any], source: str, timestamp: str | None) -> dict[str, Any]:
    sv = _as_mapping(record.get("sv"))
    grid = _as_mapping(record.get("grid"))
    state = _as_mapping(record.get("chart_state"))
    close = _pick(record, "close", "price", "lastPrice")
    high = _pick(record, "high")
    low = _pick(record, "low")
    opening = _pick(record, "open")
    poc = _pick(record, "poc", "POC_PRICE", "POC")
    if poc is None:
        poc = _pick(sv, "POC_PRICE", "POC")
    vah = _pick(record, "vah", "VAH_PRICE", "VAH")
    if vah is None:
        vah = _pick(sv, "VAH_PRICE", "VAH")
    val = _pick(record, "val", "VAL_PRICE", "VAL")
    if val is None:
        val = _pick(sv, "VAL_PRICE", "VAL")
    vwap = _pick(record, "vwap", "S_VWAP", "S VWAP")
    if vwap is None:
        vwap = _pick(sv, "S_VWAP", "S VWAP")
    npoc = _pick(record, "npoc", "NPOC_PRICE", "NPOC")
    if npoc is None:
        npoc = _pick(sv, "NPOC_PRICE", "NPOC")
    description = str(
        record.get("description")
        or grid.get("结构")
        or grid.get("方向")
        or grid.get("位置")
        or f"TV现场·{tf}"
    )
    return {
        "timeframe": tf,
        "tv_source": source,
        "tv_timestamp": timestamp,
        "tv_identity_valid": True,
        "tv_ohlcv_complete": all(value is not None for value in (opening, high, low, close)),
        "tv_action_grid": grid,
        "tv_study_values": sv,
        "tv_chart_state": state,
        "tv_lines": record.get("lines") or [],
        "tv_labels": record.get("labels") or [],
        "tv_boxes": record.get("boxes") or [],
        "open": opening,
        "close": close,
        "price": close,
        "high": high if high is not None else close,
        "low": low if low is not None else close,
        "change_pct": _number(record.get("change_pct")) or 0.0,
        "poc": poc,
        "vah": vah,
        "val": val,
        "vwap": vwap,
        "npoc": npoc,
        "direction": str(grid.get("方向") or record.get("direction") or "待判"),
        "description": description,
    }


def normalize_engine_klines(validation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Convert a validated snapshot into the engine's per-timeframe shape."""
    if not isinstance(validation, dict):
        return {}
    payload = _as_mapping(validation.get("payload"))
    raw = _as_mapping(payload.get("timeframes"))
    source = str(validation.get("source") or payload.get("source") or "tradingview_mcp")
    timestamp = validation.get("timestamp")
    output: dict[str, dict[str, Any]] = {}
    for tf in REQUIRED_TIMEFRAMES:
        record = None
        for raw_tf, raw_record in raw.items():
            if normalize_timeframe(raw_tf) == tf and isinstance(raw_record, dict):
                record = raw_record
                break
        if record is not None:
            output[tf] = _normalise_record(tf, record, source, timestamp)
    return output


def _candidate_paths(symbol: str, data_dir: Path) -> list[Path]:
    key = _canonical_symbol(symbol)
    if key.endswith("USDT"):
        names = ["keylevels_candidates.json", f"tv_five_tf_{key}.json"]
    elif key == "XAUUSD":
        names = ["xau_tv_state.json", f"tv_five_tf_{key}.json"]
    else:
        names = [f"tv_five_tf_{key}.json"]
    return [data_dir / name for name in names]


def load_five_tf_snapshot(
    symbol: str,
    *,
    data_dir: str | Path | None = None,
    max_age_minutes: float = 30.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Load the newest valid symbol-scoped five-timeframe snapshot."""
    root = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parents[1] / "data"
    invalid: list[dict[str, Any]] = []
    for path in _candidate_paths(symbol, root):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            invalid.append({"usable": False, "source_path": str(path), "reason": f"TV五周期缓存不可读: {exc}"})
            continue
        validation = validate_five_tf_payload(
            payload,
            symbol,
            max_age_minutes=max_age_minutes,
            now=now,
            source_path=path,
        )
        if validation["usable"]:
            return validation
        invalid.append(validation)
    if invalid:
        return max(invalid, key=lambda item: item.get("timestamp") or "")
    return {
        "usable": False,
        "identity_valid": False,
        "fresh": False,
        "symbol": None,
        "expected_symbol": symbol,
        "timestamp": None,
        "age_seconds": None,
        "timeframes": [],
        "missing": list(REQUIRED_TIMEFRAMES),
        "coverage": 0,
        "reason": "TV五周期缓存不存在",
        "source": "tradingview_mcp",
        "source_path": "",
        "payload": {},
    }
