from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from chart_evidence import build_chart_evidence, normalize_timeframe
from decision_loop import resolve_final_verdict


def _main():
    return {
        "grade": "A多", "direction": "多", "data_grade": "A",
        "snapshot_age_sec": 5, "location_valid": True,
        "trigger_confirmed": True, "bar_closed": True,
        "entry": 100.0, "stop": 98.0, "target": 105.0,
        "risk_label": "风控", "mcp_entry_valid_code": 3,
    }


def _risk():
    return {"allowed": True, "risk_usd": 1.0}


def _evidence(status="verified"):
    return {
        "status": status,
        "identity_errors": [],
    }


def test_timeframe_alias_is_canonicalized():
    assert normalize_timeframe("15m") == "15"
    assert normalize_timeframe("1h") == "60"


def test_chart_evidence_marks_partial_when_ict_objects_are_not_readable():
    evidence = build_chart_evidence(
        state={
            "symbol": "BINANCE:BTCUSDT.P", "resolution": "15",
            "studies": [
                {"name": "SVP+ICT+VWAP+CVD"},
                {"name": "Volume"},
                {"name": "Volume Aggregated Spot & Futures"},
            ],
        },
        quote=100,
        indicators={"mcp_struct_pack": "123"},
        lines=[], boxes=[], labels=[],
        expected_symbol="BINANCE:BTCUSDT.P", expected_timeframe="15m",
    )
    assert evidence["status"] == "partial"


def test_quote_payload_populates_price_bar_and_zone_is_ict_evidence():
    evidence = build_chart_evidence(
        state={
            "symbol": "BINANCE:BTCUSDT.P",
            "resolution": "15",
            "studies": [
                {"name": "SVP+ICT+VWAP+CVD"},
                {"name": "Volume"},
                {"name": "Volume Aggregated Spot & Futures"},
            ],
        },
        quote={"last": 78782.4, "open": 78623.5, "high": 78832, "low": 78470.6, "close": 78782.4},
        indicators={"mcp_struct_pack": 121},
        lines=[{"price": 78832.9}],
        boxes=[{"high": 77805.5, "low": 77464.6}],
        labels=[],
        expected_symbol="BINANCE:BTCUSDT.P",
        expected_timeframe="15m",
    )
    assert evidence["status"] == "verified"
    assert evidence["price_context"]["open"] == 78623.5
    assert evidence["price_context"]["high"] == 78832.0
    assert len(evidence["ict"]["zones"]) == 1
    assert evidence["ict"]["struct_pack_present"] is True


def test_chart_identity_mismatch_is_hard_block():
    verdict = resolve_final_verdict(
        "BTCUSDT", _main(), {"asset_is_crypto": False},
        risk=_risk(), chart_evidence={"status": "identity_mismatch", "identity_errors": ["timeframe_mismatch"]},
    )
    assert verdict.state == "NO-GO"
    assert "chart_identity" in verdict.blockers
    assert verdict.executable is False


def test_partial_chart_can_never_be_go_a():
    verdict = resolve_final_verdict(
        "BTCUSDT", _main(), {"asset_is_crypto": False},
        risk=_risk(), chart_evidence=_evidence("partial"),
    )
    assert verdict.state == "WAIT"
    assert verdict.executable is False
    assert verdict.chart_evidence_status == "partial"
