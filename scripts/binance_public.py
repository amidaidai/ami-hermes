#!/usr/bin/env python3
"""Reliable public Binance market-data access with honest fallbacks.

Spot market data uses Binance's primary REST host and the official market-data-only
``data-api.binance.vision`` fallback. Futures-only metrics fall back to Orion's
Binance screener feed and are marked quality B rather than impersonating a direct
Binance Futures response.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any

UA = "TangXi/1.0"
SPOT_BASES = (
    "https://api.binance.com",
    "https://data-api.binance.vision",
)
ORION_URL = "https://screener.orionterminal.com/api/screener?exchange=binance"
_HOST_DOWN_UNTIL: dict[str, float] = {}
HOST_COOLDOWN_SECONDS = 300.0
_ORION_CACHE: dict[str, dict[str, Any]] = {}
_ORION_CACHE_AT = 0.0
ORION_CACHE_SECONDS = 30.0
_FAPI_HEALTH: bool | None = None
_FAPI_HEALTH_AT = 0.0
FAPI_HEALTH_SECONDS = 300.0


def _opener():
    """Use a direct connection; provider traffic must not inherit a local proxy."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch_url(url: str, timeout: int = 8) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with _opener().open(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return None


def fetch_spot(path: str, params: dict[str, Any] | None = None, timeout: int = 8) -> Any:
    query = urllib.parse.urlencode(params or {})
    suffix = f"?{query}" if query else ""
    now = time.monotonic()
    for base in SPOT_BASES:
        if _HOST_DOWN_UNTIL.get(base, 0.0) > now:
            continue
        payload = fetch_url(f"{base}{path}{suffix}", timeout=timeout)
        if payload is not None and not (isinstance(payload, dict) and payload.get("code")):
            return payload
        _HOST_DOWN_UNTIL[base] = time.monotonic() + HOST_COOLDOWN_SECONDS
    return None


def fapi_available(timeout: int = 2) -> bool:
    """Cached Binance Futures host health probe used to avoid timeout cascades."""
    global _FAPI_HEALTH, _FAPI_HEALTH_AT
    now = time.monotonic()
    if _FAPI_HEALTH is not None and now - _FAPI_HEALTH_AT <= FAPI_HEALTH_SECONDS:
        return _FAPI_HEALTH
    payload = fetch_url("https://fapi.binance.com/fapi/v1/time", timeout=timeout)
    _FAPI_HEALTH = isinstance(payload, dict) and bool(payload.get("serverTime"))
    _FAPI_HEALTH_AT = now
    return _FAPI_HEALTH


def fetch_orion_ticker(symbol: str, timeout: int = 15) -> dict[str, Any] | None:
    global _ORION_CACHE, _ORION_CACHE_AT
    now = time.monotonic()
    if not _ORION_CACHE or now - _ORION_CACHE_AT > ORION_CACHE_SECONDS:
        payload = fetch_url(ORION_URL, timeout=timeout)
        rows = payload.get("tickers") if isinstance(payload, dict) else None
        if isinstance(rows, list):
            _ORION_CACHE = {
                str(row.get("symbol") or "").upper(): row
                for row in rows
                if isinstance(row, dict) and row.get("symbol")
            }
            _ORION_CACHE_AT = now
    return _ORION_CACHE.get(str(symbol).upper())


def orion_derivatives_snapshot(symbol: str, timeout: int = 15) -> dict[str, Any]:
    row = fetch_orion_ticker(symbol, timeout=timeout)
    if not row:
        return {
            "source": "Orion/Binance Futures",
            "symbol": str(symbol).upper(),
            "ok": False,
            "quality": "C",
            "error": "Orion Binance futures feed unavailable",
        }
    mark = float(row.get("markPrice") or row.get("price") or 0)
    index = float(row.get("indexPrice") or 0)
    tf1h_raw = row.get("tf1h")
    tf1h: dict[str, Any] = tf1h_raw if isinstance(tf1h_raw, dict) else {}
    return {
        "source": "Orion/Binance Futures",
        "symbol": str(symbol).upper(),
        "ok": bool(mark and row.get("openInterest")),
        "quality": "B",
        "mark_price": mark,
        "index_price": index,
        "funding": float(row.get("fundingRate") or 0),
        "basis_pct": ((mark - index) / index * 100) if mark and index else 0.0,
        "open_interest": float(row.get("openInterest") or 0),
        "open_interest_usd": float(row.get("openInterestUsd") or 0),
        "oi_change_1h_pct": float(tf1h.get("oiChange") or 0),
        "price_change_1h_pct": float(tf1h.get("changePercent") or 0),
        "long_short_ratio": None,
        "taker_buy_sell_ratio": None,
    }
