from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import multi_source_collector as m


def test_stock_gather_uses_all_market_specific_providers(monkeypatch):
    monkeypatch.setattr(m, "av_quote", lambda s: {"price": 1, "source": "AV"})
    monkeypatch.setattr(m, "td_quote", lambda s: {"price": 1, "source": "TD"})
    monkeypatch.setattr(m, "td_technical", lambda s: {"rsi": 50})
    monkeypatch.setattr(m, "fmp_quote", lambda s: {"price": 1, "source": "FMP"})
    monkeypatch.setattr(m, "massive_aggs", lambda s, asset: {"price": 1, "source": "Massive"})
    monkeypatch.setattr(m, "tushare_daily", lambda s: {})
    monkeypatch.setattr(m, "macro_overview", lambda: {"sentiment": "neutral"})

    result = m.gather_all("stock", "AAPL")
    assert {"av", "td", "td_tech", "fmp", "massive", "macro"} <= set(result)
    assert "tushare" not in result


def test_forex_and_futures_use_asset_specific_sources(monkeypatch):
    monkeypatch.setattr(m, "fmp_forex", lambda s: {"price": 1.1})
    monkeypatch.setattr(m, "td_quote", lambda s: {"price": 1.1})
    monkeypatch.setattr(m, "td_technical", lambda s: {"rsi": 50})
    monkeypatch.setattr(m, "macro_overview", lambda: {"sentiment": "neutral"})
    monkeypatch.setattr(m, "massive_futures_snapshot", lambda s: {"price": 5000})

    assert {"fmp", "td", "td_tech", "macro"} <= set(m.gather_all("forex", "EURUSD"))
    assert {"massive", "macro"} <= set(m.gather_all("futures", "ES"))
