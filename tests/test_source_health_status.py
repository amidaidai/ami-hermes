"""source_status 只在是合法状态字符串时才被采信；结构化值不得让判定崩溃。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_health import inspect_payload


def test_dict_source_status_does_not_crash_inspection():
    # 实测：刷新器把逐子项状态写成 dict 放在 source_status 上，旧代码
    # `explicit in VALID_STATES` 直接抛 unhashable type: 'dict'。
    payload = {"timestamp": "2026-09-13T12:00:00+08:00",
               "source_status": {"fear_greed": "live", "x_note": "live"}}
    out = inspect_payload(payload, max_age_hours=6.0)
    assert isinstance(out, dict) and out.get("status")


def test_valid_string_source_status_is_still_honoured():
    payload = {"timestamp": "2000-01-01T00:00:00+00:00", "source_status": "stale_cache"}
    assert inspect_payload(payload, max_age_hours=1.0)["status"] == "stale_cache"
