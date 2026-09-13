"""宏观快照必须走 FMP 现行 /stable 端点，并按符号如实上报可用性。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import multi_source_collector as M


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "CACHE", tmp_path / "api_cache.json")
    monkeypatch.setattr(M, "SOURCE_STATE", tmp_path / "source_circuit_state.json")


def _quote(price, chg, key="changePercentage"):
    return [{"symbol": "X", "price": price, key: chg, "change": 0}]


def test_uses_stable_endpoint_not_retired_v3(monkeypatch):
    """旧实现打 /api/v3/quote/{sym}（实测 403），宏观整步恒 unavailable。"""
    urls = []
    def fake_fetch(url, *args, **kwargs):
        urls.append(url)
        return _quote(15.84, -11.2)
    monkeypatch.setattr(M, "_fetch", fake_fetch)
    M.macro_overview()
    assert urls, "macro_overview 必须真的发请求"
    assert all("/stable/quote?symbol=" in url for url in urls), urls
    assert not any("/api/v3/quote/" in url for url in urls), urls


def test_change_pct_reads_stable_field_name(monkeypatch):
    """/stable 返回 changePercentage（无 s）；只读旧名会静默变成 0.0%。"""
    def fake_fetch(url, *args, **kwargs):
        if "%5EVIX" in url:
            return _quote(15.84, -11.21)
        if "%5EGSPC" in url:
            return _quote(7656.98, 0.86)
        raise OSError("HTTP Error 402")
    monkeypatch.setattr(M, "_fetch", fake_fetch)
    out = M.macro_overview()
    assert out["vix_level"] == 15.84
    assert out["spx"]["change_pct"] == 0.86


def test_legacy_field_name_still_supported():
    assert M._fmp_change_pct({"changesPercentage": 1.5}) == 1.5
    assert M._fmp_change_pct({"changePercentage": 2.5}) == 2.5
    assert M._fmp_change_pct({}) == 0


def test_partial_plan_restriction_is_visible_and_not_faked(monkeypatch):
    """本套餐 ^TNX/DX-Y.NYB/GC=F 返回 402：要报告，不能用默认值补齐。"""
    def fake_fetch(url, *args, **kwargs):
        if "%5EVIX" in url or "%5EGSPC" in url:
            return _quote(15.84 if "%5EVIX" in url else 7656.98,
                          -11.2 if "%5EVIX" in url else 0.86)
        raise OSError("HTTP Error 402: Payment Required")
    monkeypatch.setattr(M, "_fetch", fake_fetch)
    out = M.macro_overview()
    assert "us10y" not in out and "dxy" not in out
    assert set(out["unavailable_fields"]) == {"us10y", "dxy", "gold_fut"}
    assert out["_source_status"] == "live", out.get("_source_status")


def test_all_symbols_failing_stays_unavailable(monkeypatch):
    def boom(url, *args, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr(M, "_fetch", boom)
    out = M.macro_overview()
    assert "vix_level" not in out and "sentiment" not in out
    assert out.get("_source_status") == "unavailable"


# ── 空结果不得被洗成 live ──────────────────────────────────────────────────

def test_empty_result_is_never_cached_as_live(monkeypatch):
    """实测：失败的 fetch() 返回 {} 会被 _cached 当成成功写盘，随后 5 分钟内
    以 status='cache'（属于 LIVE_STATES）返回，把宏观洗成 live。"""
    calls = {"n": 0}
    def empty(url, *args, **kwargs):
        calls["n"] += 1
        raise OSError("HTTP Error 402")
    monkeypatch.setattr(M, "_fetch", empty)
    first = M.macro_overview()
    assert first.get("_source_status") == "unavailable"
    assert calls["n"] > 0
    before = calls["n"]
    second = M.macro_overview()
    assert second.get("_source_status") == "unavailable"
    assert calls["n"] > before, "空结果不该被缓存，必须重新尝试"


def test_non_empty_cache_is_still_reused(monkeypatch):
    monkeypatch.setattr(M, "_CACHED_TEST_TTL", 300, raising=False)
    calls = {"n": 0}
    def good(url, *args, **kwargs):
        calls["n"] += 1
        return _quote(15.84, -11.21)
    monkeypatch.setattr(M, "_fetch", good)
    first = M.macro_overview()
    assert first.get("_source_status") == "live"
    after_first = calls["n"]
    second = M.macro_overview()
    assert second.get("_source_status") == "cache"
    assert calls["n"] == after_first, "非空缓存应被复用"
