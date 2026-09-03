from __future__ import annotations

from datetime import datetime, timezone, timedelta

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tv_five_tf_contract import (  # type: ignore[import-not-found]
    REQUIRED_TIMEFRAMES,
    load_five_tf_snapshot,
    normalize_engine_klines,
    validate_five_tf_payload,
)


BJT = timezone(timedelta(hours=8))


def _payload(*, symbol="BINANCE:BTCUSDT.P", timestamp="2026-09-02T08:00:00+08:00", keys=None):
    keys = keys or REQUIRED_TIMEFRAMES
    return {
        "symbol": symbol,
        "ts": timestamp,
        "layers": ["D", "240", "60", "15", "5"],
        "timeframes": {
            key: {
                "price": 100.0,
                "sv": {"POC_PRICE": 99.0, "VAH_PRICE": 101.0, "VAL_PRICE": 98.0},
                "grid": {"结构": f"{key}结构"},
                "chart_state": {"symbol": symbol, "timeframe": key},
            }
            for key in keys
        },
    }


def test_validate_requires_real_payload_for_each_canonical_timeframe():
    result = validate_five_tf_payload(
        _payload(keys=("D", "4h", "1h", "15m")),
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )

    assert result["usable"] is False
    assert result["missing"] == ["5m"]
    assert result["coverage"] == 4
    assert result["identity_valid"] is True
    assert result["fresh"] is True


def test_validate_accepts_exchange_qualified_symbol_and_alias_timeframes():
    payload = _payload(keys=("1D", "240", "60", "15", "5"))
    result = validate_five_tf_payload(
        payload,
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )

    assert result["usable"] is True
    assert result["missing"] == []
    assert result["timeframes"] == list(REQUIRED_TIMEFRAMES)


def test_validate_rejects_wrong_symbol_and_stale_payload():
    wrong_symbol = validate_five_tf_payload(
        _payload(symbol="OANDA:XAUUSD"),
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )
    stale = validate_five_tf_payload(
        _payload(timestamp="2026-09-02T06:00:00+08:00"),
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
        max_age_minutes=30,
    )

    assert wrong_symbol["usable"] is False
    assert wrong_symbol["identity_valid"] is False
    assert stale["usable"] is False
    assert stale["fresh"] is False


def test_normalize_engine_klines_keeps_tv_identity_and_action_grid():
    result = validate_five_tf_payload(
        _payload(),
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )
    klines = normalize_engine_klines(result)

    assert list(klines) == list(REQUIRED_TIMEFRAMES)
    assert klines["15m"]["tv_source"] == "tradingview_mcp"
    assert klines["15m"]["poc"] == 99.0
    assert klines["15m"]["vah"] == 101.0
    assert klines["15m"]["val"] == 98.0
    assert klines["15m"]["tv_action_grid"]["结构"] == "15m结构"


def test_normalize_engine_klines_parses_tradingview_compact_price_units():
    payload = _payload()
    payload["timeframes"]["15m"]["sv"] = {
        "POC_PRICE": "63.79\u202fK",
        "VAH_PRICE": "77.75 K",
        "VAL_PRICE": "61.78K",
    }
    result = validate_five_tf_payload(
        payload,
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )
    klines = normalize_engine_klines(result)

    assert klines["15m"]["poc"] == 63790.0
    assert klines["15m"]["vah"] == 77750.0
    assert klines["15m"]["val"] == 61780.0


def test_load_five_tf_snapshot_reads_symbol_specific_candidate_file(tmp_path):
    import json

    path = tmp_path / "keylevels_candidates.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    result = load_five_tf_snapshot(
        "BTCUSDT",
        data_dir=tmp_path,
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )

    assert result["usable"] is True
    assert result["source_path"] == str(path)
    assert result["coverage"] == 5


def test_validate_rejects_nonempty_but_unusable_timeframe_record():
    payload = _payload()
    payload["timeframes"]["15m"] = {"unexpected": "field"}

    result = validate_five_tf_payload(
        payload,
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )

    assert result["usable"] is False
    assert "15m" in result["invalid_timeframes"]


def test_validate_requires_explicit_payload_timestamp_even_for_fresh_file(tmp_path):
    import json

    path = tmp_path / "keylevels_candidates.json"
    payload = _payload()
    payload.pop("ts")
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = load_five_tf_snapshot(
        "BTCUSDT",
        data_dir=tmp_path,
        now=datetime.now(timezone.utc),
    )

    assert result["usable"] is False
    assert "时间戳缺失" in result["reason"]


def test_validate_rejects_timeframe_record_with_wrong_chart_identity():
    payload = _payload()
    payload["timeframes"]["15m"]["chart_state"] = {
        "symbol": "OANDA:XAUUSD",
        "timeframe": "1h",
    }

    result = validate_five_tf_payload(
        payload,
        "BTCUSDT",
        now=datetime(2026, 9, 2, 8, 10, tzinfo=BJT),
    )

    assert result["usable"] is False
    assert "15m" in result["invalid_timeframes"]
