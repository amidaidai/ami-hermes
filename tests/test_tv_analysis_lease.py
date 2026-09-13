"""交互式分析租约 + 后台让路 + 图表归属棘轮（20260911 防抢图）。

背景：共用同一张 TradingView 图表。`tv_collection_lock` 只序列化后台任务彼此；
对话里的分析是直接读行动格 + 截图（不持锁），后台续航照样按 cron 切周期 ——
实测 2026-09-11 14:07 读 5m 被 btc_tv_refresh 连抢两次，行动格整张读成空表。

被测契约：
1. 租约能声明/查询/释放，过期与损坏文件一律视为「无分析」；
2. TTL 有上限，脚本崩溃不会把后台续航永久锁死；
3. 后台切图任务（BTC 续航 / XAU 同步）遇租约让路，且让路**不计失败**；
4. 图表归属棘轮：恢复失败后不把残留周期当成「用户图表」。
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

TZ = timezone(timedelta(hours=8))


def bridge(monkeypatch, tmp_path):
    import tv_data_bridge as b

    monkeypatch.setattr(b, "ANALYSIS_LEASE", tmp_path / "tv_analysis_lease.json")
    monkeypatch.setattr(b, "CHART_OWNER", tmp_path / "tv_chart_owner.json")
    return b


def test_analysis_lease_lifecycle(monkeypatch, tmp_path):
    b = bridge(monkeypatch, tmp_path)
    assert b.analysis_lease_status()["active"] is False
    assert b.analysis_in_progress() is False

    b.begin_analysis_lease(3.0, note="unit", symbol="BINANCE:BTCUSDT.P")
    status = b.analysis_lease_status()
    assert status["active"] is True
    assert status["symbol"] == "BINANCE:BTCUSDT.P"
    assert status["note"] == "unit"
    assert 0 < status["remaining_seconds"] <= 180
    assert b.analysis_in_progress() is True

    b.end_analysis_lease()
    assert b.analysis_lease_status()["active"] is False


def test_end_analysis_lease_is_idempotent(monkeypatch, tmp_path):
    b = bridge(monkeypatch, tmp_path)
    b.end_analysis_lease()
    b.end_analysis_lease()
    assert b.analysis_lease_status()["active"] is False


def test_expired_lease_is_not_active(monkeypatch, tmp_path):
    b = bridge(monkeypatch, tmp_path)
    b.begin_analysis_lease(10.0)
    path = tmp_path / "tv_analysis_lease.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["expires_at"] = (datetime.now(TZ) - timedelta(minutes=1)).isoformat(timespec="seconds")
    path.write_text(json.dumps(raw), encoding="utf-8")

    status = b.analysis_lease_status()
    assert status["active"] is False
    assert "过期" in status["reason"]
    assert b.analysis_in_progress() is False


def test_lease_ttl_is_capped(monkeypatch, tmp_path):
    b = bridge(monkeypatch, tmp_path)
    payload = b.begin_analysis_lease(999.0)
    assert payload["minutes"] == b.ANALYSIS_LEASE_MAX_MINUTES
    assert payload["minutes"] >= 0.5


def test_corrupt_lease_file_never_blocks_background_jobs(monkeypatch, tmp_path):
    """损坏/半截文件必须当成「无租约」——不能让一个坏文件永久冻住续航。"""
    b = bridge(monkeypatch, tmp_path)
    (tmp_path / "tv_analysis_lease.json").write_text("{not json", encoding="utf-8")
    assert b.analysis_lease_status()["active"] is False
    (tmp_path / "tv_analysis_lease.json").write_text('{"active": true}', encoding="utf-8")
    assert b.analysis_lease_status()["active"] is False


def test_chart_owner_ratchet_breaks_after_failed_restore(monkeypatch, tmp_path):
    b = bridge(monkeypatch, tmp_path)
    # 进入时用户在看 BTC 15m → 记为归还目标
    target = b.chart_owner_resolve_restore("OANDA:XAUUSD", "BINANCE:BTCUSDT.P", "15")
    assert target == {"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"}

    # 上一轮没还干净：图停在 XAU，但「待归还」仍是 BTC → 用记录修回来，不认残留
    target = b.chart_owner_resolve_restore("OANDA:XAUUSD", "OANDA:XAUUSD", "5")
    assert target["symbol"] == "BINANCE:BTCUSDT.P"
    assert target["resolution"] == "15"
    state = json.loads((tmp_path / "tv_chart_owner.json").read_text(encoding="utf-8"))
    assert state["ratchet_break_from"] == "OANDA:XAUUSD"

    # 真还回去了 → 清掉待归还
    b.chart_owner_mark_restored()
    state = json.loads((tmp_path / "tv_chart_owner.json").read_text(encoding="utf-8"))
    assert "pending_restore" not in state
    assert state["restored_at"]

    # pending 已清，但图又停在 XAU：必须用记住的 user_symbol 修回来
    target = b.chart_owner_resolve_restore("OANDA:XAUUSD", "OANDA:XAUUSD", "5")
    assert target["symbol"] == "BINANCE:BTCUSDT.P"
    assert target["resolution"] == "15"


def test_user_on_collector_symbol_keeps_its_own_chart(monkeypatch, tmp_path):
    """用户真的在看采集品种时，不要自作聪明把图切走。"""
    b = bridge(monkeypatch, tmp_path)
    target = b.chart_owner_resolve_restore("BINANCE:BTCUSDT.P", "BINANCE:BTCUSDT.P", "5")
    assert target == {"symbol": "BINANCE:BTCUSDT.P", "resolution": "5"}


def test_btc_collector_defers_and_deferral_is_not_a_failure():
    source = (ROOT / "scripts" / "keylevels_collect.py").read_text(encoding="utf-8")
    assert "_require_no_analysis_lease()" in source
    assert "AnalysisLeaseActive" in source
    # 让路必须用独立退出码，且 supervisor 要认它——否则 cron 会把让路记成采集失败
    assert "DEFER_EXIT_CODE = 7" in source
    assert "return DEFER_EXIT_CODE" in source
    assert "child.returncode == DEFER_EXIT_CODE" in source


def test_xau_and_btc_background_jobs_defer_when_analysis_is_running():
    for name in ("xau_tv_sync.py", "btc_tv_refresh.py"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "analysis_lease_status" in source, name
        assert "让路" in source, name
    btc = (ROOT / "scripts" / "btc_tv_refresh.py").read_text(encoding="utf-8")
    # 阈值必须 < cron 间隔(20min) − 采集耗时(~3.3min)，否则「下一 tick」会跳过，
    # 留下 >30min 的合同空窗（2026-09-14 由 18.0 校正到 12.0；推导见
    # tests/test_audit_fixes_20260914.py::test_btc_refresh_thresholds_respect_cadence_and_contract）。
    assert "max_age_minutes=12.0" in btc


def test_chart_owner_logic_has_one_implementation():
    """BTC/XAU 不再各写一份棘轮逻辑（同一 bug 的两份实现就是漂移来源）。"""
    xau = (ROOT / "scripts" / "xau_tv_sync.py").read_text(encoding="utf-8")
    bridge_src = (ROOT / "scripts" / "tv_data_bridge.py").read_text(encoding="utf-8")
    assert "chart_owner_resolve_restore" in xau
    assert "CHART_OWNER = ROOT" not in xau
    assert "def chart_owner_resolve_restore" in bridge_src
    assert "def chart_owner_mark_restored" in bridge_src


def test_screenshot_helper_holds_the_lease():
    """截图 + 随后的读数是一个连续动作，截图侧要持有/续期租约。"""
    source = (ROOT / "scripts" / "tv_screenshot.py").read_text(encoding="utf-8")
    assert "_hold_analysis_lease(symbol)" in source
    assert "begin_analysis_lease" in source


def test_dead_holder_pid_releases_the_lease(monkeypatch, tmp_path):
    """崩溃/被杀的分析进程不能把后台续航锁到 TTL 结束。"""
    b = bridge(monkeypatch, tmp_path)
    b.begin_analysis_lease(10.0, note="zombie")
    path = tmp_path / "tv_analysis_lease.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["pid"] = 99999999
    path.write_text(json.dumps(raw), encoding="utf-8")
    status = b.analysis_lease_status()
    assert status["active"] is False
    assert "进程" in status["reason"]
    assert b.analysis_in_progress() is False


def test_xau_defer_exit_is_visible_when_published_cache_is_stale(monkeypatch):
    sys.path.insert(0, str(SCRIPTS))
    import xau_tv_sync as xau

    monkeypatch.setattr(
        "tv_data_bridge.analysis_lease_status",
        lambda: {"active": True, "remaining_seconds": 12},
    )
    monkeypatch.setattr(
        xau, "published_xau_cache_usable",
        lambda: {"usable": False, "reason": "expired"},
    )
    assert xau.analysis_lease_defer_exit() == 1
    monkeypatch.setattr(
        xau, "published_xau_cache_usable",
        lambda: {"usable": True, "reason": "ok"},
    )
    assert xau.analysis_lease_defer_exit() == 0
    monkeypatch.setattr(
        "tv_data_bridge.analysis_lease_status",
        lambda: {"active": False},
    )
    assert xau.analysis_lease_defer_exit() is None
