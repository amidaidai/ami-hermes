"""Offline inheritance boundaries; never import the side-effectful card entrypoint."""
from datetime import datetime, timedelta, timezone
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from tv_five_tf_contract import REQUIRED_TIMEFRAMES, validate_five_tf_payload

NOW = datetime(2026, 9, 12, 4, tzinfo=timezone.utc)


def context_payload(age_hours=1):
    return {
        "symbol": "BTCUSDT", "source": "inherited_context",
        "updated_at": NOW.isoformat(),
        "timeframes": {
            tf: {"open": 100, "close": 101, "high": 110, "low": 90,
                 "tv_timestamp": (NOW - timedelta(hours=age_hours)).isoformat(),
                 "tv_identity_valid": True,
                 "tv_action_grid": {"方向": "偏多"}}
            for tf in REQUIRED_TIMEFRAMES
        },
    }


def card_function(name, **globals_):
    # Execute the real pure boundary, excluding auto_card's import-time setup.
    tree = ast.parse((ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = dict(globals_)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "scripts" / "auto_card.py"), "exec"), namespace)
    return namespace[name]


def test_inheritance_does_not_overwrite_current_execution_rows():
    merge = card_function("_merge_tv_five_tf_into_engine")
    current = {"15m": {"close": 90, "direction": "偏空"}, "5m": {"close": 89}}
    data = {"klines": {key: dict(row) for key, row in current.items()}}
    incoming = {tf: {"close": 101, "direction": "偏多", "tv_ohlcv_complete": True} for tf in REQUIRED_TIMEFRAMES}
    merge(data, {"usable": True, "scope": "inherited_context", "engine_klines": incoming})
    assert data["klines"]["15m"] == current["15m"]
    assert data["klines"]["5m"] == current["5m"]
    assert set(data["_tv_five_tf_klines"]) == {"D", "4h", "1h"}


def test_context_save_time_must_not_rejuvenate_old_observations():
    result = validate_five_tf_payload(context_payload(5), "BTCUSDT", now=NOW, max_age_minutes=240)
    assert result["usable"] is False
    assert "4h" in result["invalid_timeframes"]
