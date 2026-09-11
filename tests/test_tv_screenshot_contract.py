import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verified_chart_state_requires_symbol_timeframe_and_core_studies():
    shot = load("tv_screenshot.py")
    valid = {
        "symbol": "BINANCE:BTCUSDT.P",
        "resolution": "15",
        "studies": [
            {"name": "SVP+ICT+VWAP+CVD"},
            {"name": "Volume Aggregated Spot & Futures"},
        ],
    }
    assert shot.chart_state_is_ready(valid, "BINANCE:BTCUSDT.P", "15") is True
    assert shot.chart_state_is_ready({**valid, "resolution": "5"}, "BINANCE:BTCUSDT.P", "15") is False
    assert shot.chart_state_is_ready({**valid, "studies": []}, "BINANCE:BTCUSDT.P", "15") is False


def test_xau_help_is_side_effect_free_contract():
    sync = load("xau_tv_sync.py")
    parser = sync.build_parser()
    assert "usage:" in parser.format_help()


def test_xau_final_restore_verifies_original_chart(monkeypatch):
    sync = load("xau_tv_sync.py")
    calls = []

    def fake_tv(*args, timeout=15):
        calls.append(args)
        return "", True

    monkeypatch.setattr(sync, "_tv_command", fake_tv)
    monkeypatch.setattr(sync, "_chart_state", lambda: {"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"})
    monkeypatch.setattr(sync.time, "sleep", lambda _seconds: None)

    assert sync._restore_chart({"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"}) is True
    assert calls == [("symbol", "BINANCE:BTCUSDT.P"), ("timeframe", "15")]


def test_xau_action_cache_waits_for_verified_5m_studies(monkeypatch):
    sync = load("xau_tv_sync.py")
    calls = []
    monkeypatch.setattr(sync, "_tv_command", lambda *args, timeout=30: calls.append(args) or ("", True))
    monkeypatch.setattr(sync.time, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr(sync, "_chart_state", lambda: {
        "symbol": "OANDA:XAUUSD", "resolution": "5",
        "studies": ["SVP+ICT+VWAP+CVD", "Volume Aggregated Spot & Futures"],
    })

    assert sync._prepare_xau_main_chart() is True
    # 20260911：由「sleep(20) + 单次检查」改为【有界重试】——见下面的重试测试。
    assert any(isinstance(c[0], str) and c[0] == "sleep" for c in calls), "至少等一次重算"
    assert 5.0 in [c[1] for c in calls if c[0] == "sleep"]


def test_xau_prepare_recovers_when_chart_is_slow(monkeypatch):
    """TV 换品种要加载：前几次读到的还是旧品种，必须重试而不是直接判失败。

    这就是线上约 1/3 失败率的根因 —— 原来只检查一次。
    """
    sync = load("xau_tv_sync.py")
    monkeypatch.setattr(sync, "_tv_command", lambda *args, timeout=30: ("", True))
    monkeypatch.setattr(sync.time, "sleep", lambda seconds: None)

    seen = {"n": 0}

    def flaky_state():
        seen["n"] += 1
        if seen["n"] < 3:                       # 前两次还没切完
            return {"symbol": "BINANCE:BTCUSDT.P", "resolution": "15", "studies": ["SVP+ICT+VWAP+CVD"]}
        return {"symbol": "OANDA:XAUUSD", "resolution": "5",
                "studies": ["SVP+ICT+VWAP+CVD", "Volume Aggregated Spot & Futures"]}

    monkeypatch.setattr(sync, "_chart_state", flaky_state)
    assert sync._prepare_xau_main_chart() is True
    assert seen["n"] == 3, "应在第 3 次读到正确状态时返回"


def test_xau_prepare_gives_up_bounded(monkeypatch):
    """一直不就位时必须有界退出（不能无限等），且不吞掉重试上限。"""
    sync = load("xau_tv_sync.py")
    monkeypatch.setattr(sync, "_tv_command", lambda *args, timeout=30: ("", True))
    monkeypatch.setattr(sync.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(sync, "_chart_state", lambda: {
        "symbol": "BINANCE:BTCUSDT.P", "resolution": "15", "studies": [],
    })
    assert sync._prepare_xau_main_chart() is False
    assert sync._XAU_PREP_ATTEMPTS * sync._XAU_PREP_WAIT <= 60, "总等待必须有界"


def test_restore_chart_retries_until_timeframe_lands(monkeypatch):
    """归还时 TV 先落品种、周期稍后才到 —— 必须重试。

    线上证据：归属记录 user_timeframe=15，同步跑完图却停在 BTC 5m
    （品种回去了、周期留在 XAU 同步用的 5m）。根因是单次检查。
    """
    sync = load("xau_tv_sync.py")
    monkeypatch.setattr(sync, "_tv_command", lambda *args, timeout=30: ("", True))
    monkeypatch.setattr(sync.time, "sleep", lambda seconds: None)

    seen = {"n": 0}

    def slow_state():
        seen["n"] += 1
        if seen["n"] < 3:                     # 品种已到、周期还没跟上
            return {"symbol": "BINANCE:BTCUSDT.P", "resolution": "5"}
        return {"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"}

    monkeypatch.setattr(sync, "_chart_state", slow_state)
    assert sync._restore_chart({"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"}) is True
    assert seen["n"] == 3


def test_restore_chart_fails_bounded_when_never_lands(monkeypatch):
    sync = load("xau_tv_sync.py")
    monkeypatch.setattr(sync, "_tv_command", lambda *args, timeout=30: ("", True))
    monkeypatch.setattr(sync.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(sync, "_chart_state", lambda: {"symbol": "OANDA:XAUUSD", "resolution": "5"})
    assert sync._restore_chart({"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"}) is False
    assert sync._RESTORE_ATTEMPTS * sync._RESTORE_WAIT <= 60

