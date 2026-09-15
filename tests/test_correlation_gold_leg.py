"""黄金腿口径回归（2026-09-15 审计发现：BTC↔XAU 曾直接拿 Binance XAUUSDT 当「XAU」）。

铁律：禁拿加密合约冒充 OANDA 黄金 → 代理腿必须明标 + 与现货基准比偏差 + 偏差过大降级不给仓位建议。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import correlation_matrix as cm  # noqa: E402


def test_gold_series_contract_and_label():
    series, label, dev = cm.load_gold_series(10)
    assert isinstance(series, list) and isinstance(label, str) and label
    # 现货源不可用时必须是代理标签，且偏差为 None 或数值
    if label.endswith("_proxy"):
        assert dev is None or isinstance(dev, float)
    else:
        assert label.endswith("_spot")


def test_compute_correlation_labels_gold_source():
    st = cm.compute_correlation()
    if st.get("status") == "data_insufficient":
        return
    assert "gold_source" in st and st["gold_source"]
    if st["gold_source"].endswith("_proxy"):
        assert st.get("warning") and "代理" in st["warning"]
        assert "代理" in st["advice"], "代理腿口径必须写进结论，不能只藏在 JSON 字段里"


def test_proxy_degraded_blocks_position_advice(monkeypatch):
    """偏差超标 → 乘数必须回到 1.0（不给减仓建议），但相关性本身仍可展示。"""
    monkeypatch.setattr(cm, "compute_correlation", lambda: {
        "status": "proxy_degraded", "correlation_full": 0.9, "gold_source": "binance_xauusdt_proxy"})
    assert cm.multi_asset_risk_multiplier({"BTCUSDT": 1.0, "XAUUSD": 1.0}) == 1.0


def test_proxy_within_tolerance_still_adjusts(monkeypatch):
    monkeypatch.setattr(cm, "compute_correlation", lambda: {
        "status": "ok", "correlation_full": 0.9, "gold_source": "binance_xauusdt_proxy"})
    assert cm.multi_asset_risk_multiplier({"BTCUSDT": 1.0, "XAUUSD": 1.0}) == 0.7


def test_spot_reference_reads_sanctioned_snapshot():
    ref = cm.gold_spot_reference()
    if ref is not None:
        assert 500 < ref < 20000, f"现货基准价异常：{ref}"


def test_stale_spot_reference_is_not_used(monkeypatch, tmp_path):
    """XAU TV 同步已暂停 → 基准文件会停更。陈旧价当校准基准比不校准更危险，必须拒用。"""
    import os
    stale = tmp_path / "tv_live_XAUUSD.json"
    stale.write_text('{"last_price": 4299.5}', encoding="utf-8")
    old = time.time() - (cm.GOLD_SPOT_REF_MAX_AGE_MIN + 10) * 60
    os.utime(stale, (old, old))
    monkeypatch.setattr(cm, "DATA", tmp_path)
    assert cm.gold_spot_reference() is None, "超过时效闸的基准必须视为不可用"


def test_fresh_spot_reference_is_used(monkeypatch, tmp_path):
    fresh = tmp_path / "tv_live_XAUUSD.json"
    fresh.write_text('{"last_price": 4299.5}', encoding="utf-8")
    monkeypatch.setattr(cm, "DATA", tmp_path)
    assert cm.gold_spot_reference() == 4299.5


def test_fetch_daily_closes_empty_without_keys(monkeypatch):
    """无密钥时必须返回 ([], 'none')，不能假装有数据。"""
    import xau_ohlcv_source as xs
    monkeypatch.setattr(xs, "_read_secret", lambda name: "")
    closes, label = xs.fetch_daily_closes(30)
    assert closes == [] and label == "none"


def test_fetch_daily_closes_prefers_oanda(monkeypatch):
    """有 OANDA 密钥时优先用它，且逐根取（不是 fetch_all 的单根）。"""
    import xau_ohlcv_source as xs
    monkeypatch.setattr(xs, "_read_secret", lambda name: "TOKEN" if "oanda" in name else "")
    monkeypatch.setattr(xs, "breaker_open", lambda src: False)
    monkeypatch.setattr(xs, "_oanda_candles", lambda tok, gran, count: [
        {"close": 4000.0 + i, "complete": True} for i in range(count)])
    closes, label = xs.fetch_daily_closes(30)
    assert label == "oanda_spot" and len(closes) == 30 and closes[-1] == 4029.0


def test_load_gold_series_uses_spot_when_available(monkeypatch):
    """现货源可用时必须走现货腿（2026-09-15 修：原实现是死代码，永远退代理腿）。"""
    import xau_ohlcv_source as xs
    monkeypatch.setattr(xs, "fetch_daily_closes",
                        lambda count=30: ([4000.0 + i for i in range(count)], "oanda_spot"))
    series, label, dev = cm.load_gold_series(30)
    assert label == "oanda_spot" and dev == 0.0 and len(series) == 30


def test_twelvedata_daily_date_only_datetime_parses(monkeypatch):
    """日线的 datetime 是纯日期（"2026-09-15"）—— 必须能解析。

    2026-09-15 实测：原实现无条件拼 "+00:00" → fromisoformat 抛错 →
    日线恒 [] → 五周期整体失败 → XAU 每次退回切图（密钥其实是好的）。
    """
    import xau_ohlcv_source as xs
    payload = {
        "status": "ok",
        "meta": {"symbol": "XAU/USD", "interval": "1day"},
        "values": [
            {"datetime": "2026-09-15", "open": "4298.2", "high": "4317.6", "low": "4283.9", "close": "4290.8"},
            {"datetime": "2026-09-14", "open": "4348.3", "high": "4360.0", "low": "4280.0", "close": "4300.0"},
            {"datetime": "2026-09-13", "open": "4300.0", "high": "4350.0", "low": "4290.0", "close": "4348.3"},
        ],
    }
    monkeypatch.setattr(xs, "_http_json", lambda url: payload)
    bars = xs._twelvedata_candles("KEY", "1day", 3)
    assert bars, "日线必须能解析出已闭合 K 线（修前恒为空）"
    assert all(b["close"] > 0 for b in bars)
    # values[0]（9/15，尚在形成）必须被跳过
    assert len(bars) == 2


def test_twelvedata_intraday_datetime_still_parses(monkeypatch):
    """盘中格式（YYYY-MM-DD HH:MM:SS）不能被这次修复改坏。"""
    import xau_ohlcv_source as xs
    payload = {
        "status": "ok",
        "meta": {"symbol": "XAU/USD", "interval": "5min"},
        "values": [
            {"datetime": "2026-09-15 06:20:00", "open": "4290.1", "high": "4292.4", "low": "4289.2", "close": "4291.7"},
            {"datetime": "2026-09-15 06:15:00", "open": "4288.5", "high": "4291.0", "low": "4287.9", "close": "4290.1"},
            {"datetime": "2026-09-15 06:10:00", "open": "4286.0", "high": "4289.3", "low": "4285.1", "close": "4288.5"},
        ],
    }
    monkeypatch.setattr(xs, "_http_json", lambda url: payload)
    bars = xs._twelvedata_candles("KEY", "5min", 3)
    assert bars, "盘中格式必须仍然能解析"
    assert len(bars) == 2


def test_probe_cli_reports_missing_keys(monkeypatch, capsys):
    """`--probe` 是「填完 token 怎么验证」的入口，必须能明确报不可用。"""
    import xau_ohlcv_source as xs
    monkeypatch.setattr(xs, "_read_secret", lambda name: "")
    monkeypatch.setattr(xs, "fetch_all", lambda count=3: {})
    monkeypatch.setattr(sys, "argv", ["xau_ohlcv_source.py", "--probe"])
    rc = xs._probe_cli()
    out = capsys.readouterr().out
    assert rc == 1 and "❌" in out and "oanda=无" in out
