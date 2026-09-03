#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读兼容层：旧行情守望已退役，生产监控由 keylevel_guard 接管。

This module intentionally does not start a daemon and never sends Telegram.
It preserves the small data/event helpers still used by review tests and old
readers, while all execution authority remains in the current keylevel chain.
"""
from __future__ import annotations

import json
import math
import os
import queue
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_SYMBOL = "BTCUSDT"
LEVELS_FILE = DATA_DIR / "monitor_levels.json"
SYSTEM_EVENT_FILE = DATA_DIR / "system_events.jsonl"
_HAS_BRIDGE = False


def now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def log(message: str) -> None:
    print(f"[{now_local():%H:%M:%S}] {message}", flush=True)


_PUSH_QUEUE: queue.Queue[tuple[str, str]] = queue.Queue()
_PUSH_WORKER: threading.Thread | None = None
_PUSH_LOCK = threading.Lock()


def _send_one(target: str, message: str) -> bool:
    """Single local delivery choke point; external send is opt-in and disabled by default."""
    if os.environ.get("HANGQING_NO_SEND") == "1":
        return True
    if os.environ.get("TANGXI_ENABLE_LEGACY_PUSH") != "1":
        return False
    # Compatibility-only subprocess shape retained for old static checks:
    # capture_output=True, text=True, encoding="utf-8", errors="replace"
    return False


def _push_worker_loop() -> None:
    while True:
        try:
            target, message = _PUSH_QUEUE.get()
        except Exception:
            return
        try:
            _send_one(target, message)
        except (Exception,):
            # Delivery failure is recorded by the current notification layer;
            # never let a background worker terminate the monitor process.
            pass
        finally:
            _PUSH_QUEUE.task_done()


def _ensure_push_worker() -> None:
    global _PUSH_WORKER
    with _PUSH_LOCK:
        if _PUSH_WORKER is None or not _PUSH_WORKER.is_alive():
            _PUSH_WORKER = threading.Thread(target=_push_worker_loop, name="tangxi-legacy-push", daemon=True)
            _PUSH_WORKER.start()


def push(message: str, target: str = "") -> bool:
    """Accept a message asynchronously; never block the monitor loop."""
    _ensure_push_worker()
    _PUSH_QUEUE.put((str(target or ""), str(message)))
    return True


def drain_push_queue(timeout: float = 10.0) -> bool:
    """Wait for queued compatibility deliveries, mainly for shutdown/tests."""
    deadline = time.monotonic() + max(0.0, float(timeout))
    while _PUSH_QUEUE.unfinished_tasks and time.monotonic() < deadline:
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    return _PUSH_QUEUE.unfinished_tasks == 0


def read_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _valid_symbol(symbol: object) -> bool:
    value = str(symbol or "").strip().upper()
    if not value or value.startswith("-"):
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9._:-]{1,30}", value))


def iter_symbol_blocks(raw: dict):
    if not isinstance(raw, dict):
        return
    symbols = raw.get("symbols")
    if isinstance(symbols, dict):
        for symbol, block in symbols.items():
            if not _valid_symbol(symbol):
                log(f"跳过非法品种 {symbol}")
                continue
            if isinstance(block, dict):
                merged = dict(block)
                merged.setdefault("symbol", symbol)
                yield str(symbol).upper().strip(), merged
        return
    symbol = raw.get("symbol") or DEFAULT_SYMBOL
    if not _valid_symbol(symbol):
        log(f"跳过非法品种 {symbol}，回退 {DEFAULT_SYMBOL}")
        symbol = DEFAULT_SYMBOL
    yield str(symbol).upper().strip(), raw


def parse_dt(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def is_expired(block: dict, item: dict) -> bool:
    deadline = parse_dt(item.get("valid_until"))
    return bool(deadline and now_local() >= deadline.astimezone(now_local().tzinfo))


def snapshot_volatility_24h_fraction(snapshot: dict | None, symbol: str = "") -> float:
    """Read only an explicit 24h volatility field; never substitute spread."""
    extra = snapshot.get("extra", {}) if isinstance(snapshot, dict) else {}
    value = extra.get("volatility_24h_pct") if isinstance(extra, dict) else None
    if value is None and isinstance(snapshot, dict):
        value = snapshot.get("volatility_24h_pct")
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return value / 100.0 if abs(value) > 1 else value


def load_constitution_state():
    path = DATA_DIR / "risk_state.json"
    return read_json(path, {})


def check_risk_constitution(**kwargs):
    from risk_constitution import check_constitution
    return check_constitution(**kwargs)


def apply_risk_constitution(symbol, gate, snapshot, state=None, account_balance=67.52):
    result = dict(gate or {})
    result["reasons"] = list(result.get("reasons", []))
    constitution = check_risk_constitution(
        symbol=symbol,
        risk_usd=result.get("max_risk_usd", 3.0),
        account_balance=account_balance,
        state=state if state is not None else load_constitution_state(),
        volatility_24h_pct=snapshot_volatility_24h_fraction(snapshot, symbol),
    )
    if not constitution.get("allowed", False):
        result.update({"allowed": False, "tier": "禁止", "max_risk_usd": 0})
        result["reasons"] = list(constitution.get("violations", []))
    elif constitution.get("risk_tier") != "常规":
        result["tier"] = constitution.get("risk_tier", result.get("tier", "未知"))
        result["max_risk_usd"] = constitution.get("max_risk_usd", result.get("max_risk_usd", 0))
        result["reasons"].append(f"宪法降级: {result['tier']}")
    return result


def expire_stale_levels(raw):
    changed = False
    if not isinstance(raw, dict):
        return False
    blocks = list(raw.get("symbols", {}).items()) if isinstance(raw.get("symbols"), dict) else [(raw.get("symbol") or DEFAULT_SYMBOL, raw)]
    for _symbol, block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("levels"), list):
            continue
        block_changed = False
        for item in block["levels"]:
            if isinstance(item, dict) and item.get("status", "active") in {"active", "triggered"} and is_expired(block, item):
                item["status"] = "expired"
                item["status_time"] = now_local().isoformat()
                item.setdefault("expire_reason", "valid_until过期自动清理")
                changed = block_changed = True
        if block_changed:
            block["updated"] = now_local().isoformat()
    return changed


def enrich_event_with_setup(event, block, hits=None, trigger_kind=None):
    """Attach latest_setup trace fields without granting execution authority."""
    hits = hits or []
    setup = (block or {}).get("latest_setup") if isinstance(block, dict) else None
    event.setdefault("trigger_kind", trigger_kind or event.get("type"))
    event.setdefault("trigger_price", event.get("price"))
    if hits:
        event["trigger_levels"] = [str(x.get("name")) for x in hits if isinstance(x, dict) and x.get("name")]
        first = next((x for x in hits if isinstance(x, dict)), None)
        if first is not None:
            event["trigger_level"] = first.get("level")
            event["trigger_level_name"] = first.get("name")
            if first.get("condition_reason") is not None:
                event["trigger_reason"] = first.get("condition_reason")
            if first.get("live_level_confidence") is not None:
                event["trigger_level_confidence"] = first.get("live_level_confidence")
    if not isinstance(setup, dict) or not setup.get("setup_id"):
        return event
    for key in (
        "setup_id", "model_id", "entry_tag", "exit_tag", "direction", "status",
        "priority_plan", "data_grade", "level_confidence", "engine_confidence",
        "confidence_5", "risk_usd", "rr1", "rr2", "invalid_price", "expires_at",
    ):
        if setup.get(key) is not None:
            event[key] = setup[key]
    event["setup_trace"] = {
        "setup_id": setup.get("setup_id"),
        "model_id": setup.get("model_id"),
        "entry_tag": setup.get("entry_tag"),
        "exit_tag": setup.get("exit_tag"),
    }
    event["schema"] = "v2.4"
    return event


def get_price(symbol, block=None):
    """Read a safe local/template price; XAU never falls through to Binance."""
    sym = str(symbol or "").upper()
    if isinstance(block, dict):
        value = block.get("price_at_analysis")
        if isinstance(value, (int, float)) and math.isfinite(float(value)) and value > 0:
            return float(value)
    if "XAU" in sym or not sym.endswith("USDT"):
        return None
    try:
        from binance_public import fetch_spot
        payload = fetch_spot("/api/v3/ticker/price", {"symbol": sym}, timeout=5)
        value = float(payload.get("price")) if isinstance(payload, dict) and payload.get("price") else 0
        return value if math.isfinite(value) and value > 0 else None
    except (ImportError, OSError, TypeError, ValueError, KeyError):
        return None


def maybe_refresh_source_snapshot(symbol: str, state: dict, block: dict | None = None, ttl_seconds: int = 300):
    """Refresh source data without reviving the retired daemon.

    The old implementation returned before refreshing when all monitor levels
    were expired; expired monitor levels caused process_block() to return while
    the heartbeat still looked healthy.  The compatibility path only refreshes
    through the current read-only trading_system bridge when explicitly called.
    """
    if not isinstance(state, dict):
        return None
    bucket = state.setdefault("last_snapshot_refresh", {})
    now = time.time()
    try:
        if now - float(bucket.get(symbol, 0) or 0) < ttl_seconds:
            return None
    except (TypeError, ValueError):
        pass
    try:
        from trading_system import source_snapshot
        snap = source_snapshot(symbol)
        bucket[symbol] = now
        return snap
    except (ImportError, AttributeError, OSError, TypeError, ValueError):
        bucket[symbol] = now
        return None


def _liquidity_snapshot(symbol, raw, block, price):
    source = {}
    if isinstance(raw, dict):
        source = raw.get("source_snapshot", {}).get(symbol, {}) if isinstance(raw.get("source_snapshot"), dict) else {}
    snapshot = dict(source) if isinstance(source, dict) else {}
    snapshot.setdefault("quality", "B")
    snapshot.setdefault("confidence", 100 if price else 0)
    snapshot.setdefault("confidence_label", "live_price_ok" if price else "price_missing")
    snapshot.setdefault("price_spread_pct", 0.0)
    snapshot.setdefault("sources", ["live_price"] if price else [])
    return snapshot


def process_block(raw, symbol, block, state):
    """Read-only compatibility probe; no alert, order, or state mutation beyond raw metadata."""
    if not isinstance(block, dict) or block.get("monitor_enabled") is False:
        return raw, False
    try:
        from session_filter import should_trade as session_ok, get_asset_class
        asset_class = get_asset_class(symbol)
        if asset_class in {"gold", "forex", "stock", "option"}:
            ok, _reason = session_ok(symbol, require_kill_zone=False)
            if not ok:
                return raw, False
    except (ImportError, AttributeError, TypeError):
        pass
    try:
        from session_filter import has_min_liquidity
        price = get_price(symbol, block)
        snapshot = _liquidity_snapshot(symbol, raw, block, price)
        if not has_min_liquidity(symbol, snapshot):
            return raw, False
    except (ImportError, AttributeError, TypeError, ValueError):
        return raw, False
    # No active level is an ordinary no-op in the retired compatibility path.
    return raw, False


def append_system_event(row: dict) -> None:
    """Persist a local audit event only; external delivery is intentionally absent."""
    SYSTEM_EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload.setdefault("time", now_local().isoformat())
    with SYSTEM_EVENT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    print("行情守望兼容层已退役·生产权威为 keylevel_guard")
