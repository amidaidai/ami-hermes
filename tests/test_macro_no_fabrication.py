"""Macro overview must not fabricate VIX/SPX defaults when the fetch fails."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import multi_source_collector as M


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "CACHE", tmp_path / "api_cache.json")
    monkeypatch.setattr(M, "SOURCE_STATE", tmp_path / "source_circuit_state.json")


def test_failed_fetch_does_not_invent_vix_or_sentiment(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr(M, "_fetch", boom)
    out = M.macro_overview()
    # 旧实现固定返回「中性 | VIX 20 | SPX +0.0%」，看起来像采到了。
    assert "vix_level" not in out
    assert "sentiment" not in out
    assert out.get("_source_status") in {"unavailable", "stale_cache", "quota_cooldown"}


def test_live_fetch_keeps_real_values_and_stamps_time(monkeypatch):
    payloads = {
        "^VIX": [{"price": 31.5, "changesPercentage": 4.0, "change": 1.2}],
        "^GSPC": [{"price": 5000.0, "changesPercentage": -1.5, "change": -75.0}],
    }
    def fake_fetch(url, *args, **kwargs):
        for key, value in payloads.items():
            if key in url:
                return value
        raise RuntimeError("no data")
    monkeypatch.setattr(M, "_fetch", fake_fetch)
    out = M.macro_overview()
    assert out["vix_level"] == 31.5
    assert out["sentiment"] == "恐慌 (Risk-off)"
    assert out["spx"]["change_pct"] == -1.5
    assert out.get("timestamp")
    assert out.get("_source_status") == "live"


def test_missing_vix_is_not_reported_as_neutral(monkeypatch):
    def only_spx(url, *args, **kwargs):
        if "^GSPC" in url:
            return [{"price": 5000.0, "changesPercentage": 0.0, "change": 0.0}]
        raise RuntimeError("no data")
    monkeypatch.setattr(M, "_fetch", only_spx)
    out = M.macro_overview()
    assert "vix_level" not in out
    # SPX 真取到了但没有任何风险信号 → 中性是真实判定，允许保留。
    assert out.get("sentiment") == "中性"
