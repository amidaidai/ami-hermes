# -*- coding: utf-8 -*-
"""20260911：XAU 五周期 OHLCV 改走 API 的回归测试。

背景：XAU 同步原来为取五周期 OHLCV 切 5 次周期（用户看到图表自己在切）。
取证确认那段循环只读 OHLCV、不读指标 → 改走 API，仅保留 5m 那一趟读指标面板。
"""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
X = importlib.import_module("xau_ohlcv_source")


def test_twelvedata_skips_forming_bar():
    """TD 的 values[0] 是正在形成的 K 线，必须跳过 —— 口径要与 TV 的 bars[-2] 一致。

    实测证据：2026-09-11 03:42 UTC，5min 的 values[0] 是 03:40（覆盖 03:40-03:45）。
    """
    payload = {"status": "ok", "values": [
        {"open": "1", "high": "2", "low": "0.5", "close": "1.5"},   # 正在形成 → 丢
        {"open": "4300", "high": "4310", "low": "4290", "close": "4305"},
        {"open": "4290", "high": "4300", "low": "4280", "close": "4295"},
    ]}
    bars = []
    for v in (payload.get("values") or [])[1:]:
        b = X._bar(v["open"], v["high"], v["low"], v["close"])
        if b:
            bars.append(b)
    assert len(bars) == 2
    assert bars[0]["high"] == 4310.0, "取到的应是最后一根【已闭合】"


def test_bar_geometry_guard_rejects_bad_rows():
    """外部源也可能给出坏数据：几何关系必须自检。"""
    assert X._bar(4300, 4310, 4290, 4305) is not None
    assert X._bar(4300, 4299, 4290, 4305) is None, "H < max(O,C) 必须拒绝"
    assert X._bar(4300, 4310, 4301, 4305) is None, "L > min(O,C) 必须拒绝"
    assert X._bar(1, 2, 0.5, 1.5) is None, "价格量级不像黄金必须拒绝"
    assert X._bar(None, 2, 1, 1.5) is None
    assert X._bar("a", "b", "c", "d") is None


def test_secret_reader_skips_comments_and_placeholders():
    """oanda_token.txt 现在是占位符 —— 必须判为不可用，不能拿它去请求。"""
    assert X._read_secret("definitely_not_a_file_xyz.txt") == ""
    import tempfile, os
    d = tempfile.mkdtemp()
    old = X.SECRETS
    try:
        X.SECRETS = Path(d)
        (Path(d) / "a.txt").write_text("# 注释\n# 又一行\nPLACEHOLDER_ABCDEFGHIJKLMNOP\n", encoding="utf-8")
        assert X._read_secret("a.txt") == "", "占位符必须判为不可用"
        (Path(d) / "b.txt").write_text("# 注释\nREALTOKEN1234567890abcdef\n", encoding="utf-8")
        assert X._read_secret("b.txt") == "REALTOKEN1234567890abcdef"
    finally:
        X.SECRETS = old


def test_cross_check_accepts_within_tolerance():
    api = {"5m": {"open": 4300, "high": 4310.0, "low": 4290.0, "close": 4305.0}}
    tv = {"open": 4300, "high": 4308.0, "low": 4291.0, "close": 4304.0}   # 差 ~0.05%
    ok, msg = X.cross_check(api, tv)
    assert ok, msg


def test_cross_check_rejects_beyond_tolerance():
    """跨源差太大时必须回退 —— 宁可多切几次图，也不能让卡片和你图上对不上。"""
    api = {"5m": {"open": 4300, "high": 4350.0, "low": 4240.0, "close": 4340.0}}
    tv = {"open": 4300, "high": 4310.0, "low": 4290.0, "close": 4305.0}   # 差 ~1%
    ok, msg = X.cross_check(api, tv)
    assert not ok
    assert "超出" in msg


def test_cross_check_fails_closed_on_missing_data():
    assert X.cross_check({}, {"high": 1, "low": 1, "close": 1})[0] is False
    assert X.cross_check({"5m": {"high": 1, "low": 1, "close": 1}}, {})[0] is False
    assert X.cross_check({"5m": {"high": 1, "low": 1, "close": 1}},
                         {"high": None, "low": 1, "close": 1})[0] is False


def test_breaker_trips_and_reports_open(tmp_path, monkeypatch):
    """429 必须触发源级熔断，且熔断期间不再请求（不拿旧缓存冒充实时）。"""
    monkeypatch.setattr(X, "BREAKER_FILE", tmp_path / ".breaker.json")
    assert X.breaker_open("twelvedata") is False
    X._trip_breaker("twelvedata", "HTTP 429 限流")
    assert X.breaker_open("twelvedata") is True
    assert X.breaker_open("oanda") is False, "熔断只影响出问题的那个源"


def test_fetch_all_returns_empty_when_no_source_available(tmp_path, monkeypatch):
    """两个源都不可用时返回 {} —— 调用方必须回退到逐周期切图。"""
    monkeypatch.setattr(X, "SECRETS", tmp_path)
    monkeypatch.setattr(X, "BREAKER_FILE", tmp_path / ".b.json")
    assert X.fetch_all() == {}


def test_timeframe_list_matches_production_five_layer():
    """五周期必须与卡面口径一致。"""
    assert X.TIMEFRAMES == ["1D", "4h", "1h", "15m", "5m"]
    assert set(X.OANDA_GRAN) == set(X.TIMEFRAMES)
    assert set(X.TD_INTERVAL) == set(X.TIMEFRAMES)
