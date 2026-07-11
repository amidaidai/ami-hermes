from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import qlib_factors as qf


def test_fetch_klines_falls_back_across_binance_hosts(monkeypatch):
    calls = []
    payload = [[0, "1", "2", "0.5", "1.5", "10"]] * 60

    def fake_fetch(url, proxy=None):
        calls.append((url, proxy))
        if "data-api.binance.vision" in url:
            return payload
        raise OSError("blocked")

    monkeypatch.setattr(qf, "_fetch_json_url", fake_fetch)
    result = qf.fetch_klines("BTCUSDT", "1h", 200)

    assert result == payload
    assert any("fapi.binance.com/fapi/v1/klines" in url for url, _ in calls)
    assert any("api.binance.com/api/v3/klines" in url for url, _ in calls)
    assert any("data-api.binance.vision/api/v3/klines" in url for url, _ in calls)


def test_fetch_klines_rejects_non_list_payload(monkeypatch):
    monkeypatch.setattr(qf, "_fetch_json_url", lambda url, proxy=None: {"code": -1})
    assert qf.fetch_klines() == []
