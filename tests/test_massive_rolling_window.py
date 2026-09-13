"""massive_aggs 滚动窗口修复的回归测试（2026-09-13）。

背景：原实现把 ``from_``/``to`` 写死为 "2026-06-17"/"2026-06-18"，
导致 massive 日线**永远返回 2026-06-18 那根柱子** —— 不报错、字段齐全、
看门狗与卡面都不会拦，属最危险的「有数据但陈旧」。

本组测试锁死三件事：
  1. 取数窗口必须是滚动的（跟着今天走），不能再出现硬编码日期；
  2. 载荷必须带 ``as_of`` / ``stale_days``，且陈旧时带 ``_stale``；
  3. 期货快照的「套餐未含」要归一成可诊断的原因码，而不是被截断的 JSON 尾巴。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import multi_source_collector as m  # noqa: E402


class _FakeBar:
    def __init__(self, ts_ms: int) -> None:
        self.open = 100.0
        self.high = 105.0
        self.low = 99.0
        self.close = 104.0
        self.volume = 1000.0
        self.vwap = 102.0
        self.timestamp = ts_ms


def _install_fake_client(monkeypatch, bars, captured: dict) -> None:
    class _FakeClient:
        def __init__(self, api_key=None):  # noqa: ARG002
            pass

        def get_aggs(self, **kwargs):
            captured.update(kwargs)
            return bars

    import massive  # type: ignore

    monkeypatch.setattr(massive, "RESTClient", _FakeClient)


def _ms(days_ago: int) -> int:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return int(dt.timestamp() * 1000)


def test_massive_aggs_uses_rolling_window(monkeypatch):
    """窗口必须跟着今天滚动 —— 硬编码日期会让结果永远停在某一天。"""
    captured: dict = {}
    _install_fake_client(monkeypatch, [_FakeBar(_ms(0))], captured)

    m.massive_aggs("AAPL", "stock")

    today = datetime.now(timezone.utc).date()
    assert captured["to"] == today.isoformat()
    assert captured["from_"] == (today - timedelta(days=m.MASSIVE_WINDOW_DAYS)).isoformat()
    # 反向断言：绝不能再出现修复时那条被写死的窗口
    assert captured["from_"] != "2026-06-17"
    assert captured["to"] != "2026-06-18"


def test_massive_aggs_flags_fresh_bar(monkeypatch):
    captured: dict = {}
    _install_fake_client(monkeypatch, [_FakeBar(_ms(1))], captured)

    payload = m.massive_aggs("AAPL", "stock")

    assert payload["as_of"] == (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    assert payload["stale_days"] == 1
    assert "_stale" not in payload


def test_massive_aggs_flags_stale_bar(monkeypatch):
    """陈旧柱必须被标出来 —— 这正是原缺陷会静默放过去的情况。"""
    captured: dict = {}
    _install_fake_client(monkeypatch, [_FakeBar(_ms(87))], captured)  # 2026-06-18 距今约 87 天

    payload = m.massive_aggs("AAPL", "stock")

    assert payload["stale_days"] > m.MASSIVE_MAX_AGE_DAYS
    assert payload["_stale"] is True


def test_massive_aggs_keeps_legacy_keys(monkeypatch):
    """载荷必须保留原有键，避免破坏既有消费方。"""
    captured: dict = {}
    _install_fake_client(monkeypatch, [_FakeBar(_ms(2))], captured)

    payload = m.massive_aggs("AAPL", "stock")

    for key in ("open", "high", "low", "close", "volume", "vwap", "timestamp"):
        assert key in payload


def test_massive_aggs_surfaces_errors(monkeypatch):
    class _Boom:
        def __init__(self, api_key=None):  # noqa: ARG002
            pass

        def get_aggs(self, **kwargs):
            raise RuntimeError("network down")

    import massive  # type: ignore

    monkeypatch.setattr(massive, "RESTClient", _Boom)
    payload = m.massive_aggs("AAPL", "stock")
    assert "_error" in payload


def test_futures_snapshot_normalises_entitlement_error(monkeypatch):
    """套餐未含要变成可诊断的原因码，而不是被截断的 JSON 尾巴。"""

    class _NotEntitled:
        def __init__(self, api_key=None):  # noqa: ARG002
            pass

        def get_futures_snapshot(self, **kwargs):
            raise RuntimeError(
                '{"status":"ERROR","error":"You are not entitled to this data. '
                'Please upgrade your plan at https://massive.com/pricing"}'
            )

    import massive  # type: ignore

    monkeypatch.setattr(massive, "RESTClient", _NotEntitled)
    payload = m.massive_futures_snapshot("ES")
    assert payload["_error"].startswith("plan_not_entitled")
    assert "upgrade" in payload["_error"].lower() or "付费" in payload["_error"]
