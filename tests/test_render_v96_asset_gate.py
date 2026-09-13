from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import render_v96


def test_non_crypto_timeframe_rows_show_haldro_not_applicable():
    assert render_v96._sub_tf_text_for_asset({}, {"asset_is_crypto": False}) == "不适用"
    assert render_v96._sub_tf_text_for_asset({"sub_composite": 11}, {"asset_is_crypto": False}) == "不适用"


def test_crypto_timeframe_rows_keep_haldro_data_path():
    assert render_v96._sub_tf_text_for_asset({}, {"asset_is_crypto": True}) == "待刷新"


def test_header_line_includes_session_when_present():
    line = render_v96._header_line("BTCUSDT.P · BINANCE", "2026年09月13日13：33", "亚洲", "⚪", "NO-GO", "观望")
    assert line.startswith("📊")
    assert "亚洲时段" in line


def test_header_line_without_session_stays_compact():
    line = render_v96._header_line("BTCUSDT.P · BINANCE", "2026年09月13日13：33", "", "⚪", "NO-GO", "观望")
    assert "时段" not in line


def test_auto_card_maps_dead_session_to_off_hours():
    """防回退：卡面时段标注接线（低波动→盘外 映射）。"""
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert 'if _sess_name == "低波动":' in src
    assert '_sess_name = "盘外"' in src
    assert "session_name=_sess_name" in src


def test_nearest_trigger_names_picks_recent_sides():
    """等待条件具名化：按已排序的结构位列表取上下最近名（只给名）。"""
    levels = [
        {"level": 100.5, "kind": "15m·VAL"},
        {"level": 99.0, "kind": "5m·支"},
        {"level": 105.0, "kind": "1h·POC"},
    ]
    up, down = render_v96._nearest_trigger_names(levels, 100.0)
    assert up == "15m·VAL"
    assert down == "5m·支"


def test_nearest_trigger_names_empty_safe():
    assert render_v96._nearest_trigger_names([], 100.0) == (None, None)
    assert render_v96._nearest_trigger_names([{"level": 1, "kind": "X"}], 0) == (None, None)
