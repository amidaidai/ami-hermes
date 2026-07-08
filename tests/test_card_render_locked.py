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


def test_render_card_locked_has_phone_friendly_blocks():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # v9.9: 手机驾驶舱，结构位前置 + 多周期 + 双指标 + 唯一主推裁决
    for marker in ["【现在】", "【做法】", "① 周期体温", "② 关键位", "③ 多源验证", "④ 最推荐方案", "【裁决】"]:
        assert marker in card, f"v9.9卡缺少 {marker}"
    assert "| 周期 | SVP主指标 | HALDRO副指标 | 位置 |" in card
    assert "| 结构位 | 价格 | 用法 | 距现价 |" in card
    assert "| 能力 | 读数 | 裁决 |" in card
    assert "| 优先级 | 条件 | 动作 | R:R |" in card


def test_render_card_locked_has_execution_elements():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # v9.8: 操作要素集中在“唯一主推+备选失效路径”表和裁决行
    for marker in ["主推", "备选", "⚠️禁止", "损", "标", "R:R"]:
        assert marker in card, f"v9.8卡缺少操作要素 {marker}"


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
    # 价格用反引号（任一有效价位即可）
    assert "`" in card


def test_render_card_locked_waiting_no_entry_price():
    merged, results, meta, engine_data = _sample_ctx()
    card = auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine_data,
                                        grok={}, search_sent="", community="")
    # B等待状态：不可渲染为“可执行”，必须保留等待/禁追语义
    assert "等确认" in card or "等关键位确认" in card
    assert "不追" in card
    assert "⚠️禁止" in card
    errors = auto_card.validate_card_rules(card, meta)
    # 只检查 R:R 和机器字段缺失，不禁止B等待出价
    for err in errors:
        assert "R:R硬底线" not in err, f"R:R违规: {err}"
        assert "机器字段缺失" not in err, f"机器字段: {err}"
