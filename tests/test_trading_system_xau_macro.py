from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trading_system


def test_xau_macro_context_refreshes_stale_cache_without_relabeling_it(monkeypatch, tmp_path):
    cache = tmp_path / "xau_macro_context.json"
    cache.write_text(
        json.dumps({"time": (datetime.now().astimezone() - timedelta(days=2)).isoformat(), "prices": {"DXY": {"price": 1}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(trading_system, "XAU_MACRO_FILE", cache)
    monkeypatch.setattr(
        "macro_filter.fetch_macro_snapshot",
        lambda: {
            "timestamp": datetime.now().astimezone().isoformat(),
            "dxy": 100.1,
            "vix": 18.0,
            "spx": 6500.0,
            "us10y": 4.1,
            "gold": 4500.0,
            "silver": 60.0,
            "risk_sentiment": "neutral",
            "risk_label": "中性",
            "source_status": "live",
        },
    )

    result = trading_system._xau_macro_context()

    assert result["prices"]["DXY"]["price"] == 100.1
    assert result["source_status"] == "live"
    assert json.loads(cache.read_text(encoding="utf-8"))["prices"]["GOLD_FUT"]["price"] == 4500.0


def test_xau_macro_context_keeps_stale_cache_visible_when_refresh_fails(monkeypatch, tmp_path):
    stale = {"time": (datetime.now().astimezone() - timedelta(days=2)).isoformat(), "quality": "C", "prices": {}}
    cache = tmp_path / "xau_macro_context.json"
    cache.write_text(json.dumps(stale), encoding="utf-8")
    monkeypatch.setattr(trading_system, "XAU_MACRO_FILE", cache)
    monkeypatch.setattr("macro_filter.fetch_macro_snapshot", lambda: {})

    assert trading_system._xau_macro_context() == stale
    assert json.loads(cache.read_text(encoding="utf-8")) == stale