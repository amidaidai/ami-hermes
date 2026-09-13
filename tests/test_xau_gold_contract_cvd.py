"""XAU 黄金合约 CVD（Binance XAUUSDT·非 OANDA）显示链回归 — 2026-09-13 用户批准。

覆盖：渲染层放行（仅显式标记时）、来源标注（不冒充 OANDA）、
来源矩阵辅助行、无数据时不出现。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_v96 import _multi_source_line
from cross_validation import _generic_matrix


def test_gold_contract_cvd_labeled_in_multi_source_line():
    dual = {"asset_is_crypto": False, "gold_contract_cvd": True}
    line = _multi_source_line("卖", "A级", "", "", "", "", "伦敦", dual)
    assert "CVD" in line and "卖" in line
    assert "Binance黄金合约" in line


def test_crypto_flow_has_no_gold_note():
    line = _multi_source_line("买", "A级", "buy", "1.2", "0.01%", "68", "", {"asset_is_crypto": True})
    assert "Binance黄金合约" not in line
    assert "CVD" in line


def test_render_release_requires_explicit_marker():
    """防回退：渲染清空保险仍存在，且放行条件=显式 gold_contract_cvd 标记。"""
    src = (ROOT / "scripts" / "render_v96.py").read_text(encoding="utf-8")
    assert 'dual_indicator.get("gold_contract_cvd")' in src
    assert 'asset_is_crypto") is False' in src


def test_generic_matrix_adds_gold_cvd_row_with_status():
    engine = {
        "gold_contract_cvd": {"direction": "卖", "quality": "A级",
                              "source": "binance_xauusdt_contract"},
        "_source_records": {"cvd": {"_source_status": "live",
                                    "timestamp": "2026-09-13T14:00:00+08:00"}},
    }
    rows = _generic_matrix(engine, {"tv", "macro", "cvd"}, symbol="XAUUSD")
    row = next(r for r in rows if r["id"] == "gold_contract_cvd")
    assert row["status"] == "live"
    assert row["role"] == "observational"
    assert row["entered_final_verdict"] is False
    assert "非OANDA" in row["impact"]
    assert "卖" in row["evidence"]


def test_generic_matrix_omits_row_without_gold_cvd_data():
    rows = _generic_matrix({"cvd": {"direction": "卖"}}, {"cvd"}, symbol="XAUUSD")
    assert not any(r["id"] == "gold_contract_cvd" for r in rows)


def test_auto_card_marks_gold_cvd_source():
    """防回退：auto_card 采集侧必须写入显式来源标记与独立键。"""
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert '"source": "binance_xauusdt_contract"' in src
    assert 'engine_data["_gold_contract_cvd"] = True' in src
    assert 'engine_data["gold_contract_cvd"]' in src


def test_render_falls_back_to_gold_contract_cvd_direction():
    """防回退：订单流行 cvd_dir 必须回退黄金合约 CVD（否则显示 N/A）。"""
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert '_gold_cvd_data.get("direction")' in src
