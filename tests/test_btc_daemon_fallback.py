from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import btc_daemon as bd


def test_btc_daemon_price_falls_back_to_binance_vision(monkeypatch):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "data-api.binance.vision" in url:
            return {"price": "64000.5"}
        return None

    monkeypatch.setattr(bd, "fetch", fake_fetch)
    assert bd.get_price() == 64000.5
    assert any("api.binance.com" in url for url in calls)
    assert any("data-api.binance.vision" in url for url in calls)


def test_btc_daemon_klines_fall_back_to_binance_vision(monkeypatch):
    payload = [[1, "1", "2", "0.5", "1.5", "10"]]
    monkeypatch.setattr(bd, "fetch", lambda url: payload if "data-api.binance.vision" in url else None)
    bars = bd.get_klines(1)
    assert bars == [{"t": 1, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 10.0}]
