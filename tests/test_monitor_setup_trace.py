from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
watch_path = ROOT / "scripts" / "行情守望.py"
spec = importlib.util.spec_from_file_location("watch_monitor_setup_trace", watch_path)
watch_monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch_monitor)


def test_enrich_event_with_latest_setup_adds_trace_fields_to_trigger_event():
    block = {
        "latest_setup": {
            "setup_id": "BTCUSDT-VAL回收-20260618-205128",
            "model_id": "VAL回收",
            "entry_tag": "val_reclaim_short",
            "exit_tag": "planned_rr_exit",
            "direction": "short",
            "status": "B等待",
            "data_grade": "A",
            "level_confidence": 70,
            "engine_confidence": 0.7,
            "confidence_5": 3,
            "expires_at": "2026-06-18T21:50:28+08:00",
        }
    }
    hits = [{"name": "S1_retest", "level": 64000.0, "condition_reason": "breach", "live_level_confidence": 72}]
    event = {"symbol": "BTCUSDT", "type": "warning_breach", "tier": "warning", "price": 63950.0, "levels": [{"name": "S1_retest"}]}

    enriched = watch_monitor.enrich_event_with_setup(event, block, hits, trigger_kind="breach")

    assert enriched is event
    assert enriched["schema"] == "v2.4"
    assert enriched["setup_id"] == "BTCUSDT-VAL回收-20260618-205128"
    assert enriched["model_id"] == "VAL回收"
    assert enriched["entry_tag"] == "val_reclaim_short"
    assert enriched["exit_tag"] == "planned_rr_exit"
    assert enriched["trigger_kind"] == "breach"
    assert enriched["trigger_level"] == 64000.0
    assert enriched["trigger_price"] == 63950.0
    assert enriched["trigger_levels"] == ["S1_retest"]


def test_enrich_event_without_latest_setup_keeps_event_compatible():
    event = {"symbol": "BTCUSDT", "type": "expired", "schema": "v2.3", "price": 64000.0}
    enriched = watch_monitor.enrich_event_with_setup(event, {}, [], trigger_kind="expired")
    assert enriched is event
    assert enriched["schema"] == "v2.3"
    assert "setup_id" not in enriched
    assert enriched["trigger_kind"] == "expired"
