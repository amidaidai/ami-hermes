from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

import importlib.util
watch_path = ROOT / "scripts" / "行情守望.py"
spec = importlib.util.spec_from_file_location("watch_monitor", watch_path)
watch_monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch_monitor)

from backtest_runner import BTConfig, run_backtest, validate_trade_consistency, sanitize_setup
import trading_system


def test_xau_constitution_volatility_does_not_use_source_spread(monkeypatch):
    captured = {}
    def fake_check_constitution(**kwargs):
        captured.update(kwargs)
        return {"allowed": True, "risk_tier": "常规", "max_risk_usd": kwargs.get("risk_usd", 3.0), "violations": []}
    monkeypatch.setattr(watch_monitor, "check_risk_constitution", fake_check_constitution, raising=False)
    result = watch_monitor.apply_risk_constitution(
        symbol="XAUUSD",
        gate={"allowed": True, "tier": "常规", "max_risk_usd": 3.0, "reasons": ["ok"]},
        snapshot={"price_spread_pct": 0.55, "extra": {}},
        state={},
    )
    assert result["allowed"] is True
    assert captured["volatility_24h_pct"] == 0.0


def test_xau_constitution_volatility_normalizes_percent_to_fraction(monkeypatch):
    captured = {}
    monkeypatch.setattr(watch_monitor, "check_risk_constitution", lambda **kw: captured.update(kw) or {"allowed": True, "risk_tier": "常规", "max_risk_usd": 3.0, "violations": []}, raising=False)
    watch_monitor.apply_risk_constitution(
        symbol="XAUUSD",
        gate={"allowed": True, "tier": "常规", "max_risk_usd": 3.0, "reasons": []},
        snapshot={"price_spread_pct": 0.55, "extra": {"volatility_24h_pct": 1.25}},
        state={},
    )
    assert abs(captured["volatility_24h_pct"] - 0.0125) < 1e-9


def test_expired_active_levels_are_marked_before_processing():
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    raw = {"symbols": {"BTCUSDT": {"updated": datetime.now(timezone.utc).isoformat(), "levels": [
        {"name": "old", "level": 100.0, "status": "active", "valid_until": past},
        {"name": "new", "level": 101.0, "status": "active", "valid_until": future},
        {"name": "done", "level": 102.0, "status": "invalidated", "valid_until": past},
    ]}}}
    changed = watch_monitor.expire_stale_levels(raw)
    levels = raw["symbols"]["BTCUSDT"]["levels"]
    assert changed is True
    assert levels[0]["status"] == "expired"
    assert "status_time" in levels[0]
    assert levels[1]["status"] == "active"
    assert levels[2]["status"] == "invalidated"


def test_xau_quality_separates_spot_consensus_from_yahoo_basis():
    valid = [
        {"source": "gold-api.com现货", "price": 4268.5},
        {"source": "金十Quote", "price": 4266.13},
        {"source": "Yahoo代理 GC=F", "price": 4287.5},
        {"source": "Yahoo代理 MGC=F", "price": 4287.0},
    ]
    q, conf, label, metrics = trading_system.non_crypto_quality(valid)
    assert q == "A-"
    assert conf == 88
    assert "现货双源" in label
    assert "Yahoo" not in label or "basis" in label
    assert metrics["spot_spread_pct"] < 0.1
    assert metrics["futures_basis_pct"] > 0.3


def test_backtest_rejects_extreme_rr_and_inconsistent_trade():
    bad = {"entry": 100.0, "stop": 99.99, "targets": [120.0], "direction": "long", "model": "x", "confidence": 80, "rr_ratio": 2000}
    assert sanitize_setup(bad, atr=1.0, price=100.0) is None

    class T: pass
    t = T(); t.direction="short"; t.entry_price=100.0; t.exit_price=90.0; t.result="loss"; t.pnl_r=-1.0; t.model="x"; t.entry_time="now"
    try:
        validate_trade_consistency(t)
    except ValueError as e:
        assert "inconsistent" in str(e).lower() or "不一致" in str(e)
    else:
        raise AssertionError("expected inconsistent trade to raise")
