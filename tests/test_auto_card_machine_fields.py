from __future__ import annotations
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

import auto_card


def test_build_setup_metadata_contains_traceable_fields():
    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    merged = {
        "bias": "偏空",
        "action": "做空",
        "global_confidence": 0.62,
        "confidence_5": 3,
        "long_confidence": 0.2,
        "short_confidence": 0.62,
    }
    results = [
        {"name": "VWAP反抽", "direction": "short", "confidence": 0.78},
        {"name": "EMA趋势", "direction": "short", "confidence": 0.55},
    ]

    meta = auto_card.build_setup_metadata(
        symbol="BTCUSDT",
        merged=merged,
        results=results,
        engine_data={"quality": "A", "prices": {"primary": 64000}},
        now=now,
    )

    assert meta["setup_id"].startswith("BTCUSDT-VWAP反抽-20260618-")
    assert meta["model_id"] == "VWAP反抽"
    assert meta["entry_tag"] == "vwap_pullback_short"
    assert meta["exit_tag"] == "planned_rr_exit"
    assert meta["direction"] == "short"
    assert meta["status"] in ("A做空", "B等待")
    assert meta["data_grade"] == "A"
    assert meta["monitor_write"] is True


def test_render_machine_fields_is_card_compatible():
    meta = {
        "setup_id": "BTCUSDT-VWAP反抽-20260618-120000",
        "model_id": "VWAP反抽",
        "entry_tag": "vwap_pullback_short",
        "exit_tag": "planned_rr_exit",
        "direction": "short",
        "status": "B等待",
        "priority_plan": "A",
        "data_grade": "A",
        "level_confidence": 74,
        "engine_confidence": 0.62,
        "confidence_5": 3,
        "risk_usd": 2,
        "rr1": None,
        "rr2": None,
        "invalid_price": None,
        "expires_at": "2026-06-18T13:00:00+08:00",
        "monitor_write": True,
    }
    text = auto_card.render_machine_fields(meta)
    assert "**机器字段**" in text
    for key in ["setup_id", "model_id", "entry_tag", "exit_tag", "monitor_write"]:
        assert f"{key}：" in text
    assert "BTCUSDT-VWAP反抽" in text


def test_validate_card_rules_blocks_waiting_card_with_entry_price():
    """v6.9: B等待允许预案展开（标记为等确认后优先），验证规则仅检查 R:R 和机器字段。"""
    card = """
**④ 状态：B等待**
**四、操作**
—— 预案A · 空头延续 · VAL回收（⚠ 当前B等待·等确认后优先）——
① 方向：做空
② 入场：`64000` 限价
③ 风控：100x
   止损：`64500`
   止盈：`63000`（1:2）
"""
    errors = auto_card.validate_card_rules(card, {"status": "B等待", "rr1": 1.5, "setup_id": "t", "model_id": "VAL回收", "entry_tag": "t", "exit_tag": "e"})
    # B等待不再阻止出价，但R:R<2.0会被拦截
    assert any("R:R硬底线" in e for e in errors)


def test_validate_card_rules_blocks_low_rr():
    errors = auto_card.validate_card_rules("**④ 状态：A做多**", {"status": "A做多", "rr1": 1.5})
    assert any("R:R" in e for e in errors)


def test_append_trade_plan_writes_machine_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_card, "DATA", tmp_path)
    meta = {
        "setup_id": "BTCUSDT-VWAP反抽-20260618-120000",
        "model_id": "VWAP反抽",
        "entry_tag": "vwap_pullback_short",
        "exit_tag": "planned_rr_exit",
        "direction": "short",
        "status": "B等待",
        "data_grade": "A",
        "confidence_5": 3,
        "engine_confidence": 0.62,
        "monitor_write": True,
    }
    auto_card.append_trade_plan(meta, "card text")
    path = tmp_path / "trade_plans.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["setup_id"] == meta["setup_id"]
    assert rows[-1]["model_id"] == "VWAP反抽"
    assert rows[-1]["entry_tag"] == "vwap_pullback_short"
    assert rows[-1]["card_excerpt"] == "card text"
