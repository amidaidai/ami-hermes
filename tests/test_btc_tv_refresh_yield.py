"""btc_tv_refresh 让路语义回归：**合同内让路 = 0，超限/连续让路 = 1**。

修前的规则混用了两个阈值（触发 12 分 / 合同 30 分）：只要缓存越过 12 分触发线，
任何让路（交互式分析进行中、共享图表锁被占、采集子进程早退）都被记成 cron 失败。
实测 2026-09-16 12:07 / 13:27 / 16:07 三轮失败时缓存年龄 1054s / 1056s / 1053s
（≈17.5 分，**远在 30 分合同内**）—— 全是假失败，且会把 preflight 的 Cron策略项拖红。

新规则（本文件钉住）：
- age ≤ 24 分（0.8×合同）且连续让路 < 3 轮 → exit 0（可见让路，streak +1）
- age > 24 分 或 连续让路 ≥ 3 轮 或 age 未知 → exit 1（真失败，绝不把过期记成 ok）
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import btc_tv_refresh as b  # noqa: E402
import keylevels_collect as kc  # noqa: E402
import tv_data_bridge as tb  # noqa: E402

CONTRACT = 30.0


@pytest.fixture(autouse=True)
def _isolate_yield_state(monkeypatch, tmp_path):
    """让路计数状态必须隔离到 tmp，绝不写进仓库 data/。"""
    monkeypatch.setattr(b, "YIELD_STATE", tmp_path / "yield_state.json")
    monkeypatch.setattr(b, "COLLECT_DIAGNOSTIC", tmp_path / "collect_diag.json")


def _contract(age_min, usable=None):
    if age_min is None:
        return {"usable": False, "reason": "TV五周期缓存缺失"}
    return {"usable": age_min <= CONTRACT, "age_seconds": age_min * 60.0,
            "reason": f"TV五周期 age={age_min * 60:.0f}s"}


def _setup(monkeypatch, *, five_usable, source_fresh, lease_active=False, contract_age=17.5):
    monkeypatch.setattr(b, "btc_five_tf_status",
                        lambda: {"usable": five_usable, "reason": "x"})
    monkeypatch.setattr(b, "source_snapshot_status",
                        lambda: {"fresh": source_fresh, "reason": "y"})
    monkeypatch.setattr(b, "five_tf_contract_status", lambda: _contract(contract_age))
    monkeypatch.setattr(tb, "analysis_lease_status",
                        lambda: {"active": lease_active, "remaining_seconds": 0})


def _busy_lock(monkeypatch):
    def _busy(timeout=30.0):
        raise TimeoutError("TradingView shared chart lock timeout")
    monkeypatch.setattr(tb, "tv_collection_lock", _busy)


def _free_lock(monkeypatch):
    class _CM:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(tb, "tv_collection_lock", lambda timeout=30.0: _CM())


# ── 无动作 / 正常路径 ────────────────────────────────────────────────────

def test_nothing_to_do_returns_zero_without_probing(monkeypatch):
    _setup(monkeypatch, five_usable=True, source_fresh=True)
    monkeypatch.setattr(tb, "tv_collection_lock",
                        lambda timeout=30.0: (_ for _ in ()).throw(AssertionError("无需探测")))
    assert b.main() == 0


def test_lock_available_proceeds_to_collector(monkeypatch):
    """锁可用时必须继续走到采集（别把正常路径也拦掉）。"""
    called = {"n": 0}
    _setup(monkeypatch, five_usable=False, source_fresh=True)
    _free_lock(monkeypatch)
    monkeypatch.setattr(b, "refresh_source_snapshot", lambda: True)

    def _ok():
        called["n"] += 1
        return (0, "publish:success")

    monkeypatch.setattr(b, "run_collector", _ok)
    assert b.main() == 0
    assert called["n"] == 1


# ── 合同内让路 = 0（修前是 1） ──────────────────────────────────────────

def test_busy_chart_lock_within_contract_yields_zero(monkeypatch, capsys):
    _setup(monkeypatch, five_usable=False, source_fresh=False, contract_age=17.5)
    _busy_lock(monkeypatch)
    rc = b.main()
    out = capsys.readouterr().out
    assert rc == 0, "抢不到锁且缓存仍在合同内必须是让路(0)，否则每轮都生成 incident"
    assert "让路" in out and "共享图表锁" in out
    assert "不计失败" in out and "17.5分" in out


def test_lease_active_within_contract_yields_zero(monkeypatch, capsys):
    """交互式分析进行中 + 缓存越过触发线但仍在合同内 → 让路（修前记成失败）。"""
    _setup(monkeypatch, five_usable=False, source_fresh=False, lease_active=True,
           contract_age=17.6)
    rc = b.main()
    out = capsys.readouterr().out
    assert rc == 0, "让路时缓存仍新鲜却被记成失败 = 假失败（2026-09-16 13:27 实测）"
    assert "交互式分析" in out and "不计失败" in out


def test_lease_active_fresh_data_is_plain_yield(monkeypatch, capsys):
    _setup(monkeypatch, five_usable=True, source_fresh=True, lease_active=True)
    assert b.main() == 0
    assert "交互式分析" in capsys.readouterr().out


def test_collector_incomplete_within_contract_yields_zero(monkeypatch, capsys):
    """采集没跑完（rc!=0）但缓存仍在合同内 → 让路，不是失败（16:07 实测形态）。"""
    _setup(monkeypatch, five_usable=False, source_fresh=True, contract_age=17.5)
    _free_lock(monkeypatch)
    monkeypatch.setattr(b, "run_collector", lambda: (1, "timeframe:240:start(running)"))
    rc = b.main()
    err = capsys.readouterr().err
    assert rc == 0, "合同内的未完成刷新不该记成 cron 失败"
    assert "timeframe:240:start" in err, "失败/让路消息必须带最后采集阶段，便于一行定位"


def test_collector_defer_exit_code_is_yield(monkeypatch, capsys):
    _setup(monkeypatch, five_usable=False, source_fresh=True, contract_age=17.5)
    _free_lock(monkeypatch)
    monkeypatch.setattr(b, "run_collector", lambda: (b._DEFER_EXIT, "cli:lock_wait(running)"))
    assert b.main() == 0
    assert "采集子进程让路" in capsys.readouterr().out


# ── 越过让路上限 / 连续让路 = 1（绝不把过期记成 ok） ────────────────────

def test_busy_chart_lock_over_yield_limit_fails(monkeypatch, capsys):
    _setup(monkeypatch, five_usable=False, source_fresh=False, contract_age=26.0)
    _busy_lock(monkeypatch)
    rc = b.main()
    err = capsys.readouterr().err
    assert rc == 1, "越过让路上限(24分)必须计失败"
    assert "超让路上限" in err


def test_unknown_age_fails_closed(monkeypatch, capsys):
    _setup(monkeypatch, five_usable=False, source_fresh=False, contract_age=None)
    _busy_lock(monkeypatch)
    assert b.main() == 1, "读不到年龄就不能说新鲜（fail-closed）"
    assert "未知" in capsys.readouterr().err


def test_consecutive_yields_escalate_to_failure(monkeypatch, capsys):
    """连续让路达 3 轮 → 真失败（文件级状态，跨轮累计）。"""
    _setup(monkeypatch, five_usable=False, source_fresh=False, contract_age=17.5)
    _busy_lock(monkeypatch)
    assert b.main() == 0        # 1
    assert b.main() == 0        # 2
    rc = b.main()               # 3 → 升级
    err = capsys.readouterr().err
    assert rc == 1, "连续 3 轮让路必须升级为失败"
    assert "连续让路 3 轮" in err


def test_successful_round_resets_yield_streak(monkeypatch):
    _setup(monkeypatch, five_usable=False, source_fresh=False, contract_age=17.5)
    _busy_lock(monkeypatch)
    assert b.main() == 0
    assert b.main() == 0
    # 中间成功刷一轮 → streak 清零
    _setup(monkeypatch, five_usable=True, source_fresh=True)
    assert b.main() == 0
    _setup(monkeypatch, five_usable=False, source_fresh=False, contract_age=17.5)
    _busy_lock(monkeypatch)
    assert b.main() == 0, "成功一轮后让路计数必须清零，不能累计成假失败"


# ── 阈值/退出码契约 ─────────────────────────────────────────────────────

def test_let_up_limit_is_eighty_percent_of_contract():
    assert b.CONTRACT_MAX_AGE_MIN == 30.0
    assert b.YIELD_MAX_AGE_MIN == 0.8 * b.CONTRACT_MAX_AGE_MIN
    assert b.YIELD_STREAK_LIMIT == 3


def test_defer_exit_code_matches_collector_contract():
    """让路退出码跨进程共享，两边必须一致（否则 7 会被读成失败）。"""
    assert b._DEFER_EXIT == kc.DEFER_EXIT_CODE


def test_keylevels_contract_constant_matches_five_tf_contract():
    import tv_five_tf_contract as c
    import inspect
    sig = inspect.signature(c.load_five_tf_snapshot)
    assert sig.parameters["max_age_minutes"].default == kc.CONTRACT_MAX_AGE_MIN


def test_collect_status_ignores_trigger_threshold(monkeypatch):
    """触发口径（12 分）与合同口径（30 分）必须是两次独立取数，不能互相顶替。"""
    seen = []
    import tv_five_tf_contract as c

    def _fake(symbol, *, data_dir=None, max_age_minutes=30.0, now=None):
        seen.append(max_age_minutes)
        return {"usable": False}

    monkeypatch.setattr(c, "load_five_tf_snapshot", _fake)
    b.btc_five_tf_status()
    b.five_tf_contract_status()
    assert seen == [12.0, 30.0], seen
