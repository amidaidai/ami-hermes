"""棠溪决策闭环字段契约。"""
from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class MarketSnapshot(TypedDict):
    symbol: str
    ts: int
    price: float
    ohlcv: dict[str, Any]
    tv_indicators: dict[str, Any]
    derivatives: dict[str, Any]
    macro: dict[str, Any]
    news: dict[str, Any] | None


class CandidatePlan(TypedDict):
    model_id: str
    direction: str
    entry: float
    stop: float
    target: float
    rr: float
    grade: NotRequired[str]
    fvg_quality: NotRequired[float]
    ob_quality: NotRequired[float]


class GateResult(TypedDict):
    gate_name: str
    status: str
    reason: str


_SNAPSHOT_KEYS = frozenset(MarketSnapshot.__required_keys__)


def validate_market_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    """运行时边界校验：缺字段或契约外字段立即失败，防止实盘/回测漂移。"""
    keys = set(value)
    missing = _SNAPSHOT_KEYS - keys
    extra = keys - _SNAPSHOT_KEYS
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"extra fields: {sorted(extra)}")
    if not value.get("symbol") or int(value.get("ts") or 0) <= 0 or float(value.get("price") or 0) <= 0:
        raise ValueError("invalid snapshot identity")
    return value


__all__ = [
    "MarketSnapshot", "CandidatePlan", "GateResult", "validate_market_snapshot",
]
