"""xau_tv_sync 的「抢锁失败 = 让路」回归（与 btc_tv_refresh 同一约定）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import xau_tv_sync as x  # noqa: E402


def test_lock_timeout_with_usable_cache_yields_zero(monkeypatch, capsys):
    monkeypatch.setattr(x, "analysis_lease_defer_exit", lambda: None)
    monkeypatch.setattr(x, "published_xau_cache_usable", lambda: {"usable": True, "reason": "ok"})
    monkeypatch.setattr(x, "_audit_marker", lambda *a, **k: None)
    monkeypatch.setattr(x, "STAGED_OUT", ROOT / "data/.pytest_staged_missing.json")

    import tv_data_bridge as tb

    class _Busy:
        def __init__(self, timeout=30.0):
            raise TimeoutError("TradingView shared chart lock timeout")

    monkeypatch.setattr(tb, "tv_collection_lock", _Busy)
    rc = x.main()
    out = capsys.readouterr().out
    assert rc == 0, "缓存仍可用时，让路必须是 0（否则每 15 分钟刷一条 incident）"
    assert "让路" in out


def test_lock_timeout_with_stale_cache_surfaces(monkeypatch, capsys):
    """缓存已不可用 → 必须 exit 1：这种情况是真问题，调度器/看门狗要看得见。"""
    monkeypatch.setattr(x, "analysis_lease_defer_exit", lambda: None)
    monkeypatch.setattr(x, "published_xau_cache_usable", lambda: {"usable": False, "reason": "过期"})
    monkeypatch.setattr(x, "_audit_marker", lambda *a, **k: None)
    monkeypatch.setattr(x, "STAGED_OUT", ROOT / "data/.pytest_staged_missing.json")

    import tv_data_bridge as tb

    class _Busy:
        def __init__(self, timeout=30.0):
            raise TimeoutError("busy")

    monkeypatch.setattr(tb, "tv_collection_lock", _Busy)
    assert x.main() == 1
    assert "不可用" in capsys.readouterr().out
