from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import liquidation_collector as lc


def test_all_api_failures_are_not_reported_as_normal_market():
    conclusion, data_ok = lc._overall_conclusion([
        {"symbol": "BTCUSDT", "status": "api_error"},
        {"symbol": "ETHUSDT", "status": "api_error"},
    ])
    assert data_ok is False
    assert "不能判断" in conclusion
    assert "市场常态" not in conclusion


def test_valid_normal_rows_keep_normal_market_conclusion():
    conclusion, data_ok = lc._overall_conclusion([
        {"symbol": "BTCUSDT", "squeeze": "正常", "verdict": "○常态"},
    ])
    assert data_ok is True
    assert "市场常态" in conclusion


def test_orion_snapshot_maps_live_oi_price_and_one_hour_deltas():
    row = {
        "symbol": "BTCUSDT",
        "price": 64100,
        "openInterest": 100000,
        "openInterestUsd": 6410000000,
        "tf1h": {"oiChange": -2.5, "changePercent": -1.2},
    }
    snap = lc._orion_current(row)
    assert snap == {
        "symbol": "BTCUSDT",
        "oi": 100000.0,
        "price": 64100.0,
        "oi_delta_pct": -2.5,
        "price_delta_pct": -1.2,
        "source": "Orion/Binance",
    }


def test_analyze_prefers_provider_deltas_over_old_snapshot():
    current = {
        "symbol": "BTCUSDT",
        "oi": 100,
        "price": 100,
        "oi_delta_pct": -3.0,
        "price_delta_pct": -1.5,
        "source": "Orion/Binance",
    }
    result = lc.analyze("BTCUSDT", current, {"oi": 1, "price": 1})
    assert result["squeeze"] == "多头爆仓"
    assert result["source"] == "Orion/Binance"
