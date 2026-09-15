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
