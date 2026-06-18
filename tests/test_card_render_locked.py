from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

import auto_card


def _sample_ctx():
    merged = {
        "bias": "偏空",
        "action": "做空",
        "global_confidence": 0.62,
        "confidence_5": 3,
        "long_confidence": 0.20,
        "long_models": 2,
        "short_confidence": 0.62,
        "short_models": 5,
    }
    results = [
        {"name": "VWAP反抽", "direction": "short", "confidence": 0.78},
        {"name": "EMA趋势", "direction": "short", "confidence": 0.55},
    ]
    meta = {
        "setup_id": "BTCUSDT-VWAP反抽-20260618-120000",
        "model_id": "VWAP反抽",
        "entry_tag": "vwap_pullback_short",
        "exit_tag": "planned_rr_exit",
        "direction": "short",
        "status": "B等待",
        "priority_plan": "B",
        "data_grade": "A",
        "level_confidence": 62,
        "engine_confidence": 0.62,
        "confidence_5": 3,
        "risk_usd": 2,
        "rr1": None,
        "rr2": None,
        "invalid_price": None,
        "expires_at": "2026-06-18T13:00:00+08:00",
        "monitor_write": True,
    }
    engine_data = {"quality": "A", "prices": {"primary": 63884}}
    return merged, results, meta, engine_data


def test_render_card_locked_has_speed_read_block():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # 速读区八项，纯纵向 ①-⑧
    for marker in ["① 品种", "② 时间", "③ 市场", "④ 现价", "⑤ 状态", "⑥ 方向", "⑦ 置信", "⑧ 数据"]:
        assert marker in card, f"速读区缺少 {marker}"


def test_render_card_locked_has_five_sections():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    for sec in ["一、环境", "二、结构", "三、博弈", "四、操作", "五、风控"]:
        assert sec in card, f"正文缺少段落 {sec}"


def test_render_card_locked_hides_machine_fields():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # 机器字段不出现在卡片正文
    assert "setup_id" not in card
    assert "entry_tag" not in card
    assert "monitor_write" not in card
    # 但 model_id 中文模型名可以出现（⑤模型）
    assert "VWAP反抽" in card


def test_render_card_locked_no_engine_log_format():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # 禁止引擎日志体：无 json 代码块、无 "## 引擎结论"、无 "## 模型详情"
    assert "```json" not in card
    assert "## 引擎结论" not in card
    assert "## 模型详情" not in card
    # 禁装饰：无方括号、无竖线
    assert "｜" not in card
    # 价格用反引号
    assert "`63884`" in card or "`63,884`" in card


def test_render_card_locked_waiting_no_entry_price():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # B等待状态：操作段不得输出具体入场价，只写触发条件
    errors = auto_card.validate_card_rules(card, meta)
    assert errors == [], f"B等待卡片违反规则: {errors}"
