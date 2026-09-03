from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cross_validation
import multi_source_collector as m
import auto_card  # type: ignore[import-not-found]
from source_contract import attach_source_contract
from source_health import inspect_payload


NOW = "2026-09-02T12:00:00+00:00"


def test_source_contract_preserves_legacy_fields_and_structures_metadata():
    raw = {"symbol": "BTCUSDT", "rotation": "同步", "coin_count": 10}
    decorated = attach_source_contract(
        raw,
        "cg_top",
        status="live",
        captured_at=NOW,
        observed_at=NOW,
    )

    assert decorated["rotation"] == "同步"
    contract = decorated["_source_contract"]
    assert contract["version"] == 1
    assert contract["source_id"] == "cg_top"
    assert contract["status"] == "live"
    assert contract["timestamp"] == NOW
    assert contract["payload"] == raw
    assert contract["error"] is None
    assert decorated["_source_status"] == "live"
    assert decorated["_source_timestamp"] == NOW


def test_live_contract_without_capture_timestamp_fails_closed():
    decorated = attach_source_contract(
        {"symbol": "BTCUSDT", "value": 1},
        "cg_top",
        status="live",
    )

    contract = decorated["_source_contract"]
    assert contract["status"] == "unavailable"
    assert contract["timestamp"] is None
    assert contract["error"] == "missing_timestamp"
    assert decorated["_source_status"] == "unavailable"


def test_nested_contract_is_consumed_by_shared_health_checker():
    decorated = attach_source_contract(
        {"symbol": "BTCUSDT", "value": 1},
        "cg_top",
        status="live",
        captured_at=NOW,
        observed_at=NOW,
    )
    result = inspect_payload(
        decorated,
        max_age_hours=1,
        expected_symbol="BTCUSDT",
        now=datetime.fromisoformat(NOW),
    )

    assert result["fresh"] is True
    assert result["status"] == "live"
    assert result["timestamp"] == NOW


def test_gather_all_keeps_legacy_sources_and_records_empty_sources(monkeypatch):
    monkeypatch.setattr(m, "av_quote", lambda symbol: {"symbol": symbol, "price": 1.0})
    monkeypatch.setattr(m, "td_quote", lambda symbol: {"symbol": symbol, "price": 1.0})
    monkeypatch.setattr(m, "td_technical", lambda symbol: {"symbol": symbol, "rsi": 50.0})
    monkeypatch.setattr(m, "fmp_quote", lambda symbol: {"symbol": symbol, "price": 1.0})
    monkeypatch.setattr(m, "massive_aggs", lambda symbol, asset: {"symbol": symbol, "close": 1.0})
    monkeypatch.setattr(m, "tushare_daily", lambda symbol: {})
    monkeypatch.setattr(m, "macro_overview", lambda: {"sentiment": "neutral"})

    result = m.gather_all("stock", "AAPL")
    records = result["_source_records"]

    assert result["av"]["price"] == 1.0
    assert set(records) == {"av", "td", "td_tech", "fmp", "massive", "tushare", "macro"}
    assert records["av"]["status"] == "unavailable"
    assert records["av"]["error"] == "missing_timestamp"
    assert records["av"]["timestamp"] is None
    assert records["av"]["payload"]["price"] == 1.0
    assert records["tushare"]["status"] == "not_run"
    assert records["tushare"]["payload"] == {}


def test_nested_optional_failure_is_visible_but_not_a_hard_blocker():
    unavailable = attach_source_contract(
        None,
        "macro",
        status="unavailable",
        error="timeout",
        observed_at=NOW,
    )
    rows = cross_validation.build_source_matrix(
        "AAPL",
        {
            "_asset_sources": {"_source_records": {"macro": unavailable["_source_contract"]}},
        },
        {"asset_is_crypto": False},
        pipeline_steps=["macro"],
    )
    macro_row = next(row for row in rows if row["id"] == "macro")
    evaluation = cross_validation.evaluate_cross_validation(rows)

    assert macro_row["status"] == "unavailable"
    assert macro_row["source_error"] == "timeout"
    assert macro_row["payload_present"] is False
    assert "macro" not in evaluation["hard_blockers"]
    assert "macro" in evaluation["warnings"]


def test_auto_card_registers_old_timestamped_cache_as_stale():
    engine_data: dict = {}
    record = auto_card._register_source_record(
        engine_data,
        "x_sentiment",
        {"ts": "2020-01-01T00:00:00+00:00", "headline": "old"},
        max_age_hours=1.0,
    )

    assert record["status"] == "stale_cache"
    assert record["timestamp"].startswith("2020-01-01T00:00:00")
    assert auto_card._source_record_usable(engine_data, "x_sentiment") is False


def test_crypto_matrix_prefers_normalized_source_record_over_flat_payload():
    stale = attach_source_contract(
        {"headline": "old"},
        "x_sentiment",
        status="stale_cache",
        captured_at="2020-01-01T00:00:00+00:00",
    )
    rows = cross_validation.build_source_matrix(
        "BTCUSDT",
        {
            "_source_records": {"x_sentiment": stale["_source_contract"]},
            "x_sentiment": {"headline": "looks non-empty"},
        },
        {"asset_is_crypto": True},
        pipeline_steps=["x_sent"],
    )
    sentiment = next(row for row in rows if row["id"] == "x_sentiment")

    assert sentiment["status"] == "stale_cache"
    assert sentiment["timestamp"].startswith("2020-01-01T00:00:00")
    assert sentiment["payload_present"] is True
