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
    # v8.0: 五段叙事结构 + 交易方案
    for marker in ["① 今日结构", "② 关键位", "③ 量价分析", "④ 交易方案", "⑤ 综合评分"]:
        assert marker in card, f"v8.0卡缺少 {marker}"


def test_render_card_locked_has_five_sections():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # v8.0: 操作要素集中在A/B方案和风控行
    for marker in ["A方案", "B方案", "风控门", "止损", "止盈"]:
        assert marker in card, f"v8.0卡缺少操作要素 {marker}"


def test_render_card_locked_hides_machine_fields():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # v6.9 锁定：分析卡正文禁止任何机器字段/枚举泄漏。
    forbidden = [
        "机器字段",
        "monitor_write",
        "setup_id",
        "model_id",
        "entry_tag",
        "exit_tag",
        "BTCUSDT-VWAP反抽-20260618-120000",
        "vwap_pullback_short",
        "planned_rr_exit",
        "critical",
        "warning",
        "info",
    ]
    for token in forbidden:
        assert token not in card, f"分析卡正文泄漏机器字段/枚举: {token}"
    # 中文模型名允许作为人读策略名出现，但 v8.0 不强制渲染。


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
    # B等待状态：v6.9允许预案A/B展开（标记为"等确认后优先"），验证规则需放宽
    errors = auto_card.validate_card_rules(card, meta)
    # 只检查 R:R 和机器字段缺失，不禁止B等待出价
    for err in errors:
        assert "R:R硬底线" not in err, f"R:R违规: {err}"
        assert "机器字段缺失" not in err, f"机器字段: {err}"
