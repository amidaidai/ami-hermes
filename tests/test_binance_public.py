from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import binance_public as bp


class _Response:
    def __init__(self, payload):
        import json
        self._raw = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._raw


def test_spot_fetch_falls_back_to_vision(monkeypatch):
    calls = []

    class _Opener:
        def open(self, req, timeout):
            calls.append(req.full_url)
            if "api.binance.com" in req.full_url:
                raise OSError("tls")
            return _Response({"price": "64000"})

    monkeypatch.setattr(bp, "_opener", lambda: _Opener())
    assert bp.fetch_spot("/api/v3/ticker/price", {"symbol": "BTCUSDT"}) == {"price": "64000"}
    assert calls == [
        "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
        "https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT",
    ]


def test_orion_ticker_selects_exact_symbol(monkeypatch):
    monkeypatch.setattr(
        bp,
        "fetch_url",
        lambda *_args, **_kwargs: {"tickers": [{"symbol": "ETHUSDT"}, {"symbol": "BTCUSDT", "price": 64000}]},
    )
    assert bp.fetch_orion_ticker("btcusdt")["price"] == 64000


def test_orion_derivatives_snapshot_is_explicitly_secondary_quality(monkeypatch):
    monkeypatch.setattr(
        bp,
        "fetch_orion_ticker",
        lambda *_args, **_kwargs: {
            "symbol": "BTCUSDT",
            "price": 64000,
            "indexPrice": 64010,
            "markPrice": 64005,
            "openInterest": 100000,
            "fundingRate": 0.0001,
            "tf1h": {"oiChange": 1.2, "changePercent": 0.4},
        },
    )
    snap = bp.orion_derivatives_snapshot("BTCUSDT")
    assert snap["ok"] is True
    assert snap["quality"] == "B"
    assert snap["source"] == "Orion/Binance Futures"
    assert snap["oi_change_1h_pct"] == 1.2
