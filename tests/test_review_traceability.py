from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trading_system


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def test_log_review_inherits_trace_fields_from_matching_event(monkeypatch, tmp_path):
    event_log = tmp_path / "trade_events.jsonl"
    review_log = tmp_path / "trade_reviews.jsonl"
    plan_log = tmp_path / "trade_plans.jsonl"
    monkeypatch.setattr(trading_system, "EVENT_LOG", event_log)
    monkeypatch.setattr(trading_system, "REVIEW_LOG", review_log)
    monkeypatch.setattr(trading_system, "PLAN_LOG", plan_log)
    _write_jsonl(event_log, [{
        "time": "2026-06-18T20:00:00+08:00",
        "symbol": "BTCUSDT",
        "plan_id": "BTCUSDT-auto-card",
        "setup_id": "BTCUSDT-VAL回收-20260618-205128",
        "model_id": "VAL回收",
        "entry_tag": "val_reclaim_short",
        "exit_tag": "planned_rr_exit",
        "trigger_kind": "breach",
        "trigger_price": 63950.0,
        "trigger_level": 64000.0,
        "trigger_levels": ["S1_retest"],
    }])
    plan_log.touch()

    row = trading_system.log_review({
        "symbol": "BTCUSDT",
        "plan_id": "BTCUSDT-auto-card",
        "taken": True,
        "result_r": 1.5,
        "risk_usd": 2,
    })

    assert row["schema"] == "trade_review_v2"
    assert row["setup_id"] == "BTCUSDT-VAL回收-20260618-205128"
    assert row["model_id"] == "VAL回收"
    assert row["entry_tag"] == "val_reclaim_short"
    assert row["exit_tag"] == "planned_rr_exit"
    assert row["trigger_kind"] == "breach"
    assert row["trigger_price"] == 63950.0
    assert row["trigger_level"] == 64000.0
    assert row["model"] == "VAL回收"
    saved = json.loads(review_log.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["setup_id"] == row["setup_id"]


def test_log_review_keeps_explicit_trace_fields_over_event(monkeypatch, tmp_path):
    event_log = tmp_path / "trade_events.jsonl"
    review_log = tmp_path / "trade_reviews.jsonl"
    plan_log = tmp_path / "trade_plans.jsonl"
    monkeypatch.setattr(trading_system, "EVENT_LOG", event_log)
    monkeypatch.setattr(trading_system, "REVIEW_LOG", review_log)
    monkeypatch.setattr(trading_system, "PLAN_LOG", plan_log)
    _write_jsonl(event_log, [{"symbol": "BTCUSDT", "plan_id": "p1", "setup_id": "event-setup", "model_id": "事件模型", "entry_tag": "event_tag"}])
    plan_log.touch()

    row = trading_system.log_review({
        "symbol": "BTCUSDT",
        "plan_id": "p1",
        "setup_id": "manual-setup",
        "model_id": "手动模型",
        "entry_tag": "manual_entry",
        "exit_tag": "manual_exit",
        "taken": False,
        "result_r": 0,
    })

    assert row["setup_id"] == "manual-setup"
    assert row["model_id"] == "手动模型"
    assert row["entry_tag"] == "manual_entry"
    assert row["exit_tag"] == "manual_exit"
