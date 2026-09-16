"""分析租约「自持采集放行」必须在**每一条**后台采集路径上落地。

背景：2026-09-14 修过一次「租约自锁」—— 分析管线声明租约后，它自己发起的采集
被同一份租约判 deferred。当时只把放行逻辑落在 ``keylevels_collect``，``xau_tv_sync``
没跟上，于是 2026-09-16 实测：XAU 卡前置同步带 ``defer:cache_usable`` 让路 →
读侧 5 分钟窗口拒绝 6 分钟的缓存 → 门2「TV现场确认」恒红、管线审计判
「TV主周期可用=False」，而同一张卡的 ① 表却照常显示 TV 现场（卡内自相矛盾）。

约定（三条）：
1. ``TANGXI_ANALYSIS_OWNER=1`` = 本次采集由分析管线自己发起 → 放行，不判让路；
2. 外部后台（cron 定时轮 / btc_tv_refresh）不带该变量 → 照旧让路；
3. 允许让路时，缓存可用 = 0、缓存过期 = 1（调度器必须看得见）。
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card
import keylevels_collect
import tv_data_bridge
import xau_tv_sync

LEASE = tv_data_bridge.ANALYSIS_OWNER_ENV


def test_owner_env_constant_is_defined_once():
    assert auto_card.ANALYSIS_OWNER_ENV == LEASE
    assert keylevels_collect.ANALYSIS_OWNER_ENV == LEASE
    assert tv_data_bridge.ANALYSIS_OWNER_ENV == LEASE


def test_auto_card_marks_its_own_collection(monkeypatch):
    monkeypatch.delenv(LEASE, raising=False)
    env = auto_card._analysis_owner_env()
    assert env.get(LEASE) == "1"
    # 不改动调用方进程的环境（子进程独享）
    assert LEASE not in __import__("os").environ


def test_self_collection_is_not_blocked_by_own_lease(monkeypatch):
    monkeypatch.setenv(LEASE, "1")
    monkeypatch.setattr(tv_data_bridge, "analysis_lease_status",
                        lambda *a, **k: {"active": True, "remaining_seconds": 600})
    assert xau_tv_sync.analysis_lease_defer_exit() is None


def test_external_background_still_defers(monkeypatch):
    monkeypatch.delenv(LEASE, raising=False)
    monkeypatch.setattr(tv_data_bridge, "analysis_lease_status",
                        lambda *a, **k: {"active": True, "remaining_seconds": 600})
    monkeypatch.setattr(xau_tv_sync, "published_xau_cache_usable",
                        lambda *a, **k: {"usable": True, "reason": "ok"})
    assert xau_tv_sync.analysis_lease_defer_exit() == 0
    monkeypatch.setattr(xau_tv_sync, "published_xau_cache_usable",
                        lambda *a, **k: {"usable": False, "reason": "已过期"})
    assert xau_tv_sync.analysis_lease_defer_exit() == 1


def test_no_lease_means_proceed(monkeypatch):
    monkeypatch.delenv(LEASE, raising=False)
    monkeypatch.setattr(tv_data_bridge, "analysis_lease_status",
                        lambda *a, **k: {"active": False, "reason": "无分析租约"})
    assert xau_tv_sync.analysis_lease_defer_exit() is None
