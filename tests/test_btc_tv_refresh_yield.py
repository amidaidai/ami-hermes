"""btc_tv_refresh 的「抢锁失败 = 让路，不是失败」回归。

背景：采集子进程自己要抢 tv_data_bridge.tv_collection_lock(timeout=180)。
XAU 同步持锁时会空等两轮后以「未发布新快照」退出 → 每轮记成 cron 失败 incident
（实测 2026-09-15 11:08 / 11:28 / 11:49 连续三条）。修法：先探测锁，抢不到就 exit 0。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import btc_tv_refresh as b  # noqa: E402
import tv_data_bridge as tb  # noqa: E402


def _setup(monkeypatch, five_usable, source_fresh, lease_active=False):
    monkeypatch.setattr(b, "btc_five_tf_status", lambda: {"usable": five_usable, "reason": "x"})
    monkeypatch.setattr(b, "source_snapshot_status", lambda: {"fresh": source_fresh, "reason": "y"})
    monkeypatch.setattr(tb, "analysis_lease_status", lambda: {"active": lease_active, "remaining_seconds": 0})
    monkeypatch.setattr(b, "run_collector", lambda: (_ for _ in ()).throw(AssertionError("不该跑到采集")))


def test_busy_chart_lock_yields_exit_zero(monkeypatch, capsys):
    _setup(monkeypatch, five_usable=False, source_fresh=False)

    def _busy(timeout=30.0):
        raise TimeoutError("TradingView shared chart lock timeout")

    monkeypatch.setattr(tb, "tv_collection_lock", _busy)
    rc = b.main()
    out = capsys.readouterr().out
    assert rc == 0, "抢不到锁必须是让路(0)，不能是失败(1) → 否则每轮都生成 incident"
    assert "让路" in out and "共享图表锁" in out


def test_lock_available_proceeds(monkeypatch):
    """锁可用时必须继续走到采集（别把正常路径也拦掉）。"""
    called = {"n": 0}
    _setup(monkeypatch, five_usable=False, source_fresh=True)

    def _ok_collect():
        called["n"] += 1
        return 0

    monkeypatch.setattr(b, "run_collector", _ok_collect)
    monkeypatch.setattr(b, "refresh_source_snapshot", lambda: True)

    class _CM:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(tb, "tv_collection_lock", lambda timeout=30.0: _CM())
    assert b.main() == 0
    assert called["n"] == 1


def test_nothing_to_do_returns_zero_without_probing(monkeypatch):
    _setup(monkeypatch, five_usable=True, source_fresh=True)
    monkeypatch.setattr(tb, "tv_collection_lock",
                        lambda timeout=30.0: (_ for _ in ()).throw(AssertionError("无需探测")))
    assert b.main() == 0


def test_lease_active_still_defers(monkeypatch, capsys):
    _setup(monkeypatch, five_usable=True, source_fresh=True, lease_active=True)
    assert b.main() == 0
    assert "交互式分析" in capsys.readouterr().out
