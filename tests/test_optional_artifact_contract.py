from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deribit_options
import dune_collector
import event_ban_live
import macro_filter
import stablecoin_collector
from source_contract import write_source_artifact


NOW = "2026-09-02T12:00:00+00:00"


def test_write_source_artifact_is_atomic_and_keeps_legacy_payload(tmp_path):
    path = tmp_path / "source.json"
    artifact = write_source_artifact(
        path,
        "example_source",
        {"value": 42, "symbol": "BTCUSDT"},
        status="live",
        captured_at=NOW,
        symbol="BTCUSDT",
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["value"] == 42
    assert saved["_source_contract"] == artifact["_source_contract"]
    assert saved["_source_contract"]["source_id"] == "example_source"
    assert saved["_source_contract"]["timestamp"] == NOW
    assert not list(tmp_path.glob("*.tmp"))


def test_dune_cache_contains_contract_without_breaking_data_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(dune_collector, "CACHE_FILE", tmp_path / "dune_cache.json")
    monkeypatch.setattr(dune_collector.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        dune_collector,
        "_get_query_results",
        lambda query_id, limit=10: [{"inflow": 1, "inflow_usd": 2, "formatted_time": NOW}]
        if query_id == dune_collector.QUERIES["btc_flow"]
        else [{"exchange": "binance", "netflow": -1, "inflow": -1}],
    )

    result = dune_collector.gather_onchain()
    saved = json.loads((tmp_path / "dune_cache.json").read_text(encoding="utf-8"))

    assert result["btc_flow"]["ok"] is True
    assert result["_source_contract"]["source_id"] == "dune"
    assert saved["data"]["btc_flow"]["ok"] is True
    assert saved["_source_contract"]["status"] == "live"
    assert saved["_source_contract"]["timestamp"] is not None


def test_deribit_cache_contains_contract_and_keeps_coin_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(deribit_options, "CACHE_FILE", tmp_path / "deribit_options.json")
    deribit_options._save_cache({"BTC": {"total_oi_usd": 123.0, "max_pain_valid": True}})
    saved = json.loads((tmp_path / "deribit_options.json").read_text(encoding="utf-8"))

    assert saved["BTC"]["total_oi_usd"] == 123.0
    assert saved["_source_contract"]["source_id"] == "deribit_options"
    assert saved["_source_contract"]["status"] == "live"
    assert saved["_source_contract"]["payload_present"] is True


def test_stablecoin_snapshot_contains_contract_and_keeps_previous_data(monkeypatch, tmp_path):
    monkeypatch.setattr(stablecoin_collector, "DATA_DIR", str(tmp_path))
    stablecoin_collector.save_snapshot({"total": 100.0, "data": {"USDT": 100.0}, "ts": NOW})
    saved = json.loads((tmp_path / "stablecoin_snapshot.json").read_text(encoding="utf-8"))

    assert saved["total"] == 100.0
    assert saved["data"]["USDT"] == 100.0
    assert saved["_source_contract"]["source_id"] == "stablecoin_snapshot"
    assert saved["_source_contract"]["timestamp"] == NOW


def test_macro_snapshot_marks_all_provider_failures_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(macro_filter, "CACHE_FILE", tmp_path / "macro_snapshot.json")
    monkeypatch.setattr(macro_filter, "_safe_fetch", lambda url, timeout=8: None)

    snapshot = macro_filter.fetch_macro_snapshot()
    saved = json.loads((tmp_path / "macro_snapshot.json").read_text(encoding="utf-8"))

    assert snapshot["_source_contract"]["source_id"] == "macro"
    assert snapshot["_source_contract"]["status"] == "unavailable"
    assert snapshot["_source_contract"]["error"] == "empty_payload"
    assert saved["timestamp"] == snapshot["timestamp"]


def test_event_cache_contains_contract_and_keeps_event_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(event_ban_live, "CACHE_FILE", tmp_path / "event_cache.json")
    monkeypatch.setattr(
        event_ban_live,
        "_fetch_jin10_calendar",
        lambda: [{"title": "CPI", "time": "2026-09-02 12:00:00", "importance": "3"}],
    )

    assert event_ban_live.refresh_event_cache() is True
    saved = json.loads((tmp_path / "event_cache.json").read_text(encoding="utf-8"))

    assert saved["count"] == 1
    assert saved["events"][0]["title"] == "CPI"
    assert saved["_source_contract"]["source_id"] == "event_ban_live"
    assert saved["_source_contract"]["status"] == "live"
